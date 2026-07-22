import { useState, useRef, useEffect } from 'react'
import { showToast } from '../components/Toast'
import { useStore } from '../store'
import { generateStudyPlan } from '../services/api'
import {
  Calendar, Upload, FileText, Download, Plus, Trash2, Send,
  CheckCircle, Clock, BookOpen, Loader, ChevronDown, ChevronUp,
  AlertTriangle, Zap, ArrowLeft, CalendarDays, X, Circle,
} from 'lucide-react'

const TABS = [
  { id: 'homework', label: 'Homework Scheduler', icon: Calendar },
  { id: 'study-plan', label: 'Study Plan', icon: BookOpen },
  { id: 'ai', label: 'AI Analysis', icon: FileText },
]

const PRIORITY_COLORS = {
  high: 'text-red-400 bg-red-400/10 border-red-400/20',
  medium: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20',
  low: 'text-green-400 bg-green-400/10 border-green-400/20',
}

const PHASE_COLORS = {
  'Learn': 'text-blue-400 bg-blue-400/10',
  'Practise': 'text-yellow-400 bg-yellow-400/10',
  'Practice': 'text-yellow-400 bg-yellow-400/10',
  'Revise': 'text-orange-400 bg-orange-400/10',
  'Final Review': 'text-red-400 bg-red-400/10',
}

const SLOT_STYLES = {
  school: { border: 'border-l-[#555]', bg: 'bg-[#1e1e2e]', icon: '🏫' },
  study: { border: 'border-l-[#7c6af7]', bg: 'bg-[#1a1a2e]', icon: '📖' },
  break: { border: 'border-l-[#06b6d4]', bg: 'bg-[#1a1e2e]', icon: '☕' },
  free: { border: 'border-l-[#4ade80]', bg: 'bg-[#1a2020]', icon: '🎮' },
  activity: { border: 'border-l-[#f472b6]', bg: 'bg-[#201a20]', icon: '⚽' },
}

export default function AIPlannerPage() {
  const [tab, setTab] = useState('homework')
  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex border-b border-[#2a2a40] px-4 overflow-x-auto flex-shrink-0">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-3 text-sm font-medium transition-colors border-b-2 whitespace-nowrap ${
              tab === t.id ? 'border-[#7c6af7] text-[#7c6af7]' : 'border-transparent text-[#888] hover:text-[#ccc]'
            }`}>
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-hidden">
        {tab === 'homework' ? <HomeworkSchedulerTab /> : tab === 'study-plan' ? <StudyPlanTab /> : <AIAnalysisTab />}
      </div>
    </div>
  )
}

// ════════════════════════════════════════════════════════════════════════════════
// HOMEWORK SCHEDULER
// ════════════════════════════════════════════════════════════════════════════════

function HomeworkSchedulerTab() {
  const [homework, setHomework] = useState([{ subject: '', task: '', due_date: '', estimated_minutes: 30, priority: 'medium' }])
  const [tests, setTests] = useState([{ subject: '', date: '', topics: '' }])
  const [activities, setActivities] = useState('')
  const [schoolStart, setSchoolStart] = useState('08:30')
  const [schoolEnd, setSchoolEnd] = useState('15:00')
  const [studyLen, setStudyLen] = useState(45)
  const [sleepTime, setSleepTime] = useState('22:00')
  const [daysAhead, setDaysAhead] = useState(14)
  const [loading, setLoading] = useState(false)
  const [schedule, setSchedule] = useState(null)
  const [ics, setIcs] = useState(null)
  const [selectedDay, setSelectedDay] = useState(null)
  const [confirmed, setConfirmed] = useState(false)
  const [showAddPanel, setShowAddPanel] = useState(false)
  const [addSubject, setAddSubject] = useState('')
  const [addTask, setAddTask] = useState('')
  const [addDueDate, setAddDueDate] = useState('')
  const [addMinutes, setAddMinutes] = useState(30)
  const [addPriority, setAddPriority] = useState('medium')
  const [adding, setAdding] = useState(false)

  useEffect(() => {
    try {
      const saved = localStorage.getItem('aria_confirmed_schedule')
      if (saved) {
        const data = JSON.parse(saved)
        setSchedule(data.schedule)
        setIcs(data.ics)
        setConfirmed(true)
      }
    } catch {}
  }, [])

  const confirmSchedule = () => {
    localStorage.setItem('aria_confirmed_schedule', JSON.stringify({ schedule, ics }))
    setConfirmed(true)
    showToast('Schedule confirmed and saved', 'success')
  }

  const unconfirmSchedule = () => {
    localStorage.removeItem('aria_confirmed_schedule')
    setConfirmed(false)
    showToast('Schedule unconfirmed', 'success')
  }

  const addHomework = () => setHomework([...homework, { subject: '', task: '', due_date: '', estimated_minutes: 30, priority: 'medium' }])
  const removeHomework = (i) => setHomework(homework.filter((_, j) => j !== i))
  const updateHomework = (i, key, val) => { const n = [...homework]; n[i] = { ...n[i], [key]: val }; setHomework(n) }

  const addTest = () => setTests([...tests, { subject: '', date: '', topics: '' }])
  const removeTest = (i) => setTests(tests.filter((_, j) => j !== i))
  const updateTest = (i, key, val) => { const n = [...tests]; n[i] = { ...n[i], [key]: val }; setTests(n) }

  const handleGenerate = async () => {
    const validHW = homework.filter(h => h.subject && h.task && h.due_date)
    const validTests = tests.filter(t => t.subject && t.date)
    if (!validHW.length && !validTests.length) { showToast('Add at least one homework or test', 'error'); return }
    setLoading(true); setSchedule(null); setIcs(null); setSelectedDay(null); setConfirmed(false)
    try {
      const resp = await fetch('/api/planner/schedule', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          homework: validHW.map(h => ({ ...h, estimated_minutes: Number(h.estimated_minutes) })),
          tests: validTests, school_start: schoolStart, school_end: schoolEnd,
          study_len: studyLen, activities: activities.split(',').map(a => a.trim()).filter(Boolean),
          sleep_time: sleepTime, days_ahead: daysAhead,
        }),
      })
      const data = await resp.json()
      if (data.error) throw new Error(data.error)
      setSchedule(data.schedule); setIcs(data.ics)
    } catch (e) { showToast(`Failed: ${e.message}`, 'error') }
    setLoading(false)
  }

  const downloadICS = () => {
    if (!ics) return
    const blob = new Blob([ics], { type: 'text/calendar;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'ARIA-Schedule.ics'; a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  const handleQuickAdd = async () => {
    if (!addSubject || !addTask || !addDueDate) { showToast('Fill subject, task, due date', 'error'); return }
    setAdding(true)
    try {
      const resp = await fetch('/api/planner/add-homework', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          schedule, subject: addSubject, task: addTask, due_date: addDueDate,
          estimated_minutes: addMinutes, priority: addPriority, study_len: studyLen,
        }),
      })
      const data = await resp.json()
      if (data.error) throw new Error(data.error)
      setSchedule(data.schedule); setIcs(data.ics)
      setAddSubject(''); setAddTask(''); setAddDueDate(''); setAddMinutes(30); setAddPriority('medium')
      setShowAddPanel(false)
      showToast('Homework added to schedule!', 'success')
    } catch (e) { showToast(`Failed: ${e.message}`, 'error') }
    setAdding(false)
  }

  // ── SCHEDULE DISPLAY (main view) ───────────────────────────────────────────
  if (schedule) {
    const today = new Date().toISOString().slice(0, 10)
    const activeDay = selectedDay !== null ? schedule[selectedDay] : null
    const totalStudy = schedule.reduce((s, d) => s + d.summary.study_minutes, 0)
    const totalTasks = schedule.reduce((s, d) => s + d.summary.tasks_scheduled, 0)

    return (
      <div className="h-full flex flex-col overflow-hidden relative">
        {/* ── Header bar ──────────────────────────────────────────────── */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#2a2a2a] bg-[#141414] flex-shrink-0">
          <div className="flex items-center gap-3">
            <button onClick={() => { setSchedule(null); setIcs(null); setSelectedDay(null) }}
              className="p-1.5 rounded-lg hover:bg-[#2a2a2a] text-[#888] hover:text-[#e8e8e8] transition-colors">
              <ArrowLeft size={16} />
            </button>
            <div>
              <h1 className="text-base font-semibold text-[#e8e8e8]">Your Schedule</h1>
              <p className="text-[10px] text-[#555]">{schedule.length} days &middot; {totalTasks} tasks &middot; {totalStudy} min study</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <StatBadge icon={Clock} value={`${totalStudy}m`} label="study" />
            <StatBadge icon={BookOpen} value={totalTasks} label="tasks" />
            {confirmed && (
              <span className="flex items-center gap-1 px-2 py-1 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 text-xs">
                <CheckCircle size={12} /> Confirmed
              </span>
            )}
            <button onClick={() => setShowAddPanel(!showAddPanel)}
              className="p-1.5 rounded-lg bg-[#7c6af7]/20 text-[#7c6af7] hover:bg-[#7c6af7]/30 transition-colors border border-[#7c6af7]/30"
              title="Add homework">
              <Plus size={14} />
            </button>
            {confirmed ? (
              <button onClick={unconfirmSchedule}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#2a2a2a] text-[#888] text-xs font-medium hover:bg-[#333] hover:text-[#e8e8e8] transition-colors border border-[#333]">
                <X size={12} /> Unconfirm
              </button>
            ) : (
              <button onClick={confirmSchedule}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-green-600 text-white text-xs font-medium hover:bg-green-500 transition-colors">
                <CheckCircle size={12} /> Confirm Schedule
              </button>
            )}
            <button onClick={downloadICS}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#7c6af7] text-white text-xs font-medium hover:bg-[#6a59e0] transition-colors">
              <Download size={12} /> Export Calendar
            </button>
          </div>
        </div>

        {/* ── Week strip ──────────────────────────────────────────────── */}
        <div className="flex gap-1 px-4 py-2 border-b border-[#2a2a2a] bg-[#111] flex-shrink-0 overflow-x-auto">
          {schedule.slice(0, 14).map((day, i) => {
            const isToday = day.date === today
            const isSelected = selectedDay === i
            const studyCount = day.slots.filter(s => s.type === 'study').length
            return (
              <button key={i} onClick={() => setSelectedDay(selectedDay === i ? null : i)}
                className={`flex flex-col items-center min-w-[60px] px-2 py-2 rounded-xl text-xs transition-all ${
                  isSelected ? 'bg-[#7c6af7]/20 border border-[#7c6af7]/40' :
                  isToday ? 'bg-[#252540] border border-[#7c6af7]/20' :
                  'bg-[#141414] border border-[#2a2a2a] hover:border-[#444]'
                }`}>
                <span className={`font-medium ${isToday ? 'text-[#7c6af7]' : 'text-[#888]'}`}>{day.day.slice(0, 3)}</span>
                <span className="text-[10px] text-[#555] mt-0.5">{day.date.slice(5)}</span>
                <div className="mt-1.5 flex items-center gap-0.5">
                  {studyCount > 0 && <span className="w-1.5 h-1.5 rounded-full bg-[#7c6af7]" />}
                  {day.summary.overdue > 0 && <span className="w-1.5 h-1.5 rounded-full bg-red-400" />}
                  {studyCount === 0 && day.summary.overdue === 0 && <span className="w-1.5 h-1.5 rounded-full bg-[#333]" />}
                </div>
                <span className="text-[10px] text-[#666] mt-0.5">{studyCount}s</span>
              </button>
            )
          })}
        </div>

        {/* ── Main content ────────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto">
          {activeDay ? (
            /* Full day detail */
            <div className="p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-bold text-[#e8e8e8]">{activeDay.day}</h2>
                  <p className="text-xs text-[#555]">{activeDay.date} {activeDay.is_weekend && '· Weekend'}</p>
                </div>
                <div className="flex items-center gap-3 text-xs text-[#666]">
                  <span>{activeDay.summary.study_minutes} min study</span>
                  <span>{activeDay.summary.tasks_scheduled} tasks</span>
                  {activeDay.summary.overdue > 0 && <span className="text-red-400">{activeDay.summary.overdue} overdue</span>}
                </div>
              </div>
              <div className="space-y-1.5">
                {activeDay.slots.map((slot, i) => {
                  const style = SLOT_STYLES[slot.type] || SLOT_STYLES.study
                  return (
                    <div key={i} className={`flex items-start gap-3 px-4 py-3 rounded-xl border-l-[3px] ${style.border} ${style.bg}`}>
                      <span className="text-base mt-0.5">{style.icon}</span>
                      <span className="text-xs text-[#666] font-mono w-28 flex-shrink-0 pt-0.5">{slot.time}</span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-[#e8e8e8]">{slot.task}</p>
                        {slot.subject && <p className="text-xs text-[#7c6af7] mt-0.5 font-medium">{slot.subject}</p>}
                        <div className="flex items-center gap-2 mt-1">
                          {slot.priority && (
                            <span className={`text-[10px] px-1.5 py-0.5 rounded border ${PRIORITY_COLORS[slot.priority] || ''}`}>
                              {slot.priority}
                            </span>
                          )}
                          {slot.phase && (
                            <span className={`text-[10px] px-1.5 py-0.5 rounded ${PHASE_COLORS[slot.phase] || ''}`}>
                              {slot.phase}
                            </span>
                          )}
                        </div>
                      </div>
                      {slot.duration && <span className="text-[10px] text-[#555] flex-shrink-0">{slot.duration}</span>}
                    </div>
                  )
                })}
              </div>
            </div>
          ) : (
            /* Week overview — all days collapsed */
            <div className="p-4 space-y-2">
              {schedule.map((day, i) => {
                const isToday = day.date === today
                const studySlots = day.slots.filter(s => s.type === 'study')
                return (
                  <button key={i} onClick={() => setSelectedDay(i)}
                    className={`w-full text-left p-4 rounded-xl border transition-all hover:border-[#7c6af7]/30 ${
                      isToday ? 'bg-[#7c6af7]/5 border-[#7c6af7]/20' : 'bg-[#141414] border-[#2a2a2a]'
                    }`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-sm font-bold ${
                          isToday ? 'bg-[#7c6af7] text-white' : 'bg-[#252540] text-[#888]'
                        }`}>
                          {day.day.slice(0, 2)}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-semibold text-[#e8e8e8]">{day.day}</span>
                            {isToday && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[#7c6af7] text-white">Today</span>}
                            {day.is_weekend && <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#252540] text-[#888]">Weekend</span>}
                          </div>
                          <p className="text-[11px] text-[#555] mt-0.5">{day.date}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        {/* Study summary pills */}
                        <div className="flex gap-1">
                          {studySlots.slice(0, 4).map((s, si) => (
                            <span key={si} className="text-[10px] px-1.5 py-0.5 rounded bg-[#7c6af7]/10 text-[#a89bf8] max-w-[80px] truncate">
                              {s.subject || s.task.slice(0, 15)}
                            </span>
                          ))}
                          {studySlots.length > 4 && (
                            <span className="text-[10px] text-[#555]">+{studySlots.length - 4}</span>
                          )}
                        </div>
                        <div className="text-right min-w-[50px]">
                          <div className="text-xs font-bold text-[#7c6af7]">{day.summary.study_minutes}m</div>
                          <div className="text-[10px] text-[#555]">{day.summary.tasks_scheduled} tasks</div>
                        </div>
                        <ChevronDown size={14} className="text-[#555]" />
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>

      {/* ── Quick Add Homework slide-out panel ──────────────────────────── */}
      {showAddPanel && (
        <div className="absolute top-14 right-0 w-80 bg-[#1a1a2e] border-l border-[#2a2a2a] shadow-2xl z-30 p-4 space-y-3 rounded-bl-xl">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-[#e8e8e8] flex items-center gap-2"><Plus size={14} className="text-[#7c6af7]" /> Add Homework</h3>
            <button onClick={() => setShowAddPanel(false)} className="text-[#555] hover:text-[#888]"><X size={14} /></button>
          </div>
          <input value={addSubject} onChange={e => setAddSubject(e.target.value)}
            placeholder="Subject" className="w-full px-3 py-2 text-sm rounded-lg bg-[#141414] border border-[#2a2a2a] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7]" />
          <input value={addTask} onChange={e => setAddTask(e.target.value)}
            placeholder="What to do" className="w-full px-3 py-2 text-sm rounded-lg bg-[#141414] border border-[#2a2a2a] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7]" />
          <input type="date" value={addDueDate} onChange={e => setAddDueDate(e.target.value)}
            className="w-full px-3 py-2 text-sm rounded-lg bg-[#141414] border border-[#2a2a2a] text-[#e8e8e8] focus:outline-none focus:border-[#7c6af7]" />
          <div className="flex gap-2">
            <input type="number" value={addMinutes} onChange={e => setAddMinutes(Number(e.target.value))}
              min="5" max="180" step="5" className="w-20 px-2 py-2 text-xs rounded-lg bg-[#141414] border border-[#2a2a2a] text-[#e8e8e8] text-center focus:outline-none focus:border-[#7c6af7]" />
            <select value={addPriority} onChange={e => setAddPriority(e.target.value)}
              className="flex-1 px-2 py-2 text-xs rounded-lg bg-[#141414] border border-[#2a2a2a] text-[#e8e8e8] focus:outline-none focus:border-[#7c6af7]">
              <option value="high">High Priority</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>
          <button onClick={handleQuickAdd} disabled={adding}
            className="w-full py-2 rounded-lg bg-[#7c6af7] text-white text-sm font-medium hover:bg-[#6a59e0] disabled:opacity-40 transition-colors">
            {adding ? 'Adding...' : 'Add to Schedule'}
          </button>
        </div>
      )}
      </div>
    )
  }

  // ── FORM (before generation) ─────────────────────────────────────────────
  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="space-y-6 max-w-4xl mx-auto">
        <Section title="Homework" icon={BookOpen} count={homework.filter(h => h.subject && h.task).length}>
          <div className="space-y-2">
            {homework.map((h, i) => (
              <div key={i} className="flex gap-2 items-start">
                <div className="flex-1 grid grid-cols-5 gap-2">
                  <input value={h.subject} onChange={e => updateHomework(i, 'subject', e.target.value)}
                    placeholder="Subject" className="px-3 py-2 text-sm rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7]" />
                  <input value={h.task} onChange={e => updateHomework(i, 'task', e.target.value)}
                    placeholder="What to do" className="col-span-2 px-3 py-2 text-sm rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7]" />
                  <input type="date" value={h.due_date} onChange={e => updateHomework(i, 'due_date', e.target.value)}
                    className="px-3 py-2 text-sm rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] focus:outline-none focus:border-[#7c6af7]" />
                  <div className="flex gap-1.5">
                    <input type="number" value={h.estimated_minutes} onChange={e => updateHomework(i, 'estimated_minutes', e.target.value)}
                      min="5" max="180" step="5" className="w-16 px-2 py-2 text-xs rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] focus:outline-none focus:border-[#7c6af7] text-center" />
                    <select value={h.priority} onChange={e => updateHomework(i, 'priority', e.target.value)}
                      className="px-2 py-2 text-xs rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] focus:outline-none focus:border-[#7c6af7]">
                      <option value="high">High</option>
                      <option value="medium">Med</option>
                      <option value="low">Low</option>
                    </select>
                  </div>
                </div>
                {homework.length > 1 && (
                  <button onClick={() => removeHomework(i)} className="p-2 text-[#555] hover:text-red-400 transition-colors">
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            ))}
          </div>
          <button onClick={addHomework} className="flex items-center gap-1.5 text-xs text-[#7c6af7] hover:text-[#a89bf8] transition-colors mt-2">
            <Plus size={13} /> Add homework
          </button>
        </Section>

        <Section title="Upcoming Tests" icon={AlertTriangle} count={tests.filter(t => t.subject && t.date).length}>
          <div className="space-y-2">
            {tests.map((t, i) => (
              <div key={i} className="flex gap-2 items-start">
                <div className="flex-1 grid grid-cols-3 gap-2">
                  <input value={t.subject} onChange={e => updateTest(i, 'subject', e.target.value)}
                    placeholder="Subject" className="px-3 py-2 text-sm rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7]" />
                  <input type="date" value={t.date} onChange={e => updateTest(i, 'date', e.target.value)}
                    className="px-3 py-2 text-sm rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] focus:outline-none focus:border-[#7c6af7]" />
                  <input value={t.topics} onChange={e => updateTest(i, 'topics', e.target.value)}
                    placeholder="Topics (comma sep)" className="px-3 py-2 text-sm rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7]" />
                </div>
                {tests.length > 1 && (
                  <button onClick={() => removeTest(i)} className="p-2 text-[#555] hover:text-red-400 transition-colors">
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            ))}
          </div>
          <button onClick={addTest} className="flex items-center gap-1.5 text-xs text-[#7c6af7] hover:text-[#a89bf8] transition-colors mt-2">
            <Plus size={13} /> Add test
          </button>
        </Section>

        <Section title="Settings" icon={Zap}>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <SettingInput label="School starts" value={schoolStart} onChange={setSchoolStart} />
            <SettingInput label="School ends" value={schoolEnd} onChange={setSchoolEnd} />
            <SettingInput label="Sleep time" value={sleepTime} onChange={setSleepTime} />
            <div>
              <label className="block text-xs text-[#888] mb-1">Session (min)</label>
              <select value={studyLen} onChange={e => setStudyLen(Number(e.target.value))}
                className="w-full px-3 py-2 text-sm rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] focus:outline-none focus:border-[#7c6af7]">
                {[25, 30, 45, 60, 90].map(n => <option key={n} value={n}>{n} min</option>)}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 mt-3">
            <div>
              <label className="block text-xs text-[#888] mb-1">Extracurriculars (comma sep)</label>
              <input value={activities} onChange={e => setActivities(e.target.value)}
                placeholder="Monday Soccer, Wednesday Music"
                className="w-full px-3 py-2 text-sm rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7]" />
            </div>
            <div>
              <label className="block text-xs text-[#888] mb-1">Days to plan</label>
              <select value={daysAhead} onChange={e => setDaysAhead(Number(e.target.value))}
                className="w-full px-3 py-2 text-sm rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] focus:outline-none focus:border-[#7c6af7]">
                {[7, 14, 21, 28].map(n => <option key={n} value={n}>{n} days</option>)}
              </select>
            </div>
          </div>
        </Section>

        <button onClick={handleGenerate} disabled={loading}
          className="w-full py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-40 transition-colors">
          {loading ? 'Generating...' : 'Generate Full Schedule'}
        </button>

        {loading && (
          <div className="flex flex-col items-center py-12 gap-3">
            <div className="w-8 h-8 border-2 border-[#7c6af7] border-t-transparent rounded-full animate-spin" />
            <p className="text-[#888] text-sm">Building your timetable...</p>
          </div>
        )}
      </div>
    </div>
  )
}

// ════════════════════════════════════════════════════════════════════════════════
// STUDY PLAN TAB
// ════════════════════════════════════════════════════════════════════════════════

function StudyPlanTab() {
  const { studyTools, setStudyTool } = useStore()
  const saved = studyTools.studyPlan
  const [topic, setTopic] = useState(saved.topic || '')
  const [days, setDays] = useState(saved.days || 7)
  const [plan, setPlan] = useState(saved.plan || [])
  const [loading, setLoading] = useState(false)
  const [checked, setChecked] = useState(saved.checked || {})

  useEffect(() => {
    setStudyTool('studyPlan', { plan, checked, topic, days })
  }, [plan, checked, topic, days])

  const generate = async () => {
    if (!topic.trim()) return
    setLoading(true); setPlan([]); setChecked({})
    try {
      const data = await generateStudyPlan(topic, days)
      setPlan(data.plan || [])
    } catch {}
    setLoading(false)
  }

  const toggleTask = (day, task) => {
    const key = `${day}-${task}`
    setChecked(c => ({ ...c, [key]: !c[key] }))
  }

  const exportICS = () => {
    const now = new Date()
    const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//ARIA Study Plan//EN', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH']
    plan.forEach((day, i) => {
      const startDate = new Date(now); startDate.setDate(startDate.getDate() + 1 + i); startDate.setHours(9, 0, 0, 0)
      const endDate = new Date(startDate); endDate.setMinutes(endDate.getMinutes() + (day.time_minutes || 30))
      const tasks = (day.tasks || []).map((t, ti) => `${ti + 1}. ${t}`).join('\\n')
      const fmtDT = (d) => d.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z'
      lines.push('BEGIN:VEVENT', `DTSTART:${fmtDT(startDate)}`, `DTEND:${fmtDT(endDate)}`, `SUMMARY:Day ${day.day}: ${day.title || topic}`, `DESCRIPTION:Topic: ${topic}\\n\\nTasks:\\n${tasks}`, 'LOCATION:Study Session', 'STATUS:CONFIRMED', 'END:VEVENT')
    })
    lines.push('END:VCALENDAR')
    const blob = new Blob([lines.join('\r\n')], { type: 'text/calendar;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = `ARIA-Study-Plan-${topic.replace(/\s+/g, '-')}.ics`; a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  const totalTasks = plan.reduce((sum, d) => sum + (d.tasks?.length || 0), 0)
  const doneTasks = Object.values(checked).filter(Boolean).length

  if (plan.length === 0 && !loading) {
    return (
      <div className="h-full overflow-y-auto p-4">
        <div className="space-y-4 max-w-lg mx-auto pt-8">
          <input value={topic} onChange={e => setTopic(e.target.value)} onKeyDown={e => e.key === 'Enter' && generate()}
            placeholder="What do you need to study? (e.g. Year 7 Maths exam)"
            className="w-full bg-[#1a1a2e] border border-[#2a2a40] rounded-xl px-4 py-2.5 text-sm text-[#e8e8e8] placeholder-[#555] outline-none focus:border-[#7c6af7]" />
          <div className="flex items-center gap-3">
            <label className="text-xs text-[#888]">Days:</label>
            {[3, 5, 7, 14, 30].map(n => (
              <button key={n} onClick={() => setDays(n)}
                className={`w-10 h-8 rounded-lg text-xs ${days === n ? 'bg-[#7c6af7] text-white' : 'bg-[#1a1a2e] border border-[#2a2a40] text-[#888]'}`}>
                {n}
              </button>
            ))}
          </div>
          <button onClick={generate} disabled={!topic.trim()}
            className="w-full py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-40">
            Create Study Plan
          </button>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <div className="w-8 h-8 border-2 border-[#7c6af7] border-t-transparent rounded-full animate-spin" />
        <p className="text-[#888] text-sm">Building your study plan...</p>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="space-y-3 max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h2 className="text-[#e8e8e8] font-medium text-sm">{topic}</h2>
            <p className="text-xs text-[#888] mt-0.5">{doneTasks}/{totalTasks} tasks completed</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-20"><div className="w-full bg-[#2a2a2a] rounded-full h-1.5"><div className="bg-[#7c6af7] h-1.5 rounded-full transition-all" style={{ width: `${totalTasks ? (doneTasks / totalTasks) * 100 : 0}%` }} /></div></div>
            <button onClick={exportICS} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1a1a2e] border border-[#2a2a2a] text-xs text-[#888] hover:text-[#e8e8e8] hover:border-[#7c6af7]/50 transition-colors">
              <Download size={12} /> Export
            </button>
          </div>
        </div>
        {plan.map((day, di) => (
          <div key={di} className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <span className="text-xs text-[#7c6af7] font-semibold">Day {day.day}</span>
                <p className="text-sm text-[#e8e8e8] mt-0.5">{day.title}</p>
              </div>
              <span className="text-xs text-[#555]">{day.time_minutes} min</span>
            </div>
            <div className="space-y-2">
              {(day.tasks || []).map((task, ti) => {
                const key = `${di}-${ti}`; const done = checked[key]
                return (
                  <button key={ti} onClick={() => toggleTask(di, ti)} className="w-full flex items-center gap-2.5 text-left text-xs group">
                    {done ? <CheckCircle size={14} className="text-green-400 flex-shrink-0" /> : <Circle size={14} className="text-[#444] group-hover:text-[#7c6af7] flex-shrink-0" />}
                    <span className={done ? 'text-[#555] line-through' : 'text-[#aaa]'}>{task}</span>
                  </button>
                )
              })}
            </div>
          </div>
        ))}
        <button onClick={() => setPlan([])} className="mt-2 text-xs text-[#555] hover:text-[#888] w-full text-center">↺ Create new plan</button>
      </div>
    </div>
  )
}

// ════════════════════════════════════════════════════════════════════════════════
// AI ANALYSIS TAB
// ════════════════════════════════════════════════════════════════════════════════

function AIAnalysisTab() {
  const [file, setFile] = useState(null)
  const [drag, setDrag] = useState(false)
  const [loading, setLoading] = useState(false)
  const [plan, setPlan] = useState(null)
  const [ics, setIcs] = useState(null)
  const [schoolStart, setSchoolStart] = useState('08:30')
  const [schoolEnd, setSchoolEnd] = useState('15:00')
  const [studyLen, setStudyLen] = useState('45')
  const [feedback, setFeedback] = useState('')
  const [refining, setRefining] = useState(false)
  const fileRef = useRef()

  const handleDrop = (e) => { e.preventDefault(); setDrag(false); if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]) }

  const handleAnalyse = async () => {
    if (!file) return
    setLoading(true); setPlan(null); setIcs(null)
    const fd = new FormData()
    fd.append('file', file); fd.append('school_start', schoolStart)
    fd.append('school_end', schoolEnd); fd.append('study_len', studyLen)
    try {
      const resp = await fetch('/api/planner/analyse', { method: 'POST', body: fd })
      const data = await resp.json()
      if (data.error) throw new Error(data.error)
      setPlan(data.study_plan); setIcs(data.ics)
    } catch (e) { showToast(`Analysis failed: ${e.message}`, 'error') }
    setLoading(false)
  }

  const handleRefine = async () => {
    if (!plan || !feedback.trim()) return
    setRefining(true)
    try {
      const resp = await fetch('/api/planner/refine', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan, feedback }),
      })
      const data = await resp.json()
      if (data.error) throw new Error(data.error)
      setPlan(data.study_plan); setIcs(data.ics); setFeedback(''); showToast('Plan updated!', 'success')
    } catch (e) { showToast(`Refine failed: ${e.message}`, 'error') }
    setRefining(false)
  }

  const downloadICS = () => {
    if (!ics) return
    const blob = new Blob([ics], { type: 'text/calendar;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'ARIA-Study-Plan.ics'; a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="space-y-4 max-w-3xl mx-auto">
        {!file && (
          <div onDragOver={e => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)} onDrop={handleDrop}
            onClick={() => fileRef.current?.click()}
            className={`flex flex-col items-center justify-center gap-3 py-16 rounded-2xl border-2 border-dashed cursor-pointer transition-all ${
              drag ? 'border-[#7c6af7] bg-[#7c6af7]/5' : 'border-[#2a2a2a] bg-[#141414] hover:border-[#444]'
            }`}>
            <Upload size={32} className={drag ? 'text-[#7c6af7]' : 'text-[#555]'} />
            <p className="text-sm text-[#888]">Drop your assessment notification here</p>
            <p className="text-xs text-[#555]">PDF, PNG, or JPG</p>
            <input ref={fileRef} type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={e => setFile(e.target.files[0])} className="hidden" />
          </div>
        )}

        {file && !plan && (
          <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText size={16} className="text-[#7c6af7]" />
                <span className="text-sm text-[#e8e8e8]">{file.name}</span>
              </div>
              <button onClick={() => setFile(null)} className="text-xs text-[#555] hover:text-[#888]">✕</button>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <SettingInput label="School starts" value={schoolStart} onChange={setSchoolStart} />
              <SettingInput label="School ends" value={schoolEnd} onChange={setSchoolEnd} />
              <div>
                <label className="block text-xs text-[#888] mb-1">Session (min)</label>
                <input value={studyLen} onChange={e => setStudyLen(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] font-mono focus:outline-none focus:border-[#7c6af7]" />
              </div>
            </div>
            <button onClick={handleAnalyse} disabled={loading}
              className="w-full py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-40 transition-colors">
              {loading ? 'Analysing...' : 'Analyse & Create Study Plan'}
            </button>
          </div>
        )}

        {loading && (
          <div className="flex flex-col items-center py-12 gap-3">
            <div className="w-8 h-8 border-2 border-[#7c6af7] border-t-transparent rounded-full animate-spin" />
            <p className="text-[#888] text-sm">Reading your assessment...</p>
          </div>
        )}

        {plan && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-[#e8e8e8]">Study Plan — {plan.length} sessions</h3>
              <button onClick={downloadICS}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#7c6af7] text-white text-xs font-medium hover:bg-[#6a59e0] transition-colors">
                <Download size={12} /> Export
              </button>
            </div>
            {plan.map((item, i) => (
              <div key={i} className="p-3 rounded-xl bg-[#141414] border border-[#2a2a2a]">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-[#7c6af7] font-semibold">{item.day}</span>
                    <span className="text-xs text-[#555]">{item.date}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {item.phase && <span className={`text-[10px] px-2 py-0.5 rounded-full ${PHASE_COLORS[item.phase] || ''}`}>{item.phase}</span>}
                    <span className="text-[10px] text-[#555]">{item.duration}</span>
                  </div>
                </div>
                <p className="text-sm text-[#e8e8e8] font-medium">{item.subject} — {item.topic}</p>
                <p className="text-xs text-[#888] mt-1">{item.task}</p>
              </div>
            ))}
            <div className="flex gap-2">
              <input value={feedback} onChange={e => setFeedback(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleRefine()}
                placeholder="e.g. Less biology, more maths..."
                className="flex-1 px-4 py-2.5 text-sm rounded-xl bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7]" />
              <button onClick={handleRefine} disabled={refining || !feedback.trim()}
                className="px-5 py-2.5 rounded-xl bg-[#252540] border border-[#2a2a40] text-sm text-[#ccc] hover:text-[#e8e8e8] hover:border-[#7c6af7]/50 disabled:opacity-40 transition-colors">
                {refining ? <Loader size={14} className="animate-spin" /> : <Send size={14} />}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ════════════════════════════════════════════════════════════════════════════════
// Shared
// ════════════════════════════════════════════════════════════════════════════════

function Section({ title, icon: Icon, count, children }) {
  return (
    <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <Icon size={16} className="text-[#7c6af7]" />
        <h3 className="text-sm font-semibold text-[#e8e8e8]">{title}</h3>
        {count !== undefined && <span className="text-[10px] text-[#555] bg-[#252540] px-2 py-0.5 rounded-full">{count}</span>}
      </div>
      {children}
    </div>
  )
}

function SettingInput({ label, value, onChange }) {
  return (
    <div>
      <label className="block text-xs text-[#888] mb-1">{label}</label>
      <input value={value} onChange={e => onChange(e.target.value)}
        className="w-full px-3 py-2 text-sm rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] font-mono focus:outline-none focus:border-[#7c6af7]" />
    </div>
  )
}

function StatBadge({ icon: Icon, value, label }) {
  return (
    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#252540] border border-[#2a2a2a]">
      <Icon size={12} className="text-[#7c6af7]" />
      <span className="text-xs font-bold text-[#e8e8e8]">{value}</span>
      <span className="text-[10px] text-[#555]">{label}</span>
    </div>
  )
}
