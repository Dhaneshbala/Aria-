const BASE = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '')

// Exposed so pages that build their own URLs (e.g. SyllabusPage) share one
// base-URL definition and one auth/error path.
export const API_BASE = BASE

export async function apiFetch(url, options = {}) {
  const headers = { ...(options.headers || {}) }
  try {
    const token = localStorage.getItem('aria_api_token')
    if (token) headers.Authorization = `Bearer ${token}`
  } catch {}
  const resp = await fetch(url, { ...options, headers })
  if (!resp.ok) {
    const text = await resp.text().catch(() => resp.statusText)
    throw new Error(`API error ${resp.status}: ${text}`)
  }
  return resp
}

// ── Chat (SSE streaming) ──────────────────────────────────────────────────────

export async function streamChat({ message, conversationId, image, document, documents, onChunk, onDone, mode = 'normal', signal }) {
  const form = new FormData()
  form.append('message', message)
  if (conversationId) form.append('conversation_id', conversationId)
  if (image) form.append('image', image)
  if (document) form.append('document', document)
  if (documents && documents.length) {
    documents.forEach(d => form.append('documents', d))
  }
  form.append('mode', mode)

  const resp = await apiFetch(`${BASE}/chat`, { method: 'POST', body: form, signal })

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
        } catch {
          // SSE parse error — ignore partial chunks
        }
      }
    }
  }
  onDone(newConvId)
}

import { validate, Schemas } from './schemas'

// ── Conversations ─────────────────────────────────────────────────────────────

export const getConversations = () =>
  apiFetch(`${BASE}/chat/conversations`).then(r => r.json()).then(d =>
    Array.isArray(d) ? d.map(c => validate(Schemas.conversationSchema, c, 'conversation')) : d)

export const getConversation = (id) =>
  apiFetch(`${BASE}/chat/conversations/${id}`).then(r => r.json())

export const deleteConversation = (id) =>
  apiFetch(`${BASE}/chat/conversations/${id}`, { method: 'DELETE' }).then(r => r.json())

export const searchConversations = (query) =>
  apiFetch(`${BASE}/chat/search?q=${encodeURIComponent(query)}`).then(r => r.json())

// ── Study ─────────────────────────────────────────────────────────────────────

export const generateQuiz = (topic, level = 'medium', count = 5, verify = true, signal) => {
  // Quiz is verified by default (as requested) — ~8-12s for 5q via parallel checks.
  // No auto-quit timeout; caller may still pass signal for manual cancel.
  const opts = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, level, count, verify }),
  }
  if (signal) opts.signal = signal
  return apiFetch(`${BASE}/study/quiz`, opts).then(r => r.json())
}

export const generateFlashcards = (topic, count = 10, signal) => {
  const opts = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, count }),
  }
  if (signal) opts.signal = signal
  return apiFetch(`${BASE}/study/flashcards`, opts).then(r => r.json())
}

export const checkAnswer = (subject, correct, extra = {}) =>
  apiFetch(`${BASE}/study/quiz/check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ subject, correct, ...extra }),
  }).then(r => r.json())

export const getDueMistakes = (limit = 20) =>
  apiFetch(`${BASE}/v2/mistakes/due?limit=${limit}`).then(r => r.json())

export const reviewMistake = (id, correct) =>
  apiFetch(`${BASE}/v2/mistakes/${id}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ correct }),
  }).then(r => r.json())

export const generateCheatsheet = (topic, subject = '', signal) => {
  const opts = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, subject }),
  }
  if (signal) opts.signal = signal
  return apiFetch(`${BASE}/study/cheatsheet`, opts).then(r => r.json())
}

// ── Quiz streaming (each verified question arrives as it's done) ───────────

export async function streamQuiz({ topic, level = 'medium', count = 5, signal, onTotal, onQuestion, onProgress }) {
  // Same streaming reader as streamChat but over apiFetch so the LAN
  // bearer token and central error handling apply here too.
  const resp = await apiFetch(`${BASE}/study/quiz/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, level, count, verify: true }),
    signal,
  })
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  const questions = []
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop()
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      let data
      try { data = JSON.parse(line.slice(6)) } catch { continue }
      if (data.type === 'total') onTotal?.(data.total)
      else if (data.type === 'question') { questions.push(data.question); onQuestion?.(data.question, questions.length) }
      else if (data.type === 'progress') onProgress?.(data.done, data.total)
      else if (data.type === 'error') throw new Error(data.content || 'Quiz stream failed')
      else if (data.type === 'done') return { questions: data.questions?.length ? data.questions : questions }
    }
  }
  return { questions }
}

// ── Exam countdown plans ────────────────────────────────────────────────────

export const createExamPlan = (exam_name, exam_date, subjects, mins_per_day = 45, signalOrExtra, maybeExtra) => {
  // Backward compat: createExamPlan(name, date, subs, mins, signal)
  // New: createExamPlan(name, date, subs, mins, {assessment_text, assessment_topics, assessment_summary, weighting, task_type}, signal)
  let signal = signalOrExtra
  let extra = maybeExtra
  if (signalOrExtra && typeof signalOrExtra === 'object' && !(signalOrExtra instanceof AbortSignal)) {
    extra = signalOrExtra
    signal = maybeExtra
  }
  const opts = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ exam_name, exam_date, subjects, mins_per_day, ...(extra || {}) }),
  }
  if (signal) opts.signal = signal
  return apiFetch(`${BASE}/study/exam-plan`, opts).then(r => r.json())
}

export const getPlanReadiness = (planId) =>
  apiFetch(`${BASE}/study/exam-plans/${planId}/readiness`).then(r => r.json())

export const getPlanPracticeSet = (planId, count = 5, level = 'hard') =>
  apiFetch(`${BASE}/study/exam-plans/${planId}/practice-set`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ count, level }),
  }).then(r => r.json())

// ── Maths Accelerator (selective 5.3 + Ext bridge) ──────────────────────────

export const getMathsTopics = () =>
  apiFetch(`${BASE}/maths/topics`).then(r => r.json())

export const generateMathsSet = (topic_id, tier = 'selective', count = 5, signal) => {
  const opts = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic_id, tier, count }),
  }
  if (signal) opts.signal = signal
  return apiFetch(`${BASE}/maths/generate`, opts).then(r => r.json())
}

export const submitMathsSet = (
  topic_id,
  tier,
  correct,
  total,
  mistakes = [],
  session_id = null,
  marks = []
) =>
  apiFetch(`${BASE}/maths/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic_id, tier, correct, total, mistakes, session_id, marks }),
  }).then(r => r.json())

export const getMathsMastery = () =>
  apiFetch(`${BASE}/maths/mastery`).then(r => r.json())

export const parseAssessmentNotification = (file) => {
  const form = new FormData()
  form.append('file', file)
  return apiFetch(`${BASE}/study/exam-plan/parse-notification`, { method: 'POST', body: form }).then(r => r.json())
}

export const listExamPlans = () =>
  apiFetch(`${BASE}/study/exam-plans`).then(r => r.json())

export const deleteExamPlan = (id) =>
  apiFetch(`${BASE}/study/exam-plans/${id}`, { method: 'DELETE' }).then(r => r.json())

// ── Spaced Repetition ────────────────────────────────────────────────────────

export const addSrCard = (front, back, subject = 'general') =>
  apiFetch(`${BASE}/v2/study/add-card`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ front, back, subject }),
  }).then(r => r.json())

export const bulkAddSrCards = (cards, subject = 'general') =>
  apiFetch(`${BASE}/v2/study/bulk-add-cards`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cards, subject }),
  }).then(r => r.json())

export const deleteSrCard = (card_id) =>
  apiFetch(`${BASE}/v2/study/delete-card`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ card_id }),
  }).then(r => r.json())

export const getDueCards = (limit = 20) =>
  apiFetch(`${BASE}/v2/study/due-cards?limit=${limit}`).then(r => r.json())

export const getSrStats = () =>
  apiFetch(`${BASE}/v2/study/sr-stats`).then(r => r.json())

export const importSrCsv = (file, subject = 'general') => {
  const form = new FormData()
  form.append('file', file)
  form.append('subject', subject)
  return apiFetch(`${BASE}/v2/study/import-csv`, { method: 'POST', body: form }).then(r => r.json())
}

/** Returns raw Response (caller does .blob()) — unlike other helpers that return JSON. */
export const exportSrCsv = (subject) =>
  apiFetch(`${BASE}/v2/study/export-csv${subject ? `?subject=${encodeURIComponent(subject)}` : ''}`)

export const reviewSrCard = (card_id, quality) =>
  apiFetch(`${BASE}/v2/study/review-card`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ card_id, quality }),
  }).then(r => r.json())

// ── Research ──────────────────────────────────────────────────────────────────

export const processYouTube = (url) =>
  apiFetch(`${BASE}/research/youtube`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  }).then(r => r.json())

// ── Image generation ──────────────────────────────────────────────────────────

// ── Napkin-style diagrams (inline visuals, no separate page) ────────────────

export const suggestVisuals = (prompt, signal) => {
  const opts = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt: prompt.slice(0, 1200) }),
  }
  if (signal) opts.signal = signal
  return apiFetch(`${BASE}/diagram/suggest`, opts).then(r => r.json())
}

export const generateDiagram = (prompt, visual_type = null, signal) => {
  const opts = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt: prompt.slice(0, 1200), visual_type }),
  }
  if (signal) opts.signal = signal
  return apiFetch(`${BASE}/diagram/generate`, opts).then(r => r.json())
}

// ── Admin ─────────────────────────────────────────────────────────────────────

export const getConfig = () => apiFetch(`${BASE}/admin/config`).then(r => r.json())
export const saveConfig = (data) =>
  apiFetch(`${BASE}/admin/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }).then(r => r.json())
export const getModels = () => apiFetch(`${BASE}/admin/models`).then(r => r.json())
export const unloadModel = (model) => apiFetch(`${BASE}/admin/models/unload`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ model }),
}).then(r => r.json())
export const getDiagnostics = () => apiFetch(`${BASE}/system/diagnostics`).then(r => r.json())
export const getHealth = () => apiFetch(`${BASE}/admin/health`).then(r => r.json()).then(d =>
  validate(Schemas.healthSchema, d, 'health'))
// ── Voice ─────────────────────────────────────────────────────────────────────

export const transcribeAudio = (blob, language) => {
  const form = new FormData()
  form.append('audio', blob, 'recording.webm')
  // Send browser language hint so Tamil/hi/ko aren't misdetected as English.
  // e.g. navigator.language 'ta-IN' -> backend normalizes to 'ta'.
  const hint = language || (typeof navigator !== 'undefined' ? navigator.language : '')
  if (hint) form.append('language', hint)
  return apiFetch(`${BASE}/voice/transcribe`, { method: 'POST', body: form }).then(r => r.json())
}

export const synthesizeSpeech = async (text) => {
  const resp = await apiFetch(`${BASE}/voice/synthesize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: text.slice(0, 3500) }),
  })
  if (!resp.ok) throw new Error(`TTS failed (${resp.status})`)
  const blob = await resp.blob()
  return URL.createObjectURL(blob)
}

// ── Memory management ─────────────────────────────────────────────────────────

export const clearAllMemory = () =>
  apiFetch(`${BASE}/admin/memory/all`, { method: 'DELETE' }).then(r => r.json())

// ═══════════════════════════════════════════════════════════════════════════════
// Intelligence API
// ═══════════════════════════════════════════════════════════════════════════════

const INTEL = `${BASE}/intelligence`

// ── Knowledge Graph ──────────────────────────────────────────────────────────

// ── Memory Intelligence ──────────────────────────────────────────────────────

// ── Background Agents ────────────────────────────────────────────────────────

// ── Study Intelligence ───────────────────────────────────────────────────────

export const getWeakTopics = () =>
  apiFetch(`${INTEL}/study/weak-topics`).then(r => r.json())

// ═══════════════════════════════════════════════════════════════════════════════
// V2 API — Analytics, Gamification, Curriculum
// ═══════════════════════════════════════════════════════════════════════════════

const V2 = `${BASE}/v2`

// ── Analytics ────────────────────────────────────────────────────────────────

export const getHeatmap = (months = 6) =>
  apiFetch(`${V2}/analytics/heatmap?months=${months}`).then(r => r.json())

export const getFocusScore = () =>
  apiFetch(`${V2}/analytics/focus-score`).then(r => r.json())

export const getWeeklySummary = () =>
  apiFetch(`${V2}/analytics/weekly-summary`).then(r => r.json())

// ── Gamification ─────────────────────────────────────────────────────────────

export const getGameProgress = () =>
  apiFetch(`${V2}/game/progress`).then(r => r.json())

export const getChallenge = () =>
  apiFetch(`${V2}/game/challenge`).then(r => r.json())

export const getLeaderboard = () =>
  apiFetch(`${V2}/game/leaderboard`).then(r => r.json())

// ── NSW Curriculum ───────────────────────────────────────────────────────────

// ── Study Intelligence (V2) ─────────────────────────────────────────────────

// ── Knowledge Base ──────────────────────────────────────────────────────────

const KB = `${BASE}/kb`

export const uploadToKB = async (file, collection = null) => {
  const form = new FormData()
  form.append('file', file)
  if (collection) form.append('collection', collection)
  const resp = await apiFetch(`${KB}/upload`, { method: 'POST', body: form })
  return resp.json()
}

export const searchKB = (q, collections = null, n = 5) => {
  let url = `${KB}/search?q=${encodeURIComponent(q)}&n=${n}`
  if (collections) url += `&collections=${encodeURIComponent(collections)}`
  return apiFetch(url).then(r => r.json())
}

export const listKBDocuments = (collection = null) => {
  let url = `${KB}/documents`
  if (collection) url += `?collection=${encodeURIComponent(collection)}`
  return apiFetch(url).then(r => r.json())
}

export const deleteKBDocument = (fileHash) =>
  apiFetch(`${KB}/documents/${fileHash}`, { method: 'DELETE' }).then(r => r.json())

export const getKBStats = () =>
  apiFetch(`${KB}/stats`).then(r => r.json())

export const getKBCollections = () =>
  apiFetch(`${KB}/collections`).then(r => r.json())

// ── Memory / Conversation History ─────────────────────────────────────────────
// Same endpoints as the Conversations helpers above — kept as aliases so
// MemoryPage / VoiceTutorPage imports stay stable (and gain zod validation).

export const getMemoryConversations = getConversations
export const searchMemoryConversations = searchConversations
export const getMemoryConversation = getConversation
export const deleteMemoryConversation = deleteConversation

export const getMemoryProfile = () =>
  apiFetch(`${BASE}/admin/profile`).then(r => r.json())

// ── AI usage ledger (server-side accounting) ─────────────────────────────────

export const getUsageSummary = (days = 30) =>
  apiFetch(`${BASE}/v2/usage/summary?days=${days}`).then(r => r.json())

// ── Todos / Assignment Inbox (solo) ───────────────────────────────────────────

const TODOS = `${BASE}/todos`

export const getTodos = () => apiFetch(`${TODOS}`).then(r => r.json()).then(d => {
  if (d && Array.isArray(d.todos)) {
    return { ...d, todos: d.todos.map(t => validate(Schemas.todoSchema, t, 'todo')) }
  }
  return d
})
export const createTodo = (subject, task, due_date = null, estimated_mins = 30, priority = 'medium') =>
  apiFetch(`${TODOS}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ subject, task, due_date, estimated_mins, priority }),
  }).then(r => r.json())
export const updateTodo = (id, updates) =>
  apiFetch(`${TODOS}/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  }).then(r => r.json())
export const deleteTodo = (id) => apiFetch(`${TODOS}/${id}`, { method: 'DELETE' }).then(r => r.json())
export const getTodoCushion = () => apiFetch(`${TODOS}/cushion`).then(r => r.json())
