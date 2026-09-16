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
  progress: null, // {pct, label, step, status}
  progressSteps: [], // array of {step, label, status}
  ollamaStatus: 'checking', // 'ok' | 'error' | 'checking'
  mode: 'normal', // 'normal' | 'think' | 'fast' | 'socratic' | 'roleplay' | 'hype'
  gameProgress: null, // {xp, level} — live updated from achievement events

  setGameProgress: (data) => set({ gameProgress: data }),

  // Config — single main model (gemma) + nomic for embeddings
  config: {
    model: 'gemma4:e4b-mlx',
    reasoning_model: 'gemma4:e4b-mlx',
    vision_model: 'gemma4:e4b-mlx',
    fallback_model: 'gemma4:e4b-mlx',
    coding_model: 'gemma4:e4b-mlx',
    embedding_model: 'nomic-embed-text',
    student_name: 'Student',
    student_age: 13,
  },

  // UI preferences (persisted)
  uiPrefs: (() => {
    try {
      return JSON.parse(localStorage.getItem('aria_ui_prefs') || '{"fontSize":"md","contrast":false}')
    } catch { return { fontSize: 'md', contrast: false } }
  })(),
  setUiPrefs: (patch) => set(s => {
    const next = { ...s.uiPrefs, ...patch }
    try { localStorage.setItem('aria_ui_prefs', JSON.stringify(next)) } catch {}
    return { uiPrefs: next }
  }),

  // Sidebar
  conversations: [],
  pinnedChats: [],

  // ── Study Tool Persistence ──────────────────────────────────────────────────
  // Persists generated content across page navigations (planner/studyTools removed → brain)
  studyTools: {
    quiz: { questions: [], current: 0, selected: null, score: 0, done: false, answers: [], topic: '', level: 'medium', count: 5 },
    flashcards: { cards: [], order: [], idx: 0, flipped: false, known: [], topic: '', count: 10 },
    youtube: { result: null, quiz: null, flashcards: null, url: '' },
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
  setIsStreaming: (v) => set({ isStreaming: v, ...(v ? {} : { progress: null, progressSteps: [] }) }),
  // ── Background tasks (survive page navigation — see services/tasks.js) ─────
  // bgTasks: { [key]: { label, page, topic, status, error, startedAt, finishedAt, runId } }
  bgTasks: {},
  setBgTask: (key, patch) => set(s => ({
    bgTasks: { ...s.bgTasks, [key]: { ...(s.bgTasks[key] || {}), ...patch } },
  })),
  clearBgTask: (key) => set(s => {
    if (!s.bgTasks[key]) return {}
    const next = { ...s.bgTasks }
    delete next[key]
    return { bgTasks: next }
  }),
  // Patch one message by id (e.g. background Visualize result landing in chat)
  updateMessage: (id, patch) => set(s => {
    const msgs = s.messages.map(m => (m.id === id ? { ...m, ...patch } : m))
    if (s.conversationId) saveMsgCache(s.conversationId, msgs)
    return { messages: msgs }
  }),
  setCurrentIntents: (v) => set({ currentIntents: v }),
  setProgress: (p) => set(s => {
    const steps = [...(s.progressSteps || [])]
    const idx = steps.findIndex(x => x.step === p.step)
    if (idx >= 0) steps[idx] = p
    else steps.push(p)
    return { progress: p, progressSteps: steps }
  }),
  clearProgress: () => set({ progress: null, progressSteps: [] }),
  setOllamaStatus: (v) => set({ ollamaStatus: v }),
  setConfig: (c) => set({ config: c }),
  setConversations: (c) => set({ conversations: c }),
  setMode: (m) => set({ mode: m }),
  newConversation: () => set({ conversationId: null, messages: [], currentIntents: [], progress: null, progressSteps: [] }),
  togglePin: (id) => set(s => {
    const pinned = s.pinnedChats.includes(id)
      ? s.pinnedChats.filter(p => p !== id)
      : [...s.pinnedChats, id]
    return { pinnedChats: pinned }
  }),
  // Adaptive title — live update from SSE / optimistic heuristic (Gemini: active chat bubbles to top)
  updateConversationTitle: (id, title) => set(s => {
    const idx = s.conversations.findIndex(c => c.id === id)
    if (idx === -1) return {}
    const updated = { ...s.conversations[idx], title }
    // Move to front for recency unless pinned (pinned stays, but we still bump within recent)
    const rest = s.conversations.filter(c => c.id !== id)
    // Keep pinned items at top in original order — insert updated after pinned block
    const pinnedCount = rest.filter(c => s.pinnedChats.includes(c.id)).length
    const before = rest.slice(0, pinnedCount)
    const after = rest.slice(pinnedCount)
    return { conversations: [...before, updated, ...after] }
  }),
  upsertConversationTitle: (id, title, timestamp) => set(s => {
    const exists = s.conversations.find(c => c.id === id)
    const ts = timestamp || new Date().toISOString()
    if (exists) {
      const updated = { ...exists, title, last_timestamp: ts, timestamp: exists.timestamp }
      const rest = s.conversations.filter(c => c.id !== id)
      const pinnedCount = rest.filter(c => s.pinnedChats.includes(c.id)).length
      const before = rest.slice(0, pinnedCount)
      const after = rest.slice(pinnedCount)
      return { conversations: [...before, updated, ...after] }
    }
    return { conversations: [{ id, title, timestamp: ts, last_timestamp: ts, turn_count: 1 }, ...s.conversations] }
  }),
}))
