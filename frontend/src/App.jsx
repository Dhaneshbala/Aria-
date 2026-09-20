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
const KBPage = lazy(() => import('./pages/KBPage'))

import { Menu, ChevronDown, Sparkles, Search, Maximize, Minimize } from 'lucide-react'

function PageLoader() {
  return (
    <div className="flex flex-col h-full w-full bg-aria-bg p-4 gap-2" role="status" aria-live="polite" aria-label="Loading page">
      <div className="skeleton h-8 w-48" aria-hidden="true" />
      <div className="skeleton h-4 w-full" aria-hidden="true" />
      <div className="skeleton h-4 w-11/12" aria-hidden="true" />
      <div className="skeleton h-4 w-4/5" aria-hidden="true" />
      <div className="card mt-2 p-4 flex items-center gap-3">
        <div className="w-8 h-8 border-2 border-aria-accent border-t-transparent rounded-full animate-spin" aria-hidden="true" />
        <p className="text-sm text-aria-muted">Loading your workspace…</p>
      </div>
    </div>
  )
}

function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center h-full px-4 py-10">
      <div className="card flex flex-col items-center px-8 py-10 text-center max-w-sm animate-fade-slide">
        <p className="text-5xl mb-3" aria-hidden="true">🔍</p>
        <h1 className="text-lg font-semibold text-aria-text mb-1">Page not found</h1>
        <p className="text-[13px] text-aria-muted mb-4">The page you&apos;re looking for doesn&apos;t exist or moved.</p>
        <a href="/chat" className="btn-primary touch-target px-5 py-2 text-sm inline-flex items-center">
          Go to Chat
        </a>
      </div>
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
    } catch (e) {
      console.warn('Fullscreen toggle failed:', e)
    }
  }
  return (
    <header className="gemini-header flex items-center justify-between px-3 sm:px-4 shrink-0 sticky top-0 z-20 backdrop-blur-xl safe-bottom border-b border-aria-border/60" style={{ background: 'rgba(15,15,16,0.82)' }}>
      <div className="flex items-center gap-3">
        <button onClick={onToggleSidebar} aria-label="Toggle menu"
          className="touch-target p-2 rounded-full hover:bg-aria-variant text-aria-text transition-colors focus-visible:ring-2 focus-visible:ring-aria-accent/30">
          <Menu size={20} />
        </button>
        <div className="flex items-center gap-2 select-none">
          <span className="text-[22px] font-medium tracking-tight text-aria-text" style={{ fontFamily: "'Google Sans', Inter, sans-serif", letterSpacing: '-0.02em' }}>Study Buddy</span>
          <span className="text-[10px] font-semibold tracking-widest px-2 py-0.5 rounded-full bg-gradient-to-r from-[#4285f4] to-[#8b5cf6] text-white ml-1 shadow-sm">2.5 • $10B</span>
        </div>
      </div>
      <div className="flex items-center gap-1">
        <button onClick={toggleFullscreen} title={isFullscreen ? 'Exit full screen (Esc)' : 'Full screen'}
          aria-label={isFullscreen ? 'Exit full screen' : 'Enter full screen'}
          aria-pressed={isFullscreen}
          className="touch-target p-2 rounded-full hover:bg-aria-variant text-aria-muted hover:text-aria-text transition-colors">
          {isFullscreen ? <Minimize size={18} /> : <Maximize size={18} />}
        </button>
        <div title={config.student_name || 'Student'} aria-label={`Signed in as ${config.student_name || 'Student'}`} className="w-8 h-8 rounded-full bg-gradient-to-br from-[#8b5cf6] to-[#4285f4] flex items-center justify-center text-white text-xs font-medium ml-1">
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
      } catch (e) {
        console.warn('Health check failed:', e)
        setOllamaStatus('error')
      }
    }
    checkHealth()
    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') checkHealth()
    }, 120000)
    const onVis = () => document.visibilityState === 'visible' && checkHealth()
    document.addEventListener('visibilitychange', onVis)

    getConversations().then(setConversations).catch((e) => console.warn('Failed to load conversations:', e))
    getConfig().then(setConfig).catch((e) => console.warn('Failed to load config:', e))

    return () => { clearInterval(interval); document.removeEventListener('visibilitychange', onVis) }
  }, [])

  return (
    <BrowserRouter>
      <div className={`flex min-h-screen w-full bg-aria-bg text-aria-text overflow-x-hidden ${fontClass} ${uiPrefs.contrast ? 'aria-contrast' : ''}`}>
        <div className="aria-bg opacity-40" />
        <Sidebar collapsed={!sidebarOpen} onToggle={() => setSidebarOpen(v => !v)} mobileOpen={sidebarOpen} setMobileOpen={setSidebarOpen} />
        <div className="flex-1 flex flex-col min-w-0 w-full">
          <GeminiHeader onToggleSidebar={() => setSidebarOpen(v => !v)} />
          <StatusBar />
          <main className="flex-1 w-full overflow-y-auto bg-aria-bg flex flex-col">
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
                  <Route path="/kb" element={<KBPage />} />
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
