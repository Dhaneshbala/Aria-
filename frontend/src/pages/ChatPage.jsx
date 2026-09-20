import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useStore } from '../store'
import { getConversation } from '../services/api'
import { useChat } from '../hooks/useChat'
import Message from '../components/Message'
import ChatInput from '../components/ChatInput'
import ExportButton from '../components/ExportButton'
import { Zap, BookOpen, Calculator, Globe, FlaskConical, Code, FileText, MessageCircleQuestion, Drama } from 'lucide-react'

const SUGGESTIONS = [
  { icon: Calculator,   text: 'Explain quadratic equations step by step', short: 'Solve maths' },
  { icon: FlaskConical, text: 'How does photosynthesis work? Draw a mind map', short: 'Explain science' },
  { icon: Globe,        text: 'Summarise the causes of World War 1', short: 'History summary' },
  { icon: Code,         text: 'Teach me Python for loops with examples', short: 'Coding help' },
  { icon: BookOpen,     text: 'Make a quiz on the solar system — medium', short: 'Make a quiz' },
  { icon: FileText,     text: 'Create study notes on the French Revolution', short: 'Study notes' },
]

const GEMINI_CHIPS = [
  { icon: '📝', label: 'Make a quiz', prompt: 'Make a quiz on my weakest topic — medium, 5 questions' },
  { icon: '🧠', label: 'Explain', prompt: 'Explain photosynthesis step by step' },
  { icon: '🗺️', label: 'Mind map', prompt: 'Draw me a mind map of the water cycle' },
  { icon: '📊', label: 'Timeline', prompt: 'Make a timeline for World War 2' },
]

function ProgressBar() {
  const { progress, progressSteps, isStreaming } = useStore()
  if (!isStreaming || !progress) return null
  const pct = progress.pct || 0
  return (
    <div className="sticky top-0 z-10 bg-aria-elevated/90 backdrop-blur-xl border-b border-aria-border px-4 py-2.5" role="status" aria-live="polite">
      <div className="w-full">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs text-aria-accent-blue font-medium flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-aria-accent-blue animate-pulse shadow-glow" />
            {progress.label || 'Thinking...'}
          </span>
          <span className="text-[10px] font-medium tracking-widest text-aria-muted">{pct}%</span>
        </div>
        <div className="w-full bg-aria-bg rounded-full h-1.5 overflow-hidden p-0.5">
          <div className="bg-gradient-to-r from-[#4285f4] via-[#8ab4f8] to-[#7c6af7] h-full rounded-full transition-all duration-700 ease-out shadow-glow" style={{ width: `${pct}%` }} />
        </div>
        {progressSteps.length > 1 && (
          <div className="flex gap-1.5 mt-2 flex-wrap">
            {progressSteps.map(s => (
              <span key={s.step} className={`text-[10px] px-2 py-0.5 rounded-full border font-medium transition-colors ${s.status === 'done' ? 'bg-aria-accent-blue/15 text-aria-accent-blue border-aria-accent-blue/20' : s.status === 'running' ? 'bg-aria-surface text-aria-muted border-aria-border animate-pulse' : 'bg-aria-surface text-aria-muted/60 border-aria-border'}`}>
                {s.status === 'done' ? '✓' : s.status === 'running' ? '⏳' : '•'} {s.label || s.step}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default function ChatPage() {
  const { id } = useParams()
  const {
    conversationId, messages, isStreaming, ollamaStatus, mode,
    setConversationId, setMessages,
  } = useStore()
  const { sendMessage } = useChat()
  const bottomRef = useRef()

  // Load existing conversation when navigating to /chat/:id
  // Don't clobber an in-flight stream — the live messages are in the store
  useEffect(() => {
    const { isStreaming: streamingNow } = useStore.getState()
    if (streamingNow) return
    if (id && id !== conversationId) {
      setConversationId(id)
      getConversation(id).then(turns => {
        // If a stream started while we were fetching, don't overwrite
        if (useStore.getState().isStreaming) return
        if (!Array.isArray(turns)) { setMessages([]); return }
        const msgs = turns.flatMap(t => ([
          { id: `u-${t.timestamp}`, role: 'user',      content: t.user, timestamp: t.timestamp },
          { id: `a-${t.timestamp}`, role: 'assistant', content: t.ai,   timestamp: t.timestamp, tools: [], extras: null },
        ]))
        setMessages(msgs)
      }).catch(() => setMessages([]))
    } else if (!id && !conversationId && messages.length === 0) {
      // Stay on current chat — don't clear
    }
  }, [id])

  // Check for pending doc from DocsPage on mount
  useEffect(() => {
    const pendingRaw = sessionStorage.getItem('aria_pending_doc')
    if (pendingRaw) {
      try {
        const pending = JSON.parse(pendingRaw)
        if (pending.hasFile) {
          // useChat.sendMessage will pick this up from sessionStorage
          sendMessage({ text: pending.prefill || `Please help me with this document: ${pending.name}` })
        }
      } catch {}
    }
  }, [])

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const isEmpty = messages.length === 0

  return (
    <div className="flex flex-col h-full w-full bg-[#131314]">
      {/* Toolbar — only when chatting */}
      {messages.length > 0 && (
        <div className="flex items-center justify-end px-4 py-1.5">
          <ExportButton messages={messages} conversationId={conversationId} />
        </div>
      )}

      {/* Offline banner — Gemini style subtle */}
      {ollamaStatus === 'error' && (
        <div className="mx-4 mt-2 px-4 py-2.5 bg-[#3c1f1a] border border-[#5c2b22] rounded-xl text-center">
          <p className="text-xs text-[#f28b82]">
            Ollama offline — Study Buddy can’t answer. Run <code className="px-1.5 py-0.5 rounded bg-[#5c2b22] text-[#f28b82] font-mono">ollama serve</code> then refresh.
          </p>
        </div>
      )}

      {/* Active mode indicator — pill */}
      {mode === 'think' && (
        <div className="flex justify-center pt-2">
          <span className="px-3 py-1 rounded-full bg-[#8ab4f8]/15 border border-[#8ab4f8]/20 text-[11px] text-[#8ab4f8] flex items-center gap-1.5">
            <Zap size={13} /> Think mode — deeper reasoning
          </span>
        </div>
      )}
      {mode === 'hype' && (
        <div className="flex justify-center pt-2">
          <span className="px-3 py-1 rounded-full bg-orange-500/15 border border-orange-500/30 text-[11px] text-orange-300 flex items-center gap-1.5">
            🔥 Hype tutor — LET'S GOOO, free marks incoming
          </span>
        </div>
      )}
      {mode === 'socratic' && (
        <div className="flex justify-center pt-2">
          <span className="px-3 py-1 rounded-full bg-[#f59e0b]/15 border border-[#f59e0b]/20 text-[11px] text-[#fbbf24] flex items-center gap-1.5">
            <MessageCircleQuestion size={13} /> Socratic mode — guiding, not answering
          </span>
        </div>
      )}
      {mode === 'roleplay' && (
        <div className="flex justify-center pt-2">
          <span className="px-3 py-1 rounded-full bg-[#ec4899]/15 border border-[#ec4899]/20 text-[11px] text-[#f9a8d4] flex items-center gap-1.5">
            <Drama size={13} /> Roleplay mode — in character
          </span>
        </div>
      )}

      {/* Progress bar */}
      <ProgressBar />

      {/* Messages / Welcome */}
      <div className="flex-1 overflow-y-auto">
        {isEmpty ? (
          <Welcome onSuggest={(text) => sendMessage({ text })} sendMessage={sendMessage} isStreaming={isStreaming} />
        ) : (
          <div className="w-full px-6 lg:px-8 py-6">
            {messages.map(msg => (
              <Message key={msg.id} msg={msg} onSuggest={(text) => sendMessage({ text })} />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input bar — hidden when empty because Welcome has centered input (Gemini behavior) */}
      {!isEmpty && (
        <div className="w-full px-6 lg:px-8 pb-4 pt-2 bg-gradient-to-t from-[#131314] via-[#131314] to-transparent">
          <ChatInput onSend={sendMessage} disabled={isStreaming} />
          <p className="text-center text-[11px] text-[#5f6368] mt-3">
            Study Buddy can make mistakes. Check important info. · Private & on-device
          </p>
        </div>
      )}
    </div>
  )
}

function Welcome({ onSuggest, sendMessage, isStreaming }) {
  const { config } = useStore()
  const name = config.student_name && config.student_name !== 'Student' ? config.student_name : 'there'
  const displayName = name.charAt(0).toUpperCase() + name.slice(1)
  const handleSend = sendMessage || (({ text }) => onSuggest(text))
  // Prefill handed off from the dashboard shortcuts (one-shot).
  const [draft, setDraft] = useState(() => {
    try {
      const p = sessionStorage.getItem('aria_chat_prefill')
      if (p) { sessionStorage.removeItem('aria_chat_prefill'); return p }
    } catch {}
    return ''
  })
  return (
    <div className="flex flex-col items-center justify-center min-h-full px-6 lg:px-8 py-8 md:py-12">
      <div className="w-full flex flex-col items-center">
        {/* Gemini hero greeting */}
        <h1 className="text-[40px] sm:text-[48px] md:text-[56px] font-normal leading-[1.05] tracking-tight text-center">
          <span className="gemini-gradient-text">Hello, {displayName}</span>
        </h1>
        <h2 className="text-[40px] sm:text-[48px] md:text-[56px] font-normal leading-[1.05] tracking-tight text-[#5f6368] text-center -mt-1">
          How can I help?
        </h2>
        <p className="text-sm text-[#9aa0a6] mt-4 mb-8 text-center">Your private study assistant — offline, on-device</p>

        {/* Centered composer — Gemini puts input in the middle when empty */}
        <div className="w-full">
          <ChatInput onSend={handleSend} disabled={isStreaming} autoFocus text={draft} onTextChange={setDraft} />
          <p className="text-center text-[11px] text-[#5f6368] mt-3">Study Buddy can make mistakes — verify important work</p>
        </div>

        {/* Quick chips — Gemini style horizontal pills */}
        <div className="flex flex-wrap justify-center gap-2 mt-6 w-full">
          {GEMINI_CHIPS.map(c => (
            <button
              key={c.label}
              onClick={() => onSuggest(c.prompt)}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#1e1f20] hover:bg-[#2d2e30] border border-[#2d2e30] hover:border-[#3c4043] text-sm text-[#e3e3e3] transition-colors"
            >
              <span>{c.icon}</span> {c.label}
            </button>
          ))}
        </div>

        {/* Suggestion cards — Gemini 2x2 grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full mt-8">
          {SUGGESTIONS.slice(0, 4).map(({ icon: Icon, text, short }) => (
            <button
              key={text}
              onClick={() => onSuggest(text)}
              className="group relative flex flex-col text-left p-4 rounded-2xl bg-[#1e1f20] hover:bg-[#2d2e30] border border-[#2d2e30] hover:border-[#3c4043] transition-all min-h-[110px]"
            >
              <div className="flex items-start justify-between mb-3">
                <span className="text-xs font-medium text-[#9aa0a6] uppercase tracking-wide">{short}</span>
                <span className="w-8 h-8 rounded-full bg-[#2d2e30] group-hover:bg-[#35363a] flex items-center justify-center shrink-0">
                  <Icon size={16} className="text-[#8ab4f8]" />
                </span>
              </div>
              <span className="text-[13px] leading-snug text-[#e3e3e3] line-clamp-2 pr-2">{text}</span>
              <span className="absolute bottom-3 right-3 w-6 h-6 rounded-full bg-[#131314] group-hover:bg-[#1e1f20] flex items-center justify-center text-[#9aa0a6] text-xs">↗</span>
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 mt-8 text-[11px] text-[#5f6368]">
          <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
          Runs locally on your Mac · No data leaves your device
        </div>
      </div>
    </div>
  )
}
