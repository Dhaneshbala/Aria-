/** Voice follow-up (STT), Visualize (Napkin picker), Listen (TTS). Extracted from Message.jsx. */
import React, { useState } from 'react'
import NapkinDiagram, { NAPKIN_TYPES } from '../NapkinDiagram'
import { transcribeAudio, suggestVisuals, generateDiagram } from '../../services/api'
import { startTask, useBgTask } from '../../services/tasks'
import { useStore } from '../../store'
import { Mic, MicOff, Loader, Sparkles, Volume2 } from 'lucide-react'
export function VoiceFollowUp({ onSuggest }) {
  const [recording, setRecording] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState('')
  const recorderRef = React.useRef(null)
  const chunksRef = React.useRef([])

  const start = async () => {
    setError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      chunksRef.current = []
      rec.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      rec.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        if (blob.size < 500) { setError('No audio'); setRecording(false); return }
        setProcessing(true)
        try {
          const data = await transcribeAudio(blob, typeof navigator !== 'undefined' ? navigator.language : undefined)
          const txt = (data?.transcript || data?.text || '').trim()
          if (txt && onSuggest) onSuggest(txt)
          else if (!txt) setError(data?.language && !String(data.language).startsWith('en') ? `Heard ${data.language} but got no text — try again, closer` : 'Heard nothing')
        } catch (e) {
          setError('Transcribe failed')
        } finally {
          setProcessing(false)
          setRecording(false)
        }
      }
      recorderRef.current = rec
      rec.start()
      setRecording(true)
    } catch (e) {
      setError('Mic denied')
    }
  }
  const stop = () => {
    try { recorderRef.current?.stop() } catch {}
  }

  if (error) return (
    <button onClick={() => setError('')} className="text-[10px] text-amber-400 hover:text-amber-300 flex items-center gap-1">
      <MicOff size={11} /> {error} — retry?
    </button>
  )
  if (processing) return (
    <span className="flex items-center gap-1 text-[11px] text-[#666]"><Loader size={11} className="animate-spin" /> Transcribing…</span>
  )
  if (recording) return (
    <button onClick={stop} className="flex items-center gap-1.5 text-[11px] text-red-400 hover:text-red-300 animate-pulse">
      <MicOff size={11} /> Stop recording
    </button>
  )
  return (
    <button onClick={start} className="flex items-center gap-1.5 text-[11px] text-[#666] hover:text-[#a89bf8] transition-colors">
      <Mic size={11} /> Ask aloud
    </button>
  )
}

// ── Visualize (Napkin-style) — turn any answer into an editable visual ──────
// No new page: pick from 3 suggested visual types, rendered inline below.

export function VisualizeButton({ text, msgId, savedSpec }) {
  const taskKey = `viz-${msgId || 'x'}`
  const bg = useBgTask(taskKey)
  const [open, setOpen] = useState(false)
  const [options, setOptions] = useState(null)
  const [source, setSource] = useState('')
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(null)
  // Spec may have landed in the store while we were on another page.
  const [spec, setSpec] = useState(savedSpec || null)
  const [error, setError] = useState('')
  const mountedRef = React.useRef(true)
  React.useEffect(() => () => { mountedRef.current = false }, [])

  // Adopt a background result that finished while we were away.
  React.useEffect(() => {
    if (!spec && savedSpec) {
      setSpec(savedSpec)
      setGenerating(null)
      // Fresh background completion (not a reload) — reveal it automatically.
      if (bg?.status === 'done') setOpen(true)
    }
    else if ((bg?.status === 'error' || bg?.status === 'cancelled') && generating) {
      setGenerating(null)
      if (bg.status === 'error' && bg.error) setError(bg.error)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bg?.status, savedSpec])

  const plain = (md) => String(md || '')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/[#*_>`|]/g, '')
    .replace(/\$\$/g, '')
    .replace(/\s+/g, ' ')
    .trim()

  const start = async () => {
    if (open) { setOpen(false); return }
    setError('')
    // Already have a visual (e.g. finished in the background) — just show it.
    if (spec || savedSpec) { setSpec(spec || savedSpec); setOpen(true); return }
    // Napkin behaviour: visualise the SELECTED text if the user highlighted
    // part of this answer, else the whole answer.
    let sel = ''
    try {
      sel = window.getSelection()?.toString().trim() || ''
    } catch {}
    const src = (sel.length > 20 ? sel : plain(text)).slice(0, 1200)
    if (src.length < 20) { setError('Not enough text to visualise'); return }
    setSource(src)
    setOpen(true)
    setLoading(true)
    try {
      const data = await suggestVisuals(src)
      if (!mountedRef.current) return
      if (data?.error) throw new Error(data.error)
      setOptions(data?.options || null)
      if (data?.preview && !data?.options) setSpec(data.preview)
    } catch (e) {
      // Suggest is heuristic — still offer all types on failure
      if (mountedRef.current) setOptions(null)
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }

  const pick = async (type) => {
    setGenerating(type)
    setError('')
    try {
      // Background-safe: leaving chat won't stop it — the spec lands in
      // this message via the store even when this component is gone.
      const data = await startTask(taskKey, {
        label: 'Visual',
        page: '/chat',
        topic: source.slice(0, 40),
        run: (signal) => generateDiagram(source, type, signal),
        onDone: (d) => {
          if (d?.error) throw new Error(d.error)
          if (d?.spec) useStore.getState().updateMessage(msgId, { visualSpec: d.spec })
          else throw new Error('No visual returned')
        },
      })
      if (!mountedRef.current) return
      if (data?.error) throw new Error(data.error)
      if (data?.spec) setSpec(data.spec)
      else throw new Error('No visual returned')
    } catch (e) {
      if (!mountedRef.current) return
      if (e?.name !== 'AbortError') setError(e.message || 'Could not create visual')
    } finally {
      if (mountedRef.current) setGenerating(null)
    }
  }

  return (
    <div className="w-full">
      <button onClick={start}
        className="flex items-center gap-1.5 text-[11px] text-[#666] hover:text-[#a89bf8] transition-colors">
        {bg?.status === 'running' && !open
          ? <><Loader size={11} className="animate-spin" /> Drawing in background…</>
          : <><Sparkles size={11} /> {open ? 'Hide visuals' : (savedSpec || spec ? 'View visual' : 'Visualize')}</>}
      </button>
      {open && (
        <div className="mt-2 w-full bg-[#141414] border border-[#2a2a2a] rounded-2xl p-3">
          {loading && (
            <p className="text-[11px] text-[#666] flex items-center gap-2">
              <Loader size={11} className="animate-spin" /> Finding the best visuals…
            </p>
          )}
          {!loading && !spec && (
            <>
              <p className="text-[10px] text-[#555] uppercase tracking-wider mb-2">
                {options?.length ? 'Pick a style — like Napkin AI' : 'Pick a visual type'}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {(options || NAPKIN_TYPES.map(t => ({ type: t.id, label: `${t.label} — ${t.hint}` }))).map(o => (
                  <button key={o.type} onClick={() => pick(o.type)} disabled={generating}
                    className="text-[11px] px-3 py-1.5 rounded-full bg-[#1e1f20] border border-[#2a2a2a] text-[#aaa] hover:border-[#7c6af7]/60 hover:text-white transition-all disabled:opacity-50">
                    {generating === o.type ? 'Drawing…' : `✨ ${o.label}${o.recommended ? ' ★' : ''}`}
                  </button>
                ))}
              </div>
              <p className="text-[10px] text-[#444] mt-2">Tip: highlight part of my answer first to visualise just that bit.</p>
            </>
          )}
          {!loading && spec && (
            <>
              <button onClick={() => setSpec(null)} className="text-[11px] text-[#666] hover:text-[#aaa] mb-1">← try another style</button>
              <NapkinDiagram spec={spec} />
            </>
          )}
          {error && <p className="text-[11px] text-amber-400 mt-2">{error}</p>}
        </div>
      )}
    </div>
  )
}

// ── Listen button (local TTS) ─────────────────────────────────────────────────

export function ListenButton({ text }) {
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState(false)

  const play = async () => {
    if (playing) return
    setPlaying(true)
    setError(false)
    try {
      const resp = await fetch('/api/voice/synthesize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text.slice(0, 3500) }),
      })
      if (!resp.ok) throw new Error('TTS failed')
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      audio.onended = () => { URL.revokeObjectURL(url); setPlaying(false) }
      audio.onerror = () => { URL.revokeObjectURL(url); setPlaying(false); setError(true) }
      await audio.play()
    } catch {
      setPlaying(false)
      setError(true)
    }
  }

  if (error) return (
    <button onClick={() => setError(false)}
      className="text-[10px] text-[#555] hover:text-[#888] flex items-center gap-1">
      <Volume2 size={11} /> Listen unavailable
    </button>
  )

  return (
    <button onClick={play} disabled={playing}
      className="flex items-center gap-1.5 text-[11px] text-[#666] hover:text-[#a89bf8] transition-colors disabled:opacity-60">
      {playing ? <Loader size={11} className="animate-spin" /> : <Volume2 size={11} />}
      {playing ? 'Speaking…' : 'Listen'}
    </button>
  )
}
