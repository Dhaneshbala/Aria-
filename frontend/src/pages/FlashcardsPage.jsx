import { useState, useEffect, useCallback } from 'react'
import { generateFlashcards } from '../services/api'
import { CreditCard, RotateCcw, ChevronLeft, ChevronRight, Shuffle } from 'lucide-react'

export default function FlashcardsPage() {
  const [topic, setTopic] = useState('')
  const [count, setCount] = useState(10)
  const [cards, setCards] = useState([])
  const [order, setOrder] = useState([])
  const [idx, setIdx] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [known, setKnown] = useState(new Set())
  const [loading, setLoading] = useState(false)

  const generate = async () => {
    if (!topic.trim()) return
    setLoading(true)
    try {
      const data = await generateFlashcards(topic, count)
      const c = data.cards || []
      setCards(c)
      setOrder(c.map((_, i) => i))
      setIdx(0)
      setFlipped(false)
      setKnown(new Set())
    } catch {}
    setLoading(false)
  }

  const shuffle = () => {
    setOrder(o => [...o].sort(() => Math.random() - 0.5))
    setIdx(0)
    setFlipped(false)
  }

  const markKnown = () => {
    setKnown(k => new Set([...k, order[idx]]))
    next()
  }

  const next = () => {
    setFlipped(false)
    setIdx(i => (i + 1) % order.length)
  }
  const prev = () => {
    setFlipped(false)
    setIdx(i => (i - 1 + order.length) % order.length)
  }

  const currentCard = cards[order[idx]]

  // Keyboard shortcuts
  const handleKeyDown = useCallback((e) => {
    if (cards.length === 0) return
    if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); setFlipped(f => !f) }
    if (e.key === 'ArrowRight') next()
    if (e.key === 'ArrowLeft') prev()
    if (e.key === 'k' || e.key === 'K') markKnown()
  }, [cards.length, order.length, idx])

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 page-enter">
      <div className="flex items-center gap-2 mb-6">
        <CreditCard size={20} className="text-[#7c6af7]" />
        <h1 className="text-lg font-semibold text-[#e8e8e8]">Flashcards</h1>
      </div>

      {cards.length === 0 && !loading && (
        <div className="space-y-4">
          <input
            value={topic}
            onChange={e => setTopic(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && generate()}
            placeholder="Topic to study (e.g. Periodic table, French Revolution...)"
            className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-4 py-2.5 text-sm text-[#e8e8e8] placeholder-[#444] outline-none focus:border-[#7c6af7]/50"
          />
          <div className="flex items-center gap-3">
            <label className="text-xs text-[#888]">Cards:</label>
            {[5, 10, 15, 20].map(n => (
              <button key={n} onClick={() => setCount(n)}
                className={`w-10 h-8 rounded-lg text-xs ${count === n ? 'bg-[#7c6af7] text-white' : 'bg-[#1a1a1a] border border-[#2a2a2a] text-[#888]'}`}>
                {n}
              </button>
            ))}
          </div>
          <button onClick={generate} disabled={!topic.trim()}
            className="w-full py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-40">
            Generate Flashcards
          </button>
        </div>
      )}

      {loading && (
        <div className="flex flex-col items-center py-16 gap-3">
          <div className="w-8 h-8 border-2 border-[#7c6af7] border-t-transparent rounded-full animate-spin" />
          <p className="text-[#888] text-sm">Creating flashcards for "{topic}"...</p>
        </div>
      )}

      {currentCard && (
        <div>
          {/* Progress */}
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs text-[#888]">{idx + 1} / {order.length}</span>
            <span className="text-xs text-green-400">{known.size} known</span>
            <button onClick={shuffle} className="flex items-center gap-1 text-xs text-[#888] hover:text-[#aaa]">
              <Shuffle size={12} /> Shuffle
            </button>
          </div>
          <div className="w-full bg-[#2a2a2a] rounded-full h-1 mb-6">
            <div className="bg-[#7c6af7] h-1 rounded-full transition-all" style={{ width: `${((idx + 1) / order.length) * 100}%` }} />
          </div>

          {/* Card */}
          <div
            onClick={() => setFlipped(!flipped)}
            className={`min-h-48 flex flex-col items-center justify-center text-center cursor-pointer rounded-2xl border p-8 transition-all duration-200 ${
              flipped
                ? 'bg-[#7c6af7]/10 border-[#7c6af7]/30'
                : 'bg-[#1a1a1a] border-[#2a2a2a] hover:border-[#7c6af7]/30'
            } ${known.has(order[idx]) ? 'opacity-50' : ''}`}
          >
            <p className="text-xs text-[#555] mb-3">{flipped ? 'ANSWER' : 'QUESTION'}</p>
            <p className="text-lg text-[#e8e8e8]">{flipped ? currentCard.back : currentCard.front}</p>
            <p className="text-xs text-[#444] mt-4">Click to flip</p>
          </div>

          {/* Controls */}
          <div className="flex gap-3 mt-4">
            <button onClick={prev} className="p-3 rounded-xl bg-[#1a1a1a] border border-[#2a2a2a] text-[#888] hover:text-[#e8e8e8]">
              <ChevronLeft size={18} />
            </button>
            {flipped && (
              <button onClick={markKnown}
                className="flex-1 py-2.5 rounded-xl bg-green-500/20 text-green-400 hover:bg-green-500/30 text-sm transition-colors">
                ✓ Got it
              </button>
            )}
            {!flipped && <div className="flex-1" />}
            <button onClick={next} className="p-3 rounded-xl bg-[#1a1a1a] border border-[#2a2a2a] text-[#888] hover:text-[#e8e8e8]">
              <ChevronRight size={18} />
            </button>
          </div>
          <button onClick={() => setCards([])} className="mt-4 w-full text-xs text-[#555] hover:text-[#888] flex items-center gap-1 justify-center">
            <RotateCcw size={11} /> New set
          </button>
        </div>
      )}
    </div>
  )
}
