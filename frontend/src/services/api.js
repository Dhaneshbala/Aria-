const BASE = '/api'

// ── Chat (SSE streaming) ──────────────────────────────────────────────────────

export async function streamChat({ message, conversationId, image, document, onChunk, onDone }) {
  const form = new FormData()
  form.append('message', message)
  if (conversationId) form.append('conversation_id', conversationId)
  if (image) form.append('image', image)
  if (document) form.append('document', document)

  const resp = await fetch(`${BASE}/chat`, { method: 'POST', body: form })
  if (!resp.ok) throw new Error(`Chat error: ${resp.status}`)

  const newConvId = resp.headers.get('X-Conversation-Id')
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop()
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6))
          onChunk(data)
          if (data.type === 'done') { onDone(newConvId); return }
        } catch {}
      }
    }
  }
  onDone(newConvId)
}

// ── Conversations ─────────────────────────────────────────────────────────────

export const getConversations = () =>
  fetch(`${BASE}/chat/conversations`).then(r => r.json())

export const getConversation = (id) =>
  fetch(`${BASE}/chat/conversations/${id}`).then(r => r.json())

export const deleteConversation = (id) =>
  fetch(`${BASE}/chat/conversations/${id}`, { method: 'DELETE' }).then(r => r.json())

// ── Study ─────────────────────────────────────────────────────────────────────

export const generateQuiz = (topic, level = 'medium', count = 5) =>
  fetch(`${BASE}/study/quiz`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, level, count }),
  }).then(r => r.json())

export const generateFlashcards = (topic, count = 10) =>
  fetch(`${BASE}/study/flashcards`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, count }),
  }).then(r => r.json())

export const generateMindmap = (topic) =>
  fetch(`${BASE}/study/mindmap`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic }),
  }).then(r => r.json())

export const generateStudyPlan = (topic, days = 7) =>
  fetch(`${BASE}/study/study-plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, days }),
  }).then(r => r.json())

export const checkAnswer = (subject, correct) =>
  fetch(`${BASE}/study/quiz/check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ subject, correct }),
  }).then(r => r.json())

// ── Research ──────────────────────────────────────────────────────────────────

export const webSearch = (query) =>
  fetch(`${BASE}/research/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  }).then(r => r.json())

export const processYouTube = (url) =>
  fetch(`${BASE}/research/youtube`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  }).then(r => r.json())

// ── Image generation ──────────────────────────────────────────────────────────

export const generateImage = (prompt) =>
  fetch(`${BASE}/imagegen/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt }),
  }).then(r => r.json())

// ── Admin ─────────────────────────────────────────────────────────────────────

export const getConfig = () => fetch(`${BASE}/admin/config`).then(r => r.json())
export const saveConfig = (data) =>
  fetch(`${BASE}/admin/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }).then(r => r.json())
export const getModels = () => fetch(`${BASE}/admin/models`).then(r => r.json())
export const getHealth = () => fetch(`${BASE}/admin/health`).then(r => r.json())
export const getProfile = () => fetch(`${BASE}/admin/profile`).then(r => r.json())

// ── Voice ─────────────────────────────────────────────────────────────────────

export const transcribeAudio = (blob) => {
  const form = new FormData()
  form.append('audio', blob, 'recording.webm')
  return fetch(`${BASE}/voice/transcribe`, { method: 'POST', body: form }).then(r => r.json())
}

// ── Study extras ──────────────────────────────────────────────────────────────

export const generateNotes = (topic, style = 'structured') =>
  fetch(`${BASE}/study/notes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, level: style }),
  }).then(r => r.json())

export const generateExam = (topic, count = 10) =>
  fetch(`${BASE}/study/exam`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, count }),
  }).then(r => r.json())

// ── Memory management ─────────────────────────────────────────────────────────

export const clearAllMemory = () =>
  fetch(`${BASE}/admin/memory/all`, { method: 'DELETE' }).then(r => r.json())

export const exportConversation = (id) =>
  fetch(`${BASE}/admin/export/${id}`).then(r => r.json())
export const generatePptx = async (topic, slides = 10) => {
  const resp = await fetch(`${BASE}/study/pptx`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, count: slides }),
  })
  const blob = await resp.blob()
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href     = url
  a.download = `ARIA-${topic}.pptx`
  a.click()
}
