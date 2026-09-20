const BASE = import.meta.env?.VITE_API_BASE || '/api'
const DEFAULT_TIMEOUT_MS = 30_000

export class ApiError extends Error {
  constructor(status, type, message, hint = '') {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.type = type
    this.hint = hint
  }
}

function friendlyStatusMessage(status) {
  if (status === 429) return 'Too many requests — please wait a moment and try again.'
  if (status === 413) return 'That file is too large. Try a smaller file.'
  if (status === 502 || status === 503) return 'Study Buddy backend is waking up — try again in a few seconds.'
  if (status === 401 || status === 403) return 'Not allowed. Check your session and try again.'
  return ''
}

async function parseErrorBody(resp) {
  // Unified backend envelope: {detail: {type, message, hint}} — fall back to text.
  try {
    const text = await resp.text()
    if (!text) return { message: resp.statusText || `HTTP ${resp.status}`, type: 'friendly', hint: '' }
    try {
      const data = JSON.parse(text)
      const d = data?.detail
      if (typeof d === 'string') return { message: d, type: 'friendly', hint: '' }
      if (d && typeof d === 'object') {
        return {
          message: d.message || d.msg || resp.statusText,
          type: d.type || 'friendly',
          hint: d.hint || '',
        }
      }
      if (data?.message) return { message: data.message, type: 'friendly', hint: '' }
      return { message: text.slice(0, 300), type: 'friendly', hint: '' }
    } catch {
      return { message: text.slice(0, 300), type: 'friendly', hint: '' }
    }
  } catch {
    return { message: resp.statusText || `HTTP ${resp.status}`, type: 'friendly', hint: '' }
  }
}

async function apiFetch(url, options = {}) {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, retryGet = true, ...fetchOpts } = options
  const doFetch = async (signal) => fetch(url, { ...fetchOpts, ...(signal ? { signal } : {}) })

  const runOnce = async () => {
    // timeoutMs === 0 disables timeout (SSE streams).
    if (!timeoutMs || fetchOpts.signal) return doFetch(fetchOpts.signal)
    const ctrl = new AbortController()
    const t = setTimeout(() => ctrl.abort(new DOMException('Request timed out', 'TimeoutError')), timeoutMs)
    try {
      return await doFetch(ctrl.signal)
    } finally {
      clearTimeout(t)
    }
  }

  let resp
  try {
    resp = await runOnce()
  } catch (e) {
    if (e?.name === 'AbortError') throw e
    if (e?.name === 'TimeoutError') throw new ApiError(0, 'upstream', 'Request timed out — is the backend running?', 'Check http://localhost:8000/api/health')
    throw new ApiError(0, 'upstream', 'Cannot reach Study Buddy backend. Is it running?', 'Run ./start.sh, then retry.')
  }
  if (resp.ok) return resp
  // Retry once for GET on bad-gateway (proxy cold start).
  if (retryGet && (!fetchOpts.method || fetchOpts.method === 'GET') && (resp.status === 502 || resp.status === 503)) {
    await new Promise(r => setTimeout(r, 800))
    try {
      const retry = await runOnce()
      if (retry.ok) return retry
      resp = retry
    } catch {}
  }
  const parsed = await parseErrorBody(resp)
  const friendly = friendlyStatusMessage(resp.status)
  throw new ApiError(
    resp.status,
    parsed.type,
    friendly ? `${friendly} (${parsed.message})`.slice(0, 400) : parsed.message,
    parsed.hint,
  )
}

// ── Chat (SSE streaming) ──────────────────────────────────────────────────────

function getSseReader(resp) {
  if (!resp.body) throw new Error('Streaming not supported by this browser')
  return resp.body.getReader()
}

/** Shared SSE line parser — dedupes streamChat/streamQuiz logic. */
export async function parseSseStream(resp, onEvent, { signal } = {}) {
  const reader = getSseReader(resp)
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    for (;;) {
      if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.slice(6))
          onEvent(data)
          if (data.type === 'done') return data
        } catch {
          // ignore partial chunks
        }
      }
    }
  } finally {
    try { reader.releaseLock() } catch {}
  }
  return null
}

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

  // timeoutMs: 0 — streams can run for minutes (LLM), never abort on timeout.
  const resp = await apiFetch(`${BASE}/chat`, { method: 'POST', body: form, signal, timeoutMs: 0 })

  const newConvId = resp.headers.get('X-Conversation-Id')

  try {
    await parseSseStream(resp, (data) => {
      onChunk(data)
      if (data.type === 'done') onDone(newConvId)
    }, { signal })
  } catch (err) {
    // AbortError on user cancel is expected — rethrow so caller can handle
    if (err?.name === 'AbortError') throw err
    throw new ApiError(0, 'upstream', `Stream interrupted: ${err.message}`, 'Check your connection and try again.')
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

export const searchConversations = (query) =>
  apiFetch(`${BASE}/chat/search?q=${encodeURIComponent(query)}`).then(r => r.json())

export const getConversationsForDate = (date) =>
  apiFetch(`${BASE}/chat/conversations/date/${date}`).then(r => r.json())

export const getConversationTitle = (id) =>
  apiFetch(`${BASE}/chat/conversations/${id}/title`).then(r => r.json())

export const updateConversationTitle = (id, title) =>
  apiFetch(`${BASE}/chat/conversations/${id}/title`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  }).then(r => r.json())

export const regenerateConversationTitle = (id) =>
  apiFetch(`${BASE}/chat/conversations/${id}/regenerate-title`, { method: 'POST' }).then(r => r.json())

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
  const resp = await apiFetch(`${BASE}/study/quiz/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, level, count, verify: true }),
    signal,
    timeoutMs: 0,
  })
  const questions = []
  let donePayload = null
  await parseSseStream(resp, (data) => {
    if (data.type === 'total') onTotal?.(data.total)
    else if (data.type === 'question') { questions.push(data.question); onQuestion?.(data.question, questions.length) }
    else if (data.type === 'progress') onProgress?.(data.done, data.total)
    else if (data.type === 'error') throw new ApiError(0, 'upstream', data.content || 'Quiz stream failed')
    else if (data.type === 'done') donePayload = data
  }, { signal })
  if (donePayload?.questions?.length) return { questions: donePayload.questions }
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

export const generateMathsSet = (topic_id, tier = 'stage4', count = 5, signal) => {
  const opts = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic_id, tier, count }),
  }
  if (signal) opts.signal = signal
  return apiFetch(`${BASE}/maths/generate`, opts).then(r => r.json())
}

export const submitMathsSet = (topic_id, tier, correct, total, mistakes = []) =>
  apiFetch(`${BASE}/maths/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic_id, tier, correct, total, mistakes }),
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

export const exportSrCsv = (subject) =>
  apiFetch(`${BASE}/v2/study/export-csv${subject ? `?subject=${encodeURIComponent(subject)}` : ''}`)

export const reviewSrCard = (card_id, quality) =>
  apiFetch(`${BASE}/v2/study/review-card`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ card_id, quality }),
  }).then(r => r.json())

// ── Research ──────────────────────────────────────────────────────────────────

export const webSearch = (query) =>
  apiFetch(`${BASE}/research/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  }).then(r => r.json())

export const processYouTube = (url, signal) =>
  apiFetch(`${BASE}/research/youtube`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
    signal,
  }).then(r => r.json())

// ── Image generation ──────────────────────────────────────────────────────────

export const generateImage = (prompt) =>
  apiFetch(`${BASE}/imagegen/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt }),
  }).then(r => r.json())

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
export const getHealth = () => apiFetch(`${BASE}/admin/health`).then(r => r.json())
export const getProfile = () => apiFetch(`${BASE}/admin/profile`).then(r => r.json())

export const pullModel = (name) =>
  apiFetch(`${BASE}/admin/models/pull`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  }).then(r => r.json())

export const unloadModel = (name) =>
  apiFetch(`${BASE}/admin/models/unload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  }).then(r => r.json())

// ── Backup / Restore ──────────────────────────────────────────────────────────

const BACKUP = `${BASE}/backup`

export const createBackup = (includeUploads = false) =>
  apiFetch(`${BACKUP}/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ include_uploads: includeUploads }),
  }).then(r => r.json())

export const listBackups = () =>
  apiFetch(`${BACKUP}/list`).then(r => r.json())

export const downloadBackup = (filename) =>
  apiFetch(`${BACKUP}/download/${encodeURIComponent(filename)}`)

export const deleteBackup = (filename) =>
  apiFetch(`${BACKUP}/${encodeURIComponent(filename)}`, { method: 'DELETE' }).then(r => r.json())

export const restoreBackup = async (file) => {
  const form = new FormData()
  form.append('file', file)
  return apiFetch(`${BACKUP}/restore`, { method: 'POST', body: form }).then(r => r.json())
}

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

export const synthesizeSpeech = async (text, language) => {
  const resp = await apiFetch(`${BASE}/voice/synthesize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: text.slice(0, 3500), ...(language ? { language } : {}) }),
  })
  const blob = await resp.blob()
  return URL.createObjectURL(blob)
}

// Day 3: client-side TTS URL cache + prefetch. Repeated tutor phrases
// ("Well done!", "Try again") reuse the same object URL instead of
// re-hitting /synthesize. LRU-capped to avoid blob leaks.
const _ttsUrlCache = new Map() // text -> objectUrl
const TTS_CACHE_MAX = 30

function _ttsCacheGet(text) {
  const url = _ttsUrlCache.get(text)
  if (url) {
    // refresh LRU order
    _ttsUrlCache.delete(text)
    _ttsUrlCache.set(text, url)
  }
  return url || null
}

function _ttsCachePut(text, url) {
  if (_ttsUrlCache.has(text)) _ttsUrlCache.delete(text)
  _ttsUrlCache.set(text, url)
  while (_ttsUrlCache.size > TTS_CACHE_MAX) {
    const oldest = _ttsUrlCache.keys().next().value
    const oldUrl = _ttsUrlCache.get(oldest)
    _ttsUrlCache.delete(oldest)
    try { if (oldUrl?.startsWith('blob:')) URL.revokeObjectURL(oldUrl) } catch {}
  }
}

export const synthesizeSpeechCached = async (text, language) => {
  const key = `${language || ''}\0${text.slice(0, 3500)}`
  const hit = _ttsCacheGet(key)
  if (hit) return hit
  const url = await synthesizeSpeech(text, language)
  _ttsCachePut(key, url)
  return url
}

// Fire-and-forget warm of the TTS cache for an upcoming sentence.
// Never throws — prefetch failures just mean a cache miss later.
export const prefetchSpeech = (text, language) => {
  try {
    const body = (text || '').slice(0, 3500)
    if (!body) return Promise.resolve(null)
    const key = `${language || ''}\0${body}`
    if (_ttsUrlCache.has(key)) return Promise.resolve(_ttsCacheGet(key))
    return synthesizeSpeechCached(body, language).catch(() => null)
  } catch {
    return Promise.resolve(null)
  }
}

// Day 1 realtime: split long text into TTS sentence chunks server-side,
// with local fallback if the endpoint is unavailable (older backend).
export const chunkTextForSpeech = async (text, maxChars = 350) => {
  try {
    const resp = await apiFetch(`${BASE}/voice/chunk`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text.slice(0, 10000), max_chars: maxChars }),
    })
    const data = await resp.json()
    if (Array.isArray(data?.chunks) && data.chunks.length) return data.chunks
  } catch {}
  // Local fallback mirrors backend chunking (see voiceQueue.js)
  const { chunkForSpeech } = await import('./voiceQueue.js')
  return chunkForSpeech(text, maxChars)
}

// Day 48: voice system status for the Admin panel (engines, cache, stats).
export const getVoiceStatus = () =>
  apiFetch(`${BASE}/voice/stream-info`).then(r => r.json()).catch(() => null)

// Caller MUST call this when the audio URL is no longer needed
// (prevents ObjectURL memory leaks on repeated TTS).
export const revokeSpeechUrl = (url) => {
  try { if (url && url.startsWith('blob:')) URL.revokeObjectURL(url) } catch {}
}

// ── Memory management ─────────────────────────────────────────────────────────

export const clearAllMemory = () =>
  apiFetch(`${BASE}/admin/memory/all`, { method: 'DELETE' }).then(r => r.json())

export const exportConversation = (id) =>
  apiFetch(`${BASE}/admin/export/${id}`).then(r => r.json())

// ═══════════════════════════════════════════════════════════════════════════════
// Intelligence API
// ═══════════════════════════════════════════════════════════════════════════════

const INTEL = `${BASE}/intelligence`

// ── Knowledge Graph ──────────────────────────────────────────────────────────

export const getKnowledgeGraph = () =>
  apiFetch(`${INTEL}/knowledge-graph`).then(r => r.json())

export const getKnowledgeGraphData = (maxNodes = 200) =>
  apiFetch(`${INTEL}/knowledge-graph/graph?max_nodes=${maxNodes}`).then(r => r.json())

export const getKnowledgeGraphStats = () =>
  apiFetch(`${INTEL}/knowledge-graph/stats`).then(r => r.json())

export const searchKnowledgeGraph = (q) =>
  apiFetch(`${INTEL}/knowledge-graph/search?q=${encodeURIComponent(q)}`).then(r => r.json())

export const getNodeConnections = (nodeId) =>
  apiFetch(`${INTEL}/knowledge-graph/node/${encodeURIComponent(nodeId)}/connections`).then(r => r.json())

export const getNodesByType = (type) =>
  apiFetch(`${INTEL}/knowledge-graph/type/${type}`).then(r => r.json())

export const clearKnowledgeGraph = () =>
  apiFetch(`${INTEL}/knowledge-graph`, { method: 'DELETE' }).then(r => r.json())

// ── Memory Intelligence ──────────────────────────────────────────────────────

export const getMemoryTimeline = (days = 30) =>
  apiFetch(`${INTEL}/memory/timeline?days=${days}`).then(r => r.json())

export const globalMemorySearch = (q, limit = 20) =>
  apiFetch(`${INTEL}/memory/search?q=${encodeURIComponent(q)}&limit=${limit}`).then(r => r.json())

export const compressMemory = (olderThanDays = 7) =>
  apiFetch(`${INTEL}/memory/compress?older_than_days=${olderThanDays}`, { method: 'POST' }).then(r => r.json())

export const cleanupMemory = (maxAgeDays = 90) =>
  apiFetch(`${INTEL}/memory/cleanup?max_age_days=${maxAgeDays}`, { method: 'POST' }).then(r => r.json())

// ── Background Agents ────────────────────────────────────────────────────────

export const summariseFolder = (folderPath) =>
  apiFetch(`${INTEL}/agents/summarise-folder?folder_path=${encodeURIComponent(folderPath)}`, { method: 'POST' }).then(r => r.json())

export const autoResearch = (topic, depth = 3) =>
  apiFetch(`${INTEL}/agents/auto-research?topic=${encodeURIComponent(topic)}&depth=${depth}`, { method: 'POST' }).then(r => r.json())

export const getBackgroundTasks = (status) =>
  apiFetch(`${INTEL}/agents/tasks${status ? `?status=${status}` : ''}`).then(r => r.json())

export const clearCompletedTasks = () =>
  apiFetch(`${INTEL}/agents/tasks/completed`, { method: 'DELETE' }).then(r => r.json())

// ── Study Intelligence ───────────────────────────────────────────────────────

export const getWeakTopics = () =>
  apiFetch(`${INTEL}/study/weak-topics`).then(r => r.json())

export const suggestNextTopic = () =>
  apiFetch(`${INTEL}/study/suggest-next`).then(r => r.json())

export const getRevisionNeeds = () =>
  apiFetch(`${INTEL}/study/revision-needs`).then(r => r.json())

export const getLearnedFormulas = () =>
  apiFetch(`${INTEL}/study/formulas`).then(r => r.json())

export const getCurriculum = (subject) =>
  apiFetch(`${INTEL}/study/curriculum/${encodeURIComponent(subject)}`).then(r => r.json())

export const getAdaptiveRecommendations = () =>
  apiFetch(`${INTEL}/study/adaptive`).then(r => r.json())

// ═══════════════════════════════════════════════════════════════════════════════
// V2 API — Analytics, Gamification, Curriculum
// ═══════════════════════════════════════════════════════════════════════════════

const V2 = `${BASE}/v2`

// ── Analytics ────────────────────────────────────────────────────────────────

export const getHeatmap = (months = 6) =>
  apiFetch(`${V2}/analytics/heatmap?months=${months}`).then(r => r.json())

export const getTrends = (days = 30) =>
  apiFetch(`${V2}/analytics/trends?days=${days}`).then(r => r.json())

export const getPredictedGrades = () =>
  apiFetch(`${V2}/analytics/predicted-grades`).then(r => r.json())

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

export const getStages = () =>
  apiFetch(`${V2}/curriculum/stages`).then(r => r.json())

export const getKlas = () =>
  apiFetch(`${V2}/curriculum/klas`).then(r => r.json())

export const getSubjectContent = (kla, stage) =>
  apiFetch(`${V2}/curriculum/subject/${kla}/stage/${stage}`).then(r => r.json())

export const getHscSubjects = () =>
  apiFetch(`${V2}/curriculum/hsc`).then(r => r.json())

export const searchCurriculum = (q) =>
  apiFetch(`${V2}/curriculum/search?q=${encodeURIComponent(q)}`).then(r => r.json())

export const getCurriculumForAge = (age) =>
  apiFetch(`${V2}/curriculum/age/${age}`).then(r => r.json())

export const getProgression = (kla) =>
  apiFetch(`${V2}/curriculum/progression/${kla}`).then(r => r.json())

// ── Study Intelligence (V2) ─────────────────────────────────────────────────

export const getExamReadiness = (subject, days = 14) =>
  apiFetch(`${V2}/study/exam-readiness/${encodeURIComponent(subject)}?days=${days}`).then(r => r.json())

export const getKnowledgeGaps = (subject) =>
  apiFetch(`${V2}/study/knowledge-gaps/${encodeURIComponent(subject)}`).then(r => r.json())

export const getLearningStyle = () =>
  apiFetch(`${V2}/study/learning-style`).then(r => r.json())

// ── Knowledge Base ──────────────────────────────────────────────────────────

const KB = `${BASE}/kb`

export const uploadToKB = async (file, collection = null) => {
  const form = new FormData()
  form.append('file', file)
  if (collection) form.append('collection', collection)
  const resp = await apiFetch(`${KB}/upload`, { method: 'POST', body: form })
  return resp.json()
}

export const uploadMultipleToKB = async (files, collection = null) => {
  const form = new FormData()
  for (const f of files) form.append('files', f)
  if (collection) form.append('collection', collection)
  const resp = await apiFetch(`${KB}/upload-multiple`, { method: 'POST', body: form })
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

export const rebuildKBIndex = () =>
  apiFetch(`${KB}/rebuild`, { method: 'POST' }).then(r => r.json())

// ── Memory / Conversation History ─────────────────────────────────────────────

const CHAT = `${BASE}/chat`

export const getMemoryConversations = () =>
  apiFetch(`${CHAT}/conversations`).then(r => r.json())

export const searchMemoryConversations = (q) =>
  apiFetch(`${CHAT}/search?q=${encodeURIComponent(q)}`).then(r => r.json())

export const getMemoryConversation = (id) =>
  apiFetch(`${CHAT}/conversations/${id}`).then(r => r.json())

export const deleteMemoryConversation = (id) =>
  apiFetch(`${CHAT}/conversations/${id}`, { method: 'DELETE' }).then(r => r.json())

export const getMemoryProfile = () =>
  apiFetch(`${BASE}/admin/profile`).then(r => r.json())

// ── Todos / Assignment Inbox (solo) ───────────────────────────────────────────

const TODOS = `${BASE}/todos`

export const getTodos = () => apiFetch(`${TODOS}`).then(r => r.json())
export const createTodo = (subject, task, due_date = null, estimated_mins = 30, priority = 'medium') =>
  apiFetch(`${TODOS}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ subject, task, due_date, estimated_mins, priority }),
  }).then(r => r.json())
export const createTodoFromChat = (text) =>
  apiFetch(`${TODOS}/from-chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  }).then(r => r.json())
export const updateTodo = (id, updates) =>
  apiFetch(`${TODOS}/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  }).then(r => r.json())
export const deleteTodo = (id) => apiFetch(`${TODOS}/${id}`, { method: 'DELETE' }).then(r => r.json())
export const getTodoCushion = () => apiFetch(`${TODOS}/cushion`).then(r => r.json())
