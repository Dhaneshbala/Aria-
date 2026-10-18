import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  getMemoryConversations, searchMemoryConversations, getMemoryConversation,
  deleteMemoryConversation, getMemoryProfile
} from '../services/api'
import { showToast } from '../components/Toast'
import { Search, Trash2, MessageSquare, Brain, ChevronRight, X, Loader } from 'lucide-react'

export default function MemoryPage() {
  const navigate = useNavigate()
  const [conversations, setConversations] = useState([])
  const [profile, setProfile] = useState(null)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [selectedTurns, setSelectedTurns] = useState([])
  const [loadingTurns, setLoadingTurns] = useState(false)

  const load = async () => {
    try {
      const [convs, prof] = await Promise.all([
        getMemoryConversations().catch((e) => { console.warn('memory convs failed', e); showToast("Couldn't load memories", 'error', 2500); return [] }),
        getMemoryProfile().catch((e) => { console.warn('memory profile failed', e); return null }),
      ])
      setConversations(Array.isArray(convs) ? convs : [])
      setProfile(prof)
    } catch {} finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const handleSearch = async (q) => {
    setSearch(q)
    if (!q.trim()) { load(); return }
    try {
      const results = await searchMemoryConversations(q)
      setConversations(Array.isArray(results) ? results : [])
    } catch { showToast("Couldn't search memories", 'error', 2500) }
  }

  const openConversation = async (conv) => {
    setSelected(conv)
    setLoadingTurns(true)
    try {
      const turns = await getMemoryConversation(conv.id || conv.conversation_id)
      setSelectedTurns(Array.isArray(turns) ? turns : [])
    } catch { setSelectedTurns([]); showToast("Couldn't load conversation", 'error', 2500) }
    setLoadingTurns(false)
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this conversation?')) return
    try {
      await deleteMemoryConversation(id)
      setConversations(prev => prev.filter(c => (c.id || c.conversation_id) !== id))
      if (selected?.id === id || selected?.conversation_id === id) { setSelected(null); setSelectedTurns([]) }
      showToast('Conversation deleted', 'success', 2500)
    } catch { showToast('Delete failed', 'error') }
  }

  const goChat = (convId) => {
    navigate(`/chat/${convId}`)
  }

  const subjects = profile?.subjects || {}
  const totalQ = profile?.total_questions || 0
  const correct = profile?.correct_answers || 0
  const accuracy = totalQ > 0 ? Math.round((correct / totalQ) * 100) : 0

  return (
    <div className="flex h-full w-full bg-aria-bg">
      {/* Sidebar: conversation list */}
      <div className={`${selected ? 'hidden md:flex' : 'flex'} flex-col w-full md:w-80 lg:w-96 border-r border-aria-border shrink-0`}>
        <div className="p-4 border-b border-aria-border">
          <div className="flex items-center gap-2 mb-3">
            <Brain size={18} className="text-[#8ab4f8]" />
            <h1 className="text-lg font-semibold text-aria-text">Memory</h1>
            <span className="text-xs text-aria-muted ml-auto">{conversations.length} conversations</span>
          </div>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-aria-muted" />
            <input value={search} onChange={e => handleSearch(e.target.value)}
              placeholder="Search memories…"
              className="w-full pl-9 pr-3 py-2 bg-aria-surface border border-aria-border rounded-xl text-sm text-aria-text placeholder-[#5f6368] outline-none focus:border-[#8ab4f8]" />
          </div>
        </div>

        {/* Profile summary */}
        {profile && totalQ > 0 && (
          <div className="px-4 py-3 border-b border-aria-border bg-[#1a1b1c]">
            <div className="flex items-center gap-3 text-xs">
              <span className="text-aria-muted">Study profile:</span>
              <span className="text-aria-text">{totalQ} questions</span>
              <span className="text-[#8ab4f8]">{accuracy}% accuracy</span>
            </div>
            {Object.keys(subjects).length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {Object.entries(subjects).slice(0, 6).map(([subj, data]) => {
                  const acc = data.total > 0 ? Math.round((data.correct / data.total) * 100) : 0
                  return (
                    <span key={subj} className="text-[10px] px-2 py-0.5 rounded-full bg-[#2d2e30] text-aria-muted">
                      {subj} {acc}%
                    </span>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* Conversation list */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader size={18} className="text-aria-muted animate-spin" />
            </div>
          ) : conversations.length === 0 ? (
            <div className="text-center py-12 px-4">
              <MessageSquare size={32} className="text-[#2d2e30] mx-auto mb-2" />
              <p className="text-sm text-aria-muted">{search ? 'No matches' : 'No conversations yet'}</p>
            </div>
          ) : (
            conversations.map(conv => {
              const id = conv.id || conv.conversation_id
              const isActive = selected?.id === id || selected?.conversation_id === id
              return (
                <div key={id}
                  onClick={() => openConversation(conv)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openConversation(conv) } }}
                  aria-label={`Open conversation ${conv.title || id}`}
                  className={`group flex items-start gap-3 px-4 py-3 cursor-pointer border-b border-[#1e1f20] transition-colors ${
                    isActive ? 'bg-[#8ab4f8]/8 border-l-2 border-l-[#8ab4f8]' : 'hover:bg-aria-surface'
                  }`}>
                  <MessageSquare size={14} className="text-aria-muted mt-0.5 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-aria-text truncate">{conv.title || 'Untitled conversation'}</p>
                    <p className="text-[10px] text-aria-muted mt-0.5">
                      {conv.turns || conv.turn_count || '?'} turns
                      {conv.last_active ? ` · ${new Date(conv.last_active).toLocaleDateString()}` : ''}
                    </p>
                  </div>
                  <button onClick={e => { e.stopPropagation(); handleDelete(id) }}
                    className="p-1 rounded-full opacity-0 group-hover:opacity-100 hover:bg-red-500/20 text-aria-muted hover:text-red-400 transition-all shrink-0">
                    <Trash2 size={12} />
                  </button>
                </div>
              )
            })
          )}
        </div>
      </div>

      {/* Main: conversation detail */}
      <div className={`${selected ? 'flex' : 'hidden md:flex'} flex-1 flex-col min-w-0`}>
        {selected ? (
          <>
            <div className="flex items-center gap-3 px-4 py-3 border-b border-aria-border">
              <button onClick={() => { setSelected(null); setSelectedTurns([]) }}
                className="md:hidden p-1.5 rounded-full hover:bg-[#2d2e30] text-aria-muted">
                <X size={16} />
              </button>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-aria-text truncate">{selected.title || 'Untitled'}</p>
                <p className="text-[10px] text-aria-muted">{selectedTurns.length} turns</p>
              </div>
              <button onClick={() => goChat(selected.id || selected.conversation_id)}
                className="text-xs px-3 py-1.5 rounded-full bg-[#8ab4f8]/15 text-[#8ab4f8] hover:bg-[#8ab4f8]/25 transition-colors flex items-center gap-1">
                Continue in chat <ChevronRight size={12} />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {loadingTurns ? (
                <div className="flex items-center justify-center py-12">
                  <Loader size={18} className="text-aria-muted animate-spin" />
                </div>
              ) : selectedTurns.map((turn, i) => (
                <div key={i} className="space-y-2">
                  {turn.user && (
                    <div className="flex justify-end">
                      <div className="max-w-[80%] px-4 py-2.5 rounded-2xl rounded-tr-sm bg-[#8ab4f8]/10 border border-[#8ab4f8]/20 text-sm text-aria-text">
                        {turn.user}
                      </div>
                    </div>
                  )}
                  {turn.ai && (
                    <div className="flex justify-start">
                      <div className="max-w-[80%] px-4 py-2.5 rounded-2xl rounded-tl-sm bg-aria-surface border border-aria-border text-sm text-aria-muted whitespace-pre-wrap">
                        {turn.ai.slice(0, 500)}{turn.ai.length > 500 ? '…' : ''}
                      </div>
                    </div>
                  )}
                  {turn.timestamp && (
                    <p className="text-[9px] text-[#3c4043] text-center">{new Date(turn.timestamp).toLocaleString()}</p>
                  )}
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <Brain size={48} className="text-[#2d2e30] mx-auto mb-3" />
              <p className="text-sm text-aria-muted">Select a conversation to browse</p>
              <p className="text-xs text-[#3c4043] mt-1">ARIA remembers everything you've discussed</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
