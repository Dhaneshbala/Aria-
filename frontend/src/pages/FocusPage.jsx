import { useState, useEffect, useRef } from 'react'
import { Timer, Play, Pause, RotateCcw, Flame, Coffee, Brain, CheckCircle2 } from 'lucide-react'

const WORK_MIN = 25
const BREAK_MIN = 5
const LONG_BREAK_MIN = 15
const CYCLES_BEFORE_LONG = 4
const STORAGE_KEY = 'aria_focus_sessions'

function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function FocusPage() {
  const [mode, setMode] = useState('work') // work | break | longBreak
  const [secondsLeft, setSecondsLeft] = useState(WORK_MIN * 60)
  const [running, setRunning] = useState(false)
  const [cyclesDone, setCyclesDone] = useState(0)
  const [sessions, setSessions] = useState({})
  const tickRef = useRef(null)

  // Load today's sessions
  useEffect(() => {
    try {
      const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
      setSessions(raw)
    } catch {}
  }, [])

  const saveSession = () => {
    const today = todayStr()
    setSessions(prev => {
      const next = { ...prev, [today]: (prev[today] || 0) + 1 }
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)) } catch {}
      return next
    })
  }

  useEffect(() => {
    if (!running) return
    tickRef.current = setInterval(() => {
      setSecondsLeft(s => {
        if (s <= 1) {
          // Phase complete
          clearInterval(tickRef.current)
          if (mode === 'work') {
            saveSession()
            setCyclesDone(c => {
              const n = c + 1
              const isLong = n % CYCLES_BEFORE_LONG === 0
              setMode(isLong ? 'longBreak' : 'break')
              setSecondsLeft((isLong ? LONG_BREAK_MIN : BREAK_MIN) * 60)
              return n
            })
          } else {
            setMode('work')
            setSecondsLeft(WORK_MIN * 60)
          }
          setRunning(false)
          return 0
        }
        return s - 1
      })
    }, 1000)
    return () => clearInterval(tickRef.current)
  }, [running, mode])

  const reset = () => {
    setRunning(false)
    setMode('work')
    setSecondsLeft(WORK_MIN * 60)
    setCyclesDone(0)
  }

  const totalMin = mode === 'work' ? WORK_MIN : mode === 'break' ? BREAK_MIN : LONG_BREAK_MIN
  const progress = ((totalMin * 60 - secondsLeft) / (totalMin * 60)) * 100
  const mm = String(Math.floor(secondsLeft / 60)).padStart(2, '0')
  const ss = String(secondsLeft % 60).padStart(2, '0')
  const today = todayStr()
  const todayCount = sessions[today] || 0
  const weekCount = Object.entries(sessions)
    .filter(([d]) => d >= new Date(Date.now() - 6 * 86400000).toISOString().slice(0, 10))
    .reduce((s, [, v]) => s + v, 0)

  const accent = mode === 'work' ? '#7c6af7' : '#4ade80'
  const label = mode === 'work' ? 'Focus' : mode === 'break' ? 'Short Break' : 'Long Break'

  // Update document title with countdown
  useEffect(() => {
    document.title = `${running ? `${mm}:${ss} · ` : ''}Focus — ARIA`
    return () => { document.title = 'ARIA' }
  }, [running, mm, ss])

  return (
    <div className="min-h-full flex flex-col items-center justify-center px-4 py-8">
      {/* Header */}
      <div className="flex items-center gap-2 mb-8">
        <Timer size={20} className="text-[#7c6af7]" />
        <h1 className="text-lg font-semibold text-[#e8e8e8]">Focus Mode</h1>
      </div>

      {/* Mode selector */}
      <div className="flex gap-1 bg-[#0a0a0a] rounded-xl p-1 border border-[#1a1a1a] mb-8">
        {[['work', 'Focus', Brain], ['break', 'Short Break', Coffee], ['longBreak', 'Long Break', Timer]].map(([m, l, Icon]) => (
          <button key={m} onClick={() => { setMode(m); setRunning(false); setSecondsLeft((m === 'work' ? WORK_MIN : m === 'break' ? BREAK_MIN : LONG_BREAK_MIN) * 60) }}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium transition-colors ${
              mode === m ? 'bg-[#1a1a1a] text-[#e8e8e8]' : 'text-[#555] hover:text-[#888]'
            }`}>
            <Icon size={13} /> {l}
          </button>
        ))}
      </div>

      {/* Timer ring */}
      <div className="relative mb-8" style={{ width: 260, height: 260 }}>
        <svg viewBox="0 0 260 260" className="w-full h-full -rotate-90">
          <circle cx="130" cy="130" r="118" fill="none" stroke="#1a1a1a" strokeWidth="8" />
          <circle cx="130" cy="130" r="118" fill="none" stroke={accent} strokeWidth="8"
            strokeLinecap="round" strokeDasharray={2 * Math.PI * 118}
            strokeDashoffset={2 * Math.PI * 118 * (1 - progress / 100)}
            style={{ transition: 'stroke-dashoffset 1s linear, stroke 0.3s' }} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[11px] uppercase tracking-widest text-[#555] mb-1">{label}</span>
          <span className="text-6xl font-bold tabular-nums text-[#e8e8e8]">{mm}:{ss}</span>
          <span className="text-[10px] text-[#555] mt-2">{cyclesDone % CYCLES_BEFORE_LONG} of {CYCLES_BEFORE_LONG} cycles</span>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3 mb-10">
        <button onClick={() => setRunning(!running)}
          className="flex items-center gap-2 px-8 py-3 rounded-2xl text-white text-sm font-semibold transition-all active:scale-[0.97]"
          style={{ backgroundColor: accent }}>
          {running ? <Pause size={16} /> : <Play size={16} />}
          {running ? 'Pause' : 'Start'}
        </button>
        <button onClick={reset}
          className="p-3 rounded-2xl bg-[#1a1a1a] border border-[#2a2a2a] text-[#888] hover:text-[#e8e8e8] hover:border-[#444] transition-colors">
          <RotateCcw size={16} />
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3 w-full max-w-md">
        <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 text-center">
          <Flame size={16} className="text-[#f59e0b] mx-auto mb-1.5" />
          <div className="text-xl font-bold text-[#e8e8e8]">{todayCount}</div>
          <div className="text-[10px] text-[#555] mt-0.5">Today's focus sessions</div>
        </div>
        <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 text-center">
          <CheckCircle2 size={16} className="text-[#4ade80] mx-auto mb-1.5" />
          <div className="text-xl font-bold text-[#e8e8e8]">{weekCount}</div>
          <div className="text-[10px] text-[#555] mt-0.5">Last 7 days</div>
        </div>
        <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 text-center">
          <Timer size={16} className="text-[#7c6af7] mx-auto mb-1.5" />
          <div className="text-xl font-bold text-[#e8e8e8]">{weekCount * WORK_MIN}</div>
          <div className="text-[10px] text-[#555] mt-0.5">Min focused / week</div>
        </div>
      </div>

      <p className="text-[10px] text-[#444] mt-6 text-center max-w-sm">
        Complete a full focus session and the timer automatically flows into a break.
        Four focus sessions earn a long break.
      </p>
    </div>
  )
}
