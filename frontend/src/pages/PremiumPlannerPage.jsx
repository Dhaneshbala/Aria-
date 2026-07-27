import { useState, useEffect } from 'react'
import { showToast } from '../components/Toast'
import {
  ChevronLeft, ChevronRight, ListTodo, GripVertical, Loader,
  TrendingUp, CheckCircle, X, BookOpen, Clock, Plus,
} from 'lucide-react'
import { ppGetCourses, ppGetAssignments, ppGetSessions, ppToggleSession } from '../services/api'

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const HOURS = Array.from({ length: 15 }, (_, i) => i + 7)
const HOUR_PX = 52
const COLORS = ['#7c6af7', '#4ade80', '#f472b6', '#06b6d4', '#f59e0b', '#ef4444']

function getMonday(d) {
  const date = new Date(d)
  const day = date.getDay()
  date.setDate(date.getDate() - day + (day === 0 ? -6 : 1))
  date.setHours(0, 0, 0, 0)
  return date
}

function fmtHour(h) {
  const ampm = h >= 12 ? 'p' : 'a'
  return `${h > 12 ? h - 12 : h || 12}${ampm}`
}

function toMin(s) {
  if (!s) return 0
  const [h, m] = s.split(':').map(Number)
  return h * 60 + (m || 0)
}

export default function PremiumPlannerPage() {
  const [events, setEvents] = useState([])
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [weekStart, setWeekStart] = useState(() => getMonday(new Date()))
  const [dragTask, setDragTask] = useState(null)

  useEffect(() => {
    ;(async () => {
      try {
        const [c, s, a] = await Promise.all([
          ppGetCourses().catch(() => ({ courses: [] })),
          ppGetSessions().catch(() => ({ sessions: [] })),
          ppGetAssignments().catch(() => ({ assignments: [] })),
        ])
        const courses = (c.courses || []).reduce((acc, co) => ({ ...acc, [co.id]: co.name }), {})
        setEvents((s.sessions || []).slice(0, 30).map((se, i) => ({
          id: se.id || `e${i}`,
          dayIdx: se.date ? (new Date(se.date).getDay() + 6) % 7 : 0,
          start: se.start_time || '09:00',
          end: se.end_time || '10:00',
          label: se.task || se.title || 'Busy',
          color: COLORS[i % COLORS.length],
          type: se.type || 'other',
          completed: se.completed || false,
        })))
        setTasks((a.assignments || []).filter(t => !t.completed).map((t, i) => ({
          id: t.id || `t${i}`,
          title: t.title || 'Task',
          course: courses[t.course_id] || '',
          hours: t.estimated_hours || 1,
          due: t.due_date || '',
          color: COLORS[i % COLORS.length],
        })))
      } catch (e) { console.error(e) }
      setLoading(false)
    })()
  }, [])

  const weekDays = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(weekStart)
    d.setDate(d.getDate() + i)
    return d
  })
  const today = new Date()
  const isT = (d) => d.getDate() === today.getDate() && d.getMonth() === today.getMonth()

  const dayEvents = (date) => events.filter(e => {
    const ed = new Date(weekStart)
    ed.setDate(ed.getDate() + (e.dayIdx || 0))
    return ed.toDateString() === date.toDateString()
  })

  const dayTasks = (date) => tasks.filter(t => t.due === date.toISOString().slice(0, 10))

  const placeTask = (date, hour) => {
    if (!dragTask) return
    const hh = hour.toString().padStart(2, '0')
    const endMin = hour * 60 + Math.round(dragTask.hours * 60)
    const eh = Math.floor(endMin / 60).toString().padStart(2, '0')
    const em = (endMin % 60).toString().padStart(2, '0')
    setEvents(prev => [...prev, {
      id: `s-${Date.now()}`,
      dayIdx: (date.getDay() + 6) % 7,
      start: `${hh}:00`,
      end: `${eh}:${em}`,
      label: dragTask.title,
      color: dragTask.color,
      type: 'study',
      completed: false,
    }])
    setDragTask(null)
    showToast(`Planned: ${dragTask.title}`, 'success')
  }

  const toggleDone = async (id) => {
    try { await ppToggleSession(id) } catch {}
    setEvents(prev => prev.map(e => e.id === id ? { ...e, completed: !e.completed } : e))
  }

  const removeEvent = (id) => setEvents(prev => prev.filter(e => e.id !== id))

  if (loading) return (
    <div className="flex items-center justify-center h-full">
      <Loader size={24} className="animate-spin text-[#7c6af7]" />
    </div>
  )

  const totalHours = weekDays.reduce((sum, d) => {
    const busy = dayEvents(d).reduce((s, e) => s + (toMin(e.end) - toMin(e.start)), 0)
    return sum + (15 * 60 - busy)
  }, 0) / 60
  const needHours = tasks.reduce((s, t) => s + t.hours, 0)
  const cushion = totalHours - needHours

  return (
    <div className="flex flex-col h-full bg-[#0f0f0f]">
      {/* Top bar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[#2a2a2a] bg-[#141414] shrink-0">
        <div className="flex items-center gap-1.5">
          <button onClick={() => { const d = new Date(weekStart); d.setDate(d.getDate() - 7); setWeekStart(d) }}
            className="p-1 rounded hover:bg-[#2a2a2a] text-[#888]"><ChevronLeft size={15} /></button>
          <span className="text-xs font-semibold text-[#e8e8e8] min-w-[160px] text-center">
            {weekDays[0].toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            <span className="text-[#555] mx-1">-</span>
            {weekDays[6].toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
          </span>
          <button onClick={() => { const d = new Date(weekStart); d.setDate(d.getDate() + 7); setWeekStart(d) }}
            className="p-1 rounded hover:bg-[#2a2a2a] text-[#888]"><ChevronRight size={15} /></button>
          <button onClick={() => setWeekStart(getMonday(new Date()))}
            className="text-[10px] px-2 py-1 rounded bg-[#2a2a2a] text-[#888] hover:text-[#e8e8e8]">Today</button>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <TrendingUp size={13} className={cushion >= 0 ? 'text-[#4ade80]' : 'text-[#ef4444]'} />
          <span className={cushion >= 0 ? 'text-[#4ade80]' : 'text-[#ef4444]'}>{cushion >= 0 ? '+' : ''}{cushion.toFixed(1)}h</span>
          <span className="text-[#555]">cushion</span>
          <span className="text-[#555] ml-1">{needHours.toFixed(1)}h needed</span>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Calendar */}
        <div className="flex-1 overflow-auto">
          <div className="min-w-[550px]">
            {/* Header */}
            <div className="flex sticky top-0 z-20 bg-[#0f0f0f] border-b border-[#2a2a2a]">
              <div className="w-12 shrink-0" />
              {weekDays.map((d, i) => (
                <div key={i} className="flex-1 border-r border-[#2a2a2a] text-center py-1.5">
                  <div className="text-[9px] text-[#555] uppercase">{DAYS[i]}</div>
                  <div className={`text-sm font-bold ${isT(d) ? 'text-[#7c6af7]' : 'text-[#e8e8e8]'}`}>{d.getDate()}</div>
                  {dayTasks(d).length > 0 && (
                    <div className="text-[8px] text-red-400 mt-0.5">{dayTasks(d).length} due</div>
                  )}
                </div>
              ))}
            </div>
            {/* Body */}
            {HOURS.map(h => (
              <div key={h} className="flex border-b border-[#1a1a1a]" style={{ height: HOUR_PX }}>
                <div className="w-12 shrink-0 border-r border-[#2a2a2a] flex items-start justify-end pr-1 pt-0">
                  <span className="text-[9px] text-[#555] font-mono">{fmtHour(h)}</span>
                </div>
                {weekDays.map((d, di) => {
                  const items = dayEvents(d).filter(e => {
                    const s = toMin(e.start); const en = toMin(e.end)
                    return s < (h + 1) * 60 && en > h * 60
                  })
                  return (
                    <div key={di}
                      onClick={() => placeTask(d, h)}
                      onDragOver={e => e.preventDefault()}
                      onDrop={() => placeTask(d, h)}
                      className={`flex-1 border-r border-[#1a1a1a] relative cursor-pointer hover:bg-white/[0.03] ${isT(d) ? 'bg-[#7c6af7]/[0.03]' : ''}`}
                      style={{ minHeight: HOUR_PX }}>
                      {items.map(e => {
                        const s = toMin(e.start); const en = toMin(e.end)
                        const top = Math.max(0, (s - h * 60) / 60 * HOUR_PX)
                        const ht = Math.min((Math.min(en, (h + 1) * 60) - Math.max(s, h * 60)) / 60 * HOUR_PX, HOUR_PX - top)
                        if (ht < 4) return null
                        return (
                          <div key={e.id} className="absolute left-0.5 right-0.5 z-10 rounded overflow-hidden group"
                            style={{ top, height: Math.max(ht, 14), backgroundColor: e.color + '20', borderLeft: `3px solid ${e.color}`, opacity: e.completed ? 0.35 : 1 }}>
                            <div className="px-1 py-0.5 text-[9px] leading-tight">
                              <span className="font-medium text-[#e8e8e8] truncate block">{e.label}</span>
                              <span className="text-[7px] text-[#666]">{e.start?.slice(0, 5)}</span>
                            </div>
                            {e.type === 'study' && (
                              <div className="absolute top-0 right-0 hidden group-hover:flex gap-0.5 p-0.5 bg-black/60 rounded-bl">
                                <button onClick={e => { e.stopPropagation(); toggleDone(e.id) }}
                                  className="text-green-400 hover:text-green-300"><CheckCircle size={8} /></button>
                                <button onClick={e => { e.stopPropagation(); removeEvent(e.id) }}
                                  className="text-red-400 hover:text-red-300"><X size={8} /></button>
                              </div>
                            )}
                          </div>
                        )
                      })}
                      {dragTask && (
                        <div className="absolute inset-1 border-2 border-dashed border-[#7c6af7]/40 rounded z-20 pointer-events-none" />
                      )}
                    </div>
                  )
                })}
              </div>
            ))}
          </div>
        </div>

        {/* Right sidebar - The Pile */}
        <div className="w-56 shrink-0 border-l border-[#2a2a2a] bg-[#141414] flex flex-col">
          <div className="p-2.5 border-b border-[#2a2a2a]">
            <h2 className="text-xs font-semibold text-[#e8e8e8] flex items-center gap-1.5">
              <ListTodo size={13} className="text-[#7c6af7]" /> The Pile
            </h2>
            <div className="text-[10px] text-[#555] mt-1">{tasks.length} tasks · {needHours.toFixed(1)}h needed</div>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {tasks.length === 0 && (
              <div className="text-center py-8">
                <BookOpen size={22} className="mx-auto text-[#333] mb-2" />
                <p className="text-[11px] text-[#555]">No tasks</p>
                <p className="text-[9px] text-[#444] mt-1">Add assignments in Courses tab</p>
              </div>
            )}
            {tasks.map(t => (
              <div key={t.id} draggable onDragStart={() => setDragTask(t)} onDragEnd={() => setDragTask(null)}
                className="flex items-center gap-2 p-2 rounded-lg bg-[#1a1a2e] border border-[#2a2a40] cursor-grab active:cursor-grabbing hover:border-[#7c6af7]/40 transition-colors group">
                <GripVertical size={11} className="text-[#444] group-hover:text-[#7c6af7] shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-[11px] text-[#e8e8e8] truncate">{t.title}</div>
                  <div className="flex items-center gap-2 text-[9px] text-[#555] mt-0.5">
                    {t.course && <span className="text-[#7c6af7] truncate">{t.course}</span>}
                    <span>{t.hours}h</span>
                    {t.due && <span>Due {t.due.slice(5)}</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
