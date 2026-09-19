import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { Zap, Printer, Copy, Check, Download } from 'lucide-react'
import { generateCheatsheet } from '../services/api'
import { startTask, cancelTask, useBgTask } from '../services/tasks'
import { useStore } from '../store'
import { showToast } from '../components/Toast'

const EXAMPLES = [
  'Quadratic equations',
  'Photosynthesis',
  'World War 1 causes',
  'Trigonometry — sin, cos, tan',
  'Cell organelles',
]

const SUBJECTS = ['Maths', 'Science', 'Biology', 'Chemistry', 'Physics', 'History', 'Geography', 'English']

export default function CheatSheetPage() {
  const { studyTools, setStudyTool } = useStore()
  const saved = studyTools.cheatsheet || {}
  const [topic, setTopic] = useState(saved.topic || '')
  const [subject, setSubject] = useState(saved.subject || '')
  const [sheet, setSheet] = useState(saved.sheet || '')
  const [busy, setBusy] = useState(
    () => useStore.getState().bgTasks?.cheatsheet?.status === 'running'
  )
  const [copied, setCopied] = useState(false)
  const bg = useBgTask('cheatsheet')
  const mountedRef = useRef(true)
  useEffect(() => () => { mountedRef.current = false }, [])
  const printRef = useRef(null)

  // Adopt background run: returning to page while cheatsheet generates
  useEffect(() => {
    if (bg?.status === 'running') setBusy(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  useEffect(() => {
    if (bg?.status === 'done' && !sheet && saved.sheet) {
      setSheet(saved.sheet)
      setTopic(saved.topic || topic)
      setSubject(saved.subject || subject)
      setBusy(false)
    } else if ((bg?.status === 'error' || bg?.status === 'cancelled') && busy) {
      setBusy(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bg?.status])

  // Auto-persist to store
  useEffect(() => {
    setStudyTool('cheatsheet', { topic, subject, sheet })
  }, [topic, subject, sheet])

  const generate = async (t = topic) => {
    const clean = (t || '').trim()
    if (!clean) { showToast('Type a topic first', 'error'); return }
    cancelTask('cheatsheet', { silent: true })
    setBusy(true)
    setSheet('')
    try {
      await startTask('cheatsheet', {
        label: `Cheat sheet: ${clean.slice(0, 40)}`,
        page: '/cheatsheets',
        topic: clean,
        run: (signal) => generateCheatsheet(clean.slice(0, 150), subject, signal),
        onDone: (res) => {
          const md = res.cheatsheet || ''
          setStudyTool('cheatsheet', { topic: clean, subject, sheet: md })
          // Also save to localStorage history
          try {
            const key = 'aria_cheatsheets'
            const prev = JSON.parse(localStorage.getItem(key) || '[]')
            prev.unshift({ topic: clean, subject, sheet: md, ts: Date.now() })
            localStorage.setItem(key, JSON.stringify(prev.slice(0, 20)))
          } catch {}
        },
      })
      // If still mounted, update local state
      if (mountedRef.current) {
        const latest = useStore.getState().studyTools.cheatsheet
        setSheet(latest.sheet || '')
        setBusy(false)
      }
    } catch (e) {
      if (mountedRef.current && e?.name !== 'AbortError') {
        showToast('Could not generate: ' + e.message, 'error')
        setBusy(false)
      }
    }
  }

  const copy = async () => {
    await navigator.clipboard.writeText(sheet)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const download = () => {
    const blob = new Blob([sheet], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `cheatsheet-${(topic || 'topic').toLowerCase().replace(/[^a-z0-9]+/g, '-')}.md`
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return (
    <div className="w-full max-w-2xl mx-auto px-6 py-8">
      <div className="flex items-center gap-2 mb-1">
        <Zap size={20} className="text-amber-400" />
        <h1 className="text-2xl font-bold text-[#e8e8e8]">Cheat Sheets</h1>
      </div>
      <p className="text-sm text-[#888] mb-6">One printable page per topic: formulas, definitions, gotchas. Made for the morning bus ride 🚌</p>

      {/* Generator form */}
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl p-4 mb-4">
        <input
          value={topic}
          onChange={e => setTopic(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') generate() }}
          placeholder="Topic — e.g. Quadratic equations"
          className="w-full bg-[#141414] border border-[#2a2a2a] rounded-xl px-3 py-2.5 text-sm text-[#e8e8e8] outline-none focus:border-[#7c6af7]/60 mb-2"
        />
        <div className="flex flex-wrap gap-1.5 mb-3">
          <button
            onClick={() => setSubject('')}
            className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${!subject ? 'bg-[#7c6af7] text-white border-[#7c6af7]' : 'bg-[#141414] text-[#999] border-[#2a2a2a]'}`}
          >
            Any subject
          </button>
          {SUBJECTS.map(s => (
            <button
              key={s}
              onClick={() => setSubject(subject === s ? '' : s)}
              className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${subject === s ? 'bg-[#7c6af7] text-white border-[#7c6af7]' : 'bg-[#141414] text-[#999] border-[#2a2a2a] hover:border-[#7c6af7]/50'}`}
            >
              {s}
            </button>
          ))}
        </div>
        <button
          onClick={() => generate()}
          disabled={busy}
          className="w-full text-sm py-2.5 rounded-xl bg-[#7c6af7] text-white hover:bg-[#6a59e0] disabled:opacity-50 transition-colors"
        >
          {busy ? 'Building your one-pager…' : '⚡ Generate cheat sheet'}
        </button>
        <div className="flex flex-wrap gap-1.5 mt-3">
          {EXAMPLES.map(ex => (
            <button
              key={ex}
              onClick={() => { setTopic(ex); generate(ex) }}
              className="text-[11px] px-2.5 py-1 rounded-full bg-[#141414] border border-[#2a2a2a] text-[#888] hover:text-[#ccc] hover:border-[#7c6af7]/40 transition-colors"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>

      {/* Result — print-friendly one-pager */}
      {sheet && (
        <div className="bg-[#fafafa] text-[#1a1a1a] rounded-2xl overflow-hidden mb-4">
          <div className="flex items-center justify-between px-4 py-2.5 bg-[#f0edff] border-b border-[#e2dcff] print:hidden">
            <span className="text-xs font-semibold text-[#5b4bc4]">⚡ One-pager — {topic}</span>
            <div className="flex items-center gap-1.5">
              <button onClick={copy} className="flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-full bg-white border border-[#ddd] text-[#555] hover:text-black transition-colors">
                {copied ? <Check size={12} className="text-green-600" /> : <Copy size={12} />} {copied ? 'Copied' : 'Copy'}
              </button>
              <button onClick={download} className="flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-full bg-white border border-[#ddd] text-[#555] hover:text-black transition-colors">
                <Download size={12} /> MD
              </button>
              <button onClick={() => window.print()} className="flex items-center gap-1 text-[11px] px-3 py-1 rounded-full bg-[#7c6af7] text-white hover:bg-[#6a59e0] transition-colors">
                <Printer size={12} /> Print
              </button>
            </div>
          </div>
          <div ref={printRef} className="cheatsheet-print px-5 py-4 prose prose-sm max-w-none prose-headings:text-[#1a1a1a] prose-strong:text-[#1a1a1a] prose-li:marker:text-[#7c6af7]">
            <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
              {sheet}
            </ReactMarkdown>
          </div>
        </div>
      )}

      {!sheet && !busy && <RecentSheets onOpen={(r) => { setTopic(r.topic); setSubject(r.subject || ''); setSheet(r.sheet) }} />}

      <style>{`@media print { body * { visibility: hidden; } .cheatsheet-print, .cheatsheet-print * { visibility: visible; } .cheatsheet-print { position: absolute; left: 0; top: 0; width: 100%; } }`}</style>
    </div>
  )
}

function RecentSheets({ onOpen }) {
  let items = []
  try { items = JSON.parse(localStorage.getItem('aria_cheatsheets') || '[]') } catch {}
  if (!items.length) return <p className="text-xs text-[#555] text-center py-6">No cheat sheets yet — generate your first one above.</p>
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-[#888] uppercase tracking-wide">Recent</p>
      {items.slice(0, 8).map((r, i) => (
        <button
          key={i}
          onClick={() => onOpen(r)}
          className="w-full text-left bg-[#1a1a1a] border border-[#2a2a2a] hover:border-[#7c6af7]/40 rounded-xl px-4 py-2.5 transition-colors"
        >
          <span className="block text-sm text-[#e8e8e8] truncate">⚡ {r.topic}</span>
          <span className="block text-[11px] text-[#666]">{r.subject || 'General'} · {new Date(r.ts).toLocaleDateString()}</span>
        </button>
      ))}
    </div>
  )
}
