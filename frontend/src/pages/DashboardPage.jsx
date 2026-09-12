import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '../store'
import { getSrStats, getWeakTopics, getDueCards, getTodos, getTodoCushion, createTodo, updateTodo, deleteTodo } from '../services/api'
import { showToast } from '../components/Toast'
import {
  Clock, AlertTriangle, CheckSquare, Timer, Play, Pause, RotateCcw,
  Plus, Pencil, Trash2, X, Check
} from 'lucide-react'

function greeting() {
  const h = new Date().getHours()
  if (h < 5) return "Up late — let's make it quick"
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const { ollamaStatus } = useStore()

  // Shortcuts hand off to Chat with the composer prefilled — the dashboard
  // itself has no chat thread (chat lives on /chat).
  const pickAction = (prefill) => {
    try { sessionStorage.setItem('aria_chat_prefill', prefill) } catch {}
    navigate('/chat')
  }

  const [stats, setStats] = useState({ due: 0, weakest: null, upcoming: null })
  useEffect(() => {
    // Fetch actionable stats
    Promise.allSettled([getSrStats(), getWeakTopics(), getDueCards(5)]).then(([sr, wk, due]) => {
      const dueCount = sr.status === 'fulfilled' ? (sr.value?.due_today ?? sr.value?.due ?? 0) : 0
      const weak = wk.status === 'fulfilled' ? (wk.value?.weak_topics?.[0] || wk.value?.[0] || null) : null
      const upcoming = due.status === 'fulfilled' ? (due.value?.cards?.length || due.value?.length || 0) : 0
      setStats({ due: dueCount, weakest: weak, upcoming })
    })
  }, [])

  return (
    <div className="flex flex-col h-full w-full bg-[#131314]">
      {ollamaStatus === 'error' && (
        <div className="mx-4 mt-2 px-4 py-2.5 bg-[#3c1f1a] border border-[#5c2b22] rounded-xl text-center">
          <p className="text-xs text-[#f28b82]">
            Ollama offline — run <code className="px-1.5 py-0.5 rounded bg-[#5c2b22] text-[#f28b82] font-mono">ollama serve</code> then refresh.
          </p>
        </div>
      )}

      {/* Welcome cards — no chat thread here (chat lives on /chat) */}
      <div className="flex-1 overflow-y-auto">
        <DashboardWelcome onAction={pickAction} />
      </div>
    </div>
  )
}

function DashboardWelcome({ onAction }) {
  const navigate = useNavigate()
  const { config } = useStore()
  const name = config.student_name && config.student_name !== 'Student' ? config.student_name : ''
  const [due, setDue] = useState(0)
  const [weak, setWeak] = useState(null)
  const [pomRunning, setPomRunning] = useState(false)
  const [pomSecs, setPomSecs] = useState(25*60)
  const [pomMode, setPomMode] = useState('work')
  useEffect(() => {
    getSrStats().then(s => setDue(s?.due_today ?? s?.due ?? 0)).catch(()=>{})
    getWeakTopics().then(w => setWeak(w?.weak_topics?.[0] || w?.[0] || null)).catch(()=>{})
  }, [])
  useEffect(() => {
    if (!pomRunning) return
    const id = setInterval(() => {
      setPomSecs(s => {
        if (s <= 1) {
          setPomRunning(false)
          const nextMode = pomMode === 'work' ? 'break' : 'work'
          setPomMode(nextMode)
          return nextMode === 'work' ? 25*60 : 5*60
        }
        return s - 1
      })
    }, 1000)
    return () => clearInterval(id)
  }, [pomRunning, pomMode])

  const greet = greeting()
  return (
    <div className="flex flex-col items-center px-6 lg:px-8 py-8 md:py-10">
      <div className="w-full flex flex-col items-center">
        {/* Gemini hero — same as ChatPage */}
        <h1 className="text-[36px] sm:text-[44px] md:text-[52px] font-normal leading-[1.05] tracking-tight text-center">
          <span className="gemini-gradient-text">{greet}{name ? `, ${name}` : ''}</span>
        </h1>
        <h2 className="text-[36px] sm:text-[44px] md:text-[52px] font-normal leading-[1.05] tracking-tight text-[#5f6368] text-center -mt-1">
          What to learn?
        </h2>
        <p className="text-sm text-[#9aa0a6] mt-3 mb-8 text-center">Pick a shortcut — or just ask anything below</p>

        {/* Actionable cards — Gemini surface */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full mb-6">
          <button onClick={() => due > 0 ? navigate('/spaced') : onAction('Show my due flashcards')}
            className="group flex flex-col items-start gap-3 p-4 bg-[#1e1f20] border border-[#2d2e30] rounded-2xl hover:bg-[#2d2e30] hover:border-[#3c4043] transition-all text-left">
            <div className="w-8 h-8 rounded-full bg-[#2d2e30] group-hover:bg-[#35363a] flex items-center justify-center"><Clock size={16} className="text-[#8ab4f8]"/></div>
            <div className="w-full">
              <p className="text-xs font-medium tracking-wide text-[#9aa0a6] uppercase">Due Today</p>
              <p className="text-[22px] font-normal text-[#e3e3e3] mt-1 leading-none">{due > 0 ? `${due} cards` : 'All caught up'}</p>
              <p className="text-xs text-[#8ab4f8] mt-2 flex items-center gap-1">{due > 0 ? 'Review now →' : 'No cards due'} </p>
            </div>
          </button>
          <button onClick={() => weak && onAction(`Practice ${typeof weak === 'string' ? weak : weak?.topic || weak?.name || 'my weak topic'}`)}
            className="group flex flex-col items-start gap-3 p-4 bg-[#1e1f20] border border-[#2d2e30] rounded-2xl hover:bg-[#2d2e30] hover:border-[#3c4043] transition-all text-left">
            <div className="w-8 h-8 rounded-full bg-amber-500/15 flex items-center justify-center"><AlertTriangle size={16} className="text-amber-400"/></div>
            <div className="w-full">
              <p className="text-xs font-medium tracking-wide text-[#9aa0a6] uppercase">Weakest Topic</p>
              <p className="text-[16px] font-medium text-[#e3e3e3] mt-1 truncate max-w-[220px]">{weak ? (typeof weak === 'string' ? weak : weak?.topic || weak?.name || 'Algebra') : 'No data yet'}</p>
              <p className="text-xs text-[#9aa0a6] group-hover:text-amber-400 mt-2">Practice →</p>
            </div>
          </button>
        </div>

        {/* Organisation — inbox + pomodoro — Gemini cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full mb-8">
          <AssignmentsCard />
          <div className="p-4 bg-[#1e1f20] border border-[#2d2e30] rounded-2xl flex flex-col items-center">
            <div className="flex items-center gap-2 mb-1">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center ${pomMode==='work' ? 'bg-[#8ab4f8]/15' : 'bg-green-500/15'}`}>
                <Timer size={14} className={pomMode==='work' ? 'text-[#8ab4f8]' : 'text-green-400'} />
              </div>
              <p className="text-sm font-medium text-[#e3e3e3]">{pomMode==='work' ? 'Focus' : 'Break'}</p>
            </div>
            <p className="text-[32px] font-light font-mono text-[#e3e3e3] my-2 tracking-widest">{String(Math.floor(pomSecs/60)).padStart(2,'0')}:{String(pomSecs%60).padStart(2,'0')}</p>
            <div className="flex items-center gap-2">
              <button onClick={() => setPomRunning(!pomRunning)} className={`w-9 h-9 rounded-full flex items-center justify-center transition-colors ${pomRunning ? 'bg-[#2d2e30] text-[#e3e3e3]' : 'bg-[#8ab4f8] text-[#062e6f] hover:bg-[#aecbfa]'}`}>
                {pomRunning ? <Pause size={16}/> : <Play size={16} className="ml-0.5"/>}
              </button>
              <button onClick={() => { setPomRunning(false); setPomSecs(pomMode==='work'?25*60:5*60)}} className="w-9 h-9 rounded-full bg-[#2d2e30] hover:bg-[#35363a] text-[#9aa0a6] hover:text-[#e3e3e3] flex items-center justify-center"><RotateCcw size={16}/></button>
              <button onClick={() => { const nm = pomMode==='work'?'break':'work'; setPomMode(nm); setPomSecs(nm==='work'?25*60:5*60); setPomRunning(false)}} className="ml-1 px-3 py-1.5 rounded-full bg-[#2d2e30] hover:bg-[#35363a] text-xs text-[#9aa0a6] hover:text-[#e3e3e3]">Switch</button>
            </div>
          </div>
        </div>

        <p className="text-[11px] text-[#5f6368] mt-6 text-center max-w-xl">Try “Essay feedback”, “Timeline for WW2”, “Worksheet on algebra”, “Check my handwriting” with a photo</p>
      </div>
    </div>
  )
}

const SUBJECTS = ['General', 'Maths', 'English', 'Science', 'History', 'Geography', 'PDHPE', 'Technology', 'Art', 'Music', 'Commerce']
const PRIORITIES = ['low', 'medium', 'high']

const emptyForm = { subject: 'General', task: '', due_date: '', estimated_mins: 30, priority: 'medium' }

function AssignmentsCard() {
  const [todos, setTodos] = useState([])
  const [cushion, setCushion] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)

  const refresh = async () => {
    try {
      const d = await getTodos()
      setTodos(d.todos || [])
      setCushion(d.cushion || null)
      if (!d.cushion) {
        getTodoCushion().then(setCushion).catch(() => {})
      }
    } catch {
      // offline — keep existing
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  const startAdd = () => {
    setEditingId(null)
    setForm(emptyForm)
    setShowForm(true)
  }

  const startEdit = (t) => {
    setEditingId(t.id)
    setForm({
      subject: t.subject || 'General',
      task: t.task || '',
      due_date: t.due_date || '',
      estimated_mins: t.estimated_mins || 30,
      priority: t.priority || 'medium',
    })
    setShowForm(true)
  }

  const cancelForm = () => {
    setShowForm(false)
    setEditingId(null)
    setForm(emptyForm)
  }

  const handleSave = async (e) => {
    e?.preventDefault?.()
    if (!form.task.trim()) {
      showToast('Describe the assignment first', 'error')
      return
    }
    setSaving(true)
    try {
      if (editingId) {
        const updated = await updateTodo(editingId, {
          subject: form.subject,
          task: form.task.trim(),
          due_date: form.due_date || null,
          estimated_mins: Number(form.estimated_mins) || 30,
          priority: form.priority,
        })
        setTodos(prev => prev.map(t => (t.id === editingId ? updated : t)))
        showToast('Assignment updated', 'success', 2500)
      } else {
        const created = await createTodo(
          form.subject,
          form.task.trim(),
          form.due_date || null,
          Number(form.estimated_mins) || 30,
          form.priority
        )
        setTodos(prev => [created, ...prev])
        showToast('Assignment added', 'success', 2500)
      }
      cancelForm()
      refresh()
    } catch (err) {
      showToast(`Couldn't save: ${err.message}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleToggle = async (t) => {
    try {
      const updated = await updateTodo(t.id, { completed: !t.completed })
      setTodos(prev => prev.map(x => (x.id === t.id ? updated : x)))
      refresh()
    } catch (err) {
      showToast(`Couldn't update: ${err.message}`, 'error')
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this assignment?')) return
    try {
      await deleteTodo(id)
      setTodos(prev => prev.filter(t => t.id !== id))
      showToast('Assignment deleted', 'success', 2500)
      refresh()
    } catch (err) {
      showToast(`Couldn't delete: ${err.message}`, 'error')
    }
  }

  return (
    <div className="p-4 bg-[#1e1f20] border border-[#2d2e30] rounded-2xl flex flex-col">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-7 h-7 rounded-full bg-[#2d2e30] flex items-center justify-center"><CheckSquare size={14} className="text-green-400" /></div>
        <p className="text-sm font-medium text-[#e3e3e3]">Assignments</p>
        <span className={`ml-auto text-[11px] px-2 py-1 rounded-full border font-medium ${cushion?.status === 'overloaded' ? 'bg-red-500/15 text-[#f28b82] border-red-500/30' : cushion?.status === 'busy' ? 'bg-amber-500/15 text-amber-300 border-amber-500/30' : 'bg-green-500/10 text-green-300 border-green-500/20'}`}>
          {cushion ? `${cushion.status} · ${cushion.total_mins}m` : '…'}
        </span>
        <button
          onClick={showForm ? cancelForm : startAdd}
          title={showForm ? 'Close' : 'Add assignment'}
          className={`w-7 h-7 rounded-full flex items-center justify-center transition-colors ${showForm ? 'bg-[#2d2e30] text-[#9aa0a6] hover:text-white' : 'bg-[#8ab4f8] text-[#062e6f] hover:bg-[#aecbfa]'}`}
        >
          {showForm ? <X size={14} /> : <Plus size={14} />}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSave} className="mb-3 p-3 rounded-xl bg-[#131314] border border-[#2d2e30] space-y-2">
          <p className="text-xs font-medium text-[#9aa0a6] uppercase tracking-wide">{editingId ? 'Edit assignment' : 'New assignment'}</p>
          <input
            value={form.task}
            onChange={e => setForm({ ...form, task: e.target.value })}
            placeholder="e.g. Algebra worksheet p.42 Q1-10"
            className="w-full px-3 py-2 rounded-lg bg-[#1e1f20] border border-[#2d2e30] text-sm text-[#e3e3e3] placeholder-[#5f6368] outline-none focus:border-[#8ab4f8]"
            autoFocus
          />
          <div className="grid grid-cols-2 gap-2">
            <select
              value={form.subject}
              onChange={e => setForm({ ...form, subject: e.target.value })}
              className="px-2 py-2 rounded-lg bg-[#1e1f20] border border-[#2d2e30] text-xs text-[#e3e3e3] outline-none"
            >
              {SUBJECTS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <select
              value={form.priority}
              onChange={e => setForm({ ...form, priority: e.target.value })}
              className="px-2 py-2 rounded-lg bg-[#1e1f20] border border-[#2d2e30] text-xs text-[#e3e3e3] outline-none"
            >
              {PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
            <input
              type="date"
              value={form.due_date || ''}
              onChange={e => setForm({ ...form, due_date: e.target.value })}
              className="px-2 py-2 rounded-lg bg-[#1e1f20] border border-[#2d2e30] text-xs text-[#e3e3e3] outline-none"
            />
            <div className="flex items-center gap-1 px-2 py-1 rounded-lg bg-[#1e1f20] border border-[#2d2e30]">
              <input
                type="number"
                min={5}
                max={240}
                step={5}
                value={form.estimated_mins}
                onChange={e => setForm({ ...form, estimated_mins: e.target.value })}
                className="w-full bg-transparent text-xs text-[#e3e3e3] outline-none"
              />
              <span className="text-[11px] text-[#5f6368] shrink-0">min</span>
            </div>
          </div>
          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              disabled={saving}
              className="flex-1 px-3 py-2 rounded-lg bg-[#8ab4f8] hover:bg-[#aecbfa] disabled:opacity-50 text-[#062e6f] text-xs font-semibold flex items-center justify-center gap-1"
            >
              <Check size={13} /> {saving ? 'Saving…' : editingId ? 'Save changes' : 'Add assignment'}
            </button>
            <button
              type="button"
              onClick={cancelForm}
              className="px-3 py-2 rounded-lg bg-[#2d2e30] hover:bg-[#35363a] text-xs text-[#9aa0a6]"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="text-xs text-[#5f6368] py-2">Loading…</p>
      ) : todos.length === 0 ? (
        <p className="text-xs text-[#9aa0a6] leading-relaxed">No assignments — hit + to add one. Chat still works too.</p>
      ) : (
        <div className="space-y-2 max-h-56 overflow-y-auto pr-0.5">
          {todos.map(t => (
            <div key={t.id} className={`flex items-center gap-2 text-xs rounded-xl px-2.5 py-2 border ${t.completed ? 'bg-[#131314]/60 border-[#2d2e30] opacity-60' : 'bg-[#131314] border-[#2d2e30]'}`}>
              <button
                onClick={() => handleToggle(t)}
                title={t.completed ? 'Mark incomplete' : 'Mark done'}
                className={`w-4 h-4 rounded-full border flex items-center justify-center shrink-0 transition-colors ${t.completed ? 'bg-green-500 border-green-500 text-[#062e6f]' : 'border-[#5f6368] hover:border-green-400 text-transparent'}`}
              >
                <Check size={11} />
              </button>
              <span className={`w-2 h-2 rounded-full shrink-0 ${t.priority === 'high' ? 'bg-[#f28b82]' : t.priority === 'low' ? 'bg-green-400' : 'bg-amber-400'}`} />
              <div className="flex-1 min-w-0">
                <p className={`truncate ${t.completed ? 'line-through text-[#5f6368]' : 'text-[#e3e3e3]'}`}>{t.subject}: {t.task}</p>
                <p className="text-[10px] text-[#5f6368] mt-0.5">{t.due_date ? `Due ${t.due_date}` : 'No due date'} · {t.estimated_mins}m · {t.priority}</p>
              </div>
              <button onClick={() => startEdit(t)} title="Edit" className="p-1.5 rounded-full hover:bg-[#2d2e30] text-[#9aa0a6] hover:text-white shrink-0">
                <Pencil size={12} />
              </button>
              <button onClick={() => handleDelete(t.id)} title="Delete" className="p-1.5 rounded-full hover:bg-red-500/20 text-[#9aa0a6] hover:text-[#f28b82] shrink-0">
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>
      )}
      <p className="mt-2 text-[11px] text-[#5f6368]">Tip: you can still say “add maths HW due Fri 45m” in chat.</p>
    </div>
  )
}
