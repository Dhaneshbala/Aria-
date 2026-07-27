import { useState, useEffect, useRef } from 'react'
import { showToast } from '../components/Toast'
import { exportICS, importICS } from '../services/api'
import {
  Plus, Trash2, Loader, Sun, Moon, Eye, EyeOff, Palette,
  Minus, GripVertical, ChevronDown, Upload, FileText,
  BookOpen, AlertTriangle, Download, Calendar as CalendarIcon,
} from 'lucide-react'

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const HOURS = Array.from({ length: 15 }, (_, i) => i + 7)
const HOUR_PX = 60
const COLORS = ['#7c6af7', '#4ade80', '#f472b6', '#06b6d4', '#f59e0b', '#ef4444', '#3b82f6', '#a78bfa']

function fmtHour(h) {
  const ampm = h >= 12 ? 'PM' : 'AM'
  const hh = h > 12 ? h - 12 : h || 12
  return `${hh} ${ampm}`
}

function toMin(s) {
  if (!s) return 0
  const [h, m] = s.split(':').map(Number)
  return h * 60 + (m || 0)
}

function fmtDuration(minutes) {
  if (minutes < 60) return `${minutes}m`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return m ? `${h}h ${m}m` : `${h}h`
}

function fmtTime(h, m = 0) {
  const hh = h > 12 ? h - 12 : h || 12
  return `${hh}:${m.toString().padStart(2, '0')}`
}

export default function AIPlannerPage() {
  const [courses, setCourses] = useState([
    { id: 'c1', name: 'Mathematics', color: '#7c6af7', visible: true, defaultDuration: 60 },
    { id: 'c2', name: 'Science', color: '#4ade80', visible: true, defaultDuration: 60 },
    { id: 'c3', name: 'English', color: '#f472b6', visible: true, defaultDuration: 45 },
    { id: 'c4', name: 'History', color: '#06b6d4', visible: true, defaultDuration: 60 },
  ])
  const [activities, setActivities] = useState([
    { id: 'a1', name: 'Morning Routine', color: '#888', visible: true, defaultDuration: 30 },
    { id: 'a2', name: 'Breakfast', color: '#f59e0b', visible: true, defaultDuration: 30 },
    { id: 'a3', name: 'Lunch', color: '#3b82f6', visible: true, defaultDuration: 60 },
    { id: 'a4', name: 'Dinner', color: '#f59e0b', visible: true, defaultDuration: 60 },
    { id: 'a5', name: 'Workout', color: '#06b6d4', visible: true, defaultDuration: 60 },
    { id: 'a6', name: 'Me Time', color: '#a78bfa', visible: true, defaultDuration: 60 },
  ])
  const [events, setEvents] = useState([])
  const [awakeMode, setAwakeMode] = useState(false)
  const [minBlock, setMinBlock] = useState(15)
  const [quickAddItem, setQuickAddItem] = useState(null)
  const [showAddCourse, setShowAddCourse] = useState(false)
  const [showAddActivity, setShowAddActivity] = useState(false)
  const [showUploadSyllabus, setShowUploadSyllabus] = useState(false)
  const [syllabusFile, setSyllabusFile] = useState(null)
  const [syllabusLoading, setSyllabusLoading] = useState(false)
  const [showImportCalendar, setShowImportCalendar] = useState(false)
  const [calFile, setCalFile] = useState(null)
  const [calLoading, setCalLoading] = useState(false)
  const [editEvent, setEditEvent] = useState(null)

  const toggleVisibility = (arr, setArr, id) => {
    setArr(arr.map(i => i.id === id ? { ...i, visible: !i.visible } : i))
  }

  const cycleColor = (arr, setArr, id, palette) => {
    setArr(arr.map(i => {
      if (i.id !== id) return i
      const idx = palette.indexOf(i.color)
      return { ...i, color: palette[(idx + 1) % palette.length] }
    }))
  }

  const changeDuration = (arr, setArr, id, delta) => {
    setArr(arr.map(i => {
      if (i.id !== id) return i
      return { ...i, defaultDuration: Math.max(15, Math.min(180, (i.defaultDuration || 60) + delta)) }
    }))
  }

  const addCourse = (name) => {
    if (!name.trim()) return
    setCourses([...courses, { id: `c${Date.now()}`, name: name.trim(), color: COLORS[courses.length % COLORS.length], visible: true, defaultDuration: 60 }])
    setShowAddCourse(false)
  }

  const addActivity = (name) => {
    if (!name.trim()) return
    setActivities([...activities, { id: `a${Date.now()}`, name: name.trim(), color: COLORS[activities.length % COLORS.length], visible: true, defaultDuration: 30 }])
    setShowAddActivity(false)
  }

  const placeEvent = (dayIdx, hour, item) => {
    if (!item) return
    const start = `${hour.toString().padStart(2, '0')}:00`
    const endMin = hour * 60 + (item.defaultDuration || 60)
    const endH = Math.floor(endMin / 60)
    const endM = endMin % 60
    const end = `${endH.toString().padStart(2, '0')}:${endM.toString().padStart(2, '0')}`
    const newEvent = {
      id: `e${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      dayIdx,
      start,
      end,
      label: item.name,
      color: item.color,
      courseId: item.id,
      type: item.id?.startsWith('c') ? 'course' : 'activity',
      completed: false,
    }
    setEvents(prev => [...prev, newEvent])
    setQuickAddItem(null)
    showToast(`${item.name} added to ${DAYS[dayIdx]}`, 'success')
  }

  const removeEvent = (id) => setEvents(prev => prev.filter(e => e.id !== id))

  const toggleComplete = (id) => {
    setEvents(prev => prev.map(e => e.id === id ? { ...e, completed: !e.completed } : e))
  }

  const getEventsForDay = (dayIdx) => events.filter(e => e.dayIdx === dayIdx)

  const handleSyllabusUpload = async () => {
    if (!syllabusFile) return
    setSyllabusLoading(true)
    try {
      const formData = new FormData()
      formData.append('file', syllabusFile)
      const resp = await fetch('/api/planner/upload-syllabus', { method: 'POST', body: formData })
      const data = await resp.json()
      if (data.error) throw new Error(data.error)
      if (data.data?.tasks) {
        data.data.tasks.forEach(t => {
          const existing = courses.find(c => c.name.toLowerCase() === t.subject?.toLowerCase())
          if (existing) {
            placeEvent(1, 9, existing)
          }
        })
      }
      showToast('Syllabus imported!', 'success')
    } catch (e) {
      showToast(`Failed: ${e.message}`, 'error')
    }
    setSyllabusLoading(false)
    setShowUploadSyllabus(false)
    setSyllabusFile(null)
  }

  const handleCalendarImport = async () => {
    if (!calFile) return
    setCalLoading(true)
    try {
      const data = await importICS(calFile)
      if (data.error) throw new Error(data.error)
      if (data.events?.length) {
        setEvents(prev => [...prev, ...data.events])
        showToast(`Imported ${data.count} events from Google Calendar!`, 'success')
      } else {
        showToast('No events found in the file', 'error')
      }
    } catch (e) {
      showToast(`Failed: ${e.message}`, 'error')
    }
    setCalLoading(false)
    setShowImportCalendar(false)
    setCalFile(null)
  }

  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'Escape') { setQuickAddItem(null); setEditEvent(null) }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  // Calculate study time stats
  const totalMinutesPerWeek = 7 * 15 * 60 // 7 days * 15h awake
  const busyMinutes = events.reduce((sum, e) => sum + (toMin(e.end) - toMin(e.start)), 0)
  const studyTime = Math.max(0, totalMinutesPerWeek - busyMinutes) / 60
  const busyTime = busyMinutes / 60
  const extraTime = 0

  const getFreeGaps = (dayIdx) => {
    const dayEvents = getEventsForDay(dayIdx)
      .map(e => ({ start: toMin(e.start), end: toMin(e.end) }))
      .sort((a, b) => a.start - b.start)
    const gaps = []
    const dayStart = 7 * 60
    const dayEnd = 22 * 60
    let current = dayStart
    dayEvents.forEach(e => {
      if (e.start > current) {
        gaps.push({ start: current, end: e.start })
      }
      current = Math.max(current, e.end)
    })
    if (current < dayEnd) gaps.push({ start: current, end: dayEnd })
    return gaps.filter(g => (g.end - g.start) >= minBlock)
  }

  const allItems = [...courses, ...activities]

  return (
    <div className="flex h-full bg-white text-gray-800 overflow-hidden">
      {/* ── Left Sidebar ─────────────────────────────────────────── */}
      <div className="w-56 flex-shrink-0 border-r border-gray-200 bg-white overflow-y-auto">
        <div className="p-3 border-b border-gray-200">
          <h1 className="text-sm font-bold text-gray-900">Schedule Builder</h1>
          <div className="flex items-center gap-2 mt-2">
            <button onClick={() => setAwakeMode(!awakeMode)}
              className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-[11px] font-medium border transition-colors ${
                awakeMode ? 'bg-gray-900 text-white border-gray-900' : 'bg-white text-gray-600 border-gray-300 hover:border-gray-400'
              }`}>
              {awakeMode ? <Sun size={12} /> : <Moon size={12} />}
              Awake Time
            </button>
            <button onClick={() => setShowUploadSyllabus(!showUploadSyllabus)}
              className="p-1.5 rounded-full border border-gray-300 text-gray-500 hover:bg-gray-100 transition-colors"
              title="Upload syllabus">
              <Upload size={12} />
            </button>
            <button onClick={() => setShowImportCalendar(!showImportCalendar)}
              className="p-1.5 rounded-full border border-gray-300 text-gray-500 hover:bg-gray-100 transition-colors"
              title="Import Google Calendar (.ics)">
              <CalendarIcon size={12} />
            </button>
            <button onClick={async () => {
              if (!events.length) { showToast('No events to export', 'error'); return }
              try {
                const resp = await exportICS(events)
                const blob = await resp.blob()
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url; a.download = 'aria_schedule.ics'; a.click()
                URL.revokeObjectURL(url)
                showToast('Calendar exported!', 'success')
              } catch (e) { showToast('Export failed', 'error') }
            }}
              className="p-1.5 rounded-full border border-gray-300 text-gray-500 hover:bg-gray-100 transition-colors"
              title="Download .ics calendar file">
              <Download size={12} />
            </button>
          </div>
        </div>

        {/* Courses */}
        <div className="p-3 border-b border-gray-200">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-gray-700">Courses</span>
            <button onClick={() => setShowAddCourse(true)} className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600">
              <Plus size={14} />
            </button>
          </div>
          {showAddCourse && <AddForm onSubmit={addCourse} onCancel={() => setShowAddCourse(false)} />}
          <div className="space-y-1">
            {courses.map(c => (
              <SidebarItem key={c.id} item={c} palette={COLORS}
                onToggle={() => toggleVisibility(courses, setCourses, c.id)}
                onColor={() => cycleColor(courses, setCourses, c.id, COLORS)}
                onDuration={(d) => changeDuration(courses, setCourses, c.id, d)}
                onSelect={() => setQuickAddItem(c)} />
            ))}
          </div>
        </div>

        {/* Activities */}
        <div className="p-3 border-b border-gray-200">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-gray-700">Activities</span>
            <button onClick={() => setShowAddActivity(true)} className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600">
              <Plus size={14} />
            </button>
          </div>
          {showAddActivity && <AddForm onSubmit={addActivity} onCancel={() => setShowAddActivity(false)} placeholder="Activity name" />}
          <div className="space-y-1">
            {activities.map(a => (
              <SidebarItem key={a.id} item={a} palette={COLORS}
                onToggle={() => toggleVisibility(activities, setActivities, a.id)}
                onColor={() => cycleColor(activities, setActivities, a.id, COLORS)}
                onDuration={(d) => changeDuration(activities, setActivities, a.id, d)}
                onSelect={() => setQuickAddItem(a)} />
            ))}
          </div>
        </div>

        {/* Quick add hint */}
        {quickAddItem && (
          <div className="p-3 bg-purple-50 border-b border-purple-200">
            <p className="text-[11px] text-purple-700 font-medium">Click a time slot to place:</p>
            <div className="flex items-center gap-1.5 mt-1">
              <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: quickAddItem.color }} />
              <span className="text-xs text-purple-800 font-medium">{quickAddItem.name}</span>
              <button onClick={() => setQuickAddItem(null)} className="ml-auto text-purple-400 hover:text-purple-600"><Trash2 size={10} /></button>
            </div>
          </div>
        )}

        {/* Min block slider */}
        <div className="p-3 border-b border-gray-200">
          <div className="text-xs font-semibold text-gray-700 mb-2">Minimum Study Time Block</div>
          <div className="flex items-center gap-2">
            <input type="range" min="5" max="60" step="5" value={minBlock}
              onChange={e => setMinBlock(Number(e.target.value))}
              className="flex-1 accent-gray-800 h-1" />
            <span className="text-xs text-gray-500 w-8 text-right">{minBlock}m</span>
          </div>
          <p className="text-[10px] text-gray-400 mt-1">Excludes small time blocks from your study time calculation</p>
        </div>

        {/* Stats */}
        <div className="p-3 space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-purple-600" /> Study Time</span>
            <span className="font-semibold text-gray-800">{Math.round(studyTime * 60)}h</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-gray-300" /> Busy Time</span>
            <span className="font-semibold text-gray-800">{Math.round(busyTime * 60)}h</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-gray-400" /> Extra Time</span>
            <span className="font-semibold text-gray-800">{Math.round(extraTime * 60)}h</span>
          </div>
        </div>
      </div>

      {/* ── Calendar Grid ────────────────────────────────────────── */}
      <div className="flex-1 overflow-auto bg-gray-50">
        <div className="min-w-[650px]">
          {/* Day headers */}
          <div className="flex sticky top-0 z-20 bg-white border-b border-gray-200">
            <div className="w-16 flex-shrink-0" />
            {DAYS.map((d, i) => {
              const today = new Date()
              const isToday = today.getDay() === i
              return (
                <div key={d} className={`flex-1 text-center py-2 border-r border-gray-200 ${isToday ? 'bg-gray-900 text-white' : ''}`}>
                  <div className="text-[10px] font-medium uppercase tracking-wide">{d}</div>
                </div>
              )
            })}
          </div>

          {/* Hour rows */}
          {HOURS.map(h => (
            <div key={h} className="flex border-b border-gray-100" style={{ height: HOUR_PX }}>
              <div className="w-16 flex-shrink-0 border-r border-gray-200 flex items-start justify-end pr-2 pt-1">
                <span className="text-[10px] text-gray-500 font-medium">{fmtHour(h)}</span>
              </div>
              {DAYS.map((d, di) => {
                const dayEvents = getEventsForDay(di).filter(e => {
                  const s = toMin(e.start)
                  const en = toMin(e.end)
                  return s < (h + 1) * 60 && en > h * 60
                })
                const gaps = getFreeGaps(di)
                const freeGap = gaps.find(g => {
                  const gapStart = g.start
                  return h * 60 >= gapStart && h * 60 < g.end && g.end - g.start >= minBlock
                })
                const isGapStart = freeGap && h * 60 === freeGap.start
                const gapMinutes = freeGap ? freeGap.end - freeGap.start : 0
                const gapHour = freeGap ? Math.floor(freeGap.start / 60) : 0
                const gapStartMin = freeGap ? freeGap.start % 60 : 0

                return (
                  <div key={di}
                    onClick={() => {
                      if (quickAddItem) { placeEvent(di, h, quickAddItem); return }
                      setEditEvent({ dayIdx: di, hour: h })
                    }}
                    onDragOver={e => e.preventDefault()}
                    className={`flex-1 border-r border-gray-100 relative cursor-pointer hover:bg-gray-100/80 transition-colors ${isGapStart ? 'bg-purple-50/30' : ''}`}
                    style={{ minHeight: HOUR_PX }}>
                    {/* Events in this cell */}
                    {dayEvents.map(e => {
                      const s = toMin(e.start)
                      const en = toMin(e.end)
                      const top = Math.max(0, (s - h * 60) / 60 * HOUR_PX)
                      const ht = Math.min((Math.min(en, (h + 1) * 60) - Math.max(s, h * 60)) / 60 * HOUR_PX, HOUR_PX - top)
                      if (ht < 4) return null
                      return (
                        <div key={e.id}
                          className="absolute left-1 right-1 z-10 rounded-lg overflow-hidden group shadow-sm"
                          style={{ top, height: Math.max(ht, 18), backgroundColor: e.color + '20', borderLeft: `3px solid ${e.color}` }}>
                          <div className="px-1.5 py-0.5 text-[10px] leading-tight">
                            <span className="font-medium text-gray-800 truncate block">{e.label}</span>
                            {ht > 24 && (
                              <span className="text-[9px] text-gray-500">{e.start?.slice(0,5)} - {e.end?.slice(0,5)}</span>
                            )}
                          </div>
                          <div className="absolute top-0.5 right-0.5 hidden group-hover:flex gap-0.5">
                            <button onClick={(ev) => { ev.stopPropagation(); toggleComplete(e.id) }}
                              className={`w-4 h-4 rounded-full flex items-center justify-center ${e.completed ? 'bg-green-500 text-white' : 'bg-white/80 text-gray-400 hover:text-green-500'}`}>
                              {e.completed && '✓'}
                            </button>
                            <button onClick={(ev) => { ev.stopPropagation(); removeEvent(e.id) }}
                              className="w-4 h-4 rounded-full bg-white/80 text-gray-400 hover:text-red-500 flex items-center justify-center">
                              ×
                            </button>
                          </div>
                        </div>
                      )
                    })}
                    {/* Free time label */}
                    {isGapStart && gapMinutes >= minBlock && (
                      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <span className="text-[10px] font-semibold text-purple-500 bg-white/70 px-1.5 py-0.5 rounded">
                          {fmtDuration(gapMinutes)}
                        </span>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      </div>

      {/* ── Right Panel ──────────────────────────────────────────── */}
      <div className="w-48 flex-shrink-0 border-l border-gray-200 bg-white p-4 overflow-y-auto">
        <h2 className="text-sm font-bold text-gray-900">Your Study Time</h2>
        <p className="text-[10px] text-gray-400 mt-0.5">(free time between your events)</p>

        <div className="text-center my-4">
          <div className="text-4xl font-bold text-gray-900">{Math.round(studyTime * 60)}h</div>
        </div>

        {/* Progress bar */}
        <div className="mb-3">
          <div className="flex h-3 rounded-full overflow-hidden">
            <div className="bg-orange-400" style={{ width: `${Math.min(100, (busyTime / 15) * 100)}%` }} />
            <div className="bg-green-400" style={{ width: `${Math.min(100, (studyTime / 15) * 100)}%` }} />
            <div className="bg-red-400" style={{ width: `${Math.max(0, 100 - (studyTime + busyTime) / 15 * 100)}%` }} />
          </div>
          <div className="flex justify-between text-[9px] mt-1">
            <span className="text-orange-500 font-medium">Incomplete Schedule</span>
            <span className="text-green-500 font-medium">Ideal Study Time</span>
          </div>
          <div className="text-center">
            <span className="text-[9px] text-red-500 font-medium">Too Little Study Time</span>
          </div>
        </div>

        {/* Is this enough? */}
        <div className="mt-4 p-3 bg-gray-50 rounded-xl">
          <p className="text-xs font-semibold text-gray-800">Is this enough study time?</p>
          <p className="text-[11px] text-gray-500 mt-1">
            {studyTime >= 35 ? "You're in good shape!" :
             studyTime >= 20 ? "Consider blocking more study time." :
             "You may need to free up more time for studying."}
          </p>
        </div>

        <div className="mt-4 text-center">
          <button className="text-[11px] text-purple-600 font-medium hover:underline">Find out with ARIA!</button>
        </div>
      </div>

      {/* ── Edit Event Modal ─────────────────────────────────────── */}
      {editEvent && (
        <div className="fixed bottom-4 right-4 bg-white border border-gray-200 rounded-xl shadow-2xl p-4 z-50 w-64">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-gray-800">Add Event</span>
            <button onClick={() => setEditEvent(null)} className="text-gray-400 hover:text-gray-600"><Trash2 size={12} /></button>
          </div>
          <div className="text-[11px] text-gray-500 mb-2">{DAYS[editEvent.dayIdx]} at {fmtTime(editEvent.hour)}</div>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {allItems.filter(i => i.visible).map(item => (
              <button key={item.id} onClick={() => { placeEvent(editEvent.dayIdx, editEvent.hour, item); setEditEvent(null) }}
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-left text-gray-800 hover:bg-gray-100 transition-colors">
                <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: item.color }} />
                {item.name}
                <span className="ml-auto text-[10px] text-gray-400">{item.defaultDuration}m</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Upload Syllabus Modal ────────────────────────────────── */}
      {showUploadSyllabus && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center">
          <div className="bg-white rounded-2xl shadow-2xl p-6 w-96">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-gray-900">Upload Syllabus</h3>
              <button onClick={() => setShowUploadSyllabus(false)} className="text-gray-400 hover:text-gray-600"><Trash2 size={14} /></button>
            </div>
            <p className="text-xs text-gray-500 mb-3">Upload a PDF syllabus to automatically extract courses and activities.</p>
            <input type="file" accept=".pdf,.txt,.md" onChange={e => setSyllabusFile(e.target.files[0])}
              className="w-full text-xs text-gray-500 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-medium file:bg-gray-100 file:text-gray-700 mb-3" />
            <button onClick={handleSyllabusUpload} disabled={!syllabusFile || syllabusLoading}
              className="w-full py-2.5 rounded-xl bg-gray-900 text-white text-xs font-medium hover:bg-gray-800 disabled:opacity-40 transition-colors">
              {syllabusLoading ? 'Importing...' : 'Import Syllabus'}
            </button>
          </div>
        </div>
      )}

      {/* ── Import Google Calendar Modal ────────────────────────── */}
      {showImportCalendar && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center">
          <div className="bg-white rounded-2xl shadow-2xl p-6 w-96">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-gray-900">Import Google Calendar</h3>
              <button onClick={() => setShowImportCalendar(false)} className="text-gray-400 hover:text-gray-600"><Trash2 size={14} /></button>
            </div>
            <div className="space-y-3">
              <div className="bg-blue-50 rounded-xl p-3">
                <p className="text-[11px] text-blue-800 font-medium mb-1">How to export from Google Calendar:</p>
                <ol className="text-[10px] text-blue-700 space-y-0.5 list-decimal list-inside">
                  <li>Go to <span className="font-medium">calendar.google.com</span></li>
                  <li>Click ⚙️ Settings → <span className="font-medium">Import & Export</span></li>
                  <li>Click <span className="font-medium">Export</span> — download a .ics file</li>
                  <li>Upload that file here</li>
                </ol>
              </div>
              <input type="file" accept=".ics" onChange={e => setCalFile(e.target.files[0])}
                className="w-full text-xs text-gray-500 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-medium file:bg-gray-100 file:text-gray-700" />
              <button onClick={handleCalendarImport} disabled={!calFile || calLoading}
                className="w-full py-2.5 rounded-xl bg-gray-900 text-white text-xs font-medium hover:bg-gray-800 disabled:opacity-40 transition-colors">
                {calLoading ? 'Importing...' : 'Import Calendar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function SidebarItem({ item, palette, onToggle, onColor, onDuration, onSelect }) {
  return (
    <div className="flex items-center gap-1 group">
      <button onClick={onSelect}
        className="flex-1 flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-xs text-gray-700 hover:bg-gray-100 transition-colors cursor-grab active:cursor-grabbing"
        title={`Drag ${item.name} to schedule`}>
        <GripVertical size={10} className="text-gray-300 group-hover:text-gray-400" />
        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: item.color }} />
        <span className={`truncate flex-1 ${!item.visible ? 'text-gray-400 line-through' : ''}`}>{item.name}</span>
      </button>
      <button onClick={onColor} className="p-0.5 rounded opacity-0 group-hover:opacity-100 hover:bg-gray-200 text-gray-400 transition-all" title="Change color">
        <Palette size={9} />
      </button>
      <button onClick={onToggle} className="p-0.5 rounded opacity-0 group-hover:opacity-100 hover:bg-gray-200 text-gray-400 transition-all" title={item.visible ? 'Hide' : 'Show'}>
        {item.visible ? <Eye size={9} /> : <EyeOff size={9} />}
      </button>
      <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-all">
        <button onClick={() => onDuration(-15)} className="p-0.5 rounded hover:bg-gray-200 text-gray-400"><Minus size={7} /></button>
        <span className="text-[9px] text-gray-500 font-mono w-5 text-center">{item.defaultDuration}</span>
        <button onClick={() => onDuration(15)} className="p-0.5 rounded hover:bg-gray-200 text-gray-400"><Plus size={7} /></button>
      </div>
    </div>
  )
}

function AddForm({ onSubmit, onCancel, placeholder = 'Course name' }) {
  const [val, setVal] = useState('')
  const ref = useRef()
  useEffect(() => { ref.current?.focus() }, [])
  return (
    <div className="flex gap-1 mb-1.5">
      <input ref={ref} value={val} onChange={e => setVal(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') onSubmit(val); if (e.key === 'Escape') onCancel() }}
        placeholder={placeholder}
        className="flex-1 px-2 py-1 text-[11px] rounded-lg bg-gray-50 border border-gray-200 text-gray-800 placeholder-gray-400 outline-none focus:border-gray-400" />
      <button onClick={() => onSubmit(val)}
        className="px-2 py-1 rounded-lg bg-gray-900 text-white text-[10px] font-medium hover:bg-gray-800 transition-colors">Add</button>
    </div>
  )
}
