import { useEffect, useState, lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'
import { useStore } from './store'
import { getHealth, getConversations, getConfig } from './services/api'
import { fetchMe, clearToken } from './services/auth'
import { getActiveAbort } from './hooks/useChat'
import Sidebar from './components/Sidebar'
import StatusBar from './components/StatusBar'
import OfflineBadge from './components/OfflineBadge'
import MobileNav from './components/MobileNav'
import { ToastContainer, showToast } from './components/Toast'
import BgTasks from './components/BgTasks'
import ErrorBoundary from './components/ErrorBoundary'
import Onboarding from './components/Onboarding'
import InstallPrompt from './components/InstallPrompt'

/**
 * Global keyboard shortcuts (ignored while typing, except Escape):
 *   N   — new chat        / — focus chat input        Esc — stop streaming
 */
function GlobalShortcuts() {
  const navigate = useNavigate()
  const location = useLocation()
  useEffect(() => {
    const onKey = (e) => {
      const tag = (e.target?.tagName || '').toLowerCase()
      const typing = tag === 'input' || tag === 'textarea' || e.target?.isContentEditable
      if (e.key === 'Escape') {
        const c = getActiveAbort()
        if (c) c.abort()
        return
      }
      if (typing || e.metaKey || e.ctrlKey || e.altKey) return
      // 'N' = new chat, EXCEPT on flashcard/review pages where N means
      // "don't know" mid-session (FlashcardsPage advertises it).
      const onReviewPage = /^\/(spaced|review|flashcards)/.test(location.pathname)
      if (!onReviewPage && (e.key === 'n' || e.key === 'N')) {
        e.preventDefault()
        useStore.getState().newConversation()
        if (!location.pathname.startsWith('/chat')) navigate('/chat')
      } else if (e.key === '/') {
        if (location.pathname.startsWith('/chat')) {
          e.preventDefault()
          document.querySelector('#aria-chat-input')?.focus()
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [navigate, location.pathname])
  return null
}

/** Warm the most-visited route chunks while the browser is idle. */
function useRoutePreload() {
  useEffect(() => {
    let cancelled = false
    const warm = () => {
      if (cancelled) return
      import('./pages/ChatPage').catch(() => {})
      import('./pages/DashboardPage').catch(() => {})
    }
    if ('requestIdleCallback' in window) {
      const id = window.requestIdleCallback(warm, { timeout: 5000 })
      return () => { cancelled = true; window.cancelIdleCallback(id) }
    }
    const t = setTimeout(warm, 3000)
    return () => { cancelled = true; clearTimeout(t) }
  }, [])
}

const ChatPage = lazy(() => import('./pages/ChatPage'))
const VoiceTutorPage = lazy(() => import('./pages/VoiceTutorPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const CreatePage = lazy(() => import('./pages/CreatePage'))
const CheatSheetPage = lazy(() => import('./pages/CheatSheetPage'))
const MathsAcceleratorPage = lazy(() => import('./pages/MathsAcceleratorPage'))
const AdminPage = lazy(() => import('./pages/AdminPage'))
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'))
const LoginPage = lazy(() => import('./pages/LoginPage'))
const WalletPage = lazy(() => import('./pages/WalletPage'))
const AccountPage = lazy(() => import('./pages/AccountPage'))
const HelpPage = lazy(() => import('./pages/HelpPage'))
const SpacedRepetitionPage = lazy(() => import('./pages/SpacedRepetitionPage'))
const SyllabusPage = lazy(() => import('./pages/SyllabusPage'))
const YouTubePage = lazy(() => import('./pages/YouTubePage'))
const MemoryPage = lazy(() => import('./pages/MemoryPage'))
const KBPage = lazy(() => import('./pages/KBPage'))

import { Menu, Maximize, Minimize } from 'lucide-react'

function PageLoader() {
  return (
    <div className="flex flex-col items-center justify-center h-full w-full bg-aria-bg" role="status" aria-label="Loading page">
      <div className="w-8 h-8 border-2 border-[#7c6af7] border-t-transparent rounded-full animate-spin mb-3" />
      <p className="text-sm text-[#888]">Loading...</p>
    </div>
  )
}

const ROUTE_TITLES = {
  '/': 'Dashboard — ARIA',
  '/chat': 'Chat — ARIA',
  '/voice': 'Voice Tutor — ARIA',
  '/create': 'Create — ARIA',
  '/maths': 'Maths — ARIA',
  '/cheatsheets': 'Cheat Sheets — ARIA',
  '/youtube': 'YouTube — ARIA',
  '/spaced': 'Spaced Repetition — ARIA',
  '/syllabus': 'Syllabus — ARIA',
  '/review': 'Review — ARIA',
  '/flashcards': 'Flashcards — ARIA',
  '/memory': 'Memory — ARIA',
  '/kb': 'Knowledge Base — ARIA',
  '/admin': 'Admin — ARIA',
  '/login': 'Sign in — ARIA',
  '/wallet': 'Wallet — ARIA',
  '/account': 'Account — ARIA',
  '/help': 'Help — ARIA',
}

function RouteTitle() {
  const location = useLocation()
  useEffect(() => {
    const base = location.pathname.split('/')[1]
    const key = base ? `/${base}` : '/'
    if (location.pathname.startsWith('/chat/')) document.title = 'Chat — ARIA'
    else document.title = ROUTE_TITLES[key] || ROUTE_TITLES[location.pathname] || 'ARIA — AI Study Assistant'
  }, [location.pathname])
  return null
}

function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center h-full px-4">
      <p className="text-6xl mb-4">🔍</p>
      <h1 className="text-xl font-semibold text-[#e8e8e8] mb-2">Page not found</h1>
      <p className="text-sm text-[#888] mb-4">The page you're looking for doesn't exist.</p>
      <a href="/chat" className="px-4 py-2 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm transition-colors">
        Go to Chat
      </a>
    </div>
  )
}

/** Backend-enforced permissions are the real wall; this page only
 * reflects the 403 the server would deliver anyway (Section 13C). */
function Forbidden() {
  return (
    <div className="flex flex-col items-center justify-center h-full px-4 text-center">
      <ShieldAlert size={40} className="text-[#f28b82] mb-3" />
      <h1 className="text-lg font-semibold text-[#e8e8e8] mb-2">Administrators only</h1>
      <p className="text-sm text-[#888] max-w-sm mb-4">
        This dashboard manages accounts, credits and system settings — your
        student account does not have access (and neither does your
        browser, only the server matters).
      </p>
      <a href="/" className="px-4 py-2 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm transition-colors">
        Back to Dashboard
      </a>
    </div>
  )
}

/** Route wrapper: admins and superadmins only (cosmetic — the backend
 * independently returns 403 for every admin API). */
function RequireRole({ user, children }) {
  if (user?.role === 'admin' || user?.role === 'superadmin') return children
  return <Forbidden />
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
          className="p-2 rounded-full hover:bg-[#2d2e30] text-aria-text transition-colors">
          <Menu size={20} />
        </button>
        <div className="flex items-center gap-2 select-none">
          <span className="hidden sm:block text-[22px] font-normal tracking-tight text-aria-text" style={{ fontFamily: "'Google Sans', Inter, sans-serif" }}>ARIA</span>
          <span className="hidden sm:block text-[11px] font-medium px-1.5 py-0.5 rounded bg-gradient-to-r from-[#4285f4] to-[#8b5cf6] text-white ml-1">2.5</span>
        </div>
      </div>
      <div className="flex items-center gap-1">
        <button onClick={toggleFullscreen} title={isFullscreen ? 'Exit full screen (Esc)' : 'Full screen'}
          className="p-2 rounded-full hover:bg-[#2d2e30] text-aria-muted hover:text-aria-text transition-colors">
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
  const { setOllamaStatus, setConversations, setConfig, uiPrefs, authUser, authReady, setAuth, clearAuth } = useStore()
  useRoutePreload()
  const fontClass = `aria-font-${uiPrefs.fontSize || 'md'}`
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    if (typeof window === 'undefined') return true
    return window.innerWidth >= 768
  })

  // ── Session boot (Section 13): who am I? ─────────────────────────────
  // One unauthenticated probe decides the mode:
  //   • local mode → 200, owner, no login UI (today's behaviour)
  //   • accounts mode + valid session → signed-in user
  //   • accounts mode without session → 401 → login page
  useEffect(() => {
    let cancelled = false
    fetchMe()
      .then(me => { if (!cancelled) setAuth(me) })
      .catch(e => {
        if (cancelled) return
        if (e?.status === 401) clearToken()
        clearAuth()
      })
    return () => { cancelled = true }
  }, [])

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

    // Only admins/local owner read global config — students' requests
    // would 403 and spam a toast every boot (the backend decides, so the
    // browser check here is cosmetic; both must agree).
    const role = authUser?.role
    if (!authUser?.auth_mode || authUser.auth_mode !== 'accounts' || role === 'admin' || role === 'superadmin') {
      getConfig().then(setConfig).catch(() => { showToast("Couldn't load settings", 'error', 2500) })
    }

    return () => { clearInterval(interval); document.removeEventListener('visibilitychange', onVis) }
  }, [authUser?.auth_mode, authUser?.role])

  // High-contrast preference must reach <html>/<body> — the container div
  // alone can never satisfy the CSS body/element rules in index.css.
  useEffect(() => {
    const root = document.documentElement
    root.classList.toggle('aria-contrast', !!uiPrefs.contrast)
    return () => { root.classList.remove('aria-contrast') }
  }, [uiPrefs.contrast])

  if (!authReady) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-[#0b0b0b]">
        <div className="w-8 h-8 rounded-full border-2 border-[#7c6af7] border-t-transparent animate-spin" />
      </div>
    )
  }

  // Accounts mode without a session: sign-in over everything else.
  if (!authUser && window.location.pathname !== '/login') {
    return (
      <BrowserRouter>
        <RouteTitle />
        <Suspense fallback={null}>
          <LoginPage />
        </Suspense>
      </BrowserRouter>
    )
  }

  const isAccountsMode = authUser?.auth_mode === 'accounts'
  const isAdmin = authUser?.role === 'admin' || authUser?.role === 'superadmin'

  return (
    <BrowserRouter>
      <RouteTitle />
      <GlobalShortcuts />
      <a href="#aria-main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-2 focus:px-3 focus:py-2 focus:rounded-lg focus:bg-[#7c6af7] focus:text-white text-sm">
        Skip to content
      </a>
      <div className={`flex h-screen w-full bg-aria-bg text-aria-text overflow-hidden ${fontClass} ${uiPrefs.contrast ? 'aria-contrast' : ''}`}>
        <div className="aria-bg opacity-40" />
        <Sidebar collapsed={!sidebarOpen} onToggle={() => setSidebarOpen(v => !v)} mobileOpen={sidebarOpen} setMobileOpen={setSidebarOpen} />
        <div className="flex-1 flex flex-col min-w-0 w-full">
          <GeminiHeader onToggleSidebar={() => setSidebarOpen(v => !v)} />
          <OfflineBadge />
          <StatusBar />
          <main id="aria-main" className="flex-1 w-full overflow-y-auto bg-aria-bg flex flex-col pb-16 md:pb-0">
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
                  <Route path="/syllabus" element={<SyllabusPage />} />
                  <Route path="/review" element={<SpacedRepetitionPage />} />
                  <Route path="/flashcards" element={<SpacedRepetitionPage />} />
                  <Route path="/memory" element={<MemoryPage />} />
                  <Route path="/kb" element={<KBPage />} />
                  <Route
                    path="/admin"
                    element={
                      isAccountsMode
                        ? <RequireRole user={authUser}><AdminDashboard /></RequireRole>
                        : <AdminPage />
                    }
                  />
                  <Route path="/wallet" element={isAccountsMode ? <WalletPage /> : <Navigate to="/admin" replace />} />
                  <Route
                    path="/account"
                    element={isAccountsMode ? <AccountPage /> : <Navigate to="/admin" replace />}
                  />
                  <Route path="/help" element={<HelpPage />} />
                  <Route
                    path="/profile"
                    element={<Navigate to={isAdmin || !isAccountsMode ? '/admin' : '/account'} replace />}
                  />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </Suspense>
            </ErrorBoundary>
          </main>
        </div>
        <ToastContainer />
        <BgTasks />
        <MobileNav />
        {!isAccountsMode || isAdmin ? <Onboarding /> : null}
        <InstallPrompt />
      </div>
    </BrowserRouter>
  )
}
