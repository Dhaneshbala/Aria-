import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { showToast } from '../components/Toast'
import { apiFetch, API_BASE as API } from '../services/api'

const NEXT = { none: 'learning', learning: 'confident', confident: 'none' }
const DOT = { none: 'bg-[#555]', learning: 'bg-amber-400', confident: 'bg-green-400' }

/**
 * SyllabusPage — NSW outcomes tracker. Tap a code to cycle
 * none → learning → confident; Practice asks ARIA about it.
 */
export default function SyllabusPage() {
  const navigate = useNavigate()
  const [overview, setOverview] = useState(null)
  const [kla, setKla] = useState(null)
  const [outcomes, setOutcomes] = useState([])
  const [loading, setLoading] = useState(false)

  const loadOverview = async () => {
    try {
      const r = await apiFetch(`${API}/v2/syllabus/overview`)
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setOverview(await r.json())
    } catch (e) {
      console.warn('syllabus overview failed', e)
      showToast('Could not load syllabus', 'error', 2500)
    }
  }

  useEffect(() => { loadOverview() }, [])

  const openSubject = async (k) => {
    if (!overview) return
    setKla(k)
    setLoading(true)
    try {
      const r = await apiFetch(
        `${API}/v2/syllabus/outcomes?kla=${encodeURIComponent(k)}&stage=${overview.stage}`
      )
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setOutcomes((await r.json()).outcomes || [])
    } catch (e) {
      console.warn('syllabus outcomes failed', e)
      showToast('Could not load outcomes', 'error', 2500)
    }
    setLoading(false)
  }

  const cycle = async (code, status) => {
    const next = NEXT[status] || 'learning'
    setOutcomes(os => os.map(o => (o.code === code ? { ...o, status: next } : o)))
    try {
      await apiFetch(`${API}/v2/syllabus/progress`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kla, stage: overview.stage, code, status: next }),
      })
      loadOverview()
    } catch (e) {
      console.warn('syllabus save failed', e)
    }
  }

  const practice = (code, name) => {
    try {
      sessionStorage.setItem(
        'aria_chat_prefill',
        `Teach me NSW syllabus outcome ${code} (${name}, stage ${overview?.stage}): explain it simply, give an example, then quiz me with 3 questions.`
      )
    } catch {}
    navigate('/chat')
  }

  if (!overview) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 text-[#888]">
        <p className="text-3xl">📚</p>
        <p className="text-sm">Loading syllabus…</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full w-full max-w-2xl mx-auto px-4 py-6 overflow-y-auto">
      <h1 className="text-xl font-bold text-[#e8e8e8]">Syllabus · Stage {overview.stage}</h1>
      <p className="text-xs text-[#888] mt-1 mb-4">
        Tap a code to cycle none → learning → confident. Practice drills it in chat.
      </p>

      {!kla ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {overview.subjects.map(s => (
            <button key={s.kla} onClick={() => openSubject(s.kla)}
              className="text-left p-4 rounded-2xl bg-[#1e1f20] border border-[#2d2e30] hover:border-[#3c4043] transition-colors">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-[#e8e8e8]">{s.name}</p>
                <p className="text-xs text-[#8ab4f8]">{s.pct}%</p>
              </div>
              <div className="w-full bg-[#131314] rounded-full h-2 overflow-hidden mb-2">
                <div className="bg-gradient-to-r from-[#4285f4] to-[#8b5cf6] h-2 rounded-full" style={{ width: `${s.pct}%` }} />
              </div>
              <p className="text-[11px] text-[#888]">
                {s.confident}/{s.total} confident{s.learning ? ` · ${s.learning} learning` : ''}
              </p>
            </button>
          ))}
        </div>
      ) : (
        <div>
          <button onClick={() => setKla(null)}
            className="text-xs text-[#8ab4f8] hover:underline mb-3">← All subjects</button>
          {loading ? (
            <p className="text-sm text-[#888]">Loading outcomes…</p>
          ) : (
            <div className="space-y-2">
              {outcomes.map(o => (
                <div key={o.code}
                  className="flex items-center gap-3 p-3 rounded-xl bg-[#1e1f20] border border-[#2d2e30]">
                  <button onClick={() => cycle(o.code, o.status)}
                    aria-label={`Mark ${o.code} as ${NEXT[o.status] || 'learning'}`}
                    className={`w-3 h-3 rounded-full flex-shrink-0 ${DOT[o.status] || DOT.none}`} />
                  <span className="text-sm font-mono text-[#e8e8e8]">{o.code}</span>
                  <span className="text-[10px] text-[#888] uppercase">{o.status}</span>
                  <button onClick={() => practice(o.code, overview.subjects.find(s => s.kla === kla)?.name || kla)}
                    className="ml-auto text-xs text-[#8ab4f8] hover:underline flex-shrink-0">
                    Practice →
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
