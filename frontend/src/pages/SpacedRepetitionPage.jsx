import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { showToast } from '../components/Toast'
import { getDueCards, getSrStats, reviewSrCard, addSrCard, deleteSrCard } from '../services/api'
import { getDueMistakes, reviewMistake } from '../services/api'
import { queueReview, flushReviews, setReviewSender, pendingReviewCount } from '../services/offlineQueue'
import { Trash2 } from 'lucide-react'

setReviewSender((card_id, quality) =>
  reviewSrCard(card_id, quality))

export default function SpacedRepetitionPage() {
  const navigate = useNavigate()
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
      const { synced } = await flushReviews(reviewSrCard)
      if (synced > 0) showToast(`Synced ${synced} offline review${synced > 1 ? 's' : ''}`, 'success', 2500)
      const [cards, statsData] = await Promise.all([getDueCards(20), getSrStats()])
      setDueCards(cards)
      setStats(statsData)
      if (cards.length > 0) setCurrentCard(cards[0])
      const pending = await pendingReviewCount()
      if (pending > 0) showToast(`${pending} review${pending > 1 ? 's' : ''} waiting to sync`, 'info', 3000)
    } catch { showToast('Failed to load flashcards', 'error') }
    setLoading(false)
  }

  const addCard = async () => {
    if (!newFront.trim() || !newBack.trim()) return showToast('Fill in both sides', 'error')
    try {
      await addSrCard(newFront, newBack, subject)
      setNewFront(''); setNewBack('')
      showToast('Card added!', 'success')
      loadData()
    } catch { showToast('Failed to add card', 'error') }
  }

  const reviewCard = async (quality) => {
    if (!currentCard) return
    const advance = () => {
      const remaining = dueCards.filter(c => c.id !== currentCard.id)
      setDueCards(remaining)
      setCurrentCard(remaining[0] || null)
      setShowAnswer(false)
    }
    try {
      await reviewSrCard(currentCard.id, quality)
      advance()
    } catch (e) {
      if (e instanceof TypeError) {
        // Network down — queue in IndexedDB, advance anyway, sync later
        await queueReview(currentCard.id, quality)
        advance()
        showToast('Saved offline — will sync when connected', 'info', 3000)
      } else {
        showToast('Failed to review card', 'error')
      }
    }
  }

  const deleteCard = async (cardId) => {
    try {
      await deleteSrCard(cardId)
      const remaining = dueCards.filter(c => c.id !== cardId)
      setDueCards(remaining)
      if (currentCard?.id === cardId) setCurrentCard(remaining[0] || null)
      showToast('Card deleted', 'success')
    } catch { showToast('Failed to delete card', 'error') }
  }

  const qualityLabels = [
    { q: 0, label: 'Again', color: '#ef4444', desc: 'Complete blackout' },
    { q: 1, label: 'Hard', color: '#f59e0b', desc: 'Wrong, but remembered after seeing answer' },
    { q: 2, label: 'Okay', color: '#f59e0b', desc: 'Wrong, but it was close' },
    { q: 3, label: 'Good', color: '#10b981', desc: 'Correct with hesitation' },
    { q: 4, label: 'Easy', color: '#10b981', desc: 'Correct with some thought' },
    { q: 5, label: 'Perfect', color: '#06b6d4', desc: 'Instant correct response' },
  ]

  // Keyboard review: Space reveals the answer, digits 0–5 grade (Anki-style).
  useEffect(() => {
    const handler = (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const t = e.target
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
      if (!currentCard) return
      if (!showAnswer) {
        if (e.key === ' ') { e.preventDefault(); setShowAnswer(true) }
        return
      }
      const digit = Number.parseInt(e.key, 10)
      if (Number.isInteger(digit) && digit >= 0 && digit <= 5) {
        e.preventDefault()
        reviewCard(digit)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [currentCard, showAnswer, reviewCard])

  return (
    <div className="flex flex-col h-full w-full p-4 gap-4 overflow-y-auto">
      <h1 className="text-xl font-bold text-[#e8e8e8]">Spaced Repetition</h1>

      <MistakeDrill />

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
            <div className="text-xl font-bold text-[#7c6af7]">{stats.total_cards}</div>
            <div className="text-xs text-[#888]">Total Cards</div>
          </div>
          <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
            <div className="text-xl font-bold text-red-400">{stats.due_today}</div>
            <div className="text-xs text-[#888]">Due Today</div>
          </div>
          <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
            <div className="text-xl font-bold text-[#f59e0b]">{stats.learning}</div>
            <div className="text-xs text-[#888]">Learning</div>
          </div>
          <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
            <div className="text-xl font-bold text-[#10b981]">{stats.mastered}</div>
            <div className="text-xs text-[#888]">Mastered</div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1 min-h-0">
        {/* Review area */}
        <div className="col-span-1 lg:col-span-2 flex flex-col gap-3">
          {loading ? (
            <div className="flex-1 flex items-center justify-center text-[#888]">Loading...</div>
          ) : (stats?.total_cards || 0) === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-[#888] gap-2 px-6 text-center">
              <p className="text-3xl">🃏</p>
              <p className="text-[#e8e8e8] font-medium">No flashcards yet</p>
              <p className="text-xs text-[#888]">Create your first set — ARIA will schedule reviews for you</p>
              <div className="flex gap-2 mt-2">
                <button onClick={() => navigate('/create')}
                  className="px-4 py-2 rounded-xl bg-[#7c6af7] text-white text-xs font-medium hover:bg-[#6a59e0] transition-colors">
                  Create flashcards
                </button>
                <button onClick={() => navigate('/chat')}
                  className="px-4 py-2 rounded-xl bg-[#1a1a2e] border border-[#2a2a40] text-xs text-[#888] hover:text-[#e8e8e8] transition-colors">
                  Ask in chat
                </button>
              </div>
            </div>
          ) : !currentCard ? (
            <div className="flex-1 flex flex-col items-center justify-center text-[#888] gap-2">
              <p className="text-3xl">🎉</p>
              <p>No cards due for review!</p>
              <p className="text-xs text-[#888]">Add cards below or check back later</p>
            </div>
          ) : currentCard ? (
            <>
              <div className="text-xs text-[#888]">{dueCards.length} cards remaining</div>
              <div
                className="flex-1 flex flex-col items-center justify-center p-8 rounded-xl bg-[#1a1a2e] border border-[#2a2a40] cursor-pointer min-h-[300px] relative group"
                onClick={() => setShowAnswer(!showAnswer)}
                role="button"
                tabIndex={0}
                onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setShowAnswer(s => !s) } }}
                aria-label="Review card — press Enter or Space to reveal the answer"
              >
                <button onClick={(e) => { e.stopPropagation(); deleteCard(currentCard.id) }}
                  className="absolute top-3 right-3 p-1.5 rounded-lg opacity-0 group-hover:opacity-100 bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-all"
                  title="Delete card">
                  <Trash2 size={14} />
                </button>
                <div className="text-xs text-[#888] mb-2">FRONT</div>
                <div className="text-xl text-[#e8e8e8] text-center font-medium">{currentCard.front}</div>
                {showAnswer && (
                  <div className="mt-8 text-center">
                    <div className="text-xs text-[#888] mb-2">BACK</div>
                    <div className="text-lg text-[#06b6d4]">{currentCard.back}</div>
                  </div>
                )}
                {!showAnswer && (
                  <div className="mt-4 text-xs text-[#888]">Click or press Space to reveal the answer</div>
                )}
              </div>

                {showAnswer && (
                <div className="space-y-2">
                  <div className="text-xs text-[#888] text-center">How well did you know this? <span className="text-[#5f6368]">· keys 0–5</span></div>
                  <div className="flex gap-2 justify-center flex-wrap">
                    {qualityLabels.map(({ q, label, color, desc }) => (
                      <button
                        key={q}
                        onClick={() => reviewCard(q)}
                        className="px-3 py-2 rounded-lg text-xs font-medium transition-all hover:scale-105"
                        style={{ background: color + '20', color, border: `1px solid ${color}40` }}
                        title={`${desc} (key: ${q})`}
                      >
                        <span className="opacity-60 mr-1">{q}</span>{label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </>
            ) : null
          }
        </div>

        {/* Add card form */}
        <div className="p-4 rounded-xl bg-[#1a1a2e] border border-[#2a2a40] h-fit">
          <h3 className="text-sm font-semibold text-[#aaa] mb-3">Add New Card</h3>
          <div className="space-y-3">
            <div>
              <label htmlFor="sr-front" className="block text-xs text-[#888] mb-1">Front (Question)</label>
              <textarea
                id="sr-front"
                value={newFront}
                onChange={(e) => setNewFront(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg bg-[#0f0f0f] border border-[#2a2a40] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7] h-20 resize-none"
                placeholder="What's on the front?"
              />
            </div>
            <div>
              <label htmlFor="sr-back" className="block text-xs text-[#888] mb-1">Back (Answer)</label>
              <textarea
                id="sr-back"
                value={newBack}
                onChange={(e) => setNewBack(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg bg-[#0f0f0f] border border-[#2a2a40] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7] h-20 resize-none"
                placeholder="What's on the back?"
              />
            </div>
            <div>
              <label htmlFor="sr-subject" className="block text-xs text-[#888] mb-1">Subject</label>
              <input
                type="text"
                id="sr-subject"
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

/**
 * MistakeDrill — every wrong quiz/maths answer lands here automatically.
 * Grade Got it / Missed; 3 in a row retires the item.
 */
function MistakeDrill() {
  const [items, setItems] = useState([])
  const [idx, setIdx] = useState(0)
  const [reveal, setReveal] = useState(false)
  const [stats, setStats] = useState(null)
  const [loaded, setLoaded] = useState(false)

  const load = async () => {
    try {
      const d = await getDueMistakes(20)
      setItems(d.mistakes || [])
      setStats(d.stats || null)
      setIdx(0)
      setReveal(false)
    } catch (e) {
      console.warn('mistake load failed', e)
    }
    setLoaded(true)
  }

  useEffect(() => { load() }, [])

  const grade = async (correct) => {
    const item = items[idx]
    if (!item) return
    try {
      const r = await reviewMistake(item.id, correct)
      setStats(r.stats || stats)
    } catch (e) {
      console.warn('mistake review failed', e)
    }
    // Correct → item leaves the queue view (streak saved server-side);
    // missed → rotate to the next item, this one comes back around.
    if (correct) {
      const next = items.filter(m => m.id !== item.id)
      setItems(next)
      if (idx >= next.length) setIdx(0)
    } else if (items.length > 1) {
      setIdx((idx + 1) % items.length)
    }
    setReveal(false)
  }

  if (!loaded) return null
  if (items.length === 0) {
    return (
      <div className="p-4 rounded-xl bg-[#1a1a2e] border border-[#2a2a40] flex items-center gap-3">
        <span className="text-2xl">🎯</span>
        <div>
          <p className="text-sm font-medium text-[#e8e8e8]">
            Mistake book {stats?.mastered ? `· ${stats.mastered} retired` : 'is empty'}
          </p>
          <p className="text-xs text-[#888]">
            {stats?.mastered
              ? 'Wrong answers land here automatically — drill them 3x to retire.'
              : 'Get a quiz question wrong and it lands here for drilling.'}
          </p>
        </div>
        <button onClick={load} aria-label="Refresh mistake book"
          className="ml-auto text-xs text-[#888] hover:text-[#e8e8e8] px-2 py-1">
          Refresh
        </button>
      </div>
    )
  }

  const item = items[Math.min(idx, items.length - 1)]
  return (
    <div className="p-4 rounded-xl bg-[#1a1a2e] border border-red-500/20">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-semibold text-red-400 uppercase tracking-wide">
          🎯 Mistake drill
        </span>
        <span className="text-[10px] text-[#888]">
          {item.subject}{item.topic ? ` · ${item.topic}` : ''} · missed {item.times_missed}x · streak {item.streak}/3
        </span>
        <span className="ml-auto text-[10px] text-[#888]">{items.length} left</span>
      </div>
      <p className="text-sm text-[#e8e8e8] leading-relaxed">{item.question}</p>
      {!reveal ? (
        <button onClick={() => setReveal(true)}
          className="mt-3 px-4 py-2 rounded-xl bg-[#2a2a40] text-xs text-[#e8e8e8] hover:bg-[#35355a] transition-colors">
          Reveal answer
        </button>
      ) : (
        <div className="mt-3">
          <p className="text-sm text-green-400 font-medium">{item.correct_answer || '(answer not recorded)'}</p>
          <div className="flex gap-2 mt-2">
            <button onClick={() => grade(false)}
              className="flex-1 py-2 rounded-xl bg-red-500/15 border border-red-500/30 text-xs text-red-300 hover:bg-red-500/25 transition-colors">
              Missed again
            </button>
            <button onClick={() => grade(true)}
              className="flex-1 py-2 rounded-xl bg-green-500/15 border border-green-500/30 text-xs text-green-300 hover:bg-green-500/25 transition-colors">
              Got it
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
