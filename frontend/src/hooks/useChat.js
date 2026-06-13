/**
 * useChat — custom hook that owns all streaming + orchestrator logic.
 * ChatPage just renders what this hook gives it.
 */
import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '../store'
import { streamChat, getConversations } from '../services/api'

export function useChat() {
  const navigate = useNavigate()
  const {
    conversationId,
    isStreaming,
    addMessage,
    updateLastMessage,
    setIsStreaming,
    setCurrentIntents,
    setConversationId,
    setConversations,
  } = useStore()

  const sendMessage = useCallback(async ({ text, image, document }) => {
    if (isStreaming) return
    if (!text?.trim() && !image && !document) return

    // Check for pending doc from DocsPage
    let docFile = document
    const pendingDocRaw = sessionStorage.getItem('aria_pending_doc')
    if (pendingDocRaw && !docFile) {
      try {
        const pending = JSON.parse(pendingDocRaw)
        sessionStorage.removeItem('aria_pending_doc')
        // Inject doc context into message
        text = `[Document: ${pending.name}]\n\n${pending.text.slice(0, 3000)}\n\n---\n\n${text || 'Please summarise this document and tell me the key points.'}`
      } catch {}
    }

    // User message bubble
    const userMsg = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text || '',
      imagePreview: image ? URL.createObjectURL(image) : null,
      docName: docFile?.name || null,
      timestamp: Date.now(),
    }
    addMessage(userMsg)

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
      timestamp: Date.now(),
    })
    setIsStreaming(true)

    try {
      await streamChat({
        message: text || '',
        conversationId,
        image,
        document: docFile,
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

            case 'status':
              // Status messages are shown in StatusBar — no action needed here
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
          // Mark streaming done
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

          if (newConvId && newConvId !== conversationId) {
            setConversationId(newConvId)
            navigate(`/chat/${newConvId}`, { replace: true })
            getConversations().then(setConversations).catch(() => {})
          }
        },
      })
    } catch (err) {
      useStore.setState(s => {
        const msgs = [...s.messages]
        const last = msgs[msgs.length - 1]
        if (last?.role === 'assistant') {
          msgs[msgs.length - 1] = {
            ...last,
            content: `❌ Connection error: ${err.message}\n\nMake sure Ollama is running: \`ollama serve\``,
            streaming: false,
          }
        }
        return { messages: msgs }
      })
      setIsStreaming(false)
      setCurrentIntents([])
    }
  }, [conversationId, isStreaming, navigate])

  return { sendMessage }
}
