import { useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { useStore } from '../store'
import { getConversation } from '../services/api'
import { useChat } from '../hooks/useChat'
import Message from '../components/Message'
import ChatInput from '../components/ChatInput'
import ExportButton from '../components/ExportButton'
import { Zap, BookOpen, Calculator, Globe, FlaskConical, Code, FileText } from 'lucide-react'

const SUGGESTIONS = [
  { icon: Calculator,   text: 'Explain solving quadratic equations step by step' },
  { icon: FlaskConical, text: 'How does photosynthesis work? Draw me a mind map' },
  { icon: Globe,        text: 'Summarise the causes of World War 1' },
  { icon: Code,         text: 'Teach me Python for loops with examples' },
  { icon: BookOpen,     text: 'Make a quiz on the solar system, medium difficulty' },
  { icon: FileText,     text: 'Create study notes on the French Revolution' },
]

export default function ChatPage() {
  const { id } = useParams()
  const {
    conversationId, messages, isStreaming,
    setConversationId, setMessages,
  } = useStore()
  const { sendMessage } = useChat()
  const bottomRef = useRef()

  // Load existing conversation when navigating to /chat/:id
  useEffect(() => {
    if (id && id !== conversationId) {
      setConversationId(id)
      getConversation(id).then(turns => {
        const msgs = turns.flatMap(t => ([
          { id: `u-${t.timestamp}`, role: 'user',      content: t.user, timestamp: t.timestamp },
          { id: `a-${t.timestamp}`, role: 'assistant', content: t.ai,   timestamp: t.timestamp, tools: [], extras: null },
        ]))
        setMessages(msgs)
      }).catch(() => setMessages([]))
    }
  }, [id])

  // Check for pending doc from DocsPage on mount
  useEffect(() => {
    const pendingRaw = sessionStorage.getItem('aria_pending_doc')
    if (pendingRaw) {
      // useChat.sendMessage handles this — trigger with empty text to pick it up
      sendMessage({ text: '' })
    }
  }, [])

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const isEmpty = messages.length === 0

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      {messages.length > 0 && (
        <div className="flex items-center justify-end px-4 py-1 border-b border-[#1a1a1a]">
          <ExportButton messages={messages} conversationId={conversationId} />
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        {isEmpty ? (
          <Welcome onSuggest={(text) => sendMessage({ text })} />
        ) : (
          <div className="max-w-3xl mx-auto px-4 py-6">
            {messages.map(msg => (
              <Message key={msg.id} msg={msg} />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input bar */}
      <div className="max-w-3xl mx-auto w-full px-4 pb-4">
        <ChatInput onSend={sendMessage} disabled={isStreaming} />
        <p className="text-center text-[10px] text-[#333] mt-2">
          All AI runs locally on your computer · Nothing is sent to the internet
        </p>
      </div>
    </div>
  )
}

function Welcome({ onSuggest }) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-4 py-8">
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#7c6af7] to-[#4f46e5] flex items-center justify-center mb-5 shadow-lg shadow-[#7c6af7]/20">
        <Zap size={30} className="text-white" />
      </div>
      <h1 className="text-2xl font-bold text-[#e8e8e8] mb-2">Hi! I'm ARIA 👋</h1>
      <p className="text-[#666] text-sm mb-8 text-center max-w-md leading-relaxed">
        Your personal AI study assistant. I can explain anything, solve maths,
        read your worksheets and homework, make quizzes, flashcards, mind maps, and more.
        All on your computer — completely private.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-xl">
        {SUGGESTIONS.map(({ icon: Icon, text }) => (
          <button
            key={text}
            onClick={() => onSuggest(text)}
            className="flex items-center gap-3 px-4 py-3 bg-[#141414] border border-[#2a2a2a] rounded-xl hover:border-[#7c6af7]/40 hover:bg-[#1a1a1a] transition-all text-left group"
          >
            <div className="w-7 h-7 rounded-lg bg-[#7c6af7]/10 flex items-center justify-center flex-shrink-0 group-hover:bg-[#7c6af7]/20 transition-colors">
              <Icon size={14} className="text-[#7c6af7]" />
            </div>
            <span className="text-xs text-[#888] group-hover:text-[#bbb] transition-colors">{text}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
