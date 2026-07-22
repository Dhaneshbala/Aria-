import { useState, useEffect } from 'react'
import { showToast } from '../components/Toast'

const API = '/api/v2'

export default function SpacedRepetitionPage() {
  const [dueCards, setDueCards] = useState([])
  const [stats, setStats] = useState(null)
  const [currentCard, setCurrentCard] = useState(null)
  const [showAnswer, setShowAnswer] = useState(false)
  const [loading, setLoading] = useState(true)
  const [newFront, setNewFront] = useState('')
  const [newBack, setNewBack] = useState('')
  const [subject, setSubject] = useState('general')

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [cardsRes, statsRes] = await Promise.all([
        fetch(`${API}/study/due-cards?limit=20`).then(r => r.json()),
        fetch(`${API}/study/sr-stats`).then(r => r.json()),
      ])
      setDueCards(cardsRes)
      setStats(statsRes)
      if (cardsRes.length > 0) setCurrentCard(cardsRes[0])
    } catch (e) { showToast('Failed to load flashcards', 'error') }
    setLoading(false)
  }

  const addCard = async () => {
    if (!newFront.trim() || !newBack.trim()) return showToast('Fill in both sides', 'error')
    try {
      await fetch(`${API}/study/add-card`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ front: newFront, back: newBack, subject }),
      })
      setNewFront(''); setNewBack('')
      showToast('Card added!', 'success')
      loadData()
    } catch (e) { showToast('Failed to add card', 'error') }
  }

  const reviewCard = async (quality) => {
    if (!currentCard) return
    try {
      await fetch(`${API}/study/review-card`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ card_id: currentCard.id, quality }),
      })
      const remaining = dueCards.filter(c => c.id !== currentCard.id)
      setDueCards(remaining)
      setCurrentCard(remaining[0] || null)
      setShowAnswer(false)
    } catch (e) { showToast('Failed to review card', 'error') }
  }

  const qualityLabels = [
    { q: 0, label: 'Again', color: '#ef4444', desc: 'Complete blackout' },
    { q: 1, label: 'Hard', color: '#f59e0b', desc: 'Wrong, but remembered after seeing answer' },
    { q: 2, label: 'Okay', color: '#f59e0b', desc: 'Wrong, but it was close' },
    { q: 3, label: 'Good', color: '#10b981', desc: 'Correct with hesitation' },
    { q: 4, label: 'Easy', color: '#10b981', desc: 'Correct with some thought' },
    { q: 5, label: 'Perfect', color: '#06b6d4', desc: 'Instant correct response' },
  ]

  return (
    <div className="flex flex-col h-full p-4 gap-4 overflow-y-auto">
      <h1 className="text-xl font-bold text-[#e8e8e8]">Spaced Repetition</h1>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-4 gap-3">
          <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
            <div className="text-xl font-bold text-[#7c6af7]">{stats.total_cards}</div>
            <div className="text-xs text-[#666]">Total Cards</div>
          </div>
          <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
            <div className="text-xl font-bold text-red-400">{stats.due_today}</div>
            <div className="text-xs text-[#666]">Due Today</div>
          </div>
          <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
            <div className="text-xl font-bold text-[#f59e0b]">{stats.learning}</div>
            <div className="text-xs text-[#666]">Learning</div>
          </div>
          <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
            <div className="text-xl font-bold text-[#10b981]">{stats.mastered}</div>
            <div className="text-xs text-[#666]">Mastered</div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-4 flex-1 min-h-0">
        {/* Review area */}
        <div className="col-span-2 flex flex-col gap-3">
          {loading ? (
            <div className="flex-1 flex items-center justify-center text-[#666]">Loading...</div>
          ) : !currentCard ? (
            <div className="flex-1 flex flex-col items-center justify-center text-[#666] gap-2">
              <p className="text-3xl">🎉</p>
              <p>No cards due for review!</p>
              <p className="text-xs text-[#555]">Add cards below or check back later</p>
            </div>
          ) : (
            <>
              <div className="text-xs text-[#666]">{dueCards.length} cards remaining</div>
              <div
                className="flex-1 flex flex-col items-center justify-center p-8 rounded-xl bg-[#1a1a2e] border border-[#2a2a40] cursor-pointer min-h-[300px]"
                onClick={() => setShowAnswer(!showAnswer)}
              >
                <div className="text-xs text-[#555] mb-2">FRONT</div>
                <div className="text-xl text-[#e8e8e8] text-center font-medium">{currentCard.front}</div>
                {showAnswer && (
                  <div className="mt-8 text-center">
                    <div className="text-xs text-[#555] mb-2">BACK</div>
                    <div className="text-lg text-[#06b6d4]">{currentCard.back}</div>
                  </div>
                )}
                {!showAnswer && (
                  <div className="mt-4 text-xs text-[#555]">Click to reveal answer</div>
                )}
              </div>

              {showAnswer && (
                <div className="space-y-2">
                  <div className="text-xs text-[#888] text-center">How well did you know this?</div>
                  <div className="flex gap-2 justify-center">
                    {qualityLabels.map(({ q, label, color, desc }) => (
                      <button
                        key={q}
                        onClick={() => reviewCard(q)}
                        className="px-3 py-2 rounded-lg text-xs font-medium transition-all hover:scale-105"
                        style={{ background: color + '20', color, border: `1px solid ${color}40` }}
                        title={desc}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Add card form */}
        <div className="p-4 rounded-xl bg-[#1a1a2e] border border-[#2a2a40] h-fit">
          <h3 className="text-sm font-semibold text-[#aaa] mb-3">Add New Card</h3>
          <div className="space-y-3">
            <div>
              <label className="block text-xs text-[#666] mb-1">Front (Question)</label>
              <textarea
                value={newFront}
                onChange={(e) => setNewFront(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg bg-[#0f0f0f] border border-[#2a2a40] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7] h-20 resize-none"
                placeholder="What's on the front?"
              />
            </div>
            <div>
              <label className="block text-xs text-[#666] mb-1">Back (Answer)</label>
              <textarea
                value={newBack}
                onChange={(e) => setNewBack(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg bg-[#0f0f0f] border border-[#2a2a40] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7] h-20 resize-none"
                placeholder="What's on the back?"
              />
            </div>
            <div>
              <label className="block text-xs text-[#666] mb-1">Subject</label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg bg-[#0f0f0f] border border-[#2a2a40] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7]"
                placeholder="e.g. mathematics, science..."
              />
            </div>
            <button
              onClick={addCard}
              className="w-full py-2 text-sm rounded-lg bg-[#7c6af7] text-white hover:bg-[#6a59e0] transition-colors"
            >
              Add Card
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
