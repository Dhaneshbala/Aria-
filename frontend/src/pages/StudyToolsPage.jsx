import { useState, useRef } from 'react'
import { generateEssayFeedback, generateFormula, generateTimeline, generateAssessmentPlan } from '../services/api'
import { BookOpen, PenTool, Calculator, Clock, Loader, FileText, Upload, CheckCircle, Circle, Download, File } from 'lucide-react'

const TOOLS = [
  { id: 'essay',       icon: PenTool,    label: 'Essay Feedback',     color: 'text-yellow-400' },
  { id: 'formula',     icon: Calculator, label: 'Formula Reference',   color: 'text-blue-400' },
  { id: 'timeline',    icon: Clock,      label: 'Timeline Generator',  color: 'text-green-400' },
  { id: 'assessment',  icon: FileText,   label: 'Assessment Planner',  color: 'text-purple-400' },
]

function generateICS(plan, topic) {
  const now = new Date()
  const lines = [
    'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//ARIA Study Plan//EN',
    'CALSCALE:GREGORIAN', 'METHOD:PUBLISH',
  ]
  plan.forEach((day) => {
    const startDate = new Date(now)
    startDate.setDate(startDate.getDate() + 1 + (day.day - 1))
    startDate.setHours(9, 0, 0, 0)
    const endDate = new Date(startDate)
    endDate.setMinutes(endDate.getMinutes() + (day.time_minutes || 30))
    const tasks = (day.tasks || []).map((t, i) => `${i + 1}. ${t}`).join('\\n')
    const formatDT = (d) => d.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z'
    lines.push('BEGIN:VEVENT')
    lines.push(`DTSTART:${formatDT(startDate)}`)
    lines.push(`DTEND:${formatDT(endDate)}`)
    lines.push(`SUMMARY:Day ${day.day}: ${day.title || topic}`)
    lines.push(`DESCRIPTION:Tasks:\\n${tasks}`)
    lines.push('STATUS:CONFIRMED')
    lines.push('END:VEVENT')
  })
  lines.push('END:VCALENDAR')
  return lines.join('\r\n')
}

export default function StudyToolsPage() {
  const [activeTool, setActiveTool] = useState('essay')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState('')

  // Essay state
  const [essay, setEssay] = useState('')
  const [essayTopic, setEssayTopic] = useState('')

  // Formula state
  const [formulaTopic, setFormulaTopic] = useState('')

  // Timeline state
  const [timelineTopic, setTimelineTopic] = useState('')

  // Assessment state
  const [assessFile, setAssessFile] = useState(null)
  const [assessDrag, setAssessDrag] = useState(false)
  const [assessDays, setAssessDays] = useState(7)
  const [assessResult, setAssessResult] = useState(null)
  const [assessLoading, setAssessLoading] = useState(false)
  const [assessChecked, setAssessChecked] = useState({})
  const assessRef = useRef()

  const handleEssay = async () => {
    if (!essay.trim()) return
    setLoading(true); setResult('')
    try {
      const data = await generateEssayFeedback(essay, essayTopic)
      setResult(data.feedback || 'No feedback generated.')
    } catch (e) { setResult('Error: ' + e.message) }
    setLoading(false)
  }

  const handleFormula = async () => {
    if (!formulaTopic.trim()) return
    setLoading(true); setResult('')
    try {
      const data = await generateFormula(formulaTopic)
      setResult(data.reference || 'No formulas generated.')
    } catch (e) { setResult('Error: ' + e.message) }
    setLoading(false)
  }

  const handleTimeline = async () => {
    if (!timelineTopic.trim()) return
    setLoading(true); setResult('')
    try {
      const data = await generateTimeline(timelineTopic)
      setResult(data.timeline || 'No timeline generated.')
    } catch (e) { setResult('Error: ' + e.message) }
    setLoading(false)
  }

  const handleAssessDrop = (e) => {
    e.preventDefault(); setAssessDrag(false)
    const f = e.dataTransfer.files[0]
    if (f && f.name.endsWith('.pdf')) setAssessFile(f)
  }
  const handleAssessFile = (e) => {
    const f = e.target.files[0]
    if (f) setAssessFile(f)
  }

  const handleAssessAnalyse = async () => {
    if (!assessFile) return
    setAssessLoading(true); setAssessResult(null); setAssessChecked({})
    try {
      const data = await generateAssessmentPlan(assessFile, assessDays)
      setAssessResult(data)
    } catch (e) { setAssessResult({ error: e.message }) }
    setAssessLoading(false)
  }

  const toggleAssessTask = (day, task) => {
    const key = `${day}-${task}`
    setAssessChecked(c => ({ ...c, [key]: !c[key] }))
  }

  const exportAssessICS = () => {
    if (!assessResult?.plan) return
    const ics = generateICS(assessResult.plan, assessResult.assessment?.name || assessFile?.name || 'Assessment')
    const blob = new Blob([ics], { type: 'text/calendar;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url
    a.download = `ARIA-Assessment-Plan.ics`; a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 page-enter">
      <div className="flex items-center gap-2 mb-6">
        <BookOpen size={20} className="text-[#7c6af7]" />
        <h1 className="text-lg font-semibold text-[#e8e8e8]">Study Tools</h1>
      </div>

      {/* Tool tabs */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {TOOLS.map(tool => (
          <button key={tool.id} onClick={() => { setActiveTool(tool.id); setResult('') }}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm transition-all ${
              activeTool === tool.id
                ? 'bg-[#7c6af7]/15 text-[#a89bf8] border border-[#7c6af7]/30'
                : 'bg-[#141414] border border-[#2a2a2a] text-[#666] hover:text-[#aaa]'
            }`}>
            <tool.icon size={15} className={activeTool === tool.id ? tool.color : ''} />
            {tool.label}
          </button>
        ))}
      </div>

      {/* ── Essay Feedback ─────────────────────────────────────────── */}
      {activeTool === 'essay' && (
        <div className="space-y-3">
          <p className="text-xs text-[#555]">Paste your essay below and get detailed feedback on structure, grammar, arguments, and more.</p>
          <input value={essayTopic} onChange={e => setEssayTopic(e.target.value)}
            placeholder="Essay topic (optional)"
            className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-4 py-2.5 text-sm text-[#e8e8e8] placeholder-[#444] outline-none focus:border-[#7c6af7]/50" />
          <textarea value={essay} onChange={e => setEssay(e.target.value)}
            placeholder="Paste your essay here..." rows={10}
            className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-4 py-3 text-sm text-[#e8e8e8] placeholder-[#444] outline-none focus:border-[#7c6af7]/50 resize-none" />
          <button onClick={handleEssay} disabled={!essay.trim() || loading}
            className="w-full py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-40 transition-colors">
            {loading ? 'Analysing essay...' : 'Get Feedback'}
          </button>
        </div>
      )}

      {/* ── Formula Reference ───────────────────────────────────────── */}
      {activeTool === 'formula' && (
        <div className="space-y-3">
          <p className="text-xs text-[#555]">Get a comprehensive formula reference sheet for any topic.</p>
          <input value={formulaTopic} onChange={e => setFormulaTopic(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleFormula()}
            placeholder="e.g. Quadratic equations, Chemical bonding, Newton's laws..."
            className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-4 py-2.5 text-sm text-[#e8e8e8] placeholder-[#444] outline-none focus:border-[#7c6af7]/50" />
          <button onClick={handleFormula} disabled={!formulaTopic.trim() || loading}
            className="w-full py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-40 transition-colors">
            {loading ? 'Generating formulas...' : 'Get Formulas'}
          </button>
        </div>
      )}

      {/* ── Timeline Generator ──────────────────────────────────────── */}
      {activeTool === 'timeline' && (
        <div className="space-y-3">
          <p className="text-xs text-[#555]">Generate a chronological timeline for any historical topic.</p>
          <input value={timelineTopic} onChange={e => setTimelineTopic(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleTimeline()}
            placeholder="e.g. World War 2, Ancient Egypt, Renaissance..."
            className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-4 py-2.5 text-sm text-[#e8e8e8] placeholder-[#444] outline-none focus:border-[#7c6af7]/50" />
          <button onClick={handleTimeline} disabled={!timelineTopic.trim() || loading}
            className="w-full py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-40 transition-colors">
            {loading ? 'Generating timeline...' : 'Generate Timeline'}
          </button>
        </div>
      )}

      {/* ── Assessment Planner ──────────────────────────────────────── */}
      {activeTool === 'assessment' && (
        <div className="space-y-4">
          <p className="text-xs text-[#555]">Upload your assessment notification PDF. ARIA will read it, extract key dates and topics, and create a personalised study plan.</p>

          {/* Upload zone */}
          {!assessFile && (
            <div
              onDragOver={(e) => { e.preventDefault(); setAssessDrag(true) }}
              onDragLeave={() => setAssessDrag(false)}
              onDrop={handleAssessDrop}
              onClick={() => assessRef.current?.click()}
              className={`flex flex-col items-center justify-center gap-3 py-12 rounded-2xl border-2 border-dashed cursor-pointer transition-all ${
                assessDrag
                  ? 'border-[#7c6af7] bg-[#7c6af7]/5'
                  : 'border-[#2a2a2a] bg-[#141414] hover:border-[#444]'
              }`}
            >
              <Upload size={28} className={assessDrag ? 'text-[#7c6af7]' : 'text-[#555]'} />
              <div className="text-center">
                <p className="text-sm text-[#888]">Drop your assessment notification here</p>
                <p className="text-xs text-[#555] mt-1">or click to browse &middot; PDF only</p>
              </div>
              <input ref={assessRef} type="file" accept=".pdf" onChange={handleAssessFile} className="hidden" />
            </div>
          )}

          {/* File info */}
          {assessFile && !assessResult && (
            <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <File size={16} className="text-[#7c6af7]" />
                  <span className="text-sm text-[#e8e8e8]">{assessFile.name}</span>
                  <span className="text-xs text-[#555]">({(assessFile.size / 1024).toFixed(0)} KB)</span>
                </div>
                <button onClick={() => setAssessFile(null)} className="text-xs text-[#555] hover:text-[#888]">✕ Remove</button>
              </div>
              <div>
                <p className="text-xs text-[#555] mb-2">Days until exam:</p>
                <div className="flex items-center gap-2">
                  {[3, 5, 7, 10, 14].map(n => (
                    <button key={n} onClick={() => setAssessDays(n)}
                      className={`w-10 h-8 rounded-lg text-xs transition-all ${
                        assessDays === n ? 'bg-[#7c6af7] text-white' : 'bg-[#1a1a1a] border border-[#2a2a2a] text-[#888]'
                      }`}>
                      {n}
                    </button>
                  ))}
                </div>
              </div>
              <button onClick={handleAssessAnalyse} disabled={assessLoading}
                className="w-full py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-40 transition-colors">
                {assessLoading ? 'Analysing notification...' : 'Analyse & Create Study Plan'}
              </button>
            </div>
          )}

          {/* Loading */}
          {assessLoading && (
            <div className="flex flex-col items-center py-12 gap-3">
              <div className="w-8 h-8 border-2 border-[#7c6af7] border-t-transparent rounded-full animate-spin" />
              <p className="text-[#888] text-sm">Reading your assessment notification...</p>
            </div>
          )}

          {/* Error */}
          {assessResult?.error && (
            <div className="bg-red-900/20 border border-red-500/30 rounded-xl p-4 text-sm text-red-300">
              {assessResult.error}
            </div>
          )}

          {/* Results */}
          {assessResult && !assessResult.error && (
            <div className="space-y-4">
              {/* Assessment info card */}
              {assessResult.assessment && (
                <div className="bg-[#141414] border border-[#7c6af7]/20 rounded-xl p-4">
                  <h3 className="text-xs font-semibold text-[#7c6af7] mb-3 uppercase tracking-wide">Assessment Details</h3>
                  <div className="grid grid-cols-2 gap-3">
                    {assessResult.assessment.name && (
                      <div className="col-span-2">
                        <span className="text-xs text-[#555]">Name</span>
                        <p className="text-sm text-[#e8e8e8]">{assessResult.assessment.name}</p>
                      </div>
                    )}
                    {assessResult.assessment.subject && (
                      <div>
                        <span className="text-xs text-[#555]">Subject</span>
                        <p className="text-sm text-[#e8e8e8]">{assessResult.assessment.subject}</p>
                      </div>
                    )}
                    {assessResult.assessment.date && (
                      <div>
                        <span className="text-xs text-[#555]">Date</span>
                        <p className="text-sm text-[#e8e8e8]">{assessResult.assessment.date}</p>
                      </div>
                    )}
                    {assessResult.assessment.format && (
                      <div>
                        <span className="text-xs text-[#555]">Format</span>
                        <p className="text-sm text-[#e8e8e8]">{assessResult.assessment.format}</p>
                      </div>
                    )}
                    {assessResult.assessment.marking && (
                      <div>
                        <span className="text-xs text-[#555]">Marking</span>
                        <p className="text-sm text-[#e8e8e8]">{assessResult.assessment.marking}</p>
                      </div>
                    )}
                    {assessResult.assessment.topics?.length > 0 && (
                      <div className="col-span-2">
                        <span className="text-xs text-[#555]">Topics</span>
                        <div className="flex flex-wrap gap-1.5 mt-1">
                          {assessResult.assessment.topics.map((t, i) => (
                            <span key={i} className="px-2 py-0.5 rounded-full bg-[#7c6af7]/10 border border-[#7c6af7]/20 text-xs text-[#a89bf8]">
                              {t}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {assessResult.assessment.instructions && (
                      <div className="col-span-2">
                        <span className="text-xs text-[#555]">Instructions</span>
                        <p className="text-sm text-[#e8e8e8]">{assessResult.assessment.instructions}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Study plan */}
              {assessResult.plan?.length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-xs font-semibold text-[#e8e8e8] uppercase tracking-wide">Study Plan</h3>
                    <button onClick={exportAssessICS}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] text-xs text-[#888] hover:text-[#e8e8e8] hover:border-[#7c6af7]/50 transition-colors">
                      <Download size={12} /> Export to Calendar
                    </button>
                  </div>
                  <div className="space-y-3">
                    {assessResult.plan.map((day, di) => {
                      const tasksDone = (day.tasks || []).filter((_, ti) => assessChecked[`${di}-${ti}`]).length
                      return (
                        <div key={di} className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4">
                          <div className="flex items-center justify-between mb-2">
                            <div>
                              <span className="text-xs text-[#7c6af7] font-semibold">Day {day.day}</span>
                              <p className="text-sm text-[#e8e8e8] mt-0.5">{day.title}</p>
                            </div>
                            <div className="flex items-center gap-3">
                              {day.focus_topics?.length > 0 && (
                                <div className="flex gap-1">
                                  {day.focus_topics.slice(0, 2).map((ft, fi) => (
                                    <span key={fi} className="text-[10px] px-1.5 py-0.5 rounded bg-[#7c6af7]/10 text-[#a89bf8]">{ft}</span>
                                  ))}
                                </div>
                              )}
                              <span className="text-xs text-[#555]">{day.time_minutes} min</span>
                            </div>
                          </div>
                          <div className="space-y-1.5">
                            {(day.tasks || []).map((task, ti) => {
                              const key = `${di}-${ti}`
                              const done = assessChecked[key]
                              return (
                                <button key={ti} onClick={() => toggleAssessTask(di, ti)}
                                  className="w-full flex items-center gap-2.5 text-left text-xs group">
                                  {done
                                    ? <CheckCircle size={13} className="text-green-400 flex-shrink-0" />
                                    : <Circle size={13} className="text-[#444] group-hover:text-[#7c6af7] flex-shrink-0" />}
                                  <span className={done ? 'text-[#555] line-through' : 'text-[#aaa]'}>{task}</span>
                                </button>
                              )
                            })}
                          </div>
                          {tasksDone > 0 && (
                            <div className="mt-2 flex items-center gap-2">
                              <div className="flex-1 bg-[#2a2a2a] rounded-full h-1">
                                <div className="bg-green-400 h-1 rounded-full transition-all"
                                  style={{ width: `${(tasksDone / day.tasks.length) * 100}%` }} />
                              </div>
                              <span className="text-[10px] text-[#555]">{tasksDone}/{day.tasks.length}</span>
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Tips */}
              {assessResult.tips?.length > 0 && (
                <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4">
                  <h3 className="text-xs font-semibold text-[#e8e8e8] mb-2 uppercase tracking-wide">Tips for Success</h3>
                  <ul className="space-y-2">
                    {assessResult.tips.map((tip, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-[#aaa]">
                        <span className="text-[#7c6af7] mt-0.5">•</span>
                        {tip}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Start over */}
              <button onClick={() => { setAssessResult(null); setAssessFile(null); setAssessChecked({}) }}
                className="text-xs text-[#555] hover:text-[#888] w-full text-center">
                ↺ Analyse a different notification
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── Shared loading (essay/formula/timeline) ─────────────────── */}
      {activeTool !== 'assessment' && loading && (
        <div className="flex items-center gap-2 text-xs text-[#555] py-4 justify-center">
          <Loader size={13} className="animate-spin text-[#7c6af7]" /> Processing...
        </div>
      )}

      {/* ── Shared result (essay/formula/timeline) ──────────────────── */}
      {activeTool !== 'assessment' && result && !loading && (
        <div className="mt-4 bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 text-sm text-[#d0d0d0] leading-relaxed whitespace-pre-wrap max-h-[60vh] overflow-y-auto">
          {result}
        </div>
      )}
    </div>
  )
}
