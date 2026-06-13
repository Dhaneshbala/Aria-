import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useStore } from '../store'
import { deleteConversation } from '../services/api'
import {
  MessageSquare, BookOpen, CreditCard, Network, Calendar,
  Youtube, Image, FileText, User, Settings, Plus, Search, Pin,
  Trash2, ChevronLeft, ChevronRight, Zap
} from 'lucide-react'

const NAV = [
  { icon: MessageSquare, label: 'Chat', path: '/chat' },
  { icon: BookOpen, label: 'Quiz', path: '/quiz' },
  { icon: CreditCard, label: 'Flashcards', path: '/flashcards' },
  { icon: Network, label: 'Mind Map', path: '/mindmap' },
  { icon: Calendar, label: 'Study Plan', path: '/study-plan' },
  { icon: Youtube, label: 'YouTube', path: '/youtube' },
  { icon: FileText, label: 'Documents', path: '/docs' },
  { icon: Image, label: 'Image Gen', path: '/imagegen' },
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

  const filtered = conversations.filter(c =>
    c.title.toLowerCase().includes(search.toLowerCase())
  )
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
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1.5 rounded-md hover:bg-[#2a2a2a] text-[#888] hover:text-[#e8e8e8] transition-colors"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
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
      <span className="flex-1 text-xs text-[#aaa] truncate">{c.title}</span>
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
