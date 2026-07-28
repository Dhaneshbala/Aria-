import { useState, useEffect, useRef, useMemo } from 'react'
import { showToast } from '../components/Toast'
import { exportICS, importICS, loadPlannerEvents, savePlannerEvents } from '../services/api'
import {
  Plus, Trash2, Sun, Moon, Eye, EyeOff, Palette,
  GripVertical, Upload, Download, Calendar as CalendarIcon,
  ChevronLeft, ChevronRight, CheckCircle2, Circle, Clock,
  AlertTriangle, Flame, Target, ListTodo, BookOpen, Zap,
} from 'lucide-react'

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December']
const HOURS = Array.from({ length: 15 }, (_, i) => i + 7)
const HOUR_PX = 60
const COLORS = ['#7c6af7','#4ade80','#f472b6','#06b6d4','#f59e0b','#ef4444','#3b82f6','#a78bfa']

function fmtHour(h) { const ap = h >= 12 ? 'PM' : 'AM'; const hh = h > 12 ? h - 12 : h || 12; return `${hh} ${ap}` }
function toMin(s) { if (!s) return 0; const [h,m] = s.split(':').map(Number); return h*60+(m||0) }
function fmtDuration(m) { if (m < 60) return `${m}m`; const h=Math.floor(m/60); return m%60 ? `${h}h ${m%60}m` : `${h}h` }
function fmtTime(h,m=0) { return `${h>12?h-12:h||12}:${String(m).padStart(2,'0')}` }
function dateStr(d) { const y=d.getFullYear(); const m=String(d.getMonth()+1).padStart(2,'0'); const day=String(d.getDate()).padStart(2,'0'); return `${y}-${m}-${day}` }
function addDays(d, n) { const r = new Date(d); r.setDate(r.getDate()+n); return r }
function getMonday(d) { const r = new Date(d); const day = r.getDay(); r.setDate(r.getDate() - (day === 0 ? 6 : day - 1)); return r }
function sameDay(a, b) { return a.getFullYear()===b.getFullYear() && a.getMonth()===b.getMonth() && a.getDate()===b.getDate() }

function daysBetween(a, b) { const ms = new Date(a).setHours(0,0,0,0) - new Date(b).setHours(0,0,0,0); return Math.round(ms / 86400000) }
function daysUntil(due) { return daysBetween(new Date(due), new Date()) }

const DEFAULT_COURSES = [
  { id:'c1', name:'English', color:'#7c6af7', visible:true, code:'07ENGD', defaultDuration:55 },
  { id:'c2', name:'Mathematics', color:'#3b82f6', visible:true, code:'07MAT4', defaultDuration:55 },
  { id:'c3', name:'Science', color:'#4ade80', visible:true, code:'07SCID', defaultDuration:55 },
  { id:'c4', name:'HSIE', color:'#f59e0b', visible:true, code:'07HSIED', defaultDuration:55 },
  { id:'c5', name:'Religion', color:'#f472b6', visible:true, code:'07RELD', defaultDuration:55 },
  { id:'c6', name:'History & Culture', color:'#ef4444', visible:true, code:'07HRC3', defaultDuration:55 },
  { id:'c7', name:'Technology', color:'#06b6d4', visible:true, code:'07TEC2', defaultDuration:55 },
  { id:'c8', name:'Visual Arts', color:'#a78bfa', visible:true, code:'07VAR2', defaultDuration:55 },
  { id:'c9', name:'Music', color:'#f97316', visible:true, code:'07MUSD', defaultDuration:55 },
  { id:'c10', name:'PE & Health', color:'#10b981', visible:true, code:'07PDE2', defaultDuration:55 },
  { id:'c11', name:'Concert Band', color:'#8b5cf6', visible:true, code:'07CONC02', defaultDuration:55 },
  { id:'c12', name:'Enrichment', color:'#ec4899', visible:true, code:'07ENRICH3', defaultDuration:55 },
  { id:'c13', name:'Sport House', color:'#14b8a6', visible:true, code:'SPTHOUSE71', defaultDuration:55 },
]
const STORAGE_KEY = 'aria_planner'

function loadStorage() {
  try { const s = localStorage.getItem(STORAGE_KEY); return s ? JSON.parse(s) : null } catch { return null }
}
function saveStorage(data) { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(data)) } catch {} }

export default function AIPlannerPage() {
  const today = new Date()
  const todayStr = dateStr(today)
  const saved = useMemo(() => loadStorage(), [])

  const [courses, setCourses] = useState(saved?.courses || DEFAULT_COURSES)
  const [events, setEvents] = useState(saved?.events || [])
  const [tasks, setTasks] = useState(saved?.tasks || [])
  const [currentDate, setCurrentDate] = useState(saved?.currentDate ? new Date(saved.currentDate) : today)
  const [minBlock, setMinBlock] = useState(saved?.minBlock ?? 15)
  const [quickAddItem, setQuickAddItem] = useState(null)
  const [showAddCourse, setShowAddCourse] = useState(false)
  const [showAddTask, setShowAddTask] = useState(false)
  const [showImportCalendar, setShowImportCalendar] = useState(false)
  const [calFile, setCalFile] = useState(null)
  const [calLoading, setCalLoading] = useState(false)
  const [calTzOffset, setCalTzOffset] = useState(10)
  const [editEvent, setEditEvent] = useState(null)
  const [leftTab, setLeftTab] = useState('courses')
  const [rightTab, setRightTab] = useState('cushion')

  const codeToCourse = useMemo(() => {
    const m = {}
    courses.forEach(c => { if(c.code) m[c.code] = c })
    return m
  }, [courses])

  const weekStart = useMemo(() => getMonday(currentDate), [currentDate])
  const weekDays = useMemo(() => Array.from({length:7}, (_,i) => addDays(weekStart, i)), [weekStart])

  const toggleVisibility = (id) => setCourses(p => p.map(i => i.id===id ? {...i,visible:!i.visible} : i))
  const cycleColor = (id) => setCourses(p => p.map(i => i.id===id ? {...i,color:COLORS[(COLORS.indexOf(i.color)+1)%COLORS.length]} : i))

  const placeEvent = (date, hour, item) => {
    if (!item) return
    const start = `${String(hour).padStart(2,'0')}:00`
    const endMin = hour*60 + (item.defaultDuration||60)
    const end = `${String(Math.floor(endMin/60)).padStart(2,'0')}:${String(endMin%60).padStart(2,'0')}`
    setEvents(prev => [...prev, {
      id: `e${Date.now()}-${Math.random().toString(36).slice(2,6)}`,
      date, start, end, label:item.code||item.name, color:item.color,
      courseId:item.id, type:item.id?.startsWith('c')?'course':'activity', completed:false,
    }])
    setQuickAddItem(null)
    showToast(`${item.name} placed`, 'success')
  }

  const placeTask = (date, hour, taskId) => {
    const task = tasks.find(t => t.id === taskId)
    if (!task) return
    const est = task.estimate - task.completed
    const dur = Math.min(est, 60)
    const start = `${String(hour).padStart(2,'0')}:00`
    const endMin = hour*60 + dur
    const end = `${String(Math.floor(endMin/60)).padStart(2,'0')}:${String(endMin%60).padStart(2,'0')}`
    const course = courses.find(c => c.id === task.courseId)
    setEvents(prev => [...prev, {
      id: `e${Date.now()}-${Math.random().toString(36).slice(2,6)}`,
      date, start, end, label:task.name, color:course?.color||'#7c6af7',
      courseId:task.courseId, type:'task', taskId:task.id, completed:false,
    }])
    showToast(`Planned: ${task.name}`, 'success')
  }

  const removeEvent = (id) => setEvents(prev => prev.filter(e => e.id!==id))
  const toggleCompleteEvent = (id) => setEvents(prev => prev.map(e => e.id===id ? {...e,completed:!e.completed} : e))

  const addTask = (task) => {
    setTasks(prev => [...prev, {
      id: `t${Date.now()}-${Math.random().toString(36).slice(2,6)}`,
      name: task.name, courseId: task.courseId, dueDate: task.dueDate,
      estimate: task.estimate, completed: 0, status: 'todo', createdAt: todayStr,
    }])
    showToast(`Task added: ${task.name}`, 'success')
  }

  const updateTask = (id, updates) => setTasks(prev => prev.map(t => t.id===id ? {...t,...updates} : t))
  const removeTask = (id) => {
    setTasks(prev => prev.filter(t => t.id !== id))
    setEvents(prev => prev.filter(e => e.taskId !== id))
  }

  const getEventsForDate = (ds) => events.filter(e => e.date === ds).map(e => {
    const course = codeToCourse[e.label] || codeToCourse[e.code]
    return course ? {...e, color: course.color, courseId: course.id} : e
  })

  const handleCalendarImport = async () => {
    if (!calFile) return
    setCalLoading(true)
    try {
      const data = await importICS(calFile, calTzOffset)
      if (data.error) throw new Error(data.error)
      if (data.events?.length) {
        setEvents(prev => [...prev, ...data.events])
        showToast(`Imported ${data.count} events!`, 'success')
      } else { showToast('No events found','error') }
    } catch(e) { showToast(`Failed: ${e.message}`,'error') }
    setCalLoading(false); setShowImportCalendar(false); setCalFile(null)
  }

  useEffect(() => {
    const h = (e) => { if (e.key==='Escape') { setQuickAddItem(null); setEditEvent(null); setShowAddTask(false); setShowAddCourse(false) } }
    window.addEventListener('keydown',h); return () => window.removeEventListener('keydown',h)
  }, [])

  useEffect(() => {
    saveStorage({ events, courses, tasks, currentDate: currentDate.toISOString(), minBlock })
  }, [events, courses, tasks, currentDate, minBlock])

  useEffect(() => {
    const t = setTimeout(() => {
      if (events.length > 0 || tasks.length > 0) savePlannerEvents(events, tasks).catch(() => {})
    }, 1000)
    return () => clearTimeout(t)
  }, [events])

  useEffect(() => {
    loadPlannerEvents().then(data => {
      if (data.events?.length && events.length === 0) setEvents(data.events)
      if (data.tasks?.length && tasks.length === 0) setTasks(data.tasks)
    }).catch(() => {})
  }, [])

  const getFreeGaps = (dayEvents) => {
    const slots = dayEvents.map(e => ({start:toMin(e.start),end:toMin(e.end)})).sort((a,b)=>a.start-b.start)
    const gaps = []; let cur = 7*60
    slots.forEach(s => { if (s.start > cur) gaps.push({start:cur,end:s.start}); cur=Math.max(cur,s.end) })
    if (cur < 22*60) gaps.push({start:cur,end:22*60})
    return gaps.filter(g => (g.end-g.start)>=minBlock)
  }

  const navWeek = (dir) => setCurrentDate(d => addDays(d, dir*7))
  const navMonth = (dir) => setCurrentDate(d => { const r=new Date(d); r.setMonth(r.getMonth()+dir); return r })
  const goToday = () => setCurrentDate(today)

  // ── CUSHION CALCULATIONS ──────────────────────────────────────
  const totalMinPerWeek = 7*15*60
  const busyMin = events.reduce((s,e) => s+(toMin(e.end)-toMin(e.start)),0)
  const availableMin = Math.max(0, totalMinPerWeek - busyMin)
  const availableHours = availableMin / 60

  const totalTaskEstimate = tasks.reduce((s,t) => s + t.estimate, 0)
  const totalTaskCompleted = tasks.reduce((s,t) => s + t.completed, 0)
  const totalTaskRemaining = totalTaskEstimate - totalTaskCompleted

  const unfinishedTasks = tasks.filter(t => t.completed < t.estimate)
  const overdueTasks = unfinishedTasks.filter(t => daysUntil(t.dueDate) < 0)
  const dueSoonTasks = unfinishedTasks.filter(t => { const d = daysUntil(t.dueDate); return d >= 0 && d <= 3 })

  const cushionMinutes = availableMin - (totalTaskRemaining * 60)
  const cushionHours = cushionMinutes / 60
  const cushionPct = totalTaskEstimate > 0 ? Math.min(100, Math.max(0, (availableMin / (totalTaskEstimate * 60)) * 100)) : 100

  // Study streak
  const studyDays = useMemo(() => {
    const days = new Set()
    events.forEach(e => { if (e.completed) days.add(e.date) })
    return days
  }, [events])

  const streak = useMemo(() => {
    let count = 0
    let d = new Date()
    while (true) {
      const ds = dateStr(d)
      if (studyDays.has(ds) || events.some(e => e.date === ds)) { count++; d = addDays(d, -1) }
      else break
    }
    return count
  }, [studyDays, events])

  return (
    <div className="flex h-full bg-[#0f0f0f] text-[#e8e8e8] overflow-hidden">

      {/* ════════════════════ LEFT SIDEBAR ════════════════════ */}
      <div className="w-60 flex-shrink-0 border-r border-[#2a2a2a] bg-[#141414] overflow-y-auto flex flex-col">

        {/* Top Bar */}
        <div className="p-3 border-b border-[#2a2a2a]">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-[#7c6af7] to-[#4f46e5] flex items-center justify-center">
              <Zap size={12} className="text-white" />
            </div>
            <h1 className="text-sm font-bold text-[#e8e8e8]">Schedule Builder</h1>
          </div>
          <div className="flex items-center gap-1.5">
            <button onClick={()=>setShowImportCalendar(true)}
              className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg text-[10px] font-medium border border-[#2a2a2a] text-[#888] hover:bg-[#1a1a1a] hover:text-[#e8e8e8] transition-colors">
              <CalendarIcon size={10}/> Import .ics
            </button>
            <button onClick={async()=>{
              if(!events.length){showToast('No events to export','error');return}
              try{const r=await exportICS(events);const b=await r.blob();const u=URL.createObjectURL(b);const a=document.createElement('a');a.href=u;a.download='aria_schedule.ics';a.click();URL.revokeObjectURL(u);showToast('Exported!','success')}catch{showToast('Export failed','error')}
            }}
              className="flex items-center justify-center p-1.5 rounded-lg border border-[#2a2a2a] text-[#888] hover:bg-[#1a1a1a] hover:text-[#e8e8e8] transition-colors">
              <Download size={10}/>
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-[#2a2a2a]">
          {[{id:'courses',label:'Courses',icon:BookOpen},{id:'tasks',label:'Tasks',icon:ListTodo}].map(t=>(
            <button key={t.id} onClick={()=>setLeftTab(t.id)}
              className={`flex-1 flex items-center justify-center gap-1 py-2 text-[10px] font-medium transition-colors border-b-2 ${
                leftTab===t.id ? 'border-[#7c6af7] text-[#a89bf8]' : 'border-transparent text-[#555] hover:text-[#888]'
              }`}>
              <t.icon size={10}/> {t.label}
              {t.id==='tasks' && tasks.filter(tk=>tk.completed<tk.estimate).length > 0 && (
                <span className="ml-0.5 w-4 h-4 rounded-full bg-[#7c6af7] text-white text-[8px] flex items-center justify-center">
                  {tasks.filter(tk=>tk.completed<tk.estimate).length}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Courses Tab */}
        {leftTab === 'courses' && (
          <div className="p-3 space-y-1 flex-1 overflow-y-auto">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-semibold text-[#555] uppercase tracking-wider">Courses</span>
              <button onClick={()=>setShowAddCourse(true)} className="p-0.5 rounded hover:bg-[#1a1a1a] text-[#555] hover:text-[#888]"><Plus size={12}/></button>
            </div>
            {showAddCourse && (
              <AddForm placeholder="Course name"
                onSubmit={(n)=>{if(!n.trim())return;setCourses(p=>[...p,{id:`c${Date.now()}`,name:n.trim(),color:COLORS[p.length%COLORS.length],visible:true,defaultDuration:55}]);setShowAddCourse(false)}}
                onCancel={()=>setShowAddCourse(false)}/>
            )}
            {courses.map(c => (
              <div key={c.id} className="flex items-center gap-1 group">
                <button onClick={()=>setQuickAddItem(quickAddItem?.id===c.id ? null : c)}
                  className={`flex-1 flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-xs transition-colors ${
                    quickAddItem?.id===c.id ? 'bg-[#7c6af7]/15 text-[#a89bf8]' : 'text-[#888] hover:bg-[#1a1a1a] hover:text-[#e8e8e8]'
                  }`}>
                  <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{backgroundColor:c.color}}/>
                  <span className={`truncate flex-1 ${!c.visible?'text-[#555] line-through':''}`}>{c.name}</span>
                </button>
                <button onClick={()=>cycleColor(c.id)} className="p-0.5 rounded opacity-0 group-hover:opacity-100 hover:bg-[#1a1a1a] text-[#555] transition-all"><Palette size={9}/></button>
                <button onClick={()=>toggleVisibility(c.id)} className="p-0.5 rounded opacity-0 group-hover:opacity-100 hover:bg-[#1a1a1a] text-[#555] transition-all">
                  {c.visible ? <Eye size={9}/> : <EyeOff size={9}/>}
                </button>
              </div>
            ))}
            {quickAddItem && (
              <div className="mt-2 p-2 bg-[#7c6af7]/10 border border-[#7c6af7]/20 rounded-lg">
                <p className="text-[10px] text-[#a89bf8] font-medium">Click a time slot to place {quickAddItem.name}</p>
              </div>
            )}
          </div>
        )}

        {/* Tasks Tab */}
        {leftTab === 'tasks' && (
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="p-3 pb-1">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-semibold text-[#555] uppercase tracking-wider">Assignments</span>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-1">
              {tasks.length === 0 && !showAddTask && (
                <div className="text-center py-6">
                  <ListTodo size={28} className="text-[#333] mx-auto mb-2"/>
                  <p className="text-[11px] text-[#888] mb-3">No tasks yet</p>
                  <button onClick={()=>setShowAddTask(true)}
                    className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-[11px] font-medium transition-colors">
                    <Plus size={12}/> Add Your First Task
                  </button>
                </div>
              )}
              {tasks.length > 0 && !showAddTask && (
                <button onClick={()=>setShowAddTask(true)}
                  className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl border border-dashed border-[#7c6af7]/40 text-[#a89bf8] text-[11px] font-medium hover:bg-[#7c6af7]/10 transition-colors mb-2">
                  <Plus size={12}/> Add Task
                </button>
              )}
              {showAddTask && <TaskForm courses={courses} onSubmit={addTask} onCancel={()=>setShowAddTask(false)}/>}
              {tasks.sort((a,b) => new Date(a.dueDate) - new Date(b.dueDate)).map(task => {
                const course = courses.find(c => c.id === task.courseId)
                const remaining = task.estimate - task.completed
                const pct = task.estimate > 0 ? Math.min(100, (task.completed / task.estimate) * 100) : 0
                const dd = daysUntil(task.dueDate)
                const isOverdue = dd < 0 && remaining > 0
                const isDueSoon = dd >= 0 && dd <= 3 && remaining > 0
                return (
                  <div key={task.id}
                    className={`p-2 rounded-lg border transition-colors ${
                      isOverdue ? 'border-[#ef4444]/30 bg-[#ef4444]/5' :
                      isDueSoon ? 'border-[#f59e0b]/30 bg-[#f59e0b]/5' :
                      'border-[#2a2a2a] bg-[#1a1a1a]/50 hover:bg-[#1a1a1a]'
                    }`}>
                    <div className="flex items-start gap-2">
                      <button onClick={()=>updateTask(task.id, {completed: remaining > 0 ? task.completed + Math.min(remaining, 15) : 0})}
                        className="mt-0.5 flex-shrink-0">
                        {pct >= 100 ? <CheckCircle2 size={14} className="text-[#4ade80]"/> :
                         <Circle size={14} className="text-[#555] hover:text-[#888]"/>}
                      </button>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className={`text-xs font-medium truncate ${pct>=100?'text-[#555] line-through':'text-[#e8e8e8]'}`}>{task.name}</span>
                          <button onClick={()=>removeTask(task.id)} className="opacity-0 group-hover:opacity-100 text-[#333] hover:text-[#ef4444]"><Trash2 size={10}/></button>
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          {course && <span className="text-[9px] px-1.5 py-0.5 rounded-full" style={{backgroundColor:course.color+'20',color:course.color}}>{course.name}</span>}
                          <span className={`text-[9px] flex items-center gap-0.5 ${isOverdue?'text-[#ef4444]':isDueSoon?'text-[#f59e0b]':'text-[#555]'}`}>
                            {isOverdue ? <AlertTriangle size={8}/> : <Clock size={8}/>}
                            {dd < 0 ? `${Math.abs(dd)}d overdue` : dd === 0 ? 'Due today' : `${dd}d left`}
                          </span>
                        </div>
                        <div className="mt-1.5">
                          <div className="flex items-center justify-between mb-0.5">
                            <span className="text-[9px] text-[#555]">{fmtDuration(task.completed)} / {fmtDuration(task.estimate)}</span>
                            <span className="text-[9px] text-[#555]">{Math.round(pct)}%</span>
                          </div>
                          <div className="h-1 rounded-full bg-[#0d0d0d] overflow-hidden">
                            <div className="h-full rounded-full transition-all" style={{
                              width:`${pct}%`,
                              backgroundColor: pct >= 100 ? '#4ade80' : isOverdue ? '#ef4444' : isDueSoon ? '#f59e0b' : '#7c6af7'
                            }}/>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Min Block */}
        <div className="p-3 border-t border-[#2a2a2a]">
          <div className="text-[10px] font-semibold text-[#555] uppercase tracking-wider mb-1.5">Min Block</div>
          <div className="flex items-center gap-2">
            <input type="range" min="5" max="60" step="5" value={minBlock} onChange={e=>setMinBlock(Number(e.target.value))} className="flex-1 accent-[#7c6af7] h-1"/>
            <span className="text-[10px] text-[#555] w-6 text-right">{minBlock}m</span>
          </div>
        </div>
      </div>

      {/* ════════════════════ CALENDAR ════════════════════ */}
      <div className="flex-1 flex flex-col overflow-hidden bg-[#0f0f0f]">

        {/* Nav Bar */}
        <div className="flex items-center justify-between px-4 py-2 bg-[#141414] border-b border-[#2a2a2a]">
          <div className="flex items-center gap-2">
            <button onClick={()=>navMonth(-1)} className="p-1.5 rounded-lg hover:bg-[#1a1a1a] text-[#888] hover:text-[#e8e8e8]"><ChevronLeft size={16}/></button>
            <span className="text-sm font-bold text-[#e8e8e8] w-40 text-center">{MONTHS[currentDate.getMonth()]} {currentDate.getFullYear()}</span>
            <button onClick={()=>navMonth(1)} className="p-1.5 rounded-lg hover:bg-[#1a1a1a] text-[#888] hover:text-[#e8e8e8]"><ChevronRight size={16}/></button>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={()=>navWeek(-1)} className="px-2 py-1 rounded-lg text-[11px] font-medium text-[#888] hover:text-[#e8e8e8] hover:bg-[#1a1a1a] border border-[#2a2a2a] transition-colors">Prev Week</button>
            <button onClick={goToday} className="px-2 py-1 rounded-lg text-[11px] font-medium text-[#a89bf8] bg-[#7c6af7]/15 hover:bg-[#7c6af7]/25 border border-[#7c6af7]/30 transition-colors">Today</button>
            <button onClick={()=>navWeek(1)} className="px-2 py-1 rounded-lg text-[11px] font-medium text-[#888] hover:text-[#e8e8e8] hover:bg-[#1a1a1a] border border-[#2a2a2a] transition-colors">Next Week</button>
          </div>
          <div className="text-[10px] text-[#555]">{events.length} events</div>
        </div>

        {/* Quick Task Planner */}
        {unfinishedTasks.length > 0 && (
          <div className="px-4 py-1.5 bg-[#141414]/80 border-b border-[#2a2a2a] flex items-center gap-2 overflow-x-auto">
            <span className="text-[9px] text-[#555] uppercase tracking-wider flex-shrink-0">Plan tasks:</span>
            {unfinishedTasks.slice(0,8).map(task => {
              const course = courses.find(c => c.id === task.courseId)
              const dd = daysUntil(task.dueDate)
              return (
                <button key={task.id}
                  onClick={()=>setQuickAddItem(quickAddItem?.id===task.id ? null : {...task, isTask:true, color:course?.color||'#7c6af7', defaultDuration:Math.min(task.estimate-task.completed, 60)})}
                  className={`flex-shrink-0 flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] border transition-colors ${
                    quickAddItem?.id===task.id
                      ? 'border-[#7c6af7]/50 bg-[#7c6af7]/15 text-[#a89bf8]'
                      : 'border-[#2a2a2a] text-[#888] hover:bg-[#1a1a1a] hover:text-[#e8e8e8]'
                  }`}>
                  <span className="w-1.5 h-1.5 rounded-full" style={{backgroundColor:course?.color||'#7c6af7'}}/>
                  <span className="truncate max-w-[80px]">{task.name}</span>
                  {dd <= 3 && dd >= 0 && <span className="text-[#f59e0b]">{dd}d</span>}
                  {dd < 0 && <span className="text-[#ef4444]">!</span>}
                </button>
              )
            })}
          </div>
        )}

        {/* Week Grid */}
        <div className="flex-1 overflow-auto">
          <div className="min-w-[650px]">
            {/* Day headers */}
            <div className="flex sticky top-0 z-10 bg-[#141414] border-b border-[#2a2a2a]">
              <div className="w-14 flex-shrink-0"/>
              {weekDays.map((d,i) => {
                const isToday = sameDay(d, today)
                const ds = dateStr(d)
                const dayEvts = getEventsForDate(ds)
                const dayTasks = tasks.filter(t => t.dueDate === ds && t.completed < t.estimate)
                return (
                  <div key={i} className={`flex-1 text-center py-1.5 border-r border-[#2a2a2a] ${isToday?'bg-[#7c6af7]/10':''}`}>
                    <div className={`text-[9px] font-medium uppercase tracking-wide ${isToday?'text-[#a89bf8]':'text-[#555]'}`}>{DAYS[d.getDay()]}</div>
                    <div className={`text-base font-bold ${isToday?'text-[#a89bf8]':'text-[#e8e8e8]'}`}>{d.getDate()}</div>
                    {dayEvts.length > 0 && <div className="text-[8px] text-[#555]">{dayEvts.length} events</div>}
                    {dayTasks.length > 0 && <div className="text-[8px] text-[#f59e0b]">{dayTasks.length} due</div>}
                  </div>
                )
              })}
            </div>

            {/* Hour rows */}
            {HOURS.map(h => (
              <div key={h} className="flex border-b border-[#1a1a1a]" style={{height:HOUR_PX}}>
                <div className="w-14 flex-shrink-0 border-r border-[#2a2a2a] flex items-start justify-end pr-1.5 pt-1">
                  <span className="text-[9px] text-[#555] font-medium">{fmtHour(h)}</span>
                </div>
                {weekDays.map((d,di) => {
                  const ds = dateStr(d)
                  const dayEvts = getEventsForDate(ds).filter(e => {
                    const s=toMin(e.start),en=toMin(e.end)
                    return s<(h+1)*60 && en>h*60
                  })
                  const gaps = getFreeGaps(getEventsForDate(ds))
                  const freeGap = gaps.find(g => h*60>=g.start && h*60<g.end)
                  const isGapStart = freeGap && h*60===freeGap.start
                  const gapMin = freeGap ? freeGap.end-freeGap.start : 0

                  const isTaskSlot = quickAddItem?.isTask

                  return (
                    <div key={di}
                      onClick={()=>{
                        if(isTaskSlot){placeTask(ds,h,quickAddItem.id);return}
                        if(quickAddItem){placeEvent(ds,h,quickAddItem);return}
                        setEditEvent({date:ds,hour:h})
                      }}
                      className={`flex-1 border-r border-[#1a1a1a] relative cursor-pointer hover:bg-[#1a1a1a]/50 transition-colors ${
                        isGapStart?'bg-[#7c6af7]/5':''
                      } ${isTaskSlot?'hover:bg-[#f59e0b]/5':''}`}
                      style={{minHeight:HOUR_PX}}>
                      {dayEvts.map(e => {
                        const s=toMin(e.start),en=toMin(e.end)
                        const top=Math.max(0,(s-h*60)/60*HOUR_PX)
                        const ht=Math.min((Math.min(en,(h+1)*60)-Math.max(s,h*60))/60*HOUR_PX,HOUR_PX-top)
                        if(ht<4)return null
                        const isTaskEvent = e.type === 'task'
                        return (
                          <div key={e.id}
                            className="absolute left-0.5 right-0.5 z-10 rounded-md overflow-hidden group shadow-sm"
                            style={{top,height:Math.max(ht,16),backgroundColor:e.color+(isTaskEvent?'30':'20'),borderLeft:`2px solid ${e.color}`}}>
                            <div className="px-1 py-0.5 text-[9px] leading-tight">
                              <span className="font-medium text-[#e8e8e8] truncate block">{e.label}</span>
                              {ht>20 && <span className="text-[8px] text-[#888]">{e.start?.slice(0,5)}-{e.end?.slice(0,5)}</span>}
                            </div>
                            {isTaskEvent && <div className="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full bg-[#f59e0b]"/>}
                            <div className="absolute top-0 right-0.5 hidden group-hover:flex gap-0.5 pt-0.5">
                              <button onClick={(ev)=>{ev.stopPropagation();toggleCompleteEvent(e.id)}}
                                className={`w-3.5 h-3.5 rounded-full flex items-center justify-center text-[8px] ${e.completed?'bg-[#4ade80] text-white':'bg-[#1a1a1a]/80 text-[#888] hover:text-[#4ade80]'}`}>
                                {e.completed && '✓'}
                              </button>
                              <button onClick={(ev)=>{ev.stopPropagation();removeEvent(e.id)}}
                                className="w-3.5 h-3.5 rounded-full bg-[#1a1a1a]/80 text-[#888] hover:text-[#ef4444] flex items-center justify-center text-[8px]">×</button>
                            </div>
                          </div>
                        )
                      })}
                      {isGapStart && gapMin>=minBlock && (
                        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                          <span className="text-[9px] font-medium text-[#a89bf8]/60 bg-[#7c6af7]/10 px-1.5 py-0.5 rounded">{fmtDuration(gapMin)} free</span>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ════════════════════ RIGHT PANEL ════════════════════ */}
      <div className="w-52 flex-shrink-0 border-l border-[#2a2a2a] bg-[#141414] overflow-y-auto flex flex-col">

        {/* Tabs */}
        <div className="flex border-b border-[#2a2a2a]">
          {[{id:'cushion',label:'Cushion',icon:Target},{id:'stats',label:'Stats',icon:Flame}].map(t=>(
            <button key={t.id} onClick={()=>setRightTab(t.id)}
              className={`flex-1 flex items-center justify-center gap-1 py-2 text-[10px] font-medium transition-colors border-b-2 ${
                rightTab===t.id ? 'border-[#7c6af7] text-[#a89bf8]' : 'border-transparent text-[#555] hover:text-[#888]'
              }`}>
              <t.icon size={10}/> {t.label}
            </button>
          ))}
        </div>

        {/* Cushion Tab */}
        {rightTab === 'cushion' && (
          <div className="p-4 space-y-4 flex-1">

            {/* Cushion Score */}
            <div className="text-center">
              <div className="text-[10px] text-[#555] uppercase tracking-wider mb-1">Cushion™</div>
              <div className={`text-3xl font-bold ${cushionMinutes >= 0 ? 'text-[#4ade80]' : 'text-[#ef4444]'}`}>
                {cushionMinutes >= 0 ? '+' : ''}{fmtDuration(Math.abs(cushionMinutes))}
              </div>
              <p className="text-[10px] text-[#555] mt-1">
                {cushionMinutes >= 60*60 ? "You're in great shape!" :
                 cushionMinutes >= 0 ? "You have just enough time." :
                 "You're overcommitted!"}
              </p>
            </div>

            {/* Cushion Bar */}
            <div>
              <div className="h-3 rounded-full bg-[#0d0d0d] overflow-hidden flex">
                <div className="bg-[#4ade80] transition-all" style={{width:`${Math.min(100,cushionPct)}%`}}/>
                <div className="bg-[#ef4444] transition-all" style={{width:`${Math.max(0,100-cushionPct)}%`}}/>
              </div>
              <div className="flex justify-between text-[8px] mt-1">
                <span className="text-[#4ade80]">Available: {fmtDuration(availableMin)}</span>
                <span className="text-[#ef4444]">Tasks: {fmtDuration(totalTaskRemaining*60)}</span>
              </div>
            </div>

            {/* Warnings */}
            {overdueTasks.length > 0 && (
              <div className="p-2.5 bg-[#ef4444]/10 border border-[#ef4444]/20 rounded-lg">
                <div className="flex items-center gap-1 mb-1">
                  <AlertTriangle size={11} className="text-[#ef4444]"/>
                  <span className="text-[10px] font-medium text-[#ef4444]">{overdueTasks.length} Overdue</span>
                </div>
                {overdueTasks.slice(0,3).map(t => (
                  <div key={t.id} className="text-[9px] text-[#888] truncate">{t.name}</div>
                ))}
              </div>
            )}
            {dueSoonTasks.length > 0 && (
              <div className="p-2.5 bg-[#f59e0b]/10 border border-[#f59e0b]/20 rounded-lg">
                <div className="flex items-center gap-1 mb-1">
                  <Clock size={11} className="text-[#f59e0b]"/>
                  <span className="text-[10px] font-medium text-[#f59e0b]">{dueSoonTasks.length} Due Soon</span>
                </div>
                {dueSoonTasks.slice(0,3).map(t => (
                  <div key={t.id} className="text-[9px] text-[#888] truncate">{t.name} — {daysUntil(t.dueDate)===0?'today':`${daysUntil(t.dueDate)}d`}</div>
                ))}
              </div>
            )}

            {/* Breakdown */}
            <div className="space-y-2">
              <div className="text-[10px] text-[#555] uppercase tracking-wider">Breakdown</div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#888]">Available study time</span>
                <span className="font-medium text-[#e8e8e8]">{fmtDuration(availableMin)}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#888]">Class + events</span>
                <span className="font-medium text-[#e8e8e8]">{fmtDuration(busyMin)}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#888]">Tasks remaining</span>
                <span className="font-medium text-[#e8e8e8]">{fmtDuration(totalTaskRemaining*60)}</span>
              </div>
              <div className="border-t border-[#2a2a2a] pt-2 flex items-center justify-between text-xs">
                <span className="text-[#888]">Cushion</span>
                <span className={`font-bold ${cushionMinutes>=0?'text-[#4ade80]':'text-[#ef4444]'}`}>
                  {cushionMinutes>=0?'+':''}{fmtDuration(Math.abs(cushionMinutes))}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Stats Tab */}
        {rightTab === 'stats' && (
          <div className="p-4 space-y-4 flex-1">

            {/* Study Streak */}
            <div className="text-center p-3 bg-[#1a1a1a] rounded-xl border border-[#2a2a2a]">
              <Flame size={20} className={`mx-auto mb-1 ${streak>0?'text-[#f59e0b]':'text-[#333]'}`}/>
              <div className="text-2xl font-bold text-[#e8e8e8]">{streak}</div>
              <div className="text-[10px] text-[#555]">Day Streak</div>
            </div>

            {/* Task Summary */}
            <div className="space-y-2">
              <div className="text-[10px] text-[#555] uppercase tracking-wider">Tasks</div>
              <div className="grid grid-cols-2 gap-2">
                <div className="p-2 bg-[#1a1a1a] rounded-lg border border-[#2a2a2a] text-center">
                  <div className="text-lg font-bold text-[#e8e8e8]">{tasks.length}</div>
                  <div className="text-[9px] text-[#555]">Total</div>
                </div>
                <div className="p-2 bg-[#1a1a1a] rounded-lg border border-[#2a2a2a] text-center">
                  <div className="text-lg font-bold text-[#4ade80]">{tasks.filter(t=>t.completed>=t.estimate).length}</div>
                  <div className="text-[9px] text-[#555]">Done</div>
                </div>
                <div className="p-2 bg-[#1a1a1a] rounded-lg border border-[#2a2a2a] text-center">
                  <div className="text-lg font-bold text-[#f59e0b]">{dueSoonTasks.length}</div>
                  <div className="text-[9px] text-[#555]">Due Soon</div>
                </div>
                <div className="p-2 bg-[#1a1a1a] rounded-lg border border-[#2a2a2a] text-center">
                  <div className="text-lg font-bold text-[#ef4444]">{overdueTasks.length}</div>
                  <div className="text-[9px] text-[#555]">Overdue</div>
                </div>
              </div>
            </div>

            {/* Time Summary */}
            <div className="space-y-2">
              <div className="text-[10px] text-[#555] uppercase tracking-wider">Time</div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#888]">Total estimate</span>
                <span className="font-medium text-[#e8e8e8]">{fmtDuration(totalTaskEstimate*60)}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#888]">Completed</span>
                <span className="font-medium text-[#4ade80]">{fmtDuration(totalTaskCompleted*60)}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#888]">Remaining</span>
                <span className="font-medium text-[#e8e8e8]">{fmtDuration(totalTaskRemaining*60)}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#888]">Available this week</span>
                <span className="font-medium text-[#e8e8e8]">{fmtDuration(availableMin)}</span>
              </div>
            </div>

            {/* Weekly Progress */}
            <div>
              <div className="text-[10px] text-[#555] uppercase tracking-wider mb-2">Weekly Overview</div>
              <div className="flex gap-1">
                {weekDays.map((d,i) => {
                  const ds = dateStr(d)
                  const dayEvts = getEventsForDate(ds)
                  const isToday = sameDay(d, today)
                  return (
                    <div key={i} className={`flex-1 text-center py-1 rounded ${isToday?'bg-[#7c6af7]/15 border border-[#7c6af7]/30':'bg-[#1a1a1a] border border-[#2a2a2a]'}`}>
                      <div className={`text-[8px] ${isToday?'text-[#a89bf8]':'text-[#555]'}`}>{DAYS[d.getDay()].slice(0,2)}</div>
                      <div className={`text-[9px] font-medium ${isToday?'text-[#a89bf8]':'text-[#888]'}`}>{dayEvts.length}</div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ════════════════════ MODALS ════════════════════ */}

      {/* Edit Event Modal */}
      {editEvent && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center backdrop-blur-sm" onClick={()=>setEditEvent(null)}>
          <div className="bg-[#141414] border border-[#2a2a2a] rounded-2xl shadow-2xl p-5 w-80" onClick={e=>e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-bold text-[#e8e8e8]">Add Event</span>
              <button onClick={()=>setEditEvent(null)} className="text-[#555] hover:text-[#e8e8e8]"><Trash2 size={14}/></button>
            </div>
            <div className="text-[11px] text-[#888] mb-3">{editEvent.date} at {fmtTime(editEvent.hour)}</div>

            {/* Course events */}
            <div className="text-[9px] text-[#555] uppercase tracking-wider mb-1">Courses & Activities</div>
            <div className="space-y-0.5 max-h-32 overflow-y-auto mb-3">
              {courses.filter(c=>c.visible).map(c=>(
                <button key={c.id} onClick={()=>{placeEvent(editEvent.date,editEvent.hour,c);setEditEvent(null)}}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-left text-[#e8e8e8] hover:bg-[#1a1a1a] transition-colors">
                  <span className="w-2 h-2 rounded-full flex-shrink-0" style={{backgroundColor:c.color}}/>
                  {c.name}
                  <span className="ml-auto text-[9px] text-[#555]">{c.defaultDuration}m</span>
                </button>
              ))}
            </div>

            {/* Task events */}
            {unfinishedTasks.length > 0 && (
              <>
                <div className="text-[9px] text-[#555] uppercase tracking-wider mb-1">Tasks (Do Dates)</div>
                <div className="space-y-0.5 max-h-32 overflow-y-auto">
                  {unfinishedTasks.map(t=>{
                    const c = courses.find(co=>co.id===t.courseId)
                    return (
                      <button key={t.id} onClick={()=>{placeTask(editEvent.date,editEvent.hour,t.id);setEditEvent(null)}}
                        className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-left text-[#e8e8e8] hover:bg-[#1a1a1a] transition-colors">
                        <span className="w-2 h-2 rounded-full flex-shrink-0" style={{backgroundColor:c?.color||'#7c6af7'}}/>
                        <span className="truncate">{t.name}</span>
                        <span className="ml-auto text-[9px] text-[#555]">{fmtDuration((t.estimate-t.completed)*60)} left</span>
                      </button>
                    )
                  })}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Import Calendar Modal */}
      {showImportCalendar && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center backdrop-blur-sm" onClick={()=>setShowImportCalendar(false)}>
          <div className="bg-[#141414] border border-[#2a2a2a] rounded-2xl shadow-2xl p-6 w-96" onClick={e=>e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-[#e8e8e8]">Import Calendar</h3>
              <button onClick={()=>setShowImportCalendar(false)} className="text-[#555] hover:text-[#e8e8e8]"><Trash2 size={14}/></button>
            </div>
            <div className="space-y-3">
              <div className="bg-[#7c6af7]/10 border border-[#7c6af7]/20 rounded-xl p-3">
                <p className="text-[11px] text-[#a89bf8] font-medium mb-1">How to export from Compass/Google Calendar:</p>
                <ol className="text-[10px] text-[#888] space-y-0.5 list-decimal list-inside">
                  <li>Open your calendar app/website</li>
                  <li>Find <span className="font-medium text-[#e8e8e8]">Export</span> or <span className="font-medium text-[#e8e8e8]">Settings → Import & Export</span></li>
                  <li>Download the <span className="font-medium text-[#e8e8e8]">.ics</span> file</li>
                  <li>Upload it below</li>
                </ol>
              </div>
              <div>
                <label className="text-[11px] text-[#888] font-medium mb-1 block">Timezone (hours ahead of UTC)</label>
                <select value={calTzOffset} onChange={e=>setCalTzOffset(Number(e.target.value))}
                  className="w-full text-xs px-3 py-2 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] text-[#e8e8e8] outline-none focus:border-[#7c6af7]">
                  <option value={10}>AEST (UTC+10) — Sydney</option>
                  <option value={11}>AEDT (UTC+11) — Sydney daylight</option>
                  <option value={9}>JST (UTC+9) — Tokyo</option>
                  <option value={8}>SGT (UTC+8) — Singapore, Perth</option>
                  <option value={0}>UTC+0 — London</option>
                  <option value={-5}>EST (UTC-5) — New York</option>
                  <option value={-8}>PST (UTC-8) — LA</option>
                </select>
              </div>
              <input type="file" accept=".ics" onChange={e=>setCalFile(e.target.files[0])}
                className="w-full text-xs text-[#888] file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-medium file:bg-[#7c6af7] file:text-white"/>
              <button onClick={handleCalendarImport} disabled={!calFile||calLoading}
                className="w-full py-2.5 rounded-xl bg-[#7c6af7] text-white text-xs font-medium hover:bg-[#6a59e0] disabled:opacity-40 transition-colors">
                {calLoading?'Importing...':'Import Calendar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Course Modal */}
      {showAddCourse && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center backdrop-blur-sm" onClick={()=>setShowAddCourse(false)}>
          <div className="bg-[#141414] border border-[#2a2a2a] rounded-2xl shadow-2xl p-5 w-80" onClick={e=>e.stopPropagation()}>
            <h3 className="text-sm font-bold text-[#e8e8e8] mb-3">Add Course</h3>
            <AddForm placeholder="Course name"
              onSubmit={(n)=>{if(!n.trim())return;setCourses(p=>[...p,{id:`c${Date.now()}`,name:n.trim(),color:COLORS[p.length%COLORS.length],visible:true,defaultDuration:55}]);setShowAddCourse(false)}}
              onCancel={()=>setShowAddCourse(false)}/>
          </div>
        </div>
      )}
    </div>
  )
}

function TaskForm({ courses, onSubmit, onCancel }) {
  const [name, setName] = useState('')
  const [courseId, setCourseId] = useState(courses[0]?.id || '')
  const [dueDate, setDueDate] = useState(dateStr(addDays(new Date(), 7)))
  const [estimate, setEstimate] = useState(60)
  const ref = useRef()
  useEffect(()=>{ref.current?.focus()},[])

  return (
    <div className="p-2.5 bg-[#1a1a1a] rounded-lg border border-[#7c6af7]/20 space-y-2">
      <input ref={ref} value={name} onChange={e=>setName(e.target.value)} placeholder="Task name (e.g. Essay, Homework)"
        onKeyDown={e=>{if(e.key==='Enter'&&name.trim())onSubmit({name,courseId,dueDate,estimate});if(e.key==='Escape')onCancel()}}
        className="w-full px-2 py-1.5 text-[11px] rounded-lg bg-[#0d0d0d] border border-[#2a2a2a] text-[#e8e8e8] placeholder-[#555] outline-none focus:border-[#7c6af7]"/>
      <div className="flex gap-1.5">
        <select value={courseId} onChange={e=>setCourseId(e.target.value)}
          className="flex-1 px-2 py-1 text-[10px] rounded-lg bg-[#0d0d0d] border border-[#2a2a2a] text-[#e8e8e8] outline-none focus:border-[#7c6af7]">
          {courses.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <input type="date" value={dueDate} onChange={e=>setDueDate(e.target.value)}
          className="flex-1 px-2 py-1 text-[10px] rounded-lg bg-[#0d0d0d] border border-[#2a2a2a] text-[#e8e8e8] outline-none focus:border-[#7c6af7] [color-scheme:dark]"/>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-[10px] text-[#555]">Estimate:</span>
        {[15,30,45,60,90,120].map(m=>(
          <button key={m} onClick={()=>setEstimate(m)}
            className={`px-1.5 py-0.5 rounded text-[9px] font-medium transition-colors ${
              estimate===m ? 'bg-[#7c6af7] text-white' : 'bg-[#0d0d0d] border border-[#2a2a2a] text-[#888] hover:text-[#e8e8e8]'
            }`}>{m}m</button>
        ))}
      </div>
      <div className="flex gap-1.5">
        <button onClick={()=>name.trim() && onSubmit({name,courseId,dueDate,estimate})}
          className="flex-1 py-1.5 rounded-lg bg-[#7c6af7] text-white text-[10px] font-medium hover:bg-[#6a59e0] transition-colors">Add Task</button>
        <button onClick={onCancel} className="px-3 py-1.5 rounded-lg bg-[#2a2a2a] text-[#888] text-[10px] hover:text-[#e8e8e8] transition-colors">Cancel</button>
      </div>
    </div>
  )
}

function AddForm({ onSubmit, onCancel, placeholder='Course name' }) {
  const [val, setVal] = useState('')
  const ref = useRef()
  useEffect(()=>{ref.current?.focus()},[])
  return (
    <div className="flex gap-1">
      <input ref={ref} value={val} onChange={e=>setVal(e.target.value)}
        onKeyDown={e=>{if(e.key==='Enter')onSubmit(val);if(e.key==='Escape')onCancel()}}
        placeholder={placeholder}
        className="flex-1 px-2 py-1 text-[11px] rounded-lg bg-[#0d0d0d] border border-[#2a2a2a] text-[#e8e8e8] placeholder-[#555] outline-none focus:border-[#7c6af7]"/>
      <button onClick={()=>onSubmit(val)}
        className="px-2 py-1 rounded-lg bg-[#7c6af7] text-white text-[10px] font-medium hover:bg-[#6a59e0] transition-colors">Add</button>
    </div>
  )
}
