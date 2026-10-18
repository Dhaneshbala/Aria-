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

  const sendMessage = useCallback(async ({ text, image, document, documents, isRetry }) => {
    // Normalize to array — supports single or multiple PDFs
    const docList = documents && documents.length ? documents : (document ? [document] : [])
    const { isStreaming: streamingNow, conversationId: liveConvId } = useStore.getState()
    if (streamingNow) return
    if (!isRetry && !text?.trim() && !image && docList.length === 0) return
    const conversationId = liveConvId

    // Attached docs (single or multi)
    const docFiles = [...docList]

    // User message bubble — support multiple doc names
    // (skipped on retry: the earlier user message is still on screen)
    if (!isRetry) {
      const imagePreview = image ? URL.createObjectURL(image) : null
      if (imagePreview) blobUrlsRef.current.push(imagePreview)
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
        } catch {}
      }
    }

    // AI placeholder — on retry, reset the failed bubble instead of stacking a new one
    const aiId = `ai-${Date.now()}`
    if (isRetry) {
      useStore.setState(s => {
        const msgs = [...s.messages]
        const idx = msgs.findLastIndex?.(m => m.role === 'assistant')
          ?? msgs.map(m => m.role).lastIndexOf('assistant')
        if (idx >= 0) {
          msgs[idx] = { ...msgs[idx], content: '', streaming: true, failed: false, retryPayload: null, tools: [], extras: null, generatedImage: null, generatedDiagram: null, timestamp: Date.now() }
        } else {
          msgs.push({ id: aiId, role: 'assistant', content: '', streaming: true, tools: [], extras: null, generatedImage: null, generatedDiagram: null, timestamp: Date.now() })
        }
        return { messages: msgs }
      })
    } else {
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
    }
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
          // Revoke stale blob URLs (keep previews still referenced by messages)
          try {
            const live = new Set(useStore.getState().messages.map(m => m.imagePreview).filter(Boolean))
            blobUrlsRef.current.forEach(u => { if (!live.has(u)) { try { URL.revokeObjectURL(u) } catch {} } })
            blobUrlsRef.current = blobUrlsRef.current.filter(u => live.has(u))
            activeBlobUrls = blobUrlsRef.current
          } catch {}

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
            } catch {}
            if (location.pathname.startsWith('/chat')) {
              navigate(`/chat/${newConvId}`, { replace: true })
            }
            // Fetch authoritative titles (heuristic + LLM) — slight delay to let LLM title persist
            setTimeout(() => getConversations().then(setConversations).catch((e) => console.warn('conversation refresh failed', e)), 800)
          } else if (newConvId) {
            // Existing chat — refresh list to pick up LLM-refined title (with small delay for background task)
            setTimeout(() => getConversations().then(setConversations).catch((e) => console.warn('conversation refresh failed', e)), 1200)
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
      const offline = typeof navigator !== 'undefined' && navigator.onLine === false
      const hint = offline
        ? 'You appear to be offline. Reconnect and try again — your chats are saved.'
        : 'Check that ARIA is running on your Mac (`./start.sh`), then retry below.'
      useStore.setState(s => {
        const msgs = [...s.messages]
        const last = msgs[msgs.length - 1]
        if (last?.role === 'assistant') {
          msgs[msgs.length - 1] = {
            ...last,
            content: `⚠️ ${err.message || 'Request failed'}\n\n${hint}`,
            streaming: false,
            failed: true,
            retryPayload: { text, image, documents: docFiles.length ? docFiles : null },
          }
        }
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
