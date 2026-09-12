import { useEffect, useRef, useState } from 'react'
import { Mic, Square, Loader } from 'lucide-react'
import { streamChat, transcribeAudio, synthesizeSpeech } from '../services/api'
import { showToast } from '../components/Toast'

const MAX_RECORD_SECS = 45

// Strip markdown/code so TTS speaks natural sentences, not symbols
function forSpeech(text) {
  return (text || '')
    .replace(/```[\s\S]*?```/g, ' [diagram shown on screen]. ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\$\$[\s\S]*?\$\$/g, ' [equation shown on screen]. ')
    .replace(/\$([^$]+)\$/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/^[\s]*[-*]\s+/gm, '')
    .replace(/\n{2,}/g, '. ')
    .replace(/\n/g, ' ')
    .slice(0, 3500)
}

export default function VoiceTutorPage() {
  const [phase, setPhase] = useState('idle') // idle|listening|transcribing|thinking|speaking
  const [turns, setTurns] = useState([])
  const [loop, setLoop] = useState(false)
  const loopRef = useRef(false)
  const convRef = useRef(null)
  const recRef = useRef(null)
  const streamRef = useRef(null)
  const chunksRef = useRef([])
  const audioRef = useRef(null)
  const abortRef = useRef(null)
  const timerRef = useRef(null)
  const urlsRef = useRef([])

  const busy = phase !== 'idle'

  // Full cleanup on unmount
  useEffect(() => () => stopEverything(false), [])

  function stopTracks() {
    try { streamRef.current?.getTracks().forEach(t => t.stop()) } catch {}
    streamRef.current = null
  }

  function stopEverything(updateLoop = true) {
    if (updateLoop) { setLoop(false); loopRef.current = false }
    try { abortRef.current?.abort() } catch {}
    abortRef.current = null
    try { if (recRef.current?.state !== 'inactive') recRef.current?.stop() } catch {}
    recRef.current = null
    try { audioRef.current?.pause() } catch {}
    audioRef.current = null
    clearTimeout(timerRef.current)
    stopTracks()
    urlsRef.current.forEach(u => { try { URL.revokeObjectURL(u) } catch {} })
    urlsRef.current = []
    setPhase('idle')
  }

  async function listen() {
    if (!loopRef.current) return
    setPhase('listening')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      chunksRef.current = []
      const rec = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      recRef.current = rec
      rec.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      rec.onstop = () => {
        stopTracks()
        clearTimeout(timerRef.current)
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        if (blob.size < 500) {
          // Too short — listen again
          if (loopRef.current) listen()
          else setPhase('idle')
          return
        }
        handleAudio(blob)
      }
      rec.start()
      // Auto-stop long recordings
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
    let text = ''
    try {
      const data = await transcribeAudio(blob)
      text = (data?.transcript || data?.text || '').trim()
    } catch (e) {
      showToast('Transcribe failed: ' + e.message, 'error')
    }
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
    let reply = ''
    try {
      await streamChat({
        message: text,
        conversationId: convRef.current,
        mode: 'normal',
        signal: abortRef.current.signal,
        onChunk: (data) => {
          if (data.type === 'text') reply += data.content || ''
        },
        onDone: (newConvId) => {
          if (newConvId) convRef.current = newConvId
          speak(reply || "Sorry, I didn't catch that clearly. Could you say it again?")
        },
      })
    } catch (e) {
      if (e.name === 'AbortError') return
      showToast('Chat failed: ' + e.message, 'error')
      if (loopRef.current) listen()
      else setPhase('idle')
    }
  }

  async function speak(text) {
    setTurns(t => [...t, { role: 'assistant', text }])
    setPhase('speaking')
    try {
      const url = await synthesizeSpeech(forSpeech(text))
      urlsRef.current.push(url)
      const audio = new Audio(url)
      audioRef.current = audio
      audio.onended = () => {
        audioRef.current = null
        if (loopRef.current) listen()
        else setPhase('idle')
      }
      audio.onerror = () => {
        showToast('Audio playback failed', 'error')
        if (loopRef.current) listen()
        else setPhase('idle')
      }
      await audio.play()
    } catch (e) {
      showToast('Speech failed: ' + e.message, 'error')
      if (loopRef.current) listen()
      else setPhase('idle')
    }
  }

  const toggle = () => {
    if (loop) { stopEverything(true); return }
    setTurns([])
    convRef.current = null
    setLoop(true); loopRef.current = true
    listen()
  }

  const stopTalking = () => {
    // End current recording early and send it
    try { if (recRef.current?.state === 'recording') recRef.current.stop() } catch {}
  }

  const PHASE_LABEL = {
    idle: 'Tap the mic to start a spoken session',
    listening: 'Listening… tap stop when done talking',
    transcribing: 'Writing down what you said…',
    thinking: 'ARIA is thinking…',
    speaking: 'ARIA is answering…',
  }

  return (
    <div className="flex flex-col h-full w-full max-w-2xl mx-auto px-6 py-6">
      <h1 className="text-2xl font-bold text-[#e8e8e8] mb-1 text-center">Voice Tutor</h1>
      <p className="text-xs text-[#666] mb-4 text-center flex items-center justify-center gap-1.5">
        {busy && phase !== 'idle' && <Loader size={11} className="animate-spin" />}
        {PHASE_LABEL[phase]}
      </p>

      {/* Turns */}
      <div className="flex-1 overflow-y-auto space-y-3 mb-4 min-h-[200px]">
        {turns.length === 0 && (
          <div className="text-center text-xs text-[#555] py-10">
            Hands-free revision: talk, ARIA answers out loud, then listens again.<br />Best for definitions, times tables, vocab, explain-backs.
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
      </div>

      {/* Controls */}
      <div className="flex items-center justify-center gap-3 pb-2">
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
      </div>
      <p className="text-center text-[11px] text-[#555]">ARIA can make mistakes — verify important work</p>
    </div>
  )
}
