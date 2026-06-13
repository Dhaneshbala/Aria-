import { useState } from 'react'
import { generateQuiz, checkAnswer } from '../services/api'
import { BookOpen, Trophy, RotateCcw } from 'lucide-react'

const LEVELS = ['easy', 'medium', 'hard', 'olympiad']
const LETTER = ['A', 'B', 'C', 'D']

export default function QuizPage() {
  const [topic, setTopic] = useState('')
  const [level, setLevel] = useState('medium')
  const [count, setCount] = useState(5)
  const [questions, setQuestions] = useState([])
  const [current, setCurrent] = useState(0)
  const [selected, setSelected] = useState(null)
  const [score, setScore] = useState(0)
  const [done, setDone] = useState(false)
  const [loading, setLoading] = useState(false)
  const [answers, setAnswers] = useState([])

  const start = async () => {
    if (!topic.trim()) return
    setLoading(true)
    setQuestions([])
    setCurrent(0)
    setSelected(null)
    setScore(0)
    setDone(false)
    setAnswers([])
    try {
      const data = await generateQuiz(topic, level, count)
      setQuestions(data.questions || [])
    } catch {}
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

  const q = questions[current]

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 page-enter">
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
        <div className="flex flex-col items-center py-16 gap-3">
          <div className="w-8 h-8 border-2 border-[#7c6af7] border-t-transparent rounded-full animate-spin" />
          <p className="text-[#888] text-sm">Generating quiz on "{topic}"...</p>
        </div>
      )}

      {/* Quiz */}
      {q && !done && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-[#888]">Question {current + 1} of {questions.length}</span>
            <span className="text-xs text-[#888]">Score: {score}/{current + (selected !== null ? 1 : 0)}</span>
          </div>
          <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-5">
            <p className="text-[#e8e8e8] text-base mb-5">{q.question}</p>
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
                <span className="truncate">{a.question.question}</span>
              </div>
            ))}
          </div>
          <button onClick={() => { setQuestions([]); setTopic('') }}
            className="flex items-center gap-2 mx-auto px-6 py-2.5 rounded-xl bg-[#7c6af7] text-white text-sm">
            <RotateCcw size={14} /> New Quiz
          </button>
        </div>
      )}
    </div>
  )
}
