import { useState, useEffect, useRef, useCallback } from 'react'
import { Play, Pause, RotateCcw, Clock, CheckCircle, XCircle, AlertTriangle, Trophy, BarChart3 } from 'lucide-react'
import { useStore } from '../store'

const DIFFICULTY_COLORS = {
  easy: 'text-green-400 bg-green-400/10 border-green-400/20',
  medium: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20',
  hard: 'text-red-400 bg-red-400/10 border-red-400/20',
}

export default function ExamTimer({ questions, timeMinutes, difficulty, topic, onComplete }) {
  const [timeLeft, setTimeLeft] = useState(timeMinutes * 60)
  const [isRunning, setIsRunning] = useState(false)
  const [answers, setAnswers] = useState({})
  const [submitted, setSubmitted] = useState(false)
  const [currentQ, setCurrentQ] = useState(0)
  const [showResults, setShowResults] = useState(false)
  const [questionTimes, setQuestionTimes] = useState({})
  const timerRef = useRef(null)
  const qStartRef = useRef(Date.now())

  const totalSeconds = timeMinutes * 60
  const minutes = Math.floor(timeLeft / 60)
  const seconds = timeLeft % 60
  const pct = ((totalSeconds - timeLeft) / totalSeconds) * 100
  const answered = Object.keys(answers).length
  const isLow = timeLeft <= 60
  const isCritical = timeLeft <= 30

  // Timer
  useEffect(() => {
    if (!isRunning || submitted) return
    timerRef.current = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          clearInterval(timerRef.current)
          handleSubmit(true)
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(timerRef.current)
  }, [isRunning, submitted])

  // Track time per question
  const switchQuestion = useCallback((next) => {
    const now = Date.now()
    const elapsed = Math.round((now - qStartRef.current) / 1000)
    setQuestionTimes(prev => ({ ...prev, [currentQ]: (prev[currentQ] || 0) + elapsed }))
    setCurrentQ(next)
    qStartRef.current = now
  }, [currentQ])

  const start = () => {
    qStartRef.current = Date.now()
    setIsRunning(true)
  }

  const pause = () => setIsRunning(false)
  const resume = () => setIsRunning(true)

  const selectAnswer = (qIdx, letter) => {
    if (submitted) return
    setAnswers(prev => ({ ...prev, [qIdx]: letter }))
    // Auto-advance to next unanswered
    for (let i = qIdx + 1; i < questions.length; i++) {
      if (!answers[i] && i !== qIdx) {
        switchQuestion(i)
        return
      }
    }
  }

  const handleSubmit = (timedOut = false) => {
    clearInterval(timerRef.current)
    setIsRunning(false)
    setSubmitted(true)
    // Final question time
    const elapsed = Math.round((Date.now() - qStartRef.current) / 1000)
    setQuestionTimes(prev => ({ ...prev, [currentQ]: (prev[currentQ] || 0) + elapsed }))
    setShowResults(true)
    onComplete?.({
      answers,
      timedOut,
      totalTime: totalSeconds - timeLeft,
      questionTimes,
      score: calculateScore(),
    })
  }

  const calculateScore = () => {
    let correct = 0
    questions.forEach((q, i) => {
      if (answers[i] === q.correct) correct++
    })
    return { correct, total: questions.length, pct: Math.round((correct / questions.length) * 100) }
  }

  const reset = () => {
    clearInterval(timerRef.current)
    setTimeLeft(timeMinutes * 60)
    setIsRunning(false)
    setAnswers({})
    setSubmitted(false)
    setCurrentQ(0)
    setShowResults(false)
    setQuestionTimes({})
  }

  const score = submitted ? calculateScore() : null
  const grade = score ? (score.pct >= 90 ? 'A' : score.pct >= 80 ? 'B' : score.pct >= 70 ? 'C' : score.pct >= 60 ? 'D' : 'F') : null

  if (showResults) {
    const avgTimePerQ = Math.round(Object.values(questionTimes).reduce((a, b) => a + b, 0) / questions.length)
    const slowest = Math.max(...Object.values(questionTimes))
    const fastest = Math.min(...Object.values(questionTimes))

    return (
      <div className="max-w-2xl mx-auto p-6">
        <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl p-6">
          {/* Header */}
          <div className="text-center mb-6">
            <div className={`inline-flex items-center justify-center w-20 h-20 rounded-full text-3xl font-bold mb-3 ${score.pct >= 80 ? 'bg-green-500/15 text-green-400' : score.pct >= 60 ? 'bg-yellow-500/15 text-yellow-400' : 'bg-red-500/15 text-red-400'}`}>
              {grade}
            </div>
            <h2 className="text-xl font-bold text-white mb-1">Exam Complete!</h2>
            <p className="text-sm text-[#666]">{topic} — {difficulty}</p>
          </div>

          {/* Score */}
          <div className="grid grid-cols-3 gap-3 mb-6">
            <div className="bg-[#0f0f0f] rounded-xl p-3 text-center">
              <p className="text-2xl font-bold text-white">{score.correct}/{score.total}</p>
              <p className="text-[10px] text-[#666]">Correct</p>
            </div>
            <div className="bg-[#0f0f0f] rounded-xl p-3 text-center">
              <p className="text-2xl font-bold text-white">{score.pct}%</p>
              <p className="text-[10px] text-[#666]">Accuracy</p>
            </div>
            <div className="bg-[#0f0f0f] rounded-xl p-3 text-center">
              <p className="text-2xl font-bold text-white">{Math.floor(totalSeconds - timeLeft)}s</p>
              <p className="text-[10px] text-[#666]">Time Used</p>
            </div>
          </div>

          {/* Time Analytics */}
          <div className="bg-[#0f0f0f] rounded-xl p-4 mb-4">
            <h3 className="text-xs font-medium text-[#888] mb-3 flex items-center gap-1.5">
              <BarChart3 size={12} /> Time Analytics
            </h3>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div>
                <p className="text-lg font-bold text-white">{avgTimePerQ}s</p>
                <p className="text-[10px] text-[#666]">Avg per Q</p>
              </div>
              <div>
                <p className="text-lg font-bold text-green-400">{fastest}s</p>
                <p className="text-[10px] text-[#666]">Fastest</p>
              </div>
              <div>
                <p className="text-lg font-bold text-red-400">{slowest}s</p>
                <p className="text-[10px] text-[#666]">Slowest</p>
              </div>
            </div>
          </div>

          {/* Per-question breakdown */}
          <div className="space-y-2 mb-6 max-h-64 overflow-y-auto">
            {questions.map((q, i) => {
              const isCorrect = answers[i] === q.correct
              const time = questionTimes[i] || 0
              return (
                <div key={i} className={`flex items-center gap-3 p-2 rounded-lg ${isCorrect ? 'bg-green-500/5' : 'bg-red-500/5'}`}>
                  {isCorrect ? <CheckCircle size={14} className="text-green-400 flex-shrink-0" /> : <XCircle size={14} className="text-red-400 flex-shrink-0" />}
                  <span className="text-xs text-[#ccc] flex-1 truncate">{q.question.slice(0, 60)}...</span>
                  <span className="text-[10px] text-[#666]">{time}s</span>
                  {!isCorrect && <span className="text-[10px] text-red-400">Ans: {q.correct}</span>}
                </div>
              )
            })}
          </div>

          <div className="flex gap-2">
            <button onClick={reset} className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl bg-[#2a2a2a] text-[#aaa] text-sm hover:bg-[#333] transition-colors">
              <RotateCcw size={14} /> Retake
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (!questions?.length) return null

  const q = questions[currentQ]

  return (
    <div className="max-w-2xl mx-auto p-6">
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl overflow-hidden">
        {/* Timer Header */}
        <div className={`px-4 py-3 flex items-center justify-between border-b border-[#2a2a2a] ${isCritical ? 'bg-red-500/10' : isLow ? 'bg-yellow-500/10' : ''}`}>
          <div className="flex items-center gap-3">
            <div className={`flex items-center gap-1.5 font-mono text-lg font-bold ${isCritical ? 'text-red-400 animate-pulse' : isLow ? 'text-yellow-400' : 'text-white'}`}>
              <Clock size={16} />
              {String(minutes).padStart(2, '0')}:{String(seconds).padStart(2, '0')}
            </div>
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${DIFFICULTY_COLORS[difficulty] || DIFFICULTY_COLORS.medium}`}>
              {difficulty}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-[#666]">{answered}/{questions.length} answered</span>
            {!isRunning && !submitted && (
              <button onClick={start} className="p-1.5 rounded-lg bg-[#7c6af7] text-white hover:bg-[#6a59e0]">
                <Play size={14} />
              </button>
            )}
            {isRunning && (
              <button onClick={pause} className="p-1.5 rounded-lg bg-[#2a2a2a] text-[#aaa] hover:bg-[#333]">
                <Pause size={14} />
              </button>
            )}
          </div>
        </div>

        {/* Progress bar */}
        <div className="h-1 bg-[#0f0f0f]">
          <div className={`h-full transition-all duration-1000 ${isCritical ? 'bg-red-500' : isLow ? 'bg-yellow-500' : 'bg-[#7c6af7]'}`} style={{ width: `${pct}%` }} />
        </div>

        {/* Question navigation dots */}
        <div className="px-4 py-2 flex gap-1 flex-wrap border-b border-[#2a2a2a]">
          {questions.map((_, i) => (
            <button key={i} onClick={() => switchQuestion(i)}
              className={`w-6 h-6 rounded text-[10px] font-medium transition-colors ${i === currentQ ? 'bg-[#7c6af7] text-white' : answers[i] ? 'bg-[#7c6af7]/20 text-[#7c6af7]' : 'bg-[#2a2a2a] text-[#666]'}`}>
              {i + 1}
            </button>
          ))}
        </div>

        {/* Question */}
        {!isRunning && !submitted && answered === 0 ? (
          <div className="p-8 text-center">
            <AlertTriangle size={32} className="mx-auto text-[#7c6af7] mb-3" />
            <h3 className="text-lg font-bold text-white mb-2">Ready to Start?</h3>
            <p className="text-sm text-[#666] mb-4">{questions.length} questions • {timeMinutes} minutes</p>
            <button onClick={start} className="px-6 py-2.5 rounded-xl bg-[#7c6af7] text-white text-sm font-medium hover:bg-[#6a59e0] transition-colors">
              Start Exam
            </button>
          </div>
        ) : (
          <div className="p-6">
            <p className="text-xs text-[#666] mb-2">Question {currentQ + 1} of {questions.length}</p>
            <p className="text-sm text-white mb-4 leading-relaxed">{q.question}</p>
            <div className="space-y-2">
              {q.options.map((opt, i) => {
                const letter = opt.charAt(0) === '(' ? opt.slice(0, 3) : opt.charAt(0) + ')'
                const selected = answers[currentQ] === letter.charAt(0)
                return (
                  <button key={i} onClick={() => selectAnswer(currentQ, letter.charAt(0))}
                    className={`w-full text-left px-4 py-3 rounded-xl text-sm transition-all ${selected ? 'bg-[#7c6af7]/15 border border-[#7c6af7]/40 text-[#a89bf8]' : 'bg-[#0f0f0f] border border-[#2a2a2a] text-[#ccc] hover:border-[#7c6af7]/20'}`}>
                    <span className="font-medium mr-2">{letter}</span>
                    {opt.replace(/^[A-D][\)\.]\s*/, '')}
                  </button>
                )
              })}
            </div>

            {/* Navigation */}
            <div className="flex justify-between mt-6">
              <button onClick={() => switchQuestion(Math.max(0, currentQ - 1))} disabled={currentQ === 0}
                className="px-4 py-2 rounded-xl bg-[#2a2a2a] text-[#aaa] text-sm disabled:opacity-30 hover:bg-[#333]">
                Previous
              </button>
              {currentQ < questions.length - 1 ? (
                <button onClick={() => switchQuestion(currentQ + 1)}
                  className="px-4 py-2 rounded-xl bg-[#7c6af7] text-white text-sm hover:bg-[#6a59e0]">
                  Next
                </button>
              ) : (
                <button onClick={() => handleSubmit(false)}
                  className="px-4 py-2 rounded-xl bg-green-600 text-white text-sm hover:bg-green-500">
                  Submit Exam
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
