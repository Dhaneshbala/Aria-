import { useEffect, useState, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { getMathsTopics, generateMathsSet, submitMathsSet, getMathsMastery } from '../services/api'
import { mathsSetToQuiz, TIER_TO_LEVEL } from '../services/mathsQuiz'
import { startTask, cancelTask, useBgTask } from '../services/tasks'
import { useStore } from '../store'
import { showToast } from '../components/Toast'
import { Sigma, Clock, Lightbulb, AlertTriangle, Zap, Trophy } from 'lucide-react'

const MathText = ({ children, className }) => (
  <ReactMarkdown
    remarkPlugins={[remarkMath]}
    rehypePlugins={[rehypeKatex]}
    className={className}
    components={{ p: ({ children }) => <span>{children}</span> }}
  >
    {children || ''}
  </ReactMarkdown>
)

const TIERS = [
  { id: 'stage4', label: 'Stage 4 Adv', hint: 'Year 7-8 challenge' },
  { id: 'foundation', label: 'Foundation', hint: '5.2 fluency' },
  { id: 'selective', label: 'Selective', hint: '5.3 exam' },
  { id: 'extension', label: 'Extension', hint: 'Ext 1 bridge' },
]

export default function MathsAcceleratorPage() {
  const { studyTools, setStudyTool } = useStore()
  const saved = studyTools.maths || {}
  const [topics, setTopics] = useState([])
  const [tiers, setTiers] = useState({})
  const [topicId, setTopicId] = useState(saved.topicId || 'algebra_foundations')
  const [tier, setTier] = useState(saved.tier || 'stage4')
  const [count, setCount] = useState(saved.count || 5)
  const [timed, setTimed] = useState(true)
  const [secsLeft, setSecsLeft] = useState(0)
  const [questions, setQuestions] = useState(saved.questions || [])
  const [loading, setLoading] = useState(
    () => useStore.getState().bgTasks?.maths?.status === 'running'
  )
  const [revealed, setRevealed] = useState(saved.revealed || {})
  const [marks, setMarks] = useState(saved.marks || {})
  const [mastery, setMastery] = useState({})
  const [submitted, setSubmitted] = useState(saved.submitted || false)
  const [quizSent, setQuizSent] = useState(null)
  const [pendingQuiz, setPendingQuiz] = useState(saved.pendingQuiz || null)
  const sendRef = useRef(null)
  const bg = useBgTask('maths')
  const mountedRef = useRef(true)
  useEffect(() => () => { mountedRef.current = false }, [])

  useEffect(() => {
    getMathsTopics().then(d => {
      setTopics(d.topics || [])
      setTiers(d.tiers || {})
      if (d.topics?.length && !d.topics.find(t => t.id === topicId)) setTopicId(d.topics[0].id)
    }).catch(() => {})
    getMathsMastery().then(d => setMastery(d.mastery || {})).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Adopt background run on mount
  useEffect(() => {
    if (bg?.status === 'running') setLoading(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  // ── Maths → Quiz bridge: every generated set also becomes a Quiz-tab quiz.
  // Writes straight to studyTools.quiz (runs in onDone even if page is gone).
  const writeQuizToStore = (items, topicName, level) => {
    useStore.getState().setStudyTool('quiz', {
      questions: items, current: 0, selected: null, score: 0,
      done: false, answers: [], topic: topicName, level, count: items.length,
      cardState: { sending: false, done: false, count: 0 },
    })
  }
  // Never clobber an unfinished quiz — stash it for the Replace banner.
  const sendMathsToQuiz = (questions, topicName, level) => {
    const { items } = mathsSetToQuiz(questions)
    if (!items.length) return { status: 'empty', count: 0 }
    const quiz = useStore.getState().studyTools.quiz
    if (quiz?.questions?.length && !quiz.done) {
      const pend = { items, topicName, level, at: Date.now() }
      useStore.getState().setStudyTool('maths', { pendingQuiz: pend })
      sendRef.current = { ...pend, status: 'deferred' }
      return { status: 'deferred', count: items.length }
    }
    writeQuizToStore(items, topicName, level)
    useStore.getState().setStudyTool('maths', { pendingQuiz: null })
    return { status: 'sent', count: items.length }
  }
  const replaceQuiz = () => {
    if (!pendingQuiz?.items?.length) return
    writeQuizToStore(pendingQuiz.items, pendingQuiz.topicName, pendingQuiz.level)
    useStore.getState().setStudyTool('maths', { pendingQuiz: null })
    setQuizSent({ count: pendingQuiz.items.length, topic: pendingQuiz.topicName })
    setPendingQuiz(null)
    showToast(`📝 ${pendingQuiz.items.length} questions sent to Quiz Generator`, 'success', 3500)
  }
  const dismissPendingQuiz = () => {
    useStore.getState().setStudyTool('maths', { pendingQuiz: null })
    setPendingQuiz(null)
  }
  const openQuizTab = () => window.dispatchEvent(new CustomEvent('aria:open-quiz'))
  useEffect(() => {
    if (bg?.status === 'done' && questions.length === 0 && saved.questions?.length) {
      setQuestions(saved.questions)
      setTopicId(saved.topicId || topicId)
      setTier(saved.tier || tier)
      setCount(saved.count || count)
      setRevealed(saved.revealed || {})
      setMarks(saved.marks || {})
      setSubmitted(saved.submitted || false)
      setLoading(false)
      const pend = useStore.getState().studyTools.maths.pendingQuiz
      if (pend?.items?.length) setPendingQuiz(pend)
    } else if ((bg?.status === 'error' || bg?.status === 'cancelled') && loading) {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bg?.status])

  useEffect(() => {
    if (!timed || questions.length === 0 || submitted) return
    setSecsLeft(questions.reduce((a, q) => a + (q.marks || 2), 0) * 120)
    const t = setInterval(() => setSecsLeft(s => Math.max(0, s - 1)), 1000)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [questions.length, submitted])

  // Auto-persist to store
  useEffect(() => {
    setStudyTool('maths', { topicId, tier, count, questions, revealed, marks, submitted })
  }, [topicId, tier, count, questions, revealed, marks, submitted])

  const start = async () => {
    cancelTask('maths', { silent: true })
    setLoading(true)
    setQuestions([])
    setRevealed({})
    setMarks({})
    setSubmitted(false)
    setQuizSent(null)
    sendRef.current = null
    const topicName = topics.find(t => t.id === topicId)?.name || topicId
    const level = TIER_TO_LEVEL[tier] || 'medium'
    try {
      await startTask('maths', {
        label: `Maths: ${topicId} (${tier})`,
        page: '/create',
        topic: topicId,
        run: (signal) => generateMathsSet(topicId, tier, count, signal),
        onDone: (data) => {
          const qs = data.questions || []
          setStudyTool('maths', {
            topicId, tier, count,
            questions: qs,
            revealed: {}, marks: {}, submitted: false,
          })
          sendMathsToQuiz(qs, topicName, level)
        },
      })
      if (mountedRef.current) {
        const latest = useStore.getState().studyTools.maths
        setQuestions(latest.questions || [])
        setLoading(false)
        if (!latest.questions?.length) showToast('No questions — try again', 'error')
        else {
          const sent = sendRef.current
          sendRef.current = null
          if (sent?.status === 'deferred') {
            setPendingQuiz({ items: sent.items, topicName: sent.topicName, level: sent.level })
          } else if (sent?.status === 'sent') {
            setPendingQuiz(null)
            setQuizSent({ count: sent.count, topic: topicName })
            showToast(`📝 ${sent.count} questions sent to Quiz Generator`, 'success', 3500)
          }
        }
      }
    } catch (e) {
      if (mountedRef.current) {
        showToast('Could not generate set: ' + e.message, 'error')
        setLoading(false)
      }
    }
  }

  const toggleMark = (i, val) => {
    setMarks(m => ({ ...m, [i]: val }))
  }

  const submit = async () => {
    const total = questions.length
    const correct = Object.values(marks).filter(Boolean).length
    const mistakes = questions
      .map((q, i) => ({ q: q.question, correct: !!marks[i], answer: q.answer }))
      .filter(m => !m.correct)
      .slice(0, 10)
    try {
      await submitMathsSet(topicId, tier, correct, total, mistakes)
      const m = await getMathsMastery().catch(() => null)
      if (m) setMastery(m.mastery || {})
      setSubmitted(true)
      showToast(`Logged: ${correct}/${total} — mastery updated`, 'success')
    } catch (e) {
      showToast('Could not save mastery: ' + e.message, 'error')
    }
  }

  const activeTopic = topics.find(t => t.id === topicId)
  const mmss = `${Math.floor(secsLeft / 60)}:${String(secsLeft % 60).padStart(2, '0')}`
  const score = Object.values(marks).filter(Boolean).length

  return (
    <div className="w-full px-6 lg:px-8 py-6 page-enter max-w-3xl mx-auto">
      <div className="flex items-center gap-2 mb-1">
        <Sigma size={20} className="text-[#7c6af7]" />
        <h1 className="text-lg font-semibold text-[#e8e8e8]">Maths Accelerator</h1>
        <span className="ml-2 text-[10px] px-2 py-0.5 rounded-full bg-[#7c6af7]/15 border border-[#7c6af7]/30 text-[#c4b5fd]">Stage 4 Adv → Stage 5</span>
      </div>
      <p className="text-xs text-[#666] mb-5">Starts at advanced Stage 4 (Year 7-8), steps up to Stage 5 exam style + Extension bridge. Full worked solutions, traps, shortcuts — self-mark honestly.</p>

      {/* Topic grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mb-4">
        {topics.map(t => {
          const m = mastery[t.id]
          return (
            <button key={t.id} onClick={() => setTopicId(t.id)}
              className={`text-left p-3 rounded-xl border text-xs transition-colors ${topicId === t.id ? 'border-[#7c6af7] bg-[#7c6af7]/10' : 'border-[#2a2a2a] bg-[#1a1a1a] hover:border-[#444]'}`}>
              <span className="block font-medium text-[#e8e8e8] text-[13px]">{t.name}</span>
              <span className="block text-[10px] text-[#666] mt-0.5">{t.stage}</span>
              {m?.attempts > 0 && (
                <span className="block mt-1.5 h-1 rounded-full bg-[#2a2a2a] overflow-hidden">
                  <span className={`block h-1 rounded-full ${m.accuracy >= 80 ? 'bg-green-500' : m.accuracy >= 60 ? 'bg-blue-500' : 'bg-amber-500'}`}
                    style={{ width: `${m.accuracy}%` }} />
                </span>
              )}
              {m?.attempts > 0 && <span className="block text-[10px] text-[#888] mt-1">{m.accuracy}% · {m.correct}/{m.attempts}</span>}
            </button>
          )
        })}
      </div>
      {activeTopic && <p className="text-[11px] text-[#888] mb-3">Focus: {activeTopic.focus} · Needs: {activeTopic.prereq}</p>}

      {/* Tier + options */}
      <div className="flex gap-2 mb-3">
        {TIERS.map(t => (
          <button key={t.id} onClick={() => setTier(t.id)}
            className={`flex-1 py-2 rounded-xl text-xs transition-colors ${tier === t.id ? 'bg-[#7c6af7] text-white' : 'bg-[#1a1a1a] border border-[#2a2a2a] text-[#888] hover:text-[#e8e8e8]'}`}>
            <span className="block font-medium capitalize">{t.label}</span>
            <span className="block text-[10px] opacity-70">{t.hint}</span>
          </button>
        ))}
      </div>
      {tiers[tier] && <p className="text-[11px] text-[#666] mb-3">{tiers[tier].desc} · {tiers[tier].marks_hint}</p>}

      <div className="flex items-center gap-3 mb-4">
        <span className="text-xs text-[#888]">Questions:</span>
        {[3, 5, 8].map(n => (
          <button key={n} onClick={() => setCount(n)}
            className={`w-10 h-8 rounded-lg text-xs ${count === n ? 'bg-[#7c6af7] text-white' : 'bg-[#1a1a1a] border border-[#2a2a2a] text-[#888]'}`}>{n}</button>
        ))}
        <label className="ml-auto flex items-center gap-1.5 text-xs text-[#888] cursor-pointer">
          <input type="checkbox" checked={timed} onChange={e => setTimed(e.target.checked)} className="accent-[#7c6af7]" />
          <Clock size={12} /> Timed (2 min/mark)
        </label>
        <button onClick={start} disabled={loading}
          className="px-5 py-2 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-50">
          {loading ? 'Writing…' : 'Generate set'}
        </button>
      </div>

      {quizSent && (
        <div className="mb-4 p-3 rounded-xl bg-[#7c6af7]/10 border border-[#7c6af7]/30 flex items-center gap-2">
          <p className="text-xs text-[#c4b5fd] flex-1">📝 Sent {quizSent.count} questions to Quiz Generator</p>
          <button onClick={openQuizTab}
            className="text-xs px-3 py-1.5 rounded-full bg-[#7c6af7] text-white hover:bg-[#6a59e0] transition-colors">
            Take quiz →
          </button>
          <button onClick={() => setQuizSent(null)} className="text-[#666] hover:text-[#aaa] text-xs px-1">✕</button>
        </div>
      )}
      {pendingQuiz?.items?.length > 0 && (
        <div className="mb-4 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30">
          <p className="text-xs text-amber-300">Quiz Generator holds an unfinished quiz (“{pendingQuiz.topicName}”). Replace it with this set?</p>
          <div className="flex gap-2 mt-2">
            <button onClick={replaceQuiz}
              className="text-xs px-3 py-1.5 rounded-full bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 transition-colors">
              Replace with this set
            </button>
            <button onClick={dismissPendingQuiz}
              className="text-xs px-3 py-1.5 rounded-full bg-[#2a2a2a] text-[#888] hover:text-[#e8e8e8] transition-colors">
              Keep existing
            </button>
          </div>
        </div>
      )}

      {questions.length > 0 && timed && !submitted && (
        <div className={`mb-4 text-center text-sm font-mono ${secsLeft === 0 ? 'text-red-400' : 'text-[#c4b5fd]'}`}>
          ⏱ {secsLeft === 0 ? 'Time! Finish up + self-mark.' : `${mmss} left`}
        </div>
      )}

      {/* Questions */}
      <div className="space-y-3">
        {questions.map((q, i) => (
          <div key={i} className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl p-4">
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm text-[#e8e8e8] flex-1">Q{i + 1}. <MathText>{q.question}</MathText></p>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#2a2a2a] text-[#888] shrink-0">[{q.marks} marks]</span>
            </div>
            {!revealed[i] ? (
              <button onClick={() => setRevealed(r => ({ ...r, [i]: true }))}
                className="mt-3 text-xs px-3 py-1.5 rounded-lg bg-[#2a2a2a] hover:bg-[#333] text-[#ccc]">
                Reveal solution
              </button>
            ) : (
              <div className="mt-3 space-y-2 text-xs">
                <div className="p-2.5 rounded-lg bg-[#0f0f0f] border border-[#2a2a2a]">
                  <p className="text-[#888] font-medium mb-1">Solution</p>
                  <ol className="list-decimal ml-4 space-y-1 text-[#aaa]">
                    {(q.solution_steps || []).map((s, j) => <li key={j}><MathText>{s}</MathText></li>)}
                  </ol>
                  <p className="mt-2 text-green-300">Answer: <MathText>{q.answer}</MathText></p>
                </div>
                {q.trap && <p className="flex gap-1.5 text-amber-300/90"><AlertTriangle size={12} className="shrink-0 mt-0.5" /><MathText>{q.trap}</MathText></p>}
                {q.shortcut && <p className="flex gap-1.5 text-[#8ab4f8]"><Zap size={12} className="shrink-0 mt-0.5" /><MathText>{q.shortcut}</MathText></p>}
                <div className="flex gap-2 pt-1">
                  <span className="text-[11px] text-[#666] flex items-center gap-1"><Lightbulb size={11} /> Self-mark:</span>
                  <button onClick={() => toggleMark(i, true)}
                    className={`text-[11px] px-3 py-1 rounded-full border ${marks[i] === true ? 'bg-green-500/20 border-green-500/50 text-green-300' : 'border-[#333] text-[#888]'}`}>✓ Got it</button>
                  <button onClick={() => toggleMark(i, false)}
                    className={`text-[11px] px-3 py-1 rounded-full border ${marks[i] === false ? 'bg-red-500/20 border-red-500/50 text-red-300' : 'border-[#333] text-[#888]'}`}>✗ Missed</button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {questions.length > 0 && !submitted && (
        <button onClick={submit}
          className="mt-4 w-full py-3 rounded-xl bg-green-600 hover:bg-green-500 text-white text-sm font-medium flex items-center justify-center gap-2">
          <Trophy size={14} /> Log {score}/{questions.length} to mastery
        </button>
      )}
      {submitted && (
        <div className="mt-4 p-3 rounded-xl bg-green-500/10 border border-green-500/30 text-green-300 text-xs text-center">
          ✓ Saved — {score}/{questions.length}. Weak sets repeat automatically in Exam Countdown.
          {tier === 'stage4' && questions.length > 0 && score / questions.length >= 0.8 && (
            <button onClick={() => { setTier('foundation'); setQuestions([]); setSubmitted(false) }}
              className="block mx-auto mt-2 px-4 py-1.5 rounded-full bg-[#7c6af7] text-white text-xs hover:bg-[#6a59e0] transition-colors">
              Stage 4 cleared — step up to Stage 5 Foundation →
            </button>
          )}
        </div>
      )}
    </div>
  )
}
