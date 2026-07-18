import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useStore } from './store'
import { getHealth, getConversations, getConfig } from './services/api'
import Sidebar from './components/Sidebar'
import StatusBar from './components/StatusBar'
import { ToastContainer } from './components/Toast'
import ChatPage from './pages/ChatPage'
import QuizPage from './pages/QuizPage'
import FlashcardsPage from './pages/FlashcardsPage'
import MindMapPage from './pages/MindMapPage'
import StudyPlanPage from './pages/StudyPlanPage'
import YouTubePage from './pages/YouTubePage'
import ImageGenPage from './pages/ImageGenPage'
import ProfilePage from './pages/ProfilePage'
import DocsPage from './pages/DocsPage'
import AdminPage from './pages/AdminPage'
import CodingPage from './pages/CodingPage'
import StudyToolsPage from './pages/StudyToolsPage'
import PptxPage from './pages/PptxPage'

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

export default function App() {
  const { setOllamaStatus, setConversations, setConfig } = useStore()

  useEffect(() => {
    // Check health
    const checkHealth = async () => {
      try {
        const h = await getHealth()
        setOllamaStatus(h.ollama ? 'ok' : 'error')
      } catch {
        setOllamaStatus('error')
      }
    }
    checkHealth()
    const interval = setInterval(checkHealth, 30000)

    // Load conversations
    getConversations().then(setConversations).catch(() => {})

    // Load config
    getConfig().then(setConfig).catch(() => {})

    return () => clearInterval(interval)
  }, [])

  return (
    <BrowserRouter>
      <div className="flex h-screen bg-[#0f0f0f] text-[#e8e8e8] overflow-hidden">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <StatusBar />
          <main className="flex-1 overflow-y-auto">
            <Routes>
              <Route path="/" element={<Navigate to="/chat" replace />} />
              <Route path="/chat" element={<ChatPage />} />
              <Route path="/chat/:id" element={<ChatPage />} />
              <Route path="/quiz" element={<QuizPage />} />
              <Route path="/flashcards" element={<FlashcardsPage />} />
              <Route path="/mindmap" element={<MindMapPage />} />
              <Route path="/study-plan" element={<StudyPlanPage />} />
              <Route path="/pptx" element={<PptxPage />} />
              <Route path="/youtube" element={<YouTubePage />} />
              <Route path="/docs" element={<DocsPage />} />
              <Route path="/imagegen" element={<ImageGenPage />} />
              <Route path="/coding" element={<CodingPage />} />
              <Route path="/study-tools" element={<StudyToolsPage />} />
              <Route path="/profile" element={<ProfilePage />} />
              <Route path="/admin" element={<AdminPage />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </main>
        </div>
        <ToastContainer />
      </div>
    </BrowserRouter>
  )
}
