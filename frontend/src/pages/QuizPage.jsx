import { useState, useEffect, useCallback, useRef } from 'react'
import { checkAnswer, bulkAddSrCards, streamQuiz } from '../services/api'
import { startTask, cancelTask, useBgTask } from '../services/tasks'
import { useStore } from '../store'
import { BookOpen, Trophy, RotateCcw, Sparkles } from 'lucide-react'

const LEVELS = ['easy', 'medium', 'hard', 'olympiad']
const LETTER = ['A', 'B', 'C', 'D']

export default function QuizPage() {
  const { studyTools, setStudyTool } = useStore()
  const saved = studyTools.quiz
  const [topic, setTopic] = useState(saved.topic || '')
  const [level, setLevel] = useState(saved.level || 'medium')
  const [count, setCount] = useState(saved.count || 5)
  const [questions, setQuestions] = useState(saved.questions || [])
  const [current, setCurrent] = useState(saved.current || 0)
  const [selected, setSelected] = useState(saved.selected || null)
  const [score, setScore] = useState(saved.score || 0)
  const [done, setDone] = useState(saved.done || false)
  // If a quiz is already generating in the background (we navigated away
  // and back), start in loading state — no flash of the setup form.
  const [loading, setLoading] = useState(
    () => useStore.getState().bgTasks?.quiz?.status === 'running'
  )
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState('')
  const [answers, setAnswers] = useState(saved.answers || [])
  const [cardState, setCardState] = useState(saved.cardState || { sending: false, done: false, count: 0 })
  const bg = useBgTask('quiz')
  const mountedRef = useRef(true)
  useEffect(() => () => { mountedRef.current = false }, [])
  const timerRef = useRef(null)
  // Live verification progress from the quiz stream (verified X of Y)
  const [progress, setProgress] = useState({ done: 0, total: 0 })

  // Adopt a background run: returning to this page while it works (or after
  // it finished into the store while we were away) — never lose the task.
  useEffect(() => {
    if (bg?.status === 'running') {
      setLoading(true)
      if (bg.topic && !topic) setTopic(bg.topic)
      if (bg.verified != null) setProgress({ done: bg.verified, total: bg.total || count })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  useEffect(() => {
    if (bg?.status === 'done' && questions.length === 0 && saved.questions?.length) {
      setQuestions(saved.questions)
      setCurrent(saved.current || 0)
      setSelected(saved.selected || null)
      setScore(saved.score || 0)
      setDone(saved.done || false)
      setAnswers(saved.answers || [])
      setTopic(saved.topic || topic)
      setLoading(false)
    } else if ((bg?.status === 'error' || bg?.status === 'cancelled') && loading && questions.length === 0) {
      setLoading(false)
      if (bg.status === 'error' && bg.error) setError(bg.error)
      if (bg.status === 'cancelled') setError('Cancelled.')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bg?.status])

  // Auto-persist to store
  useEffect(() => {
    setStudyTool('quiz', { questions, current, selected, score, done, answers, topic, level, count, cardState })
  }, [questions, current, selected, score, done, answers, topic, level, count, cardState])

  // Elapsed timer while loading
  useEffect(() => {
    if (loading) {
      setElapsed(0)
      timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000)
    } else {
      clearInterval(timerRef.current)
    }
    return () => clearInterval(timerRef.current)
  }, [loading])

  const start = async () => {
    if (!topic.trim()) return
    const t = topic.trim(), l = level, c = count
    setLoading(true)
    setError('')
    setQuestions([])
    setProgress({ done: 0, total: c })
    setCurrent(0)
    setSelected(null)
    setScore(0)
    setDone(false)
    setAnswers([])
    try {
      // Streamed verification: each question appears the moment it's
      // verified (no 8-12s blank wait). Manager-owned so navigating away
      // keeps it running; the result lands in the store via onDone.
      const data = await startTask('quiz', {
        label: `Quiz: ${t}`,
        page: '/create',
        topic: t,
        run: (signal) => streamQuiz({
          topic: t, level: l, count: c, signal,
          onTotal: (total) => { if (mountedRef.current) setProgress(p => ({ ...p, total })) },
          onQuestion: (q) => { if (mountedRef.current) setQuestions(qs => [...qs, q]) },
          onProgress: (done, total) => {
            if (mountedRef.current) setProgress({ done, total })
            useStore.getState().setBgTask('quiz', {
              label: `Quiz: ${t} (${done}/${total})`, verified: done, total,
            })
          },
        }),
        onDone: (d) => {
          const qs = d.questions || []
          setStudyTool('quiz', {
            questions: qs, current: 0, selected: null, score: 0,
            done: false, answers: [], topic: t, level: l, count: c, cardState,
          })
        },
      })
      if (!mountedRef.current) return
      const qs = data.questions || []
      setQuestions(qs)
      setProgress({ done: qs.length, total: qs.length || c })
      if (qs.length === 0) setError('No questions generated — try a different topic.')
    } catch (e) {
      if (!mountedRef.current) return
      if (e.name === 'AbortError') setError('Cancelled.')
      else setError(e.message || 'Failed to generate quiz')
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }

  const cancel = () => {
    cancelTask('quiz')
    setLoading(false)
  }

  const handleSelect = async (i) => {
    if (selected !== null) return
    setSelected(i)
    const q = questions[current]
    const correct = LETTER[i] === q.correct
    if (correct) setScore(s => s + 1)
    setAnswers(a => [...a, { correct, selected: i, question: q }])
    try { await checkAnswer(topic, correct) } catch {}
  }

  const next = () => {
    if (current < questions.length - 1) {
      setCurrent(c => c + 1)
      setSelected(null)
    } else {
      setDone(true)
    }
  }

  const wrongAnswers = answers.filter(a => !a.correct)

  const sendToFlashcards = async () => {
    const cards = wrongAnswers.map(a => {
      const correctLetter = a.question.correct
      const correctIdx = LETTER.indexOf(correctLetter)
      const correctText = a.question.options?.[correctIdx] ?? correctLetter
      return { question: a.question.question, answer: correctText }
    })
    if (cards.length === 0) return
    setCardState(s => ({ ...s, sending: true }))
    try {
      await bulkAddSrCards(cards, topic || 'general')
      setCardState({ sending: false, done: true, count: cards.length })
    } catch {
      setCardState({ sending: false, done: false, count: 0 })
    }
  }

  const q = questions[current]

  // Keyboard shortcuts
  const handleKeyDown = useCallback((e) => {
    if (questions.length === 0 || loading) return
    if (done) return
    const keyMap = { '1': 0, '2': 1, '3': 2, '4': 3, 'a': 0, 'b': 1, 'c': 2, 'd': 3 }
    const idx = keyMap[e.key.toLowerCase()]
    if (idx !== undefined && idx < (q?.options?.length || 0)) {
      handleSelect(idx)
    }
    if ((e.key === 'Enter' || e.key === ' ') && selected !== null) {
      e.preventDefault()
      next()
    }
  }, [questions.length, loading, done, q, selected])

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  return (
    <div className="w-full px-6 lg:px-8 py-6 page-enter">
      <div className="flex items-center gap-2 mb-6">
        <BookOpen size={20} className="text-[#7c6af7]" />
        <h1 className="text-lg font-semibold text-[#e8e8e8]">Quiz Generator</h1>
      </div>

      {/* Setup */}
      {questions.length === 0 && !loading && (
        <div className="space-y-4">
          <div>
            <label className="text-xs text-[#888] mb-1.5 block">Topic</label>
            <input
              value={topic}
              onChange={e => setTopic(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && start()}
              placeholder="e.g. Quadratic equations, World War 2, Python lists..."
              className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-4 py-2.5 text-sm text-[#e8e8e8] placeholder-[#444] outline-none focus:border-[#7c6af7]/50"
            />
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="text-xs text-[#888] mb-1.5 block">Difficulty</label>
              <div className="flex gap-2">
                {LEVELS.map(l => (
                  <button key={l} onClick={() => setLevel(l)}
                    className={`flex-1 py-2 rounded-lg text-xs capitalize transition-colors ${
                      level === l ? 'bg-[#7c6af7] text-white' : 'bg-[#1a1a1a] border border-[#2a2a2a] text-[#888] hover:text-[#e8e8e8]'
                    }`}>
                    {l}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <label className="text-xs text-[#888]">Questions:</label>
            {[3, 5, 10, 15].map(n => (
              <button key={n} onClick={() => setCount(n)}
                className={`w-10 h-8 rounded-lg text-xs transition-colors ${
                  count === n ? 'bg-[#7c6af7] text-white' : 'bg-[#1a1a1a] border border-[#2a2a2a] text-[#888] hover:text-[#e8e8e8]'
                }`}>
                {n}
              </button>
            ))}
          </div>
          <button onClick={start} disabled={!topic.trim()}
            className="w-full py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium transition-colors disabled:opacity-40">
            Generate Quiz
          </button>
        </div>
      )}

      {loading && (
        <div className="flex flex-col items-center py-16 gap-3 px-6">
          <div className="w-8 h-8 border-2 border-[#7c6af7] border-t-transparent rounded-full animate-spin" />
          <p className="text-[#888] text-sm">
            {progress.total > 0 && progress.done < progress.total
              ? `Verified ${progress.done} of ${progress.total} — questions appear as they're checked…`
              : `Generating verified quiz on "${topic}"... ${elapsed}s`}
          </p>
          {progress.total > 0 && (
            <div className="w-full max-w-xs">
              <div className="w-full bg-[#2a2a2a] rounded-full h-1.5 overflow-hidden">
                <div className="bg-[#7c6af7] h-1.5 rounded-full transition-all duration-300"
                  style={{ width: `${Math.round((progress.done / Math.max(progress.total, 1)) * 100)}%` }} />
              </div>
              <p className="text-center text-[11px] text-[#666] mt-1.5">
                {questions.length > 0 ? `${questions.length} ready — rest verifying…` : 'Checking answers…'}
              </p>
            </div>
          )}
          <p className="text-[#555] text-xs">Verified mode • keeps working if you leave this page</p>
          {elapsed > 12 && progress.done === 0 && <p className="text-[#f59e0b] text-xs">Still verifying — checking answers</p>}
          <button onClick={cancel} className="mt-2 px-4 py-1.5 rounded-full bg-[#2a2a2a] text-xs text-[#888] hover:text-[#e8e8e8]">Cancel</button>
        </div>
      )}
      {error && !loading && questions.length === 0 && (
        <div className="my-4 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-400 text-center">{error}</div>
      )}

      {/* Quiz */}
      {q && !done && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-[#888]">Question {current + 1} of {questions.length}</span>
            <span className="text-xs text-[#888]">Score: {score}/{current + (selected !== null ? 1 : 0)}</span>
          </div>
          <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <p className="text-[#e8e8e8] text-base flex-1">{q.question}</p>
              {q.verified && (
                <span className={`ml-2 px-2 py-0.5 rounded-full text-[9px] font-medium flex-shrink-0 ${
                  q.verified === 'triple_verified' ? 'bg-green-500/15 text-green-400 border border-green-500/30' :
                  q.verified === 'majority_verified' ? 'bg-blue-500/15 text-blue-400 border border-blue-500/30' :
                  q.verified === 'disputed' ? 'bg-yellow-500/15 text-yellow-400 border border-yellow-500/30' :
                  'bg-[#2a2a2a] text-[#888] border border-[#333]'
                }`}>
                  {q.verified === 'triple_verified' ? '✓ Triple Verified' :
                   q.verified === 'majority_verified' ? '✓ Majority' :
                   q.verified === 'disputed' ? '? Disputed' : '— Unverified'}
                </span>
              )}
            </div>
            <div className="space-y-2.5">
              {q.options.map((opt, i) => (
                <button key={i} onClick={() => handleSelect(i)}
                  className={`w-full text-left px-4 py-3 rounded-xl border text-sm transition-all ${
                    selected === null ? 'border-[#2a2a2a] hover:border-[#7c6af7]/50 text-[#aaa]' :
                    LETTER[i] === q.correct ? 'border-green-500 bg-green-500/10 text-green-300' :
                    selected === i ? 'border-red-500 bg-red-500/10 text-red-400' :
                    'border-[#1f1f1f] text-[#444]'
                  }`}>
                  <span className="font-mono text-xs mr-2">{LETTER[i]})</span>{opt}
                </button>
              ))}
            </div>
            {selected !== null && q.explanation && (
              <div className="mt-4 p-3 bg-[#0f0f0f] border border-[#2a2a2a] rounded-lg text-xs text-[#888]">
                💡 {q.explanation}
              </div>
            )}
          </div>
          {selected !== null && (
            <button onClick={next}
              className="w-full py-2.5 rounded-xl bg-[#7c6af7]/20 text-[#a89bf8] hover:bg-[#7c6af7]/30 transition-colors text-sm">
              {current < questions.length - 1 ? 'Next Question →' : 'See Results'}
            </button>
          )}
        </div>
      )}

      {/* Results */}
      {done && (
        <div className="text-center py-8">
          <Trophy size={48} className="text-yellow-400 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-[#e8e8e8] mb-1">{score}/{questions.length}</h2>
          <p className="text-[#888] mb-6">
            {score === questions.length ? 'Perfect score! Amazing! 🎉' :
             score >= questions.length * 0.7 ? 'Great job! Keep it up! 👏' :
             score >= questions.length * 0.5 ? 'Good effort! Keep practising! 💪' :
             'Keep studying! You\'ll get it! 📚'}
          </p>
          <div className="space-y-2 text-left mb-6">
            {answers.map((a, i) => (
              <div key={i} className={`flex items-center gap-2 text-xs px-3 py-2 rounded-lg ${a.correct ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                <span>{a.correct ? '✓' : '✗'}</span>
                <span className="truncate flex-1">{a.question.question}</span>
                {a.question.verified && (
                  <span className={`text-[8px] px-1.5 py-0.5 rounded-full ${
                    a.question.verified === 'triple_verified' ? 'bg-green-500/20 text-green-400' :
                    a.question.verified === 'majority_verified' ? 'bg-blue-500/20 text-blue-400' :
                    a.question.verified === 'disputed' ? 'bg-yellow-500/20 text-yellow-400' :
                    'bg-[#2a2a2a] text-[#888]'
                  }`}>
                    {a.question.verified === 'triple_verified' ? '3x' :
                     a.question.verified === 'majority_verified' ? '2x' :
                     a.question.verified === 'disputed' ? '?' : '—'}
                  </span>
                )}
              </div>
            ))}
          </div>
          {wrongAnswers.length > 0 && !cardState.done && (
            <button onClick={sendToFlashcards} disabled={cardState.sending}
              className="flex items-center gap-2 mx-auto mb-6 px-6 py-2.5 rounded-xl bg-[#f59e0b]/15 border border-[#f59e0b]/30 text-[#f59e0b] text-sm hover:bg-[#f59e0b]/25 transition-colors disabled:opacity-50">
              <Sparkles size={14} />
              {cardState.sending ? 'Sending to flashcards...' : `Send ${wrongAnswers.length} missed question${wrongAnswers.length>1?'s':''} to revision flashcards`}
            </button>
          )}
          {cardState.done && (
            <div className="mx-auto mb-6 max-w-md px-4 py-3 rounded-xl bg-green-500/10 border border-green-500/30 text-green-400 text-xs">
              ✓ {cardState.count} card{cardState.count>1?'s':''} added to spaced-repetition flashcards — review them in Study Tools → Spaced Repetition
            </div>
          )}
          <button onClick={() => { setQuestions([]); setTopic(''); setCardState({ sending: false, done: false, count: 0 }) }}
            className="flex items-center gap-2 mx-auto px-6 py-2.5 rounded-xl bg-[#7c6af7] text-white text-sm">
            <RotateCcw size={14} /> New Quiz
          </button>
        </div>
      )}
    </div>
  )
}
