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
        } catch {
          // SSE parse error — ignore partial chunks
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

export const searchConversations = (query) =>
  apiFetch(`${BASE}/chat/search?q=${encodeURIComponent(query)}`).then(r => r.json())

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

export const generateAssessmentPlan = async (file, daysAvailable = 7) => {
  const form = new FormData()
  form.append('file', file)
  form.append('days_available', String(daysAvailable))
  const resp = await apiFetch(`${BASE}/study/assessment-plan`, { method: 'POST', body: form })
  return resp.json()
}

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
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 360_000) // 6 minutes
  try {
    const resp = await apiFetch(`${BASE}/study/pptx`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, count: slides }),
      signal: controller.signal,
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
  } finally {
    clearTimeout(timeoutId)
  }
}

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

// ── AI Superpowers ───────────────────────────────────────────────────────────

export const optimisePrompt = (prompt) =>
  apiFetch(`${INTEL}/superpowers/optimise-prompt`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt }),
  }).then(r => r.json())

export const selfCritique = (response, question) =>
  apiFetch(`${INTEL}/superpowers/self-critique`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ response, question }),
  }).then(r => r.json())

export const confidenceScore = (response, question) =>
  apiFetch(`${INTEL}/superpowers/confidence`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ response, question }),
  }).then(r => r.json())

export const hallucinationCheck = (response, context) =>
  apiFetch(`${INTEL}/superpowers/hallucination-check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ response, context }),
  }).then(r => r.json())

export const reflectOnAnswer = (response, question) =>
  apiFetch(`${INTEL}/superpowers/reflect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ response, question }),
  }).then(r => r.json())

export const multiAgentDebate = (question, models) =>
  apiFetch(`${INTEL}/superpowers/debate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, models }),
  }).then(r => r.json())

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

// ── Coding Intelligence ──────────────────────────────────────────────────────

export const understandProject = (path) =>
  apiFetch(`${INTEL}/coding/understand?path=${encodeURIComponent(path)}`).then(r => r.json())

export const viewArchitecture = (path) =>
  apiFetch(`${INTEL}/coding/architecture?path=${encodeURIComponent(path)}`).then(r => r.json())

export const analyseDependencies = (path) =>
  apiFetch(`${INTEL}/coding/dependencies?path=${encodeURIComponent(path)}`).then(r => r.json())

export const findDeadCode = (path) =>
  apiFetch(`${INTEL}/coding/dead-code?path=${encodeURIComponent(path)}`).then(r => r.json())

export const scanSecurity = (path) =>
  apiFetch(`${INTEL}/coding/security?path=${encodeURIComponent(path)}`).then(r => r.json())

export const generateChangelog = (path) =>
  apiFetch(`${INTEL}/coding/changelog?path=${encodeURIComponent(path)}`).then(r => r.json())

export const explainProjectStructure = (path) =>
  apiFetch(`${INTEL}/coding/explain?path=${encodeURIComponent(path)}`).then(r => r.json())

export const analysePerformance = (path) =>
  apiFetch(`${INTEL}/coding/performance?path=${encodeURIComponent(path)}`).then(r => r.json())

// ═══════════════════════════════════════════════════════════════════════════════
// V2 API — Analytics, Gamification, Curriculum, Utilities
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
