import { create } from 'zustand'

// Message persistence helpers
const MSG_CACHE_KEY = 'aria_msg_cache'
function loadMsgCache() {
  try { return JSON.parse(sessionStorage.getItem(MSG_CACHE_KEY) || '{}') } catch { return {} }
}
function saveMsgCache(convId, msgs) {
  if (!convId || !msgs.length) return
  const cache = loadMsgCache()
  cache[convId] = msgs.slice(-100) // keep last 100 messages
  sessionStorage.setItem(MSG_CACHE_KEY, JSON.stringify(cache))
}
function getCachedMsgs(convId) {
  return loadMsgCache()[convId] || []
}

export const useStore = create((set, get) => ({
  // Current conversation
  conversationId: null,
  messages: [],
  isStreaming: false,
  currentIntents: [],
  ollamaStatus: 'checking', // 'ok' | 'error' | 'checking'
  mode: 'normal', // 'normal' | 'think' | 'fast'

  // Config
  config: {
    reasoning_model: 'qwen3:14b',
    vision_model: 'qwen2.5vl:7b',
    fallback_model: 'llama3.2',
    student_name: 'Student',
  },

  // Sidebar
  conversations: [],
  pinnedChats: [],

  // ── Study Tool Persistence ──────────────────────────────────────────────────
  // Persists generated content across page navigations
  studyTools: {
    quiz: { questions: [], current: 0, selected: null, score: 0, done: false, answers: [], topic: '', level: 'medium', count: 5 },
    flashcards: { cards: [], order: [], idx: 0, flipped: false, known: [], topic: '', count: 10 },
    mindmap: { data: null, topic: '' },
    studyPlan: { plan: [], checked: {}, topic: '', days: 7 },
    youtube: { result: null, quiz: null, flashcards: null, url: '' },
    studyTools: { result: '', activeTool: 'essay', assessResult: null, assessChecked: {} },
  },
  setStudyTool: (tool, data) => set(s => ({
    studyTools: { ...s.studyTools, [tool]: { ...s.studyTools[tool], ...data } },
  })),
  getStudyTool: (tool) => get().studyTools[tool] || {},

  setConversationId: (id) => {
    // Save current messages before switching
    const { conversationId, messages } = get()
    if (conversationId && messages.length) {
      saveMsgCache(conversationId, messages)
    }
    // Load cached messages for new conversation
    const cached = id ? getCachedMsgs(id) : []
    set({ conversationId: id, messages: cached })
  },
  setMessages: (msgs) => {
    set({ messages: msgs })
    const { conversationId } = get()
    if (conversationId) saveMsgCache(conversationId, msgs)
  },
  addMessage: (msg) => set(s => {
    const msgs = [...s.messages, msg]
    if (s.conversationId) saveMsgCache(s.conversationId, msgs)
    return { messages: msgs }
  }),
  updateLastMessage: (patch) => set(s => {
    const msgs = [...s.messages]
    if (msgs.length > 0) {
      msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], ...patch }
    }
    if (s.conversationId) saveMsgCache(s.conversationId, msgs)
    return { messages: msgs }
  }),
  setIsStreaming: (v) => set({ isStreaming: v }),
  setCurrentIntents: (v) => set({ currentIntents: v }),
  setOllamaStatus: (v) => set({ ollamaStatus: v }),
  setConfig: (c) => set({ config: c }),
  setConversations: (c) => set({ conversations: c }),
  setMode: (m) => set({ mode: m }),
  newConversation: () => set({ conversationId: null, messages: [], currentIntents: [] }),
  togglePin: (id) => set(s => {
    const pinned = s.pinnedChats.includes(id)
      ? s.pinnedChats.filter(p => p !== id)
      : [...s.pinnedChats, id]
    return { pinnedChats: pinned }
  }),
}))
