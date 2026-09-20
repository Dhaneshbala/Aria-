import { useEffect, useRef, useState } from 'react'
import { Mic, Square, Loader, History, X, MessageSquare, Trash2, Zap } from 'lucide-react'
import { streamChat, transcribeAudio, synthesizeSpeechCached, prefetchSpeech, chunkTextForSpeech, getMemoryConversations, getMemoryConversation, deleteMemoryConversation } from '../services/api'
import { cleanForSpeech, chunkForSpeech } from '../services/voiceQueue'
import { showToast } from '../components/Toast'
import ConfirmModal from '../components/ui/ConfirmModal'

const MAX_RECORD_SECS = 45
const SILENCE_MS = 2500

function forSpeech(text) {
  return cleanForSpeech(text)
}

export default function VoiceTutorPage() {
  const [phase, setPhase] = useState('idle')
  const [turns, setTurns] = useState([])
  const [loop, setLoop] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [history, setHistory] = useState([])
  const [historyTurns, setHistoryTurns] = useState([])
  const [selectedHistory, setSelectedHistory] = useState(null)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [pendingDelete, setPendingDelete] = useState(null)
  const loopRef = useRef(false)
  const convRef = useRef(null)
  const recRef = useRef(null)
  const streamRef = useRef(null)
  const chunksRef = useRef([])
  const audioRef = useRef(null)
  const abortRef = useRef(null)
  const timerRef = useRef(null)
  const urlsRef = useRef([])
  const queueRef = useRef([]) // pending TTS sentences for streaming playback
  const queueAbortRef = useRef(false)
  const spokenUpToRef = useRef(0)
  const silenceRef = useRef({ ctx: null, analyser: null, raf: 0, lastVoice: 0 })
  const [pendingChunks, setPendingChunks] = useState(0)
  const wsStreamRef = useRef(null)
  const [livePartial, setLivePartial] = useState('')
  const livePartialRef = useRef('') // Day 21: sync mirror for use in async handlers
  const [micLevel, setMicLevel] = useState(0)
  const langRef = useRef(null) // detected STT language for matched TTS voice
  const lastSpokenRef = useRef('') // Day 18: dedupe repeated TTS sentences

  const busy = phase !== 'idle'

  useEffect(() => () => stopEverything(false), [])

  // Day 4: Escape interrupts Study Buddy mid-answer; hiding the tab pauses audio
  // so a background tab can't talk over class.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape' && (phase === 'thinking' || phase === 'speaking') && loopRef.current) {
        interrupt()
      }
    }
    const onVis = () => {
      if (document.hidden && audioRef.current) {
        try { audioRef.current.pause() } catch {}
      }
    }
    window.addEventListener('keydown', onKey)
    document.addEventListener('visibilitychange', onVis)
    return () => {
      window.removeEventListener('keydown', onKey)
      document.removeEventListener('visibilitychange', onVis)
    }
  }, [phase])

  function stopTracks() {
    try { streamRef.current?.getTracks().forEach(t => t.stop()) } catch {}
    streamRef.current = null
  }

  function stopEverything(updateLoop = true) {
    if (updateLoop) { setLoop(false); loopRef.current = false }
    queueAbortRef.current = true
    queueRef.current = []
    spokenUpToRef.current = 0
    lastSpokenRef.current = ''
    setPendingChunks(0)
    setLivePartial('')
    livePartialRef.current = ''
    try { wsStreamRef.current?.close() } catch {}
    wsStreamRef.current = null
    stopSilenceWatch()
    try { abortRef.current?.abort() } catch {}
    abortRef.current = null
    // Day 26: drop buffered mic audio BEFORE stopping the recorder, so the
    // trailing onstop event builds an empty blob and can't fire a ghost turn
    // after the user pressed stop.
    chunksRef.current = []
    try { if (recRef.current?.state !== 'inactive') recRef.current?.stop() } catch {}
    recRef.current = null
    try { audioRef.current?.pause() } catch {}
    audioRef.current = null
    clearTimeout(timerRef.current)
    stopTracks()
    // Day 3: URLs are owned by the api.js TTS cache (LRU) — do NOT revoke
    // here, or cached replays would break. Just drop our references.
    urlsRef.current = []
    setPhase('idle')
  }

  function stopSilenceWatch() {
    const s = silenceRef.current
    try { cancelAnimationFrame(s.raf) } catch {}
    try { s.ctx?.close?.() } catch {}
    silenceRef.current = { ctx: null, analyser: null, raf: 0, lastVoice: 0 }
    setMicLevel(0)
  }

  // Auto-stop recording after SILENCE_MS of near-silence (realtime feel).
  // Day 6: also publishes a throttled mic level (0..1) for the level meter.
  function startSilenceWatch(stream) {
    stopSilenceWatch()
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext
      if (!Ctx) return
      const ctx = new Ctx()
      const src = ctx.createMediaStreamSource(stream)
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 512
      src.connect(analyser)
      const data = new Uint8Array(analyser.frequencyBinCount)
      const state = { lastVoice: Date.now(), lastLevelPush: 0 }
      silenceRef.current = { ctx, analyser, raf: 0, lastVoice: state.lastVoice }
      const tick = () => {
        if (recRef.current?.state !== 'recording') return
        analyser.getByteTimeDomainData(data)
        let peak = 0
        for (let i = 0; i < data.length; i++) {
          const v = Math.abs(data[i] - 128) / 128
          if (v > peak) peak = v
        }
        const now = Date.now()
        if (now - state.lastLevelPush > 150) {
          state.lastLevelPush = now
          setMicLevel(Math.max(0, Math.min(1, peak)))
        }
        if (peak > 0.08) {
          state.lastVoice = now
          silenceRef.current.lastVoice = state.lastVoice
        } else if (now - state.lastVoice > SILENCE_MS) {
          try { if (recRef.current?.state === 'recording') recRef.current.stop() } catch {}
          stopSilenceWatch()
          return
        }
        silenceRef.current.raf = requestAnimationFrame(tick)
      }
      silenceRef.current.raf = requestAnimationFrame(tick)
    } catch {}
  }

  async function listen() {
    if (!loopRef.current) return
    setPhase('listening')
    setLivePartial('')
    livePartialRef.current = ''
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      chunksRef.current = []
      // Day 2: open WS for live partials in parallel (REST stays source of truth).
      // Fire-and-forget: failure → null → REST-only mode, no UI breakage.
      // Day 11: seed the WS hint with last turn's detected language so
      // follow-ups in Tamil/Hindi keep the right STT bias from chunk one.
      // Day 17: connect WITHOUT blocking mic start — a dead backend must
      // never delay recording (old code awaited up to the 8 s WS timeout).
      try {
        const { tryVoiceStream } = await import('../services/voiceStream')
        wsStreamRef.current?.close?.()
        wsStreamRef.current = null
        tryVoiceStream({
          language: langRef.current || undefined,
          onPartial: (text) => {
            if (text) {
              const short = text.slice(0, 200)
              livePartialRef.current = short
              setLivePartial(short)
            }
          },
          onError: () => {},
        }).then((s) => { wsStreamRef.current = s }).catch(() => {})
      } catch { wsStreamRef.current = null }
      const rec = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      recRef.current = rec
      rec.ondataavailable = e => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data)
          try { wsStreamRef.current?.sendAudio(e.data) } catch {}
        }
      }
      rec.onstop = () => {
        stopTracks()
        stopSilenceWatch()
        try { wsStreamRef.current?.close() } catch {}
        wsStreamRef.current = null
        setLivePartial('') // bubble hides; ref survives for handleAudio fallback
        clearTimeout(timerRef.current)
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        if (blob.size < 500) {
          if (loopRef.current) listen()
          else setPhase('idle')
          return
        }
        handleAudio(blob)
      }
      rec.start(250) // 250ms timeslices → WS live partials + REST final on stop
      startSilenceWatch(stream)
      timerRef.current = setTimeout(() => {
        try { if (recRef.current?.state === 'recording') recRef.current.stop() } catch {}
      }, MAX_RECORD_SECS * 1000)
    } catch {
      showToast('Microphone blocked — allow mic access and try again', 'error')
      setLoop(false); loopRef.current = false
      setPhase('idle')
    }
  }

  async function handleAudio(blob) {
    if (!loopRef.current && phase !== 'listening') return
    setPhase('transcribing')
    // Day 21: keep the WS live partial as a fallback — if REST fails or
    // hears nothing, we'd rather ask about something than discard the turn.
    const partialFallback = (livePartialRef.current || '').trim()
    let text = ''
    try {
      const data = await transcribeAudio(blob)
      text = (data?.transcript || data?.text || '').trim()
      if (data?.language) langRef.current = data.language
    } catch (e) {
      showToast('Transcribe failed: ' + e.message, 'error')
    }
    if (!text && partialFallback.length >= 3) {
      text = partialFallback
      showToast('Used live transcript (final pass failed)', 'error')
    }
    livePartialRef.current = ''
    setLivePartial('')
    if (!text) {
      showToast('Heard nothing — listening again', 'error')
      if (loopRef.current) listen()
      else setPhase('idle')
      return
    }
    askChat(text)
  }

  async function askChat(text) {
    setTurns(t => [...t, { role: 'user', text }])
    setPhase('thinking')
    abortRef.current = new AbortController()
    queueAbortRef.current = false
    queueRef.current = []
    spokenUpToRef.current = 0
    lastSpokenRef.current = ''
    let reply = ''
    let speakStarted = false
    const pumpSentences = () => {
      // Enqueue newly completed sentences while LLM streams (Day 1 realtime)
      const fresh = reply.slice(spokenUpToRef.current)
      const parts = fresh.split(/(?<=[.!?])\s+/)
      if (parts.length <= 1) return
      const ready = parts.slice(0, -1).map((s) => s.trim()).filter(Boolean)
      if (!ready.length) return
      spokenUpToRef.current += ready.join(' ').length + 1
      // Clamp in case of off-by-one
      if (spokenUpToRef.current > reply.length) spokenUpToRef.current = reply.length
      queueRef.current.push(...ready)
      setPendingChunks(queueRef.current.length)
      if (!speakStarted) {
        speakStarted = true
        setTurns(t => [...t, { role: 'assistant', text: reply }])
        setPhase('speaking')
        pumpQueue()
      }
    }
    try {
      await streamChat({
        message: text,
        conversationId: convRef.current,
        mode: 'voice',
        signal: abortRef.current.signal,
        onChunk: (data) => {
          if (queueAbortRef.current) return
          if (data.type === 'text') {
            reply += data.content || ''
            pumpSentences()
          }
        },
        onDone: (newConvId) => {
          if (queueAbortRef.current) return
          if (newConvId) convRef.current = newConvId
          const tail = reply.slice(spokenUpToRef.current).trim()
          if (tail) queueRef.current.push(tail)
          if (!speakStarted) {
            speak(reply || "Sorry, I didn't catch that clearly. Could you say it again?")
          } else {
            // Update the placeholder turn with the full text, drain queue
            setTurns(t => {
              const copy = [...t]
              for (let i = copy.length - 1; i >= 0; i--) {
                if (copy[i].role === 'assistant') { copy[i] = { role: 'assistant', text: reply }; break }
              }
              return copy
            })
            setPendingChunks(queueRef.current.length)
            if (!queueRef.current.length && !audioRef.current) {
              if (loopRef.current) listen()
              else setPhase('idle')
            }
          }
        },
      })
    } catch (e) {
      if (e.name === 'AbortError' || queueAbortRef.current) return
      showToast('Chat failed: ' + e.message, 'error')
      if (loopRef.current) listen()
      else setPhase('idle')
    }
  }

  // Sequential playback of queued sentences. Starts on sentence 1,
  // so time-to-first-audio drops from ~8s to ~1-2s. Day 3: cached TTS +
  // prefetch of the next sentence while the current one plays.
  // Day 18: skip empties and exact repeats (boundary drift between the
  // streaming splitter and the final tail can double-queue a sentence).
  async function pumpQueue() {
    if (queueAbortRef.current) return
    if (audioRef.current) return // already playing; chain via onended
    const next = queueRef.current.shift()
    setPendingChunks(queueRef.current.length)
    if (!next) return
    const lang = langRef.current || undefined
    const spoken = forSpeech(next)
    if (!spoken || spoken === lastSpokenRef.current) {
      pumpQueue()
      return
    }
    lastSpokenRef.current = spoken
    try {
      const url = await synthesizeSpeechCached(spoken, lang)
      if (queueAbortRef.current) return
      urlsRef.current.push(url)
      // Prefetch next sentence during playback (cache warm, no await)
      try {
        const peek = queueRef.current[0]
        if (peek) prefetchSpeech(forSpeech(peek), lang)
      } catch {}
      const audio = new Audio(url)
      audioRef.current = audio
      audio.onended = () => {
        audioRef.current = null
        if (queueAbortRef.current) return
        if (queueRef.current.length) pumpQueue()
        else if (loopRef.current) listen()
        else setPhase('idle')
      }
      audio.onerror = () => {
        audioRef.current = null
        if (queueAbortRef.current) return
        if (queueRef.current.length) pumpQueue()
        else if (loopRef.current) listen()
        else setPhase('idle')
      }
      await audio.play()
    } catch (e) {
      audioRef.current = null
      if (!queueAbortRef.current && queueRef.current.length) pumpQueue()
    }
  }

  // Barge-in: interrupt Study Buddy mid-answer and go straight back to listening.
  const interrupt = () => {
    queueAbortRef.current = true
    queueRef.current = []
    lastSpokenRef.current = ''
    setPendingChunks(0)
    try { abortRef.current?.abort() } catch {}
    abortRef.current = null
    try { audioRef.current?.pause() } catch {}
    audioRef.current = null
    if (loopRef.current) listen()
    else setPhase('idle')
  }

  async function speak(text) {
    // Fallback path: full-text chunked playback (used when streaming
    // didn't start, e.g. very short replies or older backend).
    setTurns(t => {
      // Avoid double-append if askChat already added a placeholder
      const last = t[t.length - 1]
      if (last?.role === 'assistant' && last.text === text) return t
      return [...t, { role: 'assistant', text }]
    })
    setPhase('speaking')
    queueAbortRef.current = false
    let chunks = []
    try {
      chunks = await chunkTextForSpeech(text)
    } catch {
      chunks = chunkForSpeech(text)
    }
    if (!chunks.length) chunks = [text]
    queueRef.current = chunks
    setPendingChunks(chunks.length)
    pumpQueue()
  }

  const toggle = () => {
    if (loop) { stopEverything(true); return }
    setTurns([])
    convRef.current = null
    langRef.current = null
    setLoop(true); loopRef.current = true
    listen()
  }

  const stopTalking = () => {
    try { if (recRef.current?.state === 'recording') recRef.current.stop() } catch {}
  }

  const loadHistory = async () => {
    setShowHistory(true)
    setLoadingHistory(true)
    try {
      const convs = await getMemoryConversations()
      // Filter to voice-like conversations (shorter, or mark as voice)
      setHistory(Array.isArray(convs) ? convs.slice(0, 30) : [])
    } catch {} finally { setLoadingHistory(false) }
  }

  const openHistory = async (conv) => {
    setSelectedHistory(conv)
    setLoadingHistory(true)
    try {
      const turns = await getMemoryConversation(conv.id || conv.conversation_id)
      setHistoryTurns(Array.isArray(turns) ? turns : [])
    } catch { setHistoryTurns([]) }
    setLoadingHistory(false)
  }

  const deleteHistory = async (id) => {
    try {
      await deleteMemoryConversation(id)
      setHistory(prev => prev.filter(c => (c.id || c.conversation_id) !== id))
      if (selectedHistory?.id === id) { setSelectedHistory(null); setHistoryTurns([]) }
      showToast('Session deleted', 'success', 2500)
    } catch { showToast('Delete failed', 'error') }
    finally { setPendingDelete(null) }
  }

  const PHASE_LABEL = {
    idle: 'Tap the mic to start a spoken session',
    listening: 'Listening… pause 2.5s to auto-send, or tap Done',
    transcribing: 'Writing down what you said…',
    thinking: 'Study Buddy is thinking… (streaming first sentence soon)',
    speaking: pendingChunks > 0 ? `Study Buddy is answering… (${pendingChunks} queued)` : 'Study Buddy is answering…',
  }

  // History panel
  if (showHistory) {
    return (
      <div className="flex flex-col h-full w-full max-w-2xl mx-auto px-6 py-6">
        <div className="flex items-center gap-2 mb-4">
          <button onClick={() => { setShowHistory(false); setSelectedHistory(null); setHistoryTurns([]) }}
            className="p-1.5 rounded-full hover:bg-[#2d2e30] text-[#9aa0a6]">
            <X size={16} />
          </button>
          <History size={16} className="text-[#8ab4f8]" />
          <h1 className="text-lg font-semibold text-[#e3e3e3]">Voice Sessions</h1>
        </div>

        {selectedHistory ? (
          <div className="flex-1 overflow-y-auto">
            <div className="flex items-center gap-2 mb-3">
              <button onClick={() => { setSelectedHistory(null); setHistoryTurns([]) }}
                className="text-xs text-[#8ab4f8] hover:underline">← Back</button>
              <span className="text-xs text-[#5f6368]">{selectedHistory.title || 'Voice session'}</span>
            </div>
            {loadingHistory ? (
              <div className="flex justify-center py-8"><Loader size={16} className="text-[#5f6368] animate-spin" /></div>
            ) : (
              <div className="space-y-3">
                {historyTurns.map((turn, i) => (
                  <div key={i} className="space-y-2">
                    {turn.user && (
                      <div className="flex justify-end">
                        <div className="max-w-[80%] px-4 py-2.5 rounded-2xl rounded-tr-sm bg-[#7c6af7]/10 border border-[#7c6af7]/20 text-sm text-[#e3e3e3]">
                          🎤 {turn.user}
                        </div>
                      </div>
                    )}
                    {turn.ai && (
                      <div className="flex justify-start">
                        <div className="max-w-[80%] px-4 py-2.5 rounded-2xl rounded-tl-sm bg-[#1a1a1a] border border-[#2a2a2a] text-sm text-[#ccc] whitespace-pre-wrap">
                          🔊 {turn.ai.slice(0, 300)}{turn.ai.length > 300 ? '…' : ''}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto">
            {loadingHistory ? (
              <div className="flex justify-center py-8"><Loader size={16} className="text-[#5f6368] animate-spin" /></div>
            ) : history.length === 0 ? (
              <div className="text-center py-12">
                <History size={32} className="text-[#2d2e30] mx-auto mb-2" />
                <p className="text-sm text-[#5f6368]">No voice sessions yet</p>
              </div>
            ) : (
              <div className="space-y-1">
                {history.map(conv => {
                  const id = conv.id || conv.conversation_id
                  return (
                    <div key={id}
                      onClick={() => openHistory(conv)}
                      className="group flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-[#1e1f20] cursor-pointer transition-colors">
                      <MessageSquare size={14} className="text-[#5f6368] shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-[#e3e3e3] truncate">{conv.title || 'Voice session'}</p>
                        <p className="text-[10px] text-[#5f6368]">{conv.turns || conv.turn_count || '?'} turns</p>
                      </div>
                      <button onClick={e => { e.stopPropagation(); setPendingDelete(id) }}
                        aria-label="Delete session"
                        className="p-1 rounded-full opacity-0 group-hover:opacity-100 hover:bg-red-500/20 text-[#5f6368] hover:text-red-400 transition-all">
                        <Trash2 size={12} />
                      </button>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

  // Main voice interface
  return (
    <div className="flex flex-col h-full w-full max-w-2xl mx-auto px-6 py-6">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-2xl font-bold text-[#e8e8e8] text-center flex-1">Voice Tutor</h1>
        <button onClick={loadHistory}
          className="p-2 rounded-full hover:bg-[#2d2e30] text-[#9aa0a6] hover:text-[#e3e3e3] transition-colors"
          title="Session history">
          <History size={18} />
        </button>
      </div>
      <p className="text-xs text-[#666] mb-4 text-center flex items-center justify-center gap-1.5">
        {busy && phase !== 'idle' && <Loader size={11} className="animate-spin" />}
        {PHASE_LABEL[phase]}
        {convRef.current && <span className="ml-1 text-[#5f6368]">(saved)</span>}
      </p>

      {/* Turns */}
      <div className="flex-1 overflow-y-auto space-y-3 mb-4 min-h-[200px]">
        {turns.length === 0 && (
          <div className="text-center text-xs text-[#555] py-10">
            Hands-free revision: talk, Study Buddy answers out loud, then listens again.<br />Best for definitions, times tables, vocab, explain-backs.
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i} className={`flex ${t.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] px-4 py-2.5 rounded-2xl text-sm whitespace-pre-wrap ${
              t.role === 'user'
                ? 'bg-[#7c6af7]/15 border border-[#7c6af7]/20 text-[#e8e8e8] rounded-tr-sm'
                : 'bg-[#1a1a1a] border border-[#2a2a2a] text-[#ccc] rounded-tl-sm'
            }`}>
              {t.role === 'user' ? '🎤 ' : '🔊 '}{t.text}
            </div>
          </div>
        ))}
        {phase === 'listening' && livePartial && (
          <div className="flex justify-end">
            <div className="max-w-[85%] px-4 py-2.5 rounded-2xl rounded-tr-sm bg-[#7c6af7]/5 border border-dashed border-[#7c6af7]/30 text-sm text-[#9aa0a6] italic">
              🎤 {livePartial}…
            </div>
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="flex flex-col items-center gap-2 pb-2">
        {phase === 'listening' && (
          <div className="w-48 h-1.5 rounded-full bg-[#2a2a2a] overflow-hidden" title="Mic level">
            <div
              className="h-full rounded-full bg-gradient-to-r from-[#7c6af7] to-[#06b6d4] transition-[width] duration-150"
              style={{ width: `${Math.round(micLevel * 100)}%` }}
            />
          </div>
        )}
        <div className="flex items-center justify-center gap-3">
        <button onClick={toggle}
          className={`w-16 h-16 rounded-full flex items-center justify-center shadow-xl transition-all ${
            loop ? 'bg-red-500 hover:bg-red-600 animate-pulse' : 'bg-[#7c6af7] hover:bg-[#6a59e0]'
          } text-white`}>
          {loop ? <Square size={22} /> : <Mic size={24} />}
        </button>
        {phase === 'listening' && (
          <button onClick={stopTalking}
            className="px-4 py-2 rounded-full bg-[#2a2a2a] text-xs text-[#ccc] hover:text-white transition-colors">
            Done talking →
          </button>
        )}
        {(phase === 'thinking' || phase === 'speaking') && loop && (
          <button onClick={interrupt}
            className="px-4 py-2 rounded-full bg-amber-500/15 border border-amber-500/30 text-xs text-amber-300 hover:bg-amber-500/25 transition-colors flex items-center gap-1.5"
            title="Interrupt Study Buddy and talk now (barge-in, or press Esc)">
            <Zap size={12} /> Interrupt
          </button>
        )}
        </div>
      </div>
      <p className="text-center text-[11px] text-[#555]">Study Buddy can make mistakes — verify important work{loop && (phase === 'thinking' || phase === 'speaking') ? ' · Esc to interrupt' : ''}</p>
      <ConfirmModal
        open={pendingDelete !== null}
        title="Delete this session?"
        body="This removes the voice session from history. This cannot be undone."
        confirmLabel="Delete"
        onConfirm={() => deleteHistory(pendingDelete)}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  )
}
