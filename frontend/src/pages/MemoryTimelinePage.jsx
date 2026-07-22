import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  getMemoryTimeline, compressMemory, cleanupMemory, globalMemorySearch,
  getAdaptiveRecommendations, getConversationsForDate, deleteConversation
} from '../services/api'
import { showToast } from '../components/Toast'

export default function MemoryTimelinePage() {
  const navigate = useNavigate()
  const [timeline, setTimeline] = useState([])
  const [recommendations, setRecommendations] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [days, setDays] = useState(30)
  const [loading, setLoading] = useState(true)
  const [compressing, setCompressing] = useState(false)
  const [cleaning, setCleaning] = useState(false)
  const [expandedDay, setExpandedDay] = useState(null)
  const [dayConversations, setDayConversations] = useState([])
  const [loadingDay, setLoadingDay] = useState(false)
  const [expandedConv, setExpandedConv] = useState(null)

  useEffect(() => { loadTimeline() }, [days])

  const loadTimeline = async () => {
    setLoading(true)
    try {
      const [tl, recs] = await Promise.all([
        getMemoryTimeline(days),
        getAdaptiveRecommendations().catch(() => null),
      ])
      setTimeline(tl)
      setRecommendations(recs)
    } catch (e) {
      showToast('Failed to load timeline', 'error')
    }
    setLoading(false)
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) { setSearchResults([]); return }
    try {
      const results = await globalMemorySearch(searchQuery)
      setSearchResults(results)
    } catch (e) {
      showToast('Search failed', 'error')
    }
  }

  const handleCompress = async () => {
    setCompressing(true)
    try {
      const result = await compressMemory(7)
      showToast(`Compressed ${result.compressed_count} conversations`, 'success')
    } catch (e) {
      showToast('Compression failed', 'error')
    }
    setCompressing(false)
  }

  const handleCleanup = async () => {
    if (!confirm('Remove conversations older than 90 days? This cannot be undone.')) return
    setCleaning(true)
    try {
      const result = await cleanupMemory(90)
      showToast(`Removed ${result.removed_conversations} old conversations`, 'success')
    } catch (e) {
      showToast('Cleanup failed', 'error')
    }
    setCleaning(false)
  }

  const toggleDay = async (date) => {
    if (expandedDay === date) {
      setExpandedDay(null)
      setDayConversations([])
      return
    }
    setExpandedDay(date)
    setLoadingDay(true)
    setExpandedConv(null)
    try {
      const convs = await getConversationsForDate(date)
      setDayConversations(convs)
    } catch (e) {
      showToast('Failed to load conversations', 'error')
    }
    setLoadingDay(false)
  }

  const handleDelete = async (convId, e) => {
    e.stopPropagation()
    if (!confirm('Delete this conversation? This cannot be undone.')) return
    try {
      await deleteConversation(convId)
      setDayConversations(prev => prev.filter(c => c.id !== convId))
      showToast('Conversation deleted', 'success')
      loadTimeline()
    } catch (e) {
      showToast('Delete failed', 'error')
    }
  }

  const totalTurns = timeline.reduce((sum, d) => sum + (d.turns || 0), 0)
  const maxTurns = Math.max(...timeline.map(d => d.turns || 0), 1)

  return (
    <div className="flex flex-col h-full p-4 gap-4 overflow-y-auto">
      <h1 className="text-xl font-bold text-[#e8e8e8]">Memory Timeline</h1>

      {/* Global Search */}
      <div className="flex gap-2">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="Search across all conversations by meaning..."
          className="flex-1 px-3 py-2 text-sm rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7]"
        />
        <button onClick={handleSearch} className="px-4 py-2 text-sm rounded-lg bg-[#7c6af7] text-white hover:bg-[#6a59e0] transition-colors">
          Search
        </button>
      </div>

      {/* Search Results */}
      {searchResults.length > 0 && (
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {searchResults.map((r, i) => (
            <div key={i} className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
              <div className="text-xs text-[#888] mb-1">
                Conversation: {r.conversation_id?.slice(0, 8)}... · {r.timestamp?.slice(0, 10)}
              </div>
              <div className="text-sm text-[#e8e8e8]">{r.text}</div>
            </div>
          ))}
        </div>
      )}

      {/* Adaptive Recommendations */}
      {recommendations && recommendations.recommendations?.length > 0 && (
        <div className="p-4 rounded-xl bg-gradient-to-r from-[#7c6af7]/10 to-[#06b6d4]/10 border border-[#7c6af7]/30">
          <h3 className="text-sm font-semibold text-[#7c6af7] mb-2">AI Recommendations</h3>
          <div className="space-y-2">
            {recommendations.recommendations.map((rec, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                <span className="text-[#06b6d4]">
                  {rec.type === 'focus_area' ? '⚠️' : rec.type === 'strength' ? '💪' : rec.type === 'revision' ? '🔄' : '📊'}
                </span>
                <span className="text-[#ccc]">{rec.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="flex items-center gap-3">
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="px-3 py-1.5 text-xs rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8]"
        >
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
          <option value={365}>Last year</option>
        </select>
        <button onClick={handleCompress} disabled={compressing} className="px-3 py-1.5 text-xs rounded-lg bg-[#1a1a2e] text-[#06b6d4] hover:bg-[#252540] transition-colors disabled:opacity-50">
          {compressing ? 'Compressing...' : 'Compress Old'}
        </button>
        <button onClick={handleCleanup} disabled={cleaning} className="px-3 py-1.5 text-xs rounded-lg bg-red-900/30 text-red-400 hover:bg-red-900/50 transition-colors disabled:opacity-50">
          {cleaning ? 'Cleaning...' : 'Cleanup Old'}
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
          <div className="text-xl font-bold text-[#7c6af7]">{timeline.length}</div>
          <div className="text-xs text-[#666]">Active Days</div>
        </div>
        <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
          <div className="text-xl font-bold text-[#06b6d4]">{totalTurns}</div>
          <div className="text-xs text-[#666]">Total Turns</div>
        </div>
        <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
          <div className="text-xl font-bold text-[#10b981]">{maxTurns}</div>
          <div className="text-xs text-[#666]">Busiest Day</div>
        </div>
      </div>

      {/* Timeline */}
      {loading ? (
        <div className="flex-1 flex items-center justify-center text-[#666]">Loading...</div>
      ) : timeline.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-[#666] gap-2">
          <p className="text-3xl">📊</p>
          <p>No activity data yet</p>
          <p className="text-xs text-[#555]">Start chatting to build your learning timeline</p>
        </div>
      ) : (
        <div className="space-y-1">
          {timeline.map((day, i) => (
            <div key={i} className="rounded-xl bg-[#1a1a2e] border border-[#2a2a40] overflow-hidden">
              {/* Day header — clickable */}
              <button
                onClick={() => toggleDay(day.date)}
                className={`w-full flex items-start gap-3 p-3 text-left transition-colors ${
                  expandedDay === day.date ? 'bg-[#252540]' : 'hover:bg-[#1f1f35]'
                }`}
              >
                <div className="flex flex-col items-center min-w-[60px]">
                  <div className="text-xs text-[#888]">{day.date?.slice(5)}</div>
                  <div
                    className="mt-1 rounded-full bg-[#7c6af7]"
                    style={{
                      width: 12,
                      height: 12,
                      opacity: 0.3 + (day.turns / maxTurns) * 0.7,
                    }}
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-[#e8e8e8]">
                      {new Date(day.date + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
                    </span>
                    <span className="text-xs text-[#7c6af7]">{day.turns} turns</span>
                    <span className="text-xs text-[#666]">· {day.conversations} conv{day.conversations !== 1 ? 's' : ''}</span>
                  </div>
                  {day.topics && day.topics.length > 0 && expandedDay !== day.date && (
                    <div className="flex flex-wrap gap-1">
                      {day.topics.slice(0, 3).map((t, j) => (
                        <span key={j} className="text-xs px-2 py-0.5 rounded-full bg-[#252540] text-[#888] truncate max-w-[200px]">
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-16 h-2 rounded-full bg-[#252540] mt-2">
                    <div
                      className="h-full rounded-full bg-[#7c6af7]"
                      style={{ width: `${(day.turns / maxTurns) * 100}%` }}
                    />
                  </div>
                  <svg
                    className={`w-4 h-4 text-[#666] transition-transform ${expandedDay === day.date ? 'rotate-180' : ''}`}
                    fill="none" viewBox="0 0 24 24" stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </button>

              {/* Expanded: conversation list */}
              {expandedDay === day.date && (
                <div className="border-t border-[#2a2a40] px-3 pb-3">
                  {loadingDay ? (
                    <div className="py-4 text-center text-[#666] text-sm">Loading conversations...</div>
                  ) : dayConversations.length === 0 ? (
                    <div className="py-4 text-center text-[#666] text-sm">No conversations found</div>
                  ) : (
                    <div className="space-y-2 pt-2">
                      {dayConversations.map((conv) => (
                        <div key={conv.id} className="rounded-lg bg-[#0f0f0f] border border-[#2a2a40] overflow-hidden">
                          {/* Conversation header */}
                          <button
                            onClick={() => setExpandedConv(expandedConv === conv.id ? null : conv.id)}
                            className="w-full flex items-center gap-3 p-3 text-left hover:bg-[#1a1a2e] transition-colors"
                          >
                            <div className="flex-1 min-w-0">
                              <div className="text-sm text-[#e8e8e8] truncate">{conv.title}</div>
                              <div className="text-xs text-[#666] mt-0.5">
                                {conv.turn_count} turn{conv.turn_count !== 1 ? 's' : ''} · {conv.id.slice(0, 8)}...
                              </div>
                            </div>
                            <div className="flex items-center gap-1">
                              <button
                                onClick={(e) => navigate(`/chat/${conv.id}`)}
                                className="px-2 py-1 text-xs rounded-md bg-[#7c6af7]/20 text-[#7c6af7] hover:bg-[#7c6af7]/30 transition-colors"
                                title="Open in chat"
                              >
                                Open
                              </button>
                              <button
                                onClick={(e) => handleDelete(conv.id, e)}
                                className="px-2 py-1 text-xs rounded-md bg-red-900/20 text-red-400 hover:bg-red-900/40 transition-colors"
                                title="Delete conversation"
                              >
                                Delete
                              </button>
                              <svg
                                className={`w-4 h-4 text-[#666] transition-transform ${expandedConv === conv.id ? 'rotate-180' : ''}`}
                                fill="none" viewBox="0 0 24 24" stroke="currentColor"
                              >
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                              </svg>
                            </div>
                          </button>

                          {/* Expanded: show turns */}
                          {expandedConv === conv.id && (
                            <div className="border-t border-[#2a2a40] px-3 pb-3 space-y-2 pt-2">
                              {conv.turns.map((turn, ti) => (
                                <div key={ti} className="space-y-1">
                                  {turn.user && (
                                    <div className="flex gap-2">
                                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#7c6af7]/20 text-[#7c6af7] shrink-0 mt-0.5">You</span>
                                      <span className="text-xs text-[#ccc] break-words">{turn.user}</span>
                                    </div>
                                  )}
                                  {turn.ai && (
                                    <div className="flex gap-2">
                                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#06b6d4]/20 text-[#06b6d4] shrink-0 mt-0.5">AI</span>
                                      <span className="text-xs text-[#aaa] break-words">{turn.ai.slice(0, 300)}{turn.ai.length > 300 ? '...' : ''}</span>
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
