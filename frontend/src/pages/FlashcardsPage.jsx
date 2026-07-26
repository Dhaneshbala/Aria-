import { useState, useEffect, useCallback } from 'react'
import { generateFlashcards, bulkAddSrCards } from '../services/api'
import { useStore } from '../store'
import { showToast } from '../components/Toast'
import { CreditCard, RotateCcw, Shuffle, Send, ChevronLeft, ChevronRight, Check, X, Sparkles, Target, Zap } from 'lucide-react'

export default function FlashcardsPage() {
  const { studyTools, setStudyTool } = useStore()
  const saved = studyTools.flashcards
  const [topic, setTopic] = useState(saved.topic || '')
  const [count, setCount] = useState(saved.count || 10)
  const [cards, setCards] = useState(saved.cards || [])
  const [order, setOrder] = useState(saved.order || [])
  const [idx, setIdx] = useState(saved.idx || 0)
  const [flipped, setFlipped] = useState(saved.flipped || false)
  const [known, setKnown] = useState(saved.known || [])
  const [loading, setLoading] = useState(false)
  const [sessionDone, setSessionDone] = useState(false)
  const [streak, setStreak] = useState(0)

  useEffect(() => {
    setStudyTool('flashcards', { cards, order, idx, flipped, known, topic, count })
  }, [cards, order, idx, flipped, known, topic, count])

  const generate = async () => {
    if (!topic.trim()) return
    setLoading(true); setSessionDone(false)
    try {
      const data = await generateFlashcards(topic, count)
      const c = data.cards || []
      setCards(c)
      setOrder(c.map((_, i) => i))
      setIdx(0); setFlipped(false); setKnown(new Set()); setStreak(0)
    } catch { showToast('Failed to generate flashcards', 'error') }
    setLoading(false)
  }

  const shuffle = () => {
    setOrder(o => [...o].sort(() => Math.random() - 0.5))
    setIdx(0); setFlipped(false)
  }

  const markKnown = () => {
    const cardIdx = order[idx]
    setKnown(k => new Set([...k, cardIdx]))
    setStreak(s => s + 1)
    advance()
  }

  const markUnknown = () => {
    setStreak(0)
    advance()
  }

  const advance = () => {
    setFlipped(false)
    if (idx + 1 >= order.length) {
      setSessionDone(true)
    } else {
      setIdx(i => i + 1)
    }
  }

  const next = () => { setFlipped(false); if (idx + 1 < order.length) setIdx(i => i + 1) }
  const prev = () => { setFlipped(false); if (idx > 0) setIdx(i => i - 1) }

  const currentCard = cards[order[idx]]

  const sendToSpacedRep = async () => {
    if (!cards.length) return
    try {
      await bulkAddSrCards(cards, topic || 'general')
      showToast(`${cards.length} cards sent to Spaced Repetition!`, 'success')
    } catch { showToast('Failed to send cards', 'error') }
  }

  const restart = () => {
    setIdx(0); setFlipped(false); setKnown(new Set()); setStreak(0); setSessionDone(false)
  }

  const handleKeyDown = useCallback((e) => {
    if (cards.length === 0 || sessionDone) return
    if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); setFlipped(f => !f) }
    if (e.key === 'ArrowRight') next()
    if (e.key === 'ArrowLeft') prev()
    if (e.key === '1' || e.key === 'y' || e.key === 'Y') markKnown()
    if (e.key === '2' || e.key === 'n' || e.key === 'N') markUnknown()
  }, [cards.length, order.length, idx, sessionDone])

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  const reviewed = known.size
  const remaining = order.length - (idx + 1)
  const accuracy = reviewed > 0 ? Math.round((reviewed / (reviewed + (idx + 1 - reviewed))) * 100) : 0

  // ── Generate Screen ──────────────────────────────────────────────────────
  if (cards.length === 0 && !loading) {
    return (
      <div className="h-full flex flex-col items-center justify-center px-4">
        <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-[#7c6af7] to-[#4f46e5] flex items-center justify-center mb-6 shadow-lg shadow-[#7c6af7]/20">
          <CreditCard size={36} className="text-white" />
        </div>
        <h1 className="text-2xl font-bold text-[#e8e8e8] mb-2">Flashcards</h1>
        <p className="text-sm text-[#555] mb-8 max-w-xs text-center">Generate AI-powered flashcards for any topic and memorise them with spaced repetition</p>

        <div className="w-full max-w-sm space-y-4">
          <input value={topic} onChange={e => setTopic(e.target.value)} onKeyDown={e => e.key === 'Enter' && generate()}
            placeholder="What do you want to study?"
            className="w-full bg-[#1a1a2e] border border-[#2a2a40] rounded-xl px-4 py-3 text-sm text-[#e8e8e8] placeholder-[#555] outline-none focus:border-[#7c6af7] transition-colors" />
          <div className="flex items-center justify-between">
            <span className="text-xs text-[#666]">Number of cards</span>
            <div className="flex gap-1.5">
              {[5, 10, 15, 20].map(n => (
                <button key={n} onClick={() => setCount(n)}
                  className={`w-10 h-8 rounded-lg text-xs font-medium transition-all ${
                    count === n ? 'bg-[#7c6af7] text-white shadow-md shadow-[#7c6af7]/20' : 'bg-[#1a1a2e] border border-[#2a2a40] text-[#888] hover:border-[#7c6af7]/50'
                  }`}>{n}</button>
              ))}
            </div>
          </div>
          <button onClick={generate} disabled={!topic.trim()}
            className="w-full py-3 rounded-xl bg-gradient-to-r from-[#7c6af7] to-[#6a59e0] text-white text-sm font-semibold disabled:opacity-40 hover:shadow-lg hover:shadow-[#7c6af7]/20 transition-all active:scale-[0.98]">
            Generate Flashcards
          </button>
        </div>
      </div>
    )
  }

  // ── Loading Screen ───────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-4">
        <div className="relative">
          <div className="w-16 h-16 border-4 border-[#2a2a40] border-t-[#7c6af7] rounded-full animate-spin" />
          <Sparkles size={20} className="text-[#7c6af7] absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 animate-pulse" />
        </div>
        <div className="text-center">
          <p className="text-sm text-[#e8e8e8] font-medium">Creating flashcards</p>
          <p className="text-xs text-[#555] mt-1">for "{topic}"</p>
        </div>
      </div>
    )
  }

  // ── Session Complete Screen ──────────────────────────────────────────────
  if (sessionDone) {
    return (
      <div className="h-full flex flex-col items-center justify-center px-4">
        <div className="w-20 h-20 rounded-full bg-green-500/10 border border-green-500/20 flex items-center justify-center mb-6">
          <Check size={36} className="text-green-400" />
        </div>
        <h1 className="text-2xl font-bold text-[#e8e8e8] mb-2">Session Complete!</h1>
        <p className="text-sm text-[#555] mb-8">You reviewed all {order.length} cards</p>

        <div className="grid grid-cols-3 gap-4 mb-8 w-full max-w-sm">
          <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 text-center">
            <div className="text-2xl font-bold text-green-400">{reviewed}</div>
            <div className="text-[10px] text-[#555] mt-1">Known</div>
          </div>
          <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 text-center">
            <div className="text-2xl font-bold text-[#7c6af7]">{order.length - reviewed}</div>
            <div className="text-[10px] text-[#555] mt-1">To Review</div>
          </div>
          <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 text-center">
            <div className="text-2xl font-bold text-[#f59e0b]">{accuracy}%</div>
            <div className="text-[10px] text-[#555] mt-1">Accuracy</div>
          </div>
        </div>

        <div className="w-full max-w-sm space-y-2">
          <button onClick={sendToSpacedRep}
            className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-[#7c6af7]/10 border border-[#7c6af7]/20 text-[#7c6af7] text-sm font-medium hover:bg-[#7c6af7]/20 transition-colors">
            <Send size={14} /> Send all to Spaced Repetition
          </button>
          <button onClick={restart}
            className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40] text-[#888] text-sm font-medium hover:text-[#e8e8e8] hover:border-[#444] transition-colors">
            <RotateCcw size={14} /> Review Again
          </button>
          <button onClick={() => { setCards([]); setSessionDone(false) }}
            className="w-full py-2 text-xs text-[#555] hover:text-[#888] transition-colors">
            New Topic
          </button>
        </div>
      </div>
    )
  }

  // ── Main Flashcard View ──────────────────────────────────────────────────
  return (
    <div className="h-full flex flex-col px-4 py-4 max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-3 flex-shrink-0">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold text-[#e8e8e8]">{topic}</h2>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#7c6af7]/10 text-[#7c6af7] border border-[#7c6af7]/20">
            {idx + 1} / {order.length}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {streak >= 3 && (
            <span className="flex items-center gap-1 text-[10px] text-[#f59e0b] bg-[#f59e0b]/10 px-2 py-0.5 rounded-full border border-[#f59e0b]/20">
              <Zap size={10} /> {streak} streak
            </span>
          )}
          <button onClick={shuffle} className="p-1.5 rounded-lg text-[#666] hover:text-[#aaa] hover:bg-[#1a1a2e] transition-colors" title="Shuffle">
            <Shuffle size={14} />
          </button>
        </div>
      </div>

      {/* Progress dots */}
      <div className="flex gap-1 mb-4 flex-shrink-0">
        {order.map((cardIdx, i) => (
          <div key={i} className={`flex-1 h-1 rounded-full transition-all ${
            i < idx ? (known.has(order[i]) ? 'bg-green-400' : 'bg-red-400') :
            i === idx ? 'bg-[#7c6af7]' : 'bg-[#2a2a2a]'
          }`} />
        ))}
      </div>

      {/* Stats bar */}
      <div className="flex items-center justify-between text-[10px] text-[#555] mb-4 flex-shrink-0">
        <span className="flex items-center gap-1"><Check size={10} className="text-green-400" /> {reviewed} known</span>
        <span>{remaining} remaining</span>
        <Target size={10} className="text-[#7c6af7]" />
      </div>

      {/* Card */}
      <div className="flex-1 flex items-center justify-center min-h-0 mb-4">
        <div
          onClick={() => setFlipped(!flipped)}
          className={`w-full max-w-lg aspect-[4/3] flex flex-col items-center justify-center text-center cursor-pointer rounded-2xl border-2 p-8 transition-all duration-300 select-none ${
            flipped
              ? 'bg-gradient-to-br from-[#7c6af7]/10 to-[#4f46e5]/10 border-[#7c6af7]/40 shadow-lg shadow-[#7c6af7]/10'
              : 'bg-gradient-to-br from-[#1a1a2e] to-[#141414] border-[#2a2a40] hover:border-[#7c6af7]/30 hover:shadow-lg hover:shadow-[#7c6af7]/5'
          }`}
        >
          <div className={`text-[10px] uppercase tracking-widest mb-4 font-medium ${
            flipped ? 'text-[#7c6af7]' : 'text-[#444]'
          }`}>
            {flipped ? 'Answer' : 'Question'}
          </div>
          <p className={`leading-relaxed ${flipped ? 'text-lg text-[#06b6d4]' : 'text-xl text-[#e8e8e8]'}`}>
            {flipped ? currentCard.back : currentCard.front}
          </p>
          <div className="mt-auto pt-4">
            <p className="text-[10px] text-[#333]">
              {flipped ? 'Press space or click to go back' : 'Click or press space to reveal'}
            </p>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3 flex-shrink-0 pb-2">
        <button onClick={prev} disabled={idx === 0}
          className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40] text-[#666] hover:text-[#e8e8e8] hover:border-[#444] disabled:opacity-30 disabled:cursor-not-allowed transition-all">
          <ChevronLeft size={18} />
        </button>

        <div className="flex-1 flex gap-2">
          {flipped ? (
            <>
              <button onClick={markUnknown}
                className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm font-medium hover:bg-red-500/20 transition-all active:scale-[0.98]">
                <X size={14} /> Don't Know
              </button>
              <button onClick={markKnown}
                className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl bg-green-500/10 border border-green-500/20 text-green-400 text-sm font-medium hover:bg-green-500/20 transition-all active:scale-[0.98]">
                <Check size={14} /> Got It
              </button>
            </>
          ) : (
            <button onClick={() => setFlipped(true)}
              className="flex-1 py-3 rounded-xl bg-gradient-to-r from-[#7c6af7] to-[#6a59e0] text-white text-sm font-semibold hover:shadow-lg hover:shadow-[#7c6af7]/20 transition-all active:scale-[0.98]">
              Reveal Answer
            </button>
          )}
        </div>

        <button onClick={next} disabled={idx >= order.length - 1}
          className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40] text-[#666] hover:text-[#e8e8e8] hover:border-[#444] disabled:opacity-30 disabled:cursor-not-allowed transition-all">
          <ChevronRight size={18} />
        </button>
      </div>

      {/* Bottom actions */}
      <div className="flex items-center justify-between flex-shrink-0 pt-2 border-t border-[#1a1a2e]">
        <button onClick={sendToSpacedRep}
          className="flex items-center gap-1.5 text-[10px] text-[#7c6af7] hover:text-[#a89bf8] transition-colors">
          <Send size={10} /> Send to Spaced Rep
        </button>
        <div className="flex gap-3 text-[10px] text-[#444]">
          <span><kbd className="px-1 py-0.5 rounded bg-[#1a1a2e] border border-[#2a2a40]">Space</kbd> flip</span>
          <span><kbd className="px-1 py-0.5 rounded bg-[#1a1a2e] border border-[#2a2a40]">Y</kbd> know</span>
          <span><kbd className="px-1 py-0.5 rounded bg-[#1a1a2e] border border-[#2a2a40]">N</kbd> don't know</span>
        </div>
        <button onClick={() => { setCards([]); setSessionDone(false) }}
          className="text-[10px] text-[#555] hover:text-[#888] transition-colors">
          New Topic
        </button>
      </div>
    </div>
  )
}
