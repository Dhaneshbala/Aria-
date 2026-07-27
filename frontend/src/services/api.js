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

export const getConversationsForDate = (date) =>
  apiFetch(`${BASE}/chat/conversations/date/${date}`).then(r => r.json())

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

export const generateWorksheet = (topic, grade = 'Year 10', questionCount = 10, includeAnswers = true) =>
  apiFetch(`${BASE}/study/worksheet`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, grade, question_count: questionCount, include_answers: includeAnswers }),
  }).then(r => r.json())

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

// ── Planner (Shovel-inspired) ────────────────────────────────────────────────

const PLANNER = `${BASE}/planner`

export const uploadSyllabus = async (file, schoolStart = '08:30', schoolEnd = '15:00', studyLen = '45') => {
  const form = new FormData()
  form.append('file', file)
  form.append('school_start', schoolStart)
  form.append('school_end', schoolEnd)
  form.append('study_len', studyLen)
  const resp = await apiFetch(`${PLANNER}/upload-syllabus`, { method: 'POST', body: form })
  return resp.json()
}

export const getCushion = (schedule, homework = [], tests = []) =>
  apiFetch(`${PLANNER}/cushion`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ schedule, homework, tests }),
  }).then(r => r.json())

export const getFreeSlots = (schedule, homework = [], tests = []) =>
  apiFetch(`${PLANNER}/free-slots`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ schedule, homework, tests }),
  }).then(r => r.json())

export const getStudyStreak = (schedule, homework = [], tests = []) =>
  apiFetch(`${PLANNER}/streak`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ schedule, homework, tests }),
  }).then(r => r.json())

export const exportICS = (events, calname = 'ARIA Study Plan') =>
  apiFetch(`${PLANNER}/export-ics`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ events, calname }),
  })

export const importICS = (file) => {
  const form = new FormData()
  form.append('file', file)
  return apiFetch(`${PLANNER}/import-ics`, { method: 'POST', body: form }).then(r => r.json())
}

// ── Premium Planner ────────────────────────────────────────────────────────────

const PP = '/api/premium-planner'

export const ppUploadSyllabus = (file) => {
  const form = new FormData()
  form.append('file', file)
  return apiFetch(`${PP}/upload-syllabus`, { method: 'POST', body: form }).then(r => r.json())
}

export const ppGetCourses = () => apiFetch(`${PP}/courses`).then(r => r.json())
export const ppCreateCourse = (course) => apiFetch(`${PP}/courses`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(course),
}).then(r => r.json())

export const ppGetAssignments = (courseId) =>
  apiFetch(`${PP}/assignments${courseId ? `?course_id=${courseId}` : ''}`).then(r => r.json())
export const ppCreateAssignment = (a) => apiFetch(`${PP}/assignments`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(a),
}).then(r => r.json())
export const ppToggleAssignment = (id) => apiFetch(`${PP}/assignments/${id}/toggle`, { method: 'POST' }).then(r => r.json())
export const ppDeleteAssignment = (id) => apiFetch(`${PP}/assignments/${id}`, { method: 'DELETE' }).then(r => r.json())

export const ppGetExams = () => apiFetch(`${PP}/exams`).then(r => r.json())
export const ppCreateExam = (e) => apiFetch(`${PP}/exams`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(e),
}).then(r => r.json())

export const ppGetAvailability = () => apiFetch(`${PP}/availability`).then(r => r.json())
export const ppSetAvailability = (blocks) => apiFetch(`${PP}/availability`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(blocks),
}).then(r => r.json())

export const ppGetSessions = (from, to) =>
  apiFetch(`${PP}/sessions${from ? `?date_from=${from}&date_to=${to}` : ''}`).then(r => r.json())
export const ppToggleSession = (id) => apiFetch(`${PP}/sessions/${id}/toggle`, { method: 'POST' }).then(r => r.json())
export const ppLockSession = (id) => apiFetch(`${PP}/sessions/${id}/lock`, { method: 'POST' }).then(r => r.json())
export const ppMoveSession = (id, date, startTime) => apiFetch(`${PP}/sessions/move`, {
  method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: `session_id=${id}&date=${date}&start_time=${startTime}`,
}).then(r => r.json())

export const ppReschedule = (id) => apiFetch(`${PP}/reschedule/${id}`, { method: 'POST' }).then(r => r.json())
export const ppRescheduleMissed = () => apiFetch(`${PP}/reschedule-missed`, { method: 'POST' }).then(r => r.json())
export const ppGenerateBlocks = () => apiFetch(`${PP}/generate-blocks`, { method: 'POST' }).then(r => r.json())
export const ppGetWorkload = () => apiFetch(`${PP}/workload`).then(r => r.json())
export const ppGetDailyPlan = () => apiFetch(`${PP}/daily-plan`).then(r => r.json())
export const ppAiAssist = (sessionId, query) => apiFetch(`${PP}/ai-assist`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ session_id: sessionId, query }),
}).then(r => r.json())
export const ppGenerateExamRevision = (examId) => apiFetch(`${PP}/exam-revision/${examId}`, { method: 'POST' }).then(r => r.json())
export const ppGetAnalytics = () => apiFetch(`${PP}/analytics`).then(r => r.json())
export const ppGetNotifications = () => apiFetch(`${PP}/notifications`).then(r => r.json())
export const ppMarkNotificationRead = (id) => apiFetch(`${PP}/notifications/${id}/read`, { method: 'POST' }).then(r => r.json())
