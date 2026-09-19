/**
 * useChat — owns streaming. Persists across route changes:
 * the fetch lives in a module-level AbortController, updates go
 * directly to the global Zustand store, so navigating to /admin etc.
 * never aborts or loses the in-flight response.
 */
import { useCallback, useRef, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useStore } from '../store'
import { streamChat, getConversations } from '../services/api'
import { showToast } from '../components/Toast'

// Module-level — survives ChatPage unmount
let activeAbort = null
let activeBlobUrls = []

function trackBlobUrl(url) {
  if (!url) return
  activeBlobUrls.push(url)
  // Cap preview URLs to avoid unbounded memory growth — revoke oldest
  while (activeBlobUrls.length > 20) {
    const old = activeBlobUrls.shift()
    try { URL.revokeObjectURL(old) } catch {}
  }
}

export function revokeAllPreviewUrls() {
  for (const u of activeBlobUrls) {
    try { URL.revokeObjectURL(u) } catch {}
  }
  activeBlobUrls = []
}

function heuristicTitle(users) {
  if (!users.length) return 'New chat'
  if (users.length === 1) {
    const t = users[0].trim()
    return t.length > 55 ? t.slice(0, 55) + '…' : t
  }
  const first = users[0].trim()
  const last = users[users.length - 1].trim()
  if (last.length < 24 && users.length >= 2) {
    const combined = `${first.slice(0, 30).trim()} → ${last}`
    return combined.length > 60 ? combined.slice(0, 60) : combined
  }
  const firstWords = new Set(first.toLowerCase().split(/\s+/).slice(0, 8))
  const lastWords = new Set(last.toLowerCase().split(/\s+/).slice(0, 8))
  let overlap = 0; firstWords.forEach(w => { if (lastWords.has(w)) overlap++ })
  if (overlap === 0 && users.length >= 3) {
    const shortFirst = first.split(/\s+/).slice(0, 3).join(' ')
    const t = `${last.slice(0, 45).trim()} · ${shortFirst}…`
    return t.length > 60 ? t.slice(0, 60) : t
  }
  return last.length > 55 ? last.slice(0, 55) + '…' : last
}

export function useChat() {
  const navigate = useNavigate()
  const location = useLocation()
  const blobUrlsRef = useRef(activeBlobUrls)
  const {
    mode,
    addMessage,
    setIsStreaming,
    setCurrentIntents,
    setConversationId,
    setConversations,
  } = useStore()

  // Keep module ref in sync
  useEffect(() => { activeBlobUrls = blobUrlsRef.current }, [blobUrlsRef.current.length])

  // Only revoke on full app unmount, not on route change
  useEffect(() => {
    return () => {
      // Do NOT abort active stream on page change — let it continue in background
      // Blob URLs are kept until stream finishes or app closes
    }
  }, [])

  const sendMessage = useCallback(async ({ text, image, document, documents }) => {
    // Normalize to array — supports single or multiple PDFs
    const docList = documents && documents.length ? documents : (document ? [document] : [])
    const { isStreaming: streamingNow, conversationId: liveConvId } = useStore.getState()
    if (streamingNow) return
    if (!text?.trim() && !image && docList.length === 0) return
    const conversationId = liveConvId

    // pending doc from library (if any) — merges with attached docs
    let docFiles = [...docList]
    const pendingDocRaw = sessionStorage.getItem('aria_pending_doc')
    if (pendingDocRaw && docFiles.length === 0) {
      try {
        const pending = JSON.parse(pendingDocRaw)
        sessionStorage.removeItem('aria_pending_doc')
        text = `[Document: ${pending.name}]\n\n${(pending.text || '').slice(0, 3000)}\n\n---\n\n${text || 'Please summarise this document and tell me the key points.'}`
      } catch {
      try { sessionStorage.removeItem('aria_pending_doc') } catch {}
      console.warn('Failed to parse pending doc from library')
    }
    }

    // User message bubble — support multiple doc names
    const imagePreview = image ? URL.createObjectURL(image) : null
    if (imagePreview) trackBlobUrl(imagePreview)
    const userMsg = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text || '',
      imagePreview,
      docName: docFiles[0]?.name || null,
      docNames: docFiles.map(f => f.name),
      timestamp: Date.now(),
    }
    addMessage(userMsg)

    // Optimistic adaptive title (Gemini-style: title evolves as chat progresses)
    if (conversationId) {
      try {
        const { messages: curMsgs } = useStore.getState()
        // curMsgs already includes the new userMsg we just added
        const users = curMsgs.filter(m => m.role === 'user').map(m => m.content)
        const optimistic = heuristicTitle(users)
        useStore.getState().upsertConversationTitle?.(conversationId, optimistic, new Date().toISOString())
        // Also update via quick heuristic; server will refine with LLM later
      } catch (e) { console.warn('Optimistic title update failed:', e) }
    }

    // AI placeholder
    const aiId = `ai-${Date.now()}`
    addMessage({
      id: aiId,
      role: 'assistant',
      content: '',
      streaming: true,
      tools: [],
      extras: null,
      generatedImage: null,
      generatedDiagram: null,
      timestamp: Date.now(),
    })
    setIsStreaming(true)

    // Create an abort controller that outlives the component
    activeAbort = new AbortController()

    try {
      await streamChat({
        message: text || ' ',
        conversationId,
        image,
        document: docFiles[0] || null,
        documents: docFiles.length > 1 ? docFiles : null,
        mode,
        signal: activeAbort.signal,
        onChunk: (data) => {
          switch (data.type) {
            case 'intent':
              setCurrentIntents(data.content || [])
              break

            case 'text':
              // Append streamed token to last message
              useStore.setState(s => {
                const msgs = [...s.messages]
                const last = msgs[msgs.length - 1]
                if (last?.role === 'assistant') {
                  msgs[msgs.length - 1] = { ...last, content: last.content + data.content }
                }
                return { messages: msgs }
              })
              break

            case 'tool':
              useStore.setState(s => {
                const msgs = [...s.messages]
                const last = msgs[msgs.length - 1]
                if (last?.role === 'assistant') {
                  msgs[msgs.length - 1] = {
                    ...last,
                    tools: [...(last.tools || []), data],
                  }
                }
                return { messages: msgs }
              })
              break

            case 'extras':
              useStore.setState(s => {
                const msgs = [...s.messages]
                const last = msgs[msgs.length - 1]
                if (last?.role === 'assistant') {
                  msgs[msgs.length - 1] = { ...last, extras: data.content }
                }
                return { messages: msgs }
              })
              break

            case 'verification':
              useStore.setState(s => {
                const msgs = [...s.messages]
                const last = msgs[msgs.length - 1]
                if (last?.role === 'assistant') {
                  msgs[msgs.length - 1] = { ...last, verification: data.content }
                }
                return { messages: msgs }
              })
              break

            case 'suggestions':
              useStore.setState(s => {
                const msgs = [...s.messages]
                const last = msgs[msgs.length - 1]
                if (last?.role === 'assistant') {
                  msgs[msgs.length - 1] = { ...last, suggestions: data.content }
                }
                return { messages: msgs }
              })
              break

            case 'sources':
              useStore.setState(s => {
                const msgs = [...s.messages]
                const last = msgs[msgs.length - 1]
                if (last?.role === 'assistant') {
                  msgs[msgs.length - 1] = { ...last, sources: data.content }
                }
                return { messages: msgs }
              })
              break

            case 'citations':
              useStore.setState(s => {
                const msgs = [...s.messages]
                const last = msgs[msgs.length - 1]
                if (last?.role === 'assistant') {
                  msgs[msgs.length - 1] = { ...last, citations: data.content }
                }
                return { messages: msgs }
              })
              break

            case 'image':
              useStore.setState(s => {
                const msgs = [...s.messages]
                const last = msgs[msgs.length - 1]
                if (last?.role === 'assistant') {
                  msgs[msgs.length - 1] = { ...last, generatedImage: data.content }
                }
                return { messages: msgs }
              })
              break

            case 'diagram':
              useStore.setState(s => {
                const msgs = [...s.messages]
                const last = msgs[msgs.length - 1]
                if (last?.role === 'assistant') {
                  msgs[msgs.length - 1] = { ...last, generatedDiagram: data.content }
                }
                return { messages: msgs }
              })
              break

            case 'status':
              break

            case 'achievement':
              // Gamification: new achievements earned during this chat
              if (data.content?.new?.length) {
                for (const a of data.content.new) {
                  showToast(`${a.icon} Achievement unlocked: ${a.name}!`, 'success', 4000)
                }
                // Update game progress in store
                useStore.getState().setGameProgress?.({
                  xp: data.content.xp,
                  level: data.content.level,
                })
              }
              break

            case 'progress':
              // Update global progress bar
              useStore.getState().setProgress?.(data)
              break

            case 'done':
              useStore.getState().clearProgress?.()
              break

            case 'title':
              // Adaptive title from backend (heuristic + LLM refinement)
              if (data.content && data.conversation_id) {
                useStore.getState().updateConversationTitle?.(data.conversation_id, data.content)
                // Also ensure conversations list has entry for new chats
                const exists = useStore.getState().conversations.find(c => c.id === data.conversation_id)
                if (!exists) {
                  useStore.getState().upsertConversationTitle?.(data.conversation_id, data.content, new Date().toISOString())
                }
              } else if (data.content) {
                // Fallback: update current conversation
                const cur = useStore.getState().conversationId || conversationId
                if (cur) useStore.getState().updateConversationTitle?.(cur, data.content)
              }
              break

            case 'error':
              useStore.setState(s => {
                const msgs = [...s.messages]
                const last = msgs[msgs.length - 1]
                if (last?.role === 'assistant') {
                  msgs[msgs.length - 1] = {
                    ...last,
                    content: last.content || `⚠️ ${data.content}`,
                    streaming: false,
                  }
                }
                return { messages: msgs }
              })
              break

            default:
              break
          }
        },
        onDone: (newConvId) => {
          useStore.setState(s => {
            const msgs = [...s.messages]
            const last = msgs[msgs.length - 1]
            if (last?.role === 'assistant') {
              msgs[msgs.length - 1] = { ...last, streaming: false }
            }
            return { messages: msgs }
          })
          setIsStreaming(false)
          setCurrentIntents([])
          activeAbort = null

          const { conversationId: curId, messages: finalMsgs } = useStore.getState()
          if (newConvId && newConvId !== curId) {
            setConversationId(newConvId)
            // For brand-new chat, seed optimistic title from first user message
            try {
              const users = finalMsgs.filter(m => m.role === 'user').map(m => m.content)
              if (users.length) {
                const seed = heuristicTitle(users)
                useStore.getState().upsertConversationTitle?.(newConvId, seed, new Date().toISOString())
              }
            } catch (e) { console.warn('Title seed failed:', e) }
            if (location.pathname.startsWith('/chat')) {
              navigate(`/chat/${newConvId}`, { replace: true })
            }
            // Fetch authoritative titles (heuristic + LLM) — slight delay to let LLM title persist
            setTimeout(() => getConversations().then(setConversations).catch((e) => console.warn('Refresh conversations failed:', e)), 800)
            getConversations().then(setConversations).catch((e) => console.warn('Refresh conversations failed:', e))
          } else if (newConvId) {
            // Existing chat — refresh list to pick up LLM-refined title (with small delay for background task)
            setTimeout(() => getConversations().then(setConversations).catch((e) => console.warn('Refresh conversations failed:', e)), 1200)
            getConversations().then(setConversations).catch((e) => console.warn('Refresh conversations failed:', e))
          }
        },
      })
    } catch (err) {
      if (err.name === 'AbortError') {
        useStore.setState(s => {
          const msgs = [...s.messages]
          const last = msgs[msgs.length - 1]
          if (last?.role === 'assistant' && last.streaming) {
            const appended = last.content ? last.content + "\n\n— Stopped." : "Response stopped."
            msgs[msgs.length - 1] = { ...last, content: appended, streaming: false }
          }
          return { messages: msgs }
        })
        setIsStreaming(false)
        setCurrentIntents([])
        useStore.getState().clearProgress?.()
        activeAbort = null
        return
      }
      useStore.setState(s => {
        const msgs = [...s.messages]
        const last = msgs[msgs.length - 1]
        if (last?.role === 'assistant') {
          msgs[msgs.length - 1] = {
            ...last,
            content: `❌ Connection error: ${err.message}\n\nMake sure Ollama is running: \`ollama serve\``,
            streaming: false,
          }        }
        return { messages: msgs }
      })
      setIsStreaming(false)
      setCurrentIntents([])
      activeAbort = null
    }
  }, [mode, navigate, location.pathname])

  return { sendMessage }
}

export function getActiveAbort() {
  return activeAbort
}
