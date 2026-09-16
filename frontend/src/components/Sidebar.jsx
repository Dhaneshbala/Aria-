import { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useStore } from '../store'
import { deleteConversation, searchConversations } from '../services/api'
import {
  MessageSquare, Settings, Plus, Search, Pin,
  Trash2, Zap, LayoutDashboard, Wand2, X, Repeat, PanelLeft, Mic, Youtube, Sigma, Brain,
} from 'lucide-react'

const NAV = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
  { icon: MessageSquare, label: 'Chat', path: '/chat' },
  { icon: Mic, label: 'Voice Tutor', path: '/voice' },
  { icon: Wand2, label: 'Create', path: '/create' },
  { icon: Sigma, label: 'Maths Accel', path: '/maths' },
  { icon: Repeat, label: 'Review', path: '/spaced' },
  { icon: Zap, label: 'Cheat Sheets', path: '/cheatsheets' },
  { icon: Youtube, label: 'YouTube', path: '/youtube' },
  { icon: Brain, label: 'Memory', path: '/memory' },
]

const BOTTOM_NAV = [
  { icon: Settings, label: 'Settings', path: '/admin' },
]

export default function Sidebar({ collapsed: collapsedProp, onToggle, mobileOpen: mobileOpenProp, setMobileOpen: setMobileOpenProp }) {
  const navigate = useNavigate()
  const location = useLocation()
  const { conversations, pinnedChats, newConversation, togglePin, setConversations, isStreaming } = useStore()
  const [internalCollapsed, setInternalCollapsed] = useState(false)
  const [internalMobileOpen, setInternalMobileOpen] = useState(false)
  const collapsed = collapsedProp !== undefined ? collapsedProp : internalCollapsed
  const mobileOpen = mobileOpenProp !== undefined ? mobileOpenProp : internalMobileOpen
  const setCollapsed = onToggle || setInternalCollapsed
  const setMobileOpen = setMobileOpenProp || setInternalMobileOpen
  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const searchTimer = useRef(null)

  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current)
    if (!search.trim()) {
      setSearchResults(null)
      return
    }
    searchTimer.current = setTimeout(async () => {
      try {
        const results = await searchConversations(search)
        setSearchResults(results)
      } catch {
        setSearchResults(null)
      }
    }, 300)
    return () => clearTimeout(searchTimer.current)
  }, [search])

  const titleFiltered = conversations.filter(c =>
    (c.title || '').toLowerCase().includes(search.toLowerCase())
  )
  const filtered = searchResults || titleFiltered
  const pinned = filtered.filter(c => pinnedChats.includes(c.id))
  const recent = filtered.filter(c => !pinnedChats.includes(c.id))

  const handleDelete = async (e, id) => {
    e.stopPropagation()
    await deleteConversation(id)
    setConversations(conversations.filter(c => c.id !== id))
  }

  const handleNew = () => {
    newConversation()
    navigate('/chat')
    if (window.innerWidth < 768) setMobileOpen(false)
  }

  const isActive = (path) => location.pathname === path || location.pathname.startsWith(path + '/')

  // Gemini collapsed width 68px, open 280px
  const widthClass = collapsed ? 'w-[68px]' : 'w-[280px]'

  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && !collapsed && (
        <div onClick={() => setMobileOpen(false)} className="fixed inset-0 bg-black/50 z-20 md:hidden" />
      )}
      {/* Mobile floating hamburger is now in header, keep overlay only */}
      <div className={`flex flex-col bg-[#1e1f20] md:bg-[#1e1f20] border-r border-[#2d2e30] transition-all duration-200 shrink-0
        ${mobileOpen ? 'fixed inset-y-0 left-0 z-30 flex' : 'hidden md:flex'}
        ${widthClass} ${!mobileOpen && collapsed ? 'hidden md:flex' : ''}`}>
        {/* Header — Gemini style minimal */}
        <div className="flex items-center justify-between h-[64px] px-3 shrink-0">
          {!collapsed ? (
            <button onClick={() => setMobileOpen(false)} className="md:hidden p-2 rounded-full hover:bg-[#2d2e30] text-[#e3e3e3]">
              <X size={20} />
            </button>
          ) : null}
          {!collapsed && <div className="hidden md:block w-8" />}
          <button
            onClick={() => (onToggle ? onToggle() : setInternalCollapsed(v => !v))}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="hidden md:flex p-2 rounded-full hover:bg-[#2d2e30] text-[#9aa0a6] hover:text-[#e3e3e3] transition-colors ml-auto"
          >
            <PanelLeft size={18} />
          </button>
        </div>

        {/* New Chat — Gemini pill */}
        <div className={`px-3 pb-3 ${collapsed ? 'flex justify-center' : ''}`}>
          {!collapsed ? (
            <button
              onClick={handleNew}
              className="flex items-center gap-3 px-4 py-3 rounded-full bg-[#2d2e30] hover:bg-[#35363a] text-[#e3e3e3] text-sm font-medium transition-colors shadow-sm w-fit"
            >
              <span className="w-6 h-6 rounded-full bg-[#1e1f20] flex items-center justify-center">
                <Plus size={14} />
              </span>
              New chat
            </button>
          ) : (
            <button
              onClick={handleNew}
              className="w-10 h-10 rounded-full bg-[#2d2e30] hover:bg-[#35363a] flex items-center justify-center text-[#e3e3e3] shadow-sm"
              title="New chat"
            >
              <Plus size={16} />
            </button>
          )}
        </div>

        {/* Scrollable middle */}
        <div className="flex-1 overflow-y-auto min-h-0">
          {/* Main Nav — rounded-full like Gemini */}
          <nav className={`px-2 py-1 space-y-0.5 ${collapsed ? 'flex flex-col items-center' : ''}`}>
            {NAV.map(({ icon: Icon, label, path }) => (
              <button
                key={path}
                onClick={() => { setMobileOpen(false); navigate(path) }}
                className={`flex items-center gap-3 px-3 py-2 rounded-full text-sm transition-colors relative w-full ${
                  isActive(path)
                    ? 'bg-[#004a77] text-[#c2e7ff]'
                    : 'text-[#e3e3e3] hover:bg-[#2d2e30]'
                } ${collapsed ? 'justify-center w-10 h-10 p-0 rounded-full' : ''}`}
                title={collapsed ? label : undefined}
              >
                <Icon size={18} className="shrink-0" />
                {!collapsed && <span className="truncate">{label}</span>}
                {isStreaming && path === '/chat' && !isActive(path) && !collapsed && (
                  <span className="ml-auto w-2 h-2 rounded-full bg-[#8ab4f8] animate-pulse" title="Working" />
                )}
              </button>
            ))}
          </nav>

          {/* Hint card — Gemini info style */}
          {!collapsed && (
            <div className="mx-3 mt-3 px-3 py-2.5 rounded-xl bg-[#2d2e30] border border-[#35363a]">
              <p className="text-[11px] leading-relaxed text-[#9aa0a6]">
                Ask anything — quiz, flashcards, mind map, essay feedback, worksheet & more. Just chat.
              </p>
            </div>
          )}

          {/* Conversations */}
          {!collapsed && (
            <div className="mt-4">
              <div className="px-3 mb-2">
                <div className="flex items-center gap-2 bg-[#2d2e30] rounded-full px-3 py-2 border border-transparent focus-within:border-[#5f6368] focus-within:bg-[#35363a] transition-colors">
                  <Search size={14} className="text-[#9aa0a6] shrink-0" />
                  <input
                    type="text"
                    placeholder="Search"
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    className="bg-transparent text-sm text-[#e3e3e3] placeholder-[#9aa0a6] flex-1 outline-none min-w-0"
                  />
                </div>
              </div>

              <div className="px-2 space-y-0.5 pb-2">
                {pinned.length > 0 && (
                  <>
                    <p className="text-[11px] font-medium text-[#9aa0a6] tracking-wide px-3 mb-1 mt-2">Pinned</p>
                    {pinned.map(c => <ConvItem key={c.id} c={c} navigate={navigate} togglePin={togglePin} handleDelete={handleDelete} pinned />)}
                  </>
                )}
                {recent.length > 0 && (
                  <>
                    <p className="text-[11px] font-medium text-[#9aa0a6] tracking-wide px-3 mb-1 mt-3">Recent</p>
                    {recent.slice(0, 20).map(c => <ConvItem key={c.id} c={c} navigate={navigate} togglePin={togglePin} handleDelete={handleDelete} />)}
                  </>
                )}
                {filtered.length === 0 && conversations.length === 0 && (
                  <p className="text-xs text-[#5f6368] px-3 py-2">No chats yet</p>
                )}
              </div>
            </div>
          )}

        </div>

        {/* Bottom nav */}
        <div className={`px-2 py-3 border-t border-[#2d2e30] space-y-0.5 ${collapsed ? 'flex flex-col items-center' : ''}`}>
          {BOTTOM_NAV.map(({ icon: Icon, label, path }) => (
            <button
              key={path}
              onClick={() => { setMobileOpen(false); navigate(path) }}
              className={`flex items-center gap-3 px-3 py-2 rounded-full text-sm transition-colors w-full ${
                isActive(path) ? 'bg-[#004a77] text-[#c2e7ff]' : 'text-[#9aa0a6] hover:text-[#e3e3e3] hover:bg-[#2d2e30]'
              } ${collapsed ? 'justify-center w-10 h-10 p-0' : ''}`}
              title={collapsed ? label : undefined}
            >
              <Icon size={18} />
              {!collapsed && label}
            </button>
          ))}
          {!collapsed && (
            <div className="px-3 pt-3 flex items-center gap-2 text-xs text-[#9aa0a6]">
              <div className="w-6 h-6 rounded-full bg-[#35363a] flex items-center justify-center text-[#e3e3e3] text-[10px]">◉</div>
              <span className="truncate">Private · on-device</span>
            </div>
          )}
        </div>
      </div>
    </>
  )
}

function ConvItem({ c, navigate, togglePin, handleDelete, pinned }) {
  return (
    <div
      onClick={() => navigate(`/chat/${c.id}`)}
      role="button"
      tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(`/chat/${c.id}`) } }}
      aria-label={`Open chat ${c.title}`}
      className="group flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-zinc-800 cursor-pointer focus:outline-none focus:ring-1 focus:ring-[#7c6af7]/50"
    >
      <div className="flex-1 min-w-0">
        <span className="text-[13px] leading-none text-[#e3e3e3] truncate block">{c.title}</span>
        {c.snippet && (
          <span className="text-[11px] text-[#9aa0a6] truncate block mt-0.5">{c.snippet}</span>
        )}
      </div>
      <div className="hidden group-hover:flex items-center gap-0.5 shrink-0">
        <button
          onClick={e => { e.stopPropagation(); togglePin(c.id) }}
          className={`p-1.5 rounded-full hover:bg-[#35363a] ${pinned ? 'text-[#8ab4f8]' : 'text-[#9aa0a6] hover:text-[#e3e3e3]'}`}
        >
          <Pin size={12} />
        </button>
        <button
          onClick={e => handleDelete(e, c.id)}
          className="p-1.5 rounded-full hover:bg-[#35363a] text-[#9aa0a6] hover:text-[#f28b82]"
        >
          <Trash2 size={12} />
        </button>
      </div>
    </div>
  )
}
