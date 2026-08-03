import { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useStore } from '../store'
import { deleteConversation, searchConversations, getNotifications } from '../services/api'
import {
  MessageSquare, BookOpen, CreditCard, Network, Calendar,
  Youtube, Image, FileText, Presentation, User, Settings, Plus, Search, Pin,
  Trash2, ChevronLeft, ChevronRight, Zap, Code, Wrench,
  Brain, Clock, BarChart3, Trophy, GraduationCap, Repeat, Scissors, ListTodo, LayoutDashboard,
  Database, Bell, Timer
} from 'lucide-react'

const NAV = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/dashboard' },
  { icon: MessageSquare, label: 'Chat', path: '/chat' },
  { icon: Code, label: 'Coding', path: '/coding' },
  { icon: BookOpen, label: 'Quiz', path: '/quiz' },
  { icon: CreditCard, label: 'Flashcards', path: '/flashcards' },
  { icon: Repeat, label: 'Spaced Rep', path: '/spaced-repetition' },
  { icon: Network, label: 'Mind Map', path: '/mindmap' },
  { icon: ListTodo, label: 'AI Planner', path: '/ai-planner' },
  { icon: Wrench, label: 'Study Tools', path: '/study-tools' },
  { icon: Timer, label: 'Focus Mode', path: '/focus' },
  { icon: Presentation, label: 'PowerPoint', path: '/pptx' },
  { icon: Youtube, label: 'YouTube', path: '/youtube' },
  { icon: FileText, label: 'Documents', path: '/docs' },
  { icon: Image, label: 'Image Gen', path: '/imagegen' },
]

const INTEL_NAV = [
  { icon: Brain, label: 'Knowledge Graph', path: '/knowledge-graph' },
  { icon: Clock, label: 'Memory Timeline', path: '/memory-timeline' },
  { icon: Database, label: 'Knowledge Base', path: '/knowledge-base' },
  { icon: BarChart3, label: 'Analytics', path: '/analytics' },
  { icon: Trophy, label: 'Achievements', path: '/achievements' },
  { icon: GraduationCap, label: 'Curriculum', path: '/curriculum' },
]

const BOTTOM_NAV = [
  { icon: User, label: 'Profile', path: '/profile' },
  { icon: Settings, label: 'Admin', path: '/admin' },
]

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { conversations, pinnedChats, newConversation, togglePin, setConversations } = useStore()
  const [collapsed, setCollapsed] = useState(false)
  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const searchTimer = useRef(null)
  const [notifs, setNotifs] = useState([])
  const [notifOpen, setNotifOpen] = useState(false)
  const notifRef = useRef(null)

  // Poll smart notifications every 60s
  useEffect(() => {
    const fetchNotifs = async () => {
      try {
        const data = await getNotifications()
        setNotifs(data.notifications || [])
      } catch {}
    }
    fetchNotifs()
    const timer = setInterval(fetchNotifs, 60000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    const onClick = (e) => {
      if (notifRef.current && !notifRef.current.contains(e.target)) setNotifOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  const openNotif = (n) => {
    setNotifOpen(false)
    navigate(n.type === 'flashcards' ? '/spaced-repetition' : '/ai-planner')
  }

  // Debounced content search
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

  // Title-only filter (fast, instant)
  const titleFiltered = conversations.filter(c =>
    c.title.toLowerCase().includes(search.toLowerCase())
  )
  // Use content search results if available, otherwise title filter
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
  }

  const isActive = (path) => location.pathname === path || location.pathname.startsWith(path + '/')

  return (
    <div className={`flex flex-col bg-[#141414] border-r border-[#2a2a2a] transition-all duration-200 ${collapsed ? 'w-14' : 'w-64'}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-[#2a2a2a]">
        {!collapsed && (
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[#7c6af7] to-[#4f46e5] flex items-center justify-center">
              <Zap size={14} className="text-white" />
            </div>
            <span className="font-semibold text-[#e8e8e8]">ARIA</span>
          </div>
        )}
        <div className="flex items-center gap-1" ref={notifRef}>
          {/* Notifications bell */}
          <div className="relative">
            <button
              onClick={() => setNotifOpen(!notifOpen)}
              className="relative p-1.5 rounded-md hover:bg-[#2a2a2a] text-[#888] hover:text-[#e8e8e8] transition-colors"
              title="Notifications"
            >
              <Bell size={15} />
              {notifs.length > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-4 h-4 px-1 rounded-full bg-red-500 text-white text-[8px] font-bold flex items-center justify-center">
                  {notifs.length > 9 ? '9+' : notifs.length}
                </span>
              )}
            </button>
            {notifOpen && (
              <div className="absolute left-0 top-full mt-1.5 w-72 bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl shadow-2xl z-50 overflow-hidden">
                <div className="flex items-center justify-between px-3 py-2 border-b border-[#2a2a2a]">
                  <span className="text-xs font-medium text-[#e8e8e8]">Notifications</span>
                  <button onClick={() => setNotifs([])} className="text-[9px] text-[#555] hover:text-[#aaa] transition-colors">
                    Clear
                  </button>
                </div>
                <div className="max-h-80 overflow-y-auto">
                  {notifs.length === 0 ? (
                    <p className="text-xs text-[#555] text-center py-6">All caught up — no reminders</p>
                  ) : (
                    notifs.map((n, i) => (
                      <button key={i} onClick={() => openNotif(n)}
                        className={`w-full text-left px-3 py-2.5 border-b border-[#141414] hover:bg-[#222] transition-colors ${
                          n.severity === 'high' ? 'border-l-2 border-l-red-500' :
                          n.severity === 'medium' ? 'border-l-2 border-l-[#f59e0b]' : 'border-l-2 border-l-[#7c6af7]'
                        }`}>
                        <p className="text-xs text-[#e8e8e8] font-medium">{n.title}</p>
                        <p className="text-[10px] text-[#666] mt-0.5">{n.body}</p>
                      </button>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="p-1.5 rounded-md hover:bg-[#2a2a2a] text-[#888] hover:text-[#e8e8e8] transition-colors"
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>
      </div>

      {/* New Chat */}
      <div className="p-2">
        <button
          onClick={handleNew}
          className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium transition-colors ${collapsed ? 'justify-center' : ''}`}
        >
          <Plus size={16} />
          {!collapsed && 'New Chat'}
        </button>
      </div>

      {/* Main Nav */}
      <nav className="px-2 space-y-0.5">
        {NAV.map(({ icon: Icon, label, path }) => (
          <button
            key={path}
            onClick={() => navigate(path)}
            className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
              isActive(path)
                ? 'bg-[#7c6af7]/15 text-[#a89bf8]'
                : 'text-[#888] hover:text-[#e8e8e8] hover:bg-[#2a2a2a]'
            } ${collapsed ? 'justify-center' : ''}`}
            title={collapsed ? label : undefined}
          >
            <Icon size={16} />
            {!collapsed && label}
          </button>
        ))}
      </nav>

      {/* Intelligence Nav */}
      {!collapsed && (
        <div className="px-2 mt-3">
          <p className="text-[10px] text-[#555] uppercase tracking-wider px-2 mb-1">Intelligence</p>
          <nav className="space-y-0.5">
            {INTEL_NAV.map(({ icon: Icon, label, path }) => (
              <button
                key={path}
                onClick={() => navigate(path)}
                className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive(path)
                    ? 'bg-[#7c6af7]/15 text-[#a89bf8]'
                    : 'text-[#888] hover:text-[#e8e8e8] hover:bg-[#2a2a2a]'
                }`}
              >
                <Icon size={16} />
                {label}
              </button>
            ))}
          </nav>
        </div>
      )}

      {/* Conversations */}
      {!collapsed && (
        <div className="flex-1 flex flex-col mt-3 min-h-0">
          <div className="px-3 mb-2">
            <div className="flex items-center gap-2 bg-[#1a1a1a] rounded-lg px-2 py-1.5">
              <Search size={13} className="text-[#555]" />
              <input
                type="text"
                placeholder="Search chats..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="bg-transparent text-xs text-[#e8e8e8] placeholder-[#555] flex-1 outline-none"
              />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-2 space-y-0.5">
            {pinned.length > 0 && (
              <>
                <p className="text-[10px] text-[#555] uppercase tracking-wider px-2 mb-1">Pinned</p>
                {pinned.map(c => <ConvItem key={c.id} c={c} navigate={navigate} togglePin={togglePin} handleDelete={handleDelete} pinned />)}
              </>
            )}
            {recent.length > 0 && (
              <>
                {pinned.length > 0 && <p className="text-[10px] text-[#555] uppercase tracking-wider px-2 mt-2 mb-1">Recent</p>}
                {recent.slice(0, 20).map(c => <ConvItem key={c.id} c={c} navigate={navigate} togglePin={togglePin} handleDelete={handleDelete} />)}
              </>
            )}
          </div>
        </div>
      )}

      {/* Bottom nav */}
      <div className="px-2 py-2 border-t border-[#2a2a2a] space-y-0.5">
        {BOTTOM_NAV.map(({ icon: Icon, label, path }) => (
          <button
            key={path}
            onClick={() => navigate(path)}
            className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
              isActive(path) ? 'bg-[#7c6af7]/15 text-[#a89bf8]' : 'text-[#888] hover:text-[#e8e8e8] hover:bg-[#2a2a2a]'
            } ${collapsed ? 'justify-center' : ''}`}
          >
            <Icon size={16} />
            {!collapsed && label}
          </button>
        ))}
      </div>
    </div>
  )
}

function ConvItem({ c, navigate, togglePin, handleDelete, pinned }) {
  return (
    <div
      onClick={() => navigate(`/chat/${c.id}`)}
      className="group flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-[#2a2a2a] cursor-pointer"
    >
      <div className="flex-1 min-w-0">
        <span className="text-xs text-[#aaa] truncate block">{c.title}</span>
        {c.snippet && (
          <span className="text-[10px] text-[#555] truncate block mt-0.5">{c.snippet}</span>
        )}
      </div>
      <div className="hidden group-hover:flex items-center gap-1">
        <button
          onClick={e => { e.stopPropagation(); togglePin(c.id) }}
          className={`p-0.5 rounded ${pinned ? 'text-[#7c6af7]' : 'text-[#555] hover:text-[#aaa]'}`}
        >
          <Pin size={11} />
        </button>
        <button
          onClick={e => handleDelete(e, c.id)}
          className="p-0.5 rounded text-[#555] hover:text-[#f87171]"
        >
          <Trash2 size={11} />
        </button>
      </div>
    </div>
  )
}
