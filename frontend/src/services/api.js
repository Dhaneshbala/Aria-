const BASE = '/api'

async function apiFetch(url, options = {}) {
  const resp = await fetch(url, options)
  if (!resp.ok) {
    const text = await resp.text().catch(() => resp.statusText)
    throw new Error(`API error ${resp.status}: ${text}`)
  }
  return resp
}

// ── Chat (SSE streaming) ──────────────────────────────────────────────────────

export async function streamChat({ message, conversationId, image, document, onChunk, onDone, mode = 'normal' }) {
  const form = new FormData()
  form.append('message', message)
  if (conversationId) form.append('conversation_id', conversationId)
  if (image) form.append('image', image)
  if (document) form.append('document', document)
  form.append('mode', mode)

  const resp = await apiFetch(`${BASE}/chat`, { method: 'POST', body: form })

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
        } catch (e) {
          console.warn('SSE parse error:', e)
        }
      }
    }
  }
  onDone(newConvId)
}

// ── Conversations ─────────────────────────────────────────────────────────────

export const getConversations = () =>
  apiFetch(`${BASE}/chat/conversations`).then(r => r.json())

export const getConversation = (id) =>
  apiFetch(`${BASE}/chat/conversations/${id}`).then(r => r.json())

export const deleteConversation = (id) =>
  apiFetch(`${BASE}/chat/conversations/${id}`, { method: 'DELETE' }).then(r => r.json())

// ── Study ─────────────────────────────────────────────────────────────────────

export const generateQuiz = (topic, level = 'medium', count = 5) =>
  apiFetch(`${BASE}/study/quiz`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, level, count }),
  }).then(r => r.json())

export const generateFlashcards = (topic, count = 10) =>
  apiFetch(`${BASE}/study/flashcards`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, count }),
  }).then(r => r.json())

export const generateMindmap = (topic) =>
  apiFetch(`${BASE}/study/mindmap`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic }),
  }).then(r => r.json())

export const generateStudyPlan = (topic, days = 7) =>
  apiFetch(`${BASE}/study/study-plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, days }),
  }).then(r => r.json())

export const checkAnswer = (subject, correct) =>
  apiFetch(`${BASE}/study/quiz/check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ subject, correct }),
  }).then(r => r.json())

export const generateNotes = (topic, style = 'structured') =>
  apiFetch(`${BASE}/study/notes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, level: style }),
  }).then(r => r.json())

export const generateExam = (topic, count = 10) =>
  apiFetch(`${BASE}/study/exam`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, count }),
  }).then(r => r.json())

export const generateEssayFeedback = (essay, topic = '') =>
  apiFetch(`${BASE}/study/essay-feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ essay, topic }),
  }).then(r => r.json())

export const generateFormula = (topic) =>
  apiFetch(`${BASE}/study/formula`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic }),
  }).then(r => r.json())

export const generateTimeline = (topic) =>
  apiFetch(`${BASE}/study/timeline`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic }),
  }).then(r => r.json())

// ── Research ──────────────────────────────────────────────────────────────────

export const webSearch = (query) =>
  apiFetch(`${BASE}/research/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  }).then(r => r.json())

export const processYouTube = (url) =>
  apiFetch(`${BASE}/research/youtube`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  }).then(r => r.json())

// ── Image generation ──────────────────────────────────────────────────────────

export const generateImage = (prompt) =>
  apiFetch(`${BASE}/imagegen/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt }),
  }).then(r => r.json())

// ── Admin ─────────────────────────────────────────────────────────────────────

export const getConfig = () => apiFetch(`${BASE}/admin/config`).then(r => r.json())
export const saveConfig = (data) =>
  apiFetch(`${BASE}/admin/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }).then(r => r.json())
export const getModels = () => apiFetch(`${BASE}/admin/models`).then(r => r.json())
export const getHealth = () => apiFetch(`${BASE}/admin/health`).then(r => r.json())
export const getProfile = () => apiFetch(`${BASE}/admin/profile`).then(r => r.json())

// ── Voice ─────────────────────────────────────────────────────────────────────

export const transcribeAudio = (blob) => {
  const form = new FormData()
  form.append('audio', blob, 'recording.webm')
  return apiFetch(`${BASE}/voice/transcribe`, { method: 'POST', body: form }).then(r => r.json())
}

// ── Memory management ─────────────────────────────────────────────────────────

export const clearAllMemory = () =>
  apiFetch(`${BASE}/admin/memory/all`, { method: 'DELETE' }).then(r => r.json())

export const exportConversation = (id) =>
  apiFetch(`${BASE}/admin/export/${id}`).then(r => r.json())

export const generatePptx = async (topic, slides = 10) => {
  const resp = await apiFetch(`${BASE}/study/pptx`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, count: slides }),
  })
  const blob = await resp.blob()
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href     = url
  a.download = `ARIA-${topic.replace(/\s+/g, '-')}.pptx`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 5000)
}
