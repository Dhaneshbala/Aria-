import { create } from 'zustand'

export const useStore = create((set, get) => ({
  // Current conversation
  conversationId: null,
  messages: [],
  isStreaming: false,
  currentIntents: [],
  ollamaStatus: 'checking', // 'ok' | 'error' | 'checking'

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

  setConversationId: (id) => set({ conversationId: id }),
  setMessages: (msgs) => set({ messages: msgs }),
  addMessage: (msg) => set(s => ({ messages: [...s.messages, msg] })),
  updateLastMessage: (patch) => set(s => {
    const msgs = [...s.messages]
    if (msgs.length > 0) {
      msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], ...patch }
    }
    return { messages: msgs }
  }),
  setIsStreaming: (v) => set({ isStreaming: v }),
  setCurrentIntents: (v) => set({ currentIntents: v }),
  setOllamaStatus: (v) => set({ ollamaStatus: v }),
  setConfig: (c) => set({ config: c }),
  setConversations: (c) => set({ conversations: c }),
  newConversation: () => set({ conversationId: null, messages: [], currentIntents: [] }),
  togglePin: (id) => set(s => {
    const pinned = s.pinnedChats.includes(id)
      ? s.pinnedChats.filter(p => p !== id)
      : [...s.pinnedChats, id]
    return { pinnedChats: pinned }
  }),
}))
