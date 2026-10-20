import { useStore } from '../store'
import { getHealth, getDiagnostics } from '../services/api'
import { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'

const INTENT_LABELS = {
  chat:             null,
  image_analysis:   '👁 Vision',
  quiz:             '📝 Quiz',
  exam_mode:        '📋 Exam',
  flashcard:        '🃏 Flashcards',
  notes:            '📒 Notes',
  worksheet_solver: '✏️ Worksheet',
  youtube:          '▶ YouTube',
  web_search:       '🔍 Search',
  image_gen:        '🎨 Image Gen',
  diagram:          '📐 Diagram',
  math:             '➗ Maths',
  summary:          '📋 Summary',
  explain:          '💡 Explain',
  doc_chat:         '📄 Document',
  coding:           '💻 Code',
  essay_feedback:   '📝 Essay',
  formula:          '📐 Formula',
  timeline:         '⏳ Timeline',
  agent:            '🤖 Agent',
}

const MODE_LABELS = {
  normal: null,
  think:  '🧠 Think',
  fast:   '⚡ Fast',
  hype:   '🔥 Hype',
  socratic: '💭 Socratic',
  roleplay: '🎭 Roleplay',
}

export default function StatusBar() {
  const { ollamaStatus, currentIntents, config, isStreaming, mode, setOllamaStatus, authUser } = useStore()
  const [checking, setChecking] = useState(false)
  const [memLow, setMemLow] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()

  // /api/system/diagnostics is an operator surface (accounts mode denies
  // students) — only poll it for admins/local owner; the health dot
  // still covers connectivity for everyone.
  const canProbeSystem = !authUser || authUser.role === 'admin' || authUser.role === 'superadmin'

  const recheck = async () => {
    setChecking(true)
    try {
      const h = await getHealth()
      setOllamaStatus(h.ollama ? 'ok' : 'error')
    } catch {
      setOllamaStatus('error')
    }
    if (canProbeSystem) {
      try {
        const d = await getDiagnostics()
        setMemLow(d?.checks?.memory?.ok === false)
      } catch {
        // diagnostics is best-effort; health dot already covers outages
      }
    }
    setChecking(false)
  }

  // Poll RAM pressure alongside health — silent unless degraded.
  useEffect(() => {
    if (!canProbeSystem) return undefined
    let cancelled = false
    const checkMem = async () => {
      try {
        const d = await getDiagnostics()
        if (!cancelled) setMemLow(d?.checks?.memory?.ok === false)
      } catch {
        // best-effort
      }
    }
    checkMem()
    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') checkMem()
    }, 120000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [canProbeSystem])

  return (
    <div className="flex items-center gap-3 px-4 py-1.5 border-b border-[#1e1e1e] bg-[#111] text-xs min-h-[34px]">
      {/* Ollama status dot — click to recheck */}
      <button onClick={recheck} disabled={checking}
        className="flex items-center gap-1.5 flex-shrink-0 group" title="Click to re-check connection">
        <div className={`w-1.5 h-1.5 rounded-full ${
          ollamaStatus === 'ok'       ? 'bg-green-400' :
          ollamaStatus === 'error'    ? 'bg-red-400' :
                                        'bg-yellow-400 animate-pulse'
        }`} />
        <span className={`${checking ? 'text-[#888]' : 'text-[#3a3a3a] group-hover:text-[#888] transition-colors'}`}>
          {checking ? 'Checking...' :
           ollamaStatus === 'ok'    ? (config.reasoning_model || 'Ollama') :
           ollamaStatus === 'error' ? 'Ollama offline — click to retry (ollama serve)' :
                                      'Connecting...'}
        </span>
      </button>

      {/* RAM pressure — early crash warning; click jumps to Admin → Memory */}
      {memLow && (
        <button
          onClick={() => navigate('/admin')}
          className="flex items-center gap-1.5 flex-shrink-0 text-amber-300 hover:text-amber-200 transition-colors"
          title="RAM nearly full — click for Admin → Memory → Unload AI models">
          <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
          <span>RAM low — risk of crash</span>
        </button>
      )}

      {/* Streaming — clickable to jump back to chat */}
      {isStreaming && (
        <button
          onClick={() => { if (!location.pathname.startsWith('/chat')) navigate('/chat') }}
          className="flex items-center gap-1.5 text-[#7c6af7] hover:text-[#a89bf8] transition-colors"
          title={location.pathname.startsWith('/chat') ? 'ARIA is working...' : 'Click to return to chat — work continues in background'}>
          <div className="flex gap-0.5 items-end h-3">
            {[0, 1, 2].map(i => (
              <div key={i}
                className="w-0.5 rounded-full bg-[#7c6af7] animate-bounce"
                style={{ height: `${6 + i * 2}px`, animationDelay: `${i * 0.12}s` }}
              />
            ))}
          </div>
          <span>{location.pathname.startsWith('/chat') ? 'Thinking' : 'Working in background — click to return'}</span>
        </button>
      )}

      {/* Active intent badges */}
      <div className="flex gap-1.5 flex-wrap">
        {mode !== 'normal' && MODE_LABELS[mode] && (
          <span key={`mode-${mode}`}
            className="px-2 py-0.5 rounded-full bg-[#7c6af7]/15 text-[#a89bf8] border border-[#7c6af7]/25 text-[10px] font-medium">
            {MODE_LABELS[mode]}
          </span>
        )}
        {currentIntents.map(intent => {
          const label = INTENT_LABELS[intent]
          if (!label) return null
          return (
            <span key={intent}
              className="px-2 py-0.5 rounded-full bg-[#7c6af7]/10 text-[#7c6af7] border border-[#7c6af7]/20">
              {label}
            </span>
          )
        })}
      </div>
    </div>
  )
}
