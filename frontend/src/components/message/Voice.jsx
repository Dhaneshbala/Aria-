import React, { useState } from 'react'
import { Mic, MicOff, Loader, Volume2 } from 'lucide-react'
import { transcribeAudio, synthesizeSpeech } from '../../services/api'

// ── Voice follow-up (STT) — Ask ARIA aloud without typing ───────────────────

function VoiceFollowUp({ onSuggest }) {
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
        } catch {
          setError('Transcribe failed')
        } finally {
          setProcessing(false)
          setRecording(false)
        }
      }
      recorderRef.current = rec
      rec.start()
      setRecording(true)
    } catch {
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
    <span className="flex items-center gap-1 text-[11px] text-[#888]"><Loader size={11} className="animate-spin" /> Transcribing…</span>
  )
  if (recording) return (
    <button onClick={stop} className="flex items-center gap-1.5 text-[11px] text-red-400 hover:text-red-300 animate-pulse">
      <MicOff size={11} /> Stop recording
    </button>
  )
  return (
    <button onClick={start} className="flex items-center gap-1.5 text-[11px] text-[#888] hover:text-[#a89bf8] transition-colors">
      <Mic size={11} /> Ask aloud
    </button>
  )
}
function ListenButton({ text }) {
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState(false)

  const play = async () => {
    if (playing) return
    setPlaying(true)
    setError(false)
    try {
      const url = await synthesizeSpeech(text)
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
      className="text-[10px] text-[#888] hover:text-[#888] flex items-center gap-1">
      <Volume2 size={11} /> Listen unavailable
    </button>
  )

  return (
    <button onClick={play} disabled={playing}
      className="flex items-center gap-1.5 text-[11px] text-[#888] hover:text-[#a89bf8] transition-colors disabled:opacity-60">
      {playing ? <Loader size={11} className="animate-spin" /> : <Volume2 size={11} />}
      {playing ? 'Speaking…' : 'Listen'}
    </button>
  )
}

export { VoiceFollowUp, ListenButton }
