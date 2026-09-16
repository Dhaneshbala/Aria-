import { useEffect, useState, lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useStore } from './store'
import { getHealth, getConversations, getConfig } from './services/api'
import Sidebar from './components/Sidebar'
import StatusBar from './components/StatusBar'
import { ToastContainer } from './components/Toast'
import BgTasks from './components/BgTasks'
import ErrorBoundary from './components/ErrorBoundary'
import Onboarding from './components/Onboarding'

const ChatPage = lazy(() => import('./pages/ChatPage'))
const VoiceTutorPage = lazy(() => import('./pages/VoiceTutorPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const CreatePage = lazy(() => import('./pages/CreatePage'))
const CheatSheetPage = lazy(() => import('./pages/CheatSheetPage'))
const MathsAcceleratorPage = lazy(() => import('./pages/MathsAcceleratorPage'))
const AdminPage = lazy(() => import('./pages/AdminPage'))
const SpacedRepetitionPage = lazy(() => import('./pages/SpacedRepetitionPage'))
const YouTubePage = lazy(() => import('./pages/YouTubePage'))
const MemoryPage = lazy(() => import('./pages/MemoryPage'))

import { Menu, ChevronDown, Sparkles, Search, Maximize, Minimize } from 'lucide-react'

function PageLoader() {
  return (
    <div className="flex flex-col items-center justify-center h-full w-full bg-[#131314]">
      <div className="w-8 h-8 border-2 border-[#7c6af7] border-t-transparent rounded-full animate-spin mb-3" />
      <p className="text-sm text-[#666]">Loading...</p>
    </div>
  )
}

function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center h-full px-4">
      <p className="text-6xl mb-4">🔍</p>
      <h1 className="text-xl font-semibold text-[#e8e8e8] mb-2">Page not found</h1>
      <p className="text-sm text-[#666] mb-4">The page you're looking for doesn't exist.</p>
      <a href="/chat" className="px-4 py-2 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm transition-colors">
        Go to Chat
      </a>
    </div>
  )
}

function GeminiHeader({ onToggleSidebar }) {
  const { config } = useStore()
  const initial = (config.student_name || 'S').trim().charAt(0).toUpperCase() || 'S'
  const [isFullscreen, setIsFullscreen] = useState(false)
  useEffect(() => {
    const onChange = () => setIsFullscreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])
  const toggleFullscreen = async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen()
      else await document.documentElement.requestFullscreen()
    } catch {}
  }
  return (
    <header className="gemini-header flex items-center justify-between px-3 sm:px-4 shrink-0 sticky top-0 z-20 backdrop-blur-md" style={{ background: 'rgba(19,19,20,0.9)' }}>
      <div className="flex items-center gap-3">
        <button onClick={onToggleSidebar} aria-label="Toggle menu"
          className="p-2 rounded-full hover:bg-[#2d2e30] text-[#e3e3e3] transition-colors">
          <Menu size={20} />
        </button>
        <div className="flex items-center gap-2 select-none">
          <span className="hidden sm:block text-[22px] font-normal tracking-tight text-[#e3e3e3]" style={{ fontFamily: "'Google Sans', Inter, sans-serif" }}>ARIA</span>
          <span className="hidden sm:block text-[11px] font-medium px-1.5 py-0.5 rounded bg-gradient-to-r from-[#4285f4] to-[#8b5cf6] text-white ml-1">2.5</span>
        </div>
      </div>
      <div className="flex items-center gap-1">
        <button onClick={toggleFullscreen} title={isFullscreen ? 'Exit full screen (Esc)' : 'Full screen'}
          className="p-2 rounded-full hover:bg-[#2d2e30] text-[#9aa0a6] hover:text-[#e3e3e3] transition-colors">
          {isFullscreen ? <Minimize size={18} /> : <Maximize size={18} />}
        </button>
        <div title={config.student_name || 'Student'} className="w-8 h-8 rounded-full bg-gradient-to-br from-[#8b5cf6] to-[#4285f4] flex items-center justify-center text-white text-xs font-medium ml-1">
          {initial}
        </div>
      </div>
    </header>
  )
}

export default function App() {
  const { setOllamaStatus, setConversations, setConfig, uiPrefs } = useStore()
  const fontClass = `aria-font-${uiPrefs.fontSize || 'md'}`
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    if (typeof window === 'undefined') return true
    return window.innerWidth >= 768
  })
  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth < 768) setSidebarOpen(false)
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const h = await getHealth()
        setOllamaStatus(h.ollama ? 'ok' : 'error')
      } catch {
        setOllamaStatus('error')
      }
    }
    checkHealth()
    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') checkHealth()
    }, 120000)
    const onVis = () => document.visibilityState === 'visible' && checkHealth()
    document.addEventListener('visibilitychange', onVis)

    getConversations().then(setConversations).catch(() => {})
    getConfig().then(setConfig).catch(() => {})

    return () => { clearInterval(interval); document.removeEventListener('visibilitychange', onVis) }
  }, [])

  return (
    <BrowserRouter>
      <div className={`flex h-screen w-full bg-[#131314] text-[#e3e3e3] overflow-hidden ${fontClass} ${uiPrefs.contrast ? 'aria-contrast' : ''}`}>
        <div className="aria-bg opacity-40" />
        <Sidebar collapsed={!sidebarOpen} onToggle={() => setSidebarOpen(v => !v)} mobileOpen={sidebarOpen} setMobileOpen={setSidebarOpen} />
        <div className="flex-1 flex flex-col min-w-0 w-full">
          <GeminiHeader onToggleSidebar={() => setSidebarOpen(v => !v)} />
          <StatusBar />
          <main className="flex-1 w-full overflow-y-auto bg-[#131314] flex flex-col">
            <ErrorBoundary>
              <Suspense fallback={<PageLoader />}>
                <Routes>
                  <Route path="/" element={<DashboardPage />} />
                  <Route path="/chat" element={<ChatPage />} />
                  <Route path="/chat/:id" element={<ChatPage />} />
                  <Route path="/voice" element={<VoiceTutorPage />} />
                  <Route path="/create" element={<CreatePage />} />
                  <Route path="/maths" element={<MathsAcceleratorPage />} />
                  <Route path="/cheatsheets" element={<CheatSheetPage />} />
                  <Route path="/library" element={<Navigate to="/cheatsheets" replace />} />
                  <Route path="/youtube" element={<YouTubePage />} />
                  <Route path="/spaced" element={<SpacedRepetitionPage />} />
                  <Route path="/review" element={<SpacedRepetitionPage />} />
                  <Route path="/flashcards" element={<SpacedRepetitionPage />} />
                  <Route path="/memory" element={<MemoryPage />} />
                  <Route path="/admin" element={<AdminPage />} />
                  <Route path="/profile" element={<Navigate to="/admin" replace />} />
                  <Route path="*" element={<Navigate to="/chat" replace />} />
                </Routes>
              </Suspense>
            </ErrorBoundary>
          </main>
        </div>
        <ToastContainer />
        <BgTasks />
        <Onboarding />
      </div>
    </BrowserRouter>
  )
}
