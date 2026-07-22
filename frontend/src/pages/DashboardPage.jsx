import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { LayoutDashboard, Calendar, Clock, BookOpen, ChevronRight, ArrowRight, Plus, Trash2, CheckCircle, X } from 'lucide-react'

const SLOT_STYLES = {
  school: { border: 'border-l-[#555]', bg: 'bg-[#1e1e2e]', icon: '\u{1F3EB}' },
  study: { border: 'border-l-[#7c6af7]', bg: 'bg-[#1a1a2e]', icon: '\u{1F4D6}' },
  break: { border: 'border-l-[#06b6d4]', bg: 'bg-[#1a1e2e]', icon: '\u2615' },
  free: { border: 'border-l-green-400', bg: 'bg-[#1a2020]', icon: '\u{1F3AE}' },
  activity: { border: 'border-l-pink-400', bg: 'bg-[#201a20]', icon: '\u26BD' },
}

function saveSchedule(sched) {
  try {
    const raw = localStorage.getItem('aria_confirmed_schedule')
    const data = raw ? JSON.parse(raw) : {}
    localStorage.setItem('aria_confirmed_schedule', JSON.stringify({ ...data, schedule: sched }))
  } catch {}
}

function EditableSlot({ slot, index, onChange, onDelete }) {
  const [editing, setEditing] = useState(false)
  const [task, setTask] = useState(slot.task)
  const [subject, setSubject] = useState(slot.subject || '')
  const [time, setTime] = useState(slot.time)
  const [duration, setDuration] = useState(slot.duration || '')
  const style = SLOT_STYLES[slot.type] || SLOT_STYLES.study

  const save = () => {
    onChange(index, { ...slot, task, subject, time, duration })
    setEditing(false)
  }

  if (editing) {
    return (
      <div className={`px-3 py-2.5 rounded-lg border-l-[3px] ${style.border} bg-[#1a1a2e] space-y-2`}>
        <div className="flex items-center gap-2">
          <input value={task} onChange={e => setTask(e.target.value)} autoFocus
            className="flex-1 px-2 py-1 text-xs rounded bg-[#141414] border border-[#2a2a2a] text-[#e8e8e8] focus:outline-none focus:border-[#7c6af7]" />
          <button onClick={save} className="p-1 rounded bg-green-600 text-white hover:bg-green-500"><CheckCircle size={12} /></button>
          <button onClick={() => setEditing(false)} className="p-1 rounded bg-[#2a2a2a] text-[#888] hover:text-[#e8e8e8]"><X size={12} /></button>
        </div>
        <div className="flex gap-2">
          <input value={subject} onChange={e => setSubject(e.target.value)} placeholder="Subject"
            className="w-28 px-2 py-1 text-[10px] rounded bg-[#141414] border border-[#2a2a2a] text-[#e8e8e8] focus:outline-none focus:border-[#7c6af7]" />
          <input value={time} onChange={e => setTime(e.target.value)} placeholder="Time"
            className="flex-1 px-2 py-1 text-[10px] rounded bg-[#141414] border border-[#2a2a2a] text-[#e8e8e8] font-mono focus:outline-none focus:border-[#7c6af7]" />
          <input value={duration} onChange={e => setDuration(e.target.value)} placeholder="Duration"
            className="w-20 px-2 py-1 text-[10px] rounded bg-[#141414] border border-[#2a2a2a] text-[#e8e8e8] focus:outline-none focus:border-[#7c6af7]" />
        </div>
      </div>
    )
  }

  return (
    <div className={`group flex items-center gap-3 px-3 py-2.5 rounded-lg border-l-[3px] ${style.border} ${style.bg} cursor-pointer hover:brightness-110 transition-all`}
      onClick={() => setEditing(true)}>
      <span className="text-sm">{style.icon}</span>
      <span className="text-[10px] text-[#666] font-mono w-24 flex-shrink-0">{slot.time}</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-[#e8e8e8] truncate">{slot.task}</p>
        {slot.subject && <p className="text-[10px] text-[#7c6af7] font-medium">{slot.subject}</p>}
      </div>
      {slot.duration && <span className="text-[10px] text-[#555]">{slot.duration}</span>}
      <button onClick={e => { e.stopPropagation(); onDelete(index) }}
        className="opacity-0 group-hover:opacity-100 p-1 rounded text-[#555] hover:text-red-400 transition-all">
        <Trash2 size={11} />
      </button>
    </div>
  )
}

function AddSlotForm({ onAdd, onCancel }) {
  const [task, setTask] = useState('')
  const [subject, setSubject] = useState('')
  const [time, setTime] = useState('16:00')
  const [duration, setDuration] = useState('45 min')
  const [type, setType] = useState('study')

  const handleAdd = () => {
    if (!task.trim()) return
    onAdd({ task, subject, time: `${time} \u2013 ${time}`, duration, type })
    onCancel()
  }

  return (
    <div className="px-3 py-2.5 rounded-lg border border-dashed border-[#7c6af7]/40 bg-[#1a1a2e]/50 space-y-2">
      <div className="flex items-center gap-2">
        <input value={task} onChange={e => setTask(e.target.value)} autoFocus placeholder="Task name"
          className="flex-1 px-2 py-1 text-xs rounded bg-[#141414] border border-[#2a2a2a] text-[#e8e8e8] focus:outline-none focus:border-[#7c6af7]" />
        <button onClick={handleAdd} className="p-1 rounded bg-green-600 text-white hover:bg-green-500"><CheckCircle size={12} /></button>
        <button onClick={onCancel} className="p-1 rounded bg-[#2a2a2a] text-[#888] hover:text-[#e8e8e8]"><X size={12} /></button>
      </div>
      <div className="flex gap-2">
        <input value={subject} onChange={e => setSubject(e.target.value)} placeholder="Subject"
          className="w-28 px-2 py-1 text-[10px] rounded bg-[#141414] border border-[#2a2a2a] text-[#e8e8e8] focus:outline-none focus:border-[#7c6af7]" />
        <input value={time} onChange={e => setTime(e.target.value)} placeholder="Start time"
          className="w-20 px-2 py-1 text-[10px] rounded bg-[#141414] border border-[#2a2a2a] text-[#e8e8e8] font-mono focus:outline-none focus:border-[#7c6af7]" />
        <input value={duration} onChange={e => setDuration(e.target.value)} placeholder="Duration"
          className="w-20 px-2 py-1 text-[10px] rounded bg-[#141414] border border-[#2a2a2a] text-[#e8e8e8] focus:outline-none focus:border-[#7c6af7]" />
        <select value={type} onChange={e => setType(e.target.value)}
          className="px-2 py-1 text-[10px] rounded bg-[#141414] border border-[#2a2a2a] text-[#e8e8e8] focus:outline-none focus:border-[#7c6af7]">
          <option value="study">Study</option>
          <option value="break">Break</option>
          <option value="free">Free</option>
          <option value="activity">Activity</option>
        </select>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [schedule, setSchedule] = useState(null)
  const [selectedDay, setSelectedDay] = useState(null)
  const [showAdd, setShowAdd] = useState(false)

  useEffect(() => {
    try {
      const saved = localStorage.getItem('aria_confirmed_schedule')
      if (saved) {
        const data = JSON.parse(saved)
        setSchedule(data.schedule)
      }
    } catch {}
  }, [])

  const persist = (newSched) => {
    setSchedule(newSched)
    saveSchedule(newSched)
  }

  const updateSlot = (dayIdx, slotIdx, newSlot) => {
    const next = schedule.map((d, di) => {
      if (di !== dayIdx) return d
      const slots = [...d.slots]
      slots[slotIdx] = newSlot
      return { ...d, slots }
    })
    persist(next)
  }

  const deleteSlot = (dayIdx, slotIdx) => {
    const next = schedule.map((d, di) => {
      if (di !== dayIdx) return d
      const slots = d.slots.filter((_, si) => si !== slotIdx)
      const studyCount = slots.filter(s => s.type === 'study').length
      const studyMin = slots.filter(s => s.type === 'study').reduce((sum, s) => {
        const m = parseInt((s.duration || '0'))
        return sum + (isNaN(m) ? 45 : m)
      }, 0)
      return { ...d, slots, summary: { ...d.summary, tasks_scheduled: studyCount, study_minutes: studyMin } }
    })
    persist(next)
  }

  const addSlot = (dayIdx, slot) => {
    const next = schedule.map((d, di) => {
      if (di !== dayIdx) return d
      const slots = [...d.slots]
      const insertIdx = Math.max(0, slots.length - 1)
      slots.splice(insertIdx, 0, slot)
      const studyCount = slots.filter(s => s.type === 'study').length
      const studyMin = slots.filter(s => s.type === 'study').reduce((sum, s) => {
        const m = parseInt((s.duration || '0'))
        return sum + (isNaN(m) ? 45 : m)
      }, 0)
      return { ...d, slots, summary: { ...d.summary, tasks_scheduled: studyCount, study_minutes: studyMin } }
    })
    persist(next)
    setShowAdd(false)
  }

  const today = new Date().toISOString().slice(0, 10)
  const activeDay = selectedDay !== null ? schedule?.[selectedDay] : null

  if (!schedule) {
    return (
      <div className="h-full flex flex-col items-center justify-center px-4">
        <div className="w-16 h-16 rounded-2xl bg-[#1a1a2e] border border-[#2a2a2a] flex items-center justify-center mb-4">
          <LayoutDashboard size={28} className="text-[#7c6af7]" />
        </div>
        <h1 className="text-xl font-semibold text-[#e8e8e8] mb-1">Dashboard</h1>
        <p className="text-sm text-[#555] mb-4">No confirmed schedule yet</p>
        <button onClick={() => navigate('/ai-planner')}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#7c6af7] text-white text-sm font-medium hover:bg-[#6a59e0] transition-colors">
          <Calendar size={14} /> Create Schedule <ArrowRight size={14} />
        </button>
      </div>
    )
  }

  const totalStudy = schedule.reduce((s, d) => s + d.summary.study_minutes, 0)
  const totalTasks = schedule.reduce((s, d) => s + d.summary.tasks_scheduled, 0)
  const todayEntry = schedule.find(d => d.date === today)
  const todayStudySlots = todayEntry ? todayEntry.slots.filter(s => s.type === 'study') : []

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-4 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-[#e8e8e8]">Dashboard</h1>
            <p className="text-xs text-[#555]">Your confirmed study schedule</p>
          </div>
          <button onClick={() => navigate('/ai-planner')}
            className="text-[10px] text-[#7c6af7] hover:text-[#a89bf8] transition-colors flex items-center gap-1">
            Open AI Planner <ChevronRight size={10} />
          </button>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 text-center">
            <Calendar size={18} className="text-[#7c6af7] mx-auto mb-2" />
            <div className="text-xl font-bold text-[#e8e8e8]">{schedule.length}</div>
            <div className="text-[10px] text-[#555]">days planned</div>
          </div>
          <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 text-center">
            <Clock size={18} className="text-[#7c6af7] mx-auto mb-2" />
            <div className="text-xl font-bold text-[#e8e8e8]">{totalStudy}m</div>
            <div className="text-[10px] text-[#555]">total study</div>
          </div>
          <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 text-center">
            <BookOpen size={18} className="text-[#7c6af7] mx-auto mb-2" />
            <div className="text-xl font-bold text-[#e8e8e8]">{totalTasks}</div>
            <div className="text-[10px] text-[#555]">tasks</div>
          </div>
        </div>

        {todayStudySlots.length > 0 && (
          <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4">
            <h2 className="text-sm font-semibold text-[#e8e8e8] mb-3 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#7c6af7] animate-pulse" /> Today&apos;s Study
            </h2>
            <div className="space-y-2">
              {todayStudySlots.map((slot, i) => {
                const style = SLOT_STYLES[slot.type] || SLOT_STYLES.study
                return (
                  <div key={i} className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border-l-[3px] ${style.border} ${style.bg}`}>
                    <span className="text-sm">{style.icon}</span>
                    <span className="text-xs text-[#666] font-mono w-24 flex-shrink-0">{slot.time}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-[#e8e8e8] truncate">{slot.task}</p>
                      {slot.subject && <p className="text-[10px] text-[#7c6af7] font-medium">{slot.subject}</p>}
                    </div>
                    {slot.duration && <span className="text-[10px] text-[#555]">{slot.duration}</span>}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-[#e8e8e8]">Weekly Overview</h2>
            <button onClick={() => navigate('/ai-planner')} className="text-[10px] text-[#7c6af7] hover:text-[#a89bf8] transition-colors flex items-center gap-1">
              View full schedule <ChevronRight size={10} />
            </button>
          </div>

          {activeDay ? (
            <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-sm font-bold text-[#e8e8e8]">{activeDay.day}</h3>
                  <p className="text-[10px] text-[#555]">{activeDay.date}</p>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => setShowAdd(true)}
                    className="flex items-center gap-1 text-[10px] text-[#7c6af7] hover:text-[#a89bf8] transition-colors">
                    <Plus size={10} /> Add slot
                  </button>
                  <button onClick={() => { setSelectedDay(null); setShowAdd(false) }} className="text-[10px] text-[#555] hover:text-[#888]">Back</button>
                </div>
              </div>
              <div className="space-y-1.5">
                {activeDay.slots.map((slot, i) => (
                  <EditableSlot key={i} slot={slot} index={i}
                    onChange={(si, ns) => updateSlot(selectedDay, si, ns)}
                    onDelete={(si) => deleteSlot(selectedDay, si)} />
                ))}
                {showAdd && (
                  <AddSlotForm
                    onAdd={(s) => addSlot(selectedDay, s)}
                    onCancel={() => setShowAdd(false)} />
                )}
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-7 gap-1.5">
              {schedule.slice(0, 7).map((day, i) => {
                const isToday = day.date === today
                const studyCount = day.slots.filter(s => s.type === 'study').length
                return (
                  <button key={i} onClick={() => setSelectedDay(i)}
                    className={`flex flex-col items-center p-2.5 rounded-xl text-xs transition-all ${
                      isToday ? 'bg-[#7c6af7]/10 border border-[#7c6af7]/30' : 'bg-[#141414] border border-[#2a2a2a] hover:border-[#444]'
                    }`}>
                    <span className={`font-medium text-[10px] ${isToday ? 'text-[#7c6af7]' : 'text-[#888]'}`}>{day.day.slice(0, 3)}</span>
                    <span className="text-[9px] text-[#555] mt-0.5">{day.date.slice(5)}</span>
                    <div className="mt-1.5 flex items-center gap-0.5">
                      {studyCount > 0 && <span className="w-1.5 h-1.5 rounded-full bg-[#7c6af7]" />}
                      {day.summary.overdue > 0 && <span className="w-1.5 h-1.5 rounded-full bg-red-400" />}
                      {studyCount === 0 && day.summary.overdue === 0 && <span className="w-1.5 h-1.5 rounded-full bg-[#333]" />}
                    </div>
                    <span className="text-[9px] text-[#666] mt-0.5">{studyCount}s</span>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
