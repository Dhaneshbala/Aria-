import { useEffect, useState, useRef } from 'react'
import { createExamPlan, listExamPlans, deleteExamPlan, updateTodo, parseAssessmentNotification, getPlanReadiness, getPlanPracticeSet } from '../services/api'
import { startTask, useBgTask } from '../services/tasks'
import { useStore } from '../store'
import { showToast } from '../components/Toast'

function daysLeftLabel(plan) {
  const n = plan.days_left ?? 0
  if (n <= 0) return 'Exam day / done'
  return `${n} day${n === 1 ? '' : 's'} left`
}

export default function ExamPlanPage() {
  const [plans, setPlans] = useState([])
  const [name, setName] = useState('')
  const [date, setDate] = useState('')
  const [subjects, setSubjects] = useState('')
  const [mins, setMins] = useState(45)
  const [busy, setBusy] = useState(false)
  const [openId, setOpenId] = useState(null)
  const [parsing, setParsing] = useState(false)
  const [notifName, setNotifName] = useState('')
  const [notif, setNotif] = useState(null) // {topics, summary, assessment_text, weighting, task_type, ...}
  const [weighting, setWeighting] = useState('')
  const [taskType, setTaskType] = useState('')
  const [readiness, setReadiness] = useState({}) // planId -> readiness obj
  const [practising, setPractising] = useState(null) // planId being generated
  const [practice, setPractice] = useState({}) // planId -> practice set
  const fileRef = useRef()
  const bg = useBgTask('examplan')
  const mountedRef = useRef(true)
  useEffect(() => () => { mountedRef.current = false }, [])

  const refresh = () => listExamPlans().then(plans => {
    setPlans(plans)
    plans.forEach(p => {
      getPlanReadiness(p.id).then(r => setReadiness(prev => ({ ...prev, [p.id]: r }))).catch(() => {})
    })
  }).catch(() => {})
  // Remount always refreshes — picks up plans created in the background
  // while we were on another page. Mirror a running background task locally.
  useEffect(() => {
    refresh()
    if (useStore.getState().bgTasks?.examplan?.status === 'running') setBusy(true)
  }, [])
  useEffect(() => {
    if ((bg?.status === 'done' || bg?.status === 'error' || bg?.status === 'cancelled') && busy) {
      setBusy(false)
      refresh()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bg?.status])

  const create = async () => {
    if (!date) { showToast('Pick an exam date', 'error'); return }
    const planName = name || notif?.exam_name || 'Exam'
    const subs = subjects.split(',').map(s => s.trim()).filter(Boolean)
    const finalSubs = subs.length ? subs : (notif?.subjects || [])
    const minsVal = Number(mins) || 45
    const wVal = weighting !== '' ? Number(weighting) : (notif?.weighting ?? null)
    const tVal = taskType || notif?.task_type || null
    const extra = {
      ...(notif ? {
        assessment_text: notif.assessment_text || null,
        assessment_topics: notif.topics || [],
        assessment_summary: notif.summary || null,
      } : {}),
      ...(wVal ? { weighting: wVal } : {}),
      ...(tVal ? { task_type: tVal } : {}),
    }
    setBusy(true)
    try {
      // Background-safe: the plan is created server-side; leaving this
      // page won't stop it, and remount refreshes the list.
      const plan = await startTask('examplan', {
        label: `Exam plan: ${planName}`,
        page: '/create',
        topic: planName,
        run: (signal) => createExamPlan(planName, date, finalSubs, minsVal, extra, signal),
      })
      if (!mountedRef.current) return
      if (plan?.detail || plan?.error) throw new Error(plan.detail || plan.error)
      setName(''); setDate(''); setSubjects('')
      setNotif(null); setNotifName('')
      setWeighting(''); setTaskType('')
      if (fileRef.current) fileRef.current.value = ''
      setOpenId(plan.id)
      await refresh()
      showToast(`Plan ready: ${plan.days.length} study days`, 'success')
    } catch (e) {
      if (!mountedRef.current) return
      if (e?.name !== 'AbortError') showToast('Could not create plan: ' + e.message, 'error')
    } finally {
      if (mountedRef.current) setBusy(false)
    }
  }

  const onNotifFile = async (f) => {
    if (!f) return
    setParsing(true)
    setNotifName(f.name)
    try {
      const res = await parseAssessmentNotification(f)
      setNotif(res)
      // Prefill form from notification — user can still edit before building
      if (res.exam_name && !name) setName(res.exam_name)
      if (res.exam_date && !date) setDate(res.exam_date)
      if (res.subjects?.length && !subjects) setSubjects(res.subjects.join(', '))
      showToast(
        res.topics?.length
          ? `Read notification: ${res.topics.length} topics found`
          : 'Read notification — check details below',
        'success'
      )
    } catch (e) {
      showToast('Could not read notification: ' + e.message, 'error')
      setNotif(null)
    } finally {
      setParsing(false)
    }
  }

  const clearNotif = () => {
    setNotif(null)
    setNotifName('')
    if (fileRef.current) fileRef.current.value = ''
  }

  const buildPractice = async (plan) => {
    setPractising(plan.id)
    try {
      const set = await getPlanPracticeSet(plan.id, 5, 'hard')
      setPractice(prev => ({ ...prev, [plan.id]: set }))
      showToast(`Practice set ready: ${set.questions?.length || 0} questions (${set.timed_mins} min)`, 'success')
    } catch (e) {
      showToast('Could not build practice set: ' + e.message, 'error')
    } finally {
      setPractising(null)
    }
  }

  const remove = async (id) => {
    await deleteExamPlan(id).catch(() => {})
    await refresh()
  }

  const toggleDay = async (plan, day) => {
    await updateTodo(day.todo_id, { completed: !day.completed }).catch(() => {})
    await refresh()
  }

  return (
    <div className="w-full max-w-2xl mx-auto px-6 py-8">
      <h1 className="text-2xl font-bold text-[#e8e8e8] mb-2">Exam Countdown</h1>
      <p className="text-sm text-[#555] mb-8 text-center">Give an exam date. ARIA plans every day — weak topics first — as real todos.</p>

      {/* New plan form */}
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl p-4 mb-6">
        {/* Assessment notification upload */}
        <div className="mb-3 p-3 rounded-xl bg-[#141414] border border-dashed border-[#3a3a3a]">
          <p className="text-xs font-medium text-[#ccc] mb-1">Assessment notification <span className="text-[#666] font-normal">(optional — ARIA plans from what's actually in it)</span></p>
          <div className="flex items-center gap-2">
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx,.doc,.txt,.md,.png,.jpg,.jpeg,.webp"
              className="hidden"
              onChange={e => onNotifFile(e.target.files?.[0])}
            />
            <button
              onClick={() => fileRef.current?.click()}
              disabled={parsing}
              className="text-xs px-3 py-2 rounded-xl bg-[#2a2a2a] hover:bg-[#35363a] text-[#e8e8e8] disabled:opacity-50 transition-colors"
            >
              {parsing ? 'Reading…' : notifName ? '↻ Replace file' : '📎 Upload notification (PDF / photo)'}
            </button>
            {notifName && <span className="text-[11px] text-[#666] truncate flex-1">{notifName}</span>}
            {notif && (
              <button onClick={clearNotif} className="text-[11px] text-[#666] hover:text-red-400 shrink-0">Remove</button>
            )}
          </div>
          {notif && (
            <div className="mt-2 text-[11px] leading-relaxed">
              {notif.summary && <p className="text-[#aaa] mb-1.5">📋 {notif.summary}</p>}
              {(notif.weighting || notif.task_type) && (
                <div className="flex flex-wrap gap-1.5 mb-1.5">
                  {notif.weighting ? <span className="px-2 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-300">{notif.weighting}% weighting</span> : null}
                  {notif.task_type ? <span className="px-2 py-0.5 rounded-full bg-blue-500/15 border border-blue-500/30 text-blue-300">{notif.task_type}</span> : null}
                </div>
              )}
              {notif.topics?.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {notif.topics.map((t, i) => (
                    <span key={i} className="px-2 py-1 rounded-full bg-[#7c6af7]/15 border border-[#7c6af7]/30 text-[#c4b5fd]">{t}</span>
                  ))}
                </div>
              )}
              {(!notif.topics || notif.topics.length === 0) && (
                <p className="text-amber-400/90">No specific topics detected — plan will use subjects + weak topics.</p>
              )}
            </div>
          )}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <input value={name} onChange={e => setName(e.target.value)} placeholder="Exam name (e.g. Maths Task 2)"
            className="bg-[#141414] border border-[#2a2a2a] rounded-xl px-3 py-2.5 text-sm text-[#e8e8e8] outline-none focus:border-[#7c6af7]/60" />
          <input type="date" value={date} onChange={e => setDate(e.target.value)}
            className="bg-[#141414] border border-[#2a2a2a] rounded-xl px-3 py-2.5 text-sm text-[#e8e8e8] outline-none focus:border-[#7c6af7]/60" />
          <input value={subjects} onChange={e => setSubjects(e.target.value)} placeholder="Subjects, comma separated"
            className="bg-[#141414] border border-[#2a2a2a] rounded-xl px-3 py-2.5 text-sm text-[#e8e8e8] outline-none focus:border-[#7c6af7]/60" />
          <div className="flex items-center gap-2">
            <span className="text-xs text-[#666]">Mins/day</span>
            <input type="number" min={15} max={180} step={15} value={mins} onChange={e => setMins(e.target.value)}
              className="w-20 bg-[#141414] border border-[#2a2a2a] rounded-xl px-3 py-2.5 text-sm text-[#e8e8e8] outline-none focus:border-[#7c6af7]/60" />
            <span className="text-xs text-[#666] ml-2">Weight %</span>
            <input type="number" min={0} max={100} value={weighting} onChange={e => setWeighting(e.target.value)} placeholder="25"
              className="w-16 bg-[#141414] border border-[#2a2a2a] rounded-xl px-2 py-2.5 text-sm text-[#e8e8e8] outline-none focus:border-[#7c6af7]/60" />
          </div>
          <input value={taskType} onChange={e => setTaskType(e.target.value)} placeholder="Task type (e.g. In-class test) — optional"
            className="sm:col-span-2 bg-[#141414] border border-[#2a2a2a] rounded-xl px-3 py-2.5 text-sm text-[#e8e8e8] outline-none focus:border-[#7c6af7]/60" />
        </div>
        <button onClick={create} disabled={busy}
          className="mt-3 w-full text-sm py-2.5 rounded-xl bg-[#7c6af7] text-white hover:bg-[#6a59e0] disabled:opacity-50 transition-colors">
          {busy ? 'Planning…' : 'Build my countdown plan →'}
        </button>
      </div>

      {/* Plans */}
      <div className="space-y-3">
        {plans.length === 0 && (
          <p className="text-xs text-[#555] text-center py-6">No exam plans yet — add your first exam above.</p>
        )}
        {plans.map(plan => {
          const done = plan.days.filter(d => d.completed).length
          const open = openId === plan.id
          return (
            <div key={plan.id} className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl overflow-hidden">
              <button onClick={() => setOpenId(open ? null : plan.id)}
                className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-[#161616] transition-colors">
                <span className="text-2xl font-bold text-[#7c6af7] min-w-[3rem]">{plan.days_left}</span>
                <span className="flex-1 min-w-0">
                  <span className="block text-sm font-semibold text-[#e8e8e8] truncate">{plan.exam_name}</span>
                  <span className="block text-[11px] text-[#666]">{plan.exam_date} · {daysLeftLabel(plan)} · {done}/{plan.days.length} done</span>
                </span>
                <span className="text-xs text-[#555]">{open ? '▲' : '▼'}</span>
              </button>
              {open && (
                <div className="border-t border-[#2a2a2a] px-4 py-2">
                  {(plan.weighting || plan.task_type) && (
                    <div className="flex flex-wrap gap-1.5 pt-2">
                      {plan.weighting ? <span className="px-2 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/30 text-[10px] text-amber-300">{plan.weighting}% weighting</span> : null}
                      {plan.task_type ? <span className="px-2 py-0.5 rounded-full bg-blue-500/15 border border-blue-500/30 text-[10px] text-blue-300">{plan.task_type}</span> : null}
                    </div>
                  )}
                  {readiness[plan.id] && (
                    <div className="mt-2 p-2.5 rounded-xl bg-[#141414] border border-[#2a2a2a]">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-[#aaa]">Readiness {readiness[plan.id].readiness}% · {readiness[plan.id].done}/{readiness[plan.id].total} days</span>
                        <span className="text-[#666]">{readiness[plan.id].verdict}</span>
                      </div>
                      <div className="mt-1.5 h-1.5 rounded-full bg-[#2a2a2a] overflow-hidden">
                        <div className={`h-1.5 rounded-full ${readiness[plan.id].readiness >= 85 ? 'bg-green-500' : readiness[plan.id].readiness >= 60 ? 'bg-blue-500' : readiness[plan.id].readiness >= 30 ? 'bg-amber-500' : 'bg-red-500'}`}
                          style={{ width: `${readiness[plan.id].readiness}%` }} />
                      </div>
                      {readiness[plan.id].weak_total > 0 && (
                        <p className="mt-1 text-[10px] text-[#888]">Weak days: {readiness[plan.id].weak_done}/{readiness[plan.id].weak_total} cleared</p>
                      )}
                      <button onClick={() => buildPractice(plan)} disabled={practising === plan.id}
                        className="mt-2 text-[11px] px-3 py-1.5 rounded-lg bg-[#7c6af7]/20 text-[#c4b5fd] hover:bg-[#7c6af7]/30 disabled:opacity-50">
                        {practising === plan.id ? 'Building timed set…' : `⚡ Timed practice from notification topics (${practice[plan.id]?.timed_mins || 10} min)`}
                      </button>
                      {practice[plan.id]?.questions?.length > 0 && (
                        <div className="mt-2 space-y-1.5">
                          <p className="text-[10px] text-[#666]">Topic: {practice[plan.id].topic} · {practice[plan.id].level}</p>
                          {practice[plan.id].questions.map((q, qi) => (
                            <div key={qi} className="p-2 rounded-lg bg-[#0f0f0f] border border-[#2a2a2a] text-[11px] text-[#aaa]">
                              <span className="text-[#ccc]">Q{qi + 1}. {q.question}</span>
                              {q.options?.length > 0 && (
                                <span className="block mt-1 text-[#666]">{q.options.map((o, oi) => `${'ABCD'[oi]}) ${o}`).join('  ')}</span>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  {plan.has_notification && (
                    <div className="py-1.5">
                      <p className="text-[11px] text-[#8ab4f8]">📎 From assessment notification</p>
                      {plan.assessment_summary && (
                        <p className="text-[11px] text-[#aaa] leading-relaxed mt-0.5">{plan.assessment_summary}</p>
                      )}
                      {(plan.assessment_topics?.length > 0) && (
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {plan.assessment_topics.map((t, i) => (
                            <span key={i} className="px-2 py-0.5 rounded-full bg-[#7c6af7]/15 border border-[#7c6af7]/30 text-[10px] text-[#c4b5fd]">{t}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  {plan.weak_topics?.length > 0 && (
                    <p className="text-[11px] text-amber-400/90 py-1.5">Weak first: {plan.weak_topics.join(', ')}</p>
                  )}
                  {plan.days.map((d, i) => (
                    <button key={i} onClick={() => toggleDay(plan, d)}
                      className="w-full flex items-center gap-2.5 py-2 border-b border-[#1a1a1a] last:border-0 text-left">
                      <span className={`w-4 h-4 rounded-full border flex-shrink-0 ${d.completed ? 'bg-green-500 border-green-500' : 'border-[#444]'}`}>
                        {d.completed && <span className="block text-center text-[10px] leading-4 text-white">✓</span>}
                      </span>
                      <span className="flex-1 min-w-0">
                        <span className={`block text-xs truncate ${d.completed ? 'line-through text-[#555]' : 'text-[#ccc]'}`}>{d.focus}</span>
                        <span className="block text-[10px] text-[#555]">{d.date} · {d.minutes}m</span>
                      </span>
                    </button>
                  ))}
                  <button onClick={() => remove(plan.id)}
                    className="my-2 text-[11px] text-[#666] hover:text-red-400 transition-colors">Delete plan</button>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
