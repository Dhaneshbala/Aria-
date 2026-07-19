import { useState } from 'react'
import { generateStudyPlan } from '../services/api'
import { Calendar, CheckCircle, Circle, Download } from 'lucide-react'

function generateICS(plan, topic) {
  const now = new Date()
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//ARIA Study Plan//EN',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
  ]

  plan.forEach((day, i) => {
    // Start date: tomorrow + i days
    const startDate = new Date(now)
    startDate.setDate(startDate.getDate() + 1 + i)
    startDate.setHours(9, 0, 0, 0) // Start at 9 AM

    const endDate = new Date(startDate)
    endDate.setMinutes(endDate.getMinutes() + (day.time_minutes || 30))

    const tasks = (day.tasks || []).map((t, ti) => `${ti + 1}. ${t}`).join('\\n')
    const dayTopic = day.title || `Study ${topic}`

    const formatDT = (d) => d.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z'

    lines.push('BEGIN:VEVENT')
    lines.push(`DTSTART:${formatDT(startDate)}`)
    lines.push(`DTEND:${formatDT(endDate)}`)
    lines.push(`SUMMARY:Day ${day.day}: ${dayTopic}`)
    lines.push(`DESCRIPTION:Topic: ${topic}\\n\\nTasks:\\n${tasks}`)
    lines.push(`LOCATION:Study Session`)
    lines.push(`STATUS:CONFIRMED`)
    lines.push(`END:VEVENT`)
  })

  lines.push('END:VCALENDAR')
  return lines.join('\r\n')
}

export default function StudyPlanPage() {
  const [topic, setTopic] = useState('')
  const [days, setDays] = useState(7)
  const [plan, setPlan] = useState([])
  const [loading, setLoading] = useState(false)
  const [checked, setChecked] = useState({})

  const generate = async () => {
    if (!topic.trim()) return
    setLoading(true)
    setPlan([])
    setChecked({})
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
    const ics = generateICS(plan, topic)
    const blob = new Blob([ics], { type: 'text/calendar;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ARIA-Study-Plan-${topic.replace(/\s+/g, '-')}.ics`
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  const totalTasks = plan.reduce((sum, d) => sum + (d.tasks?.length || 0), 0)
  const doneTasks = Object.values(checked).filter(Boolean).length

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 page-enter">
      <div className="flex items-center gap-2 mb-6">
        <Calendar size={20} className="text-[#7c6af7]" />
        <h1 className="text-lg font-semibold text-[#e8e8e8]">Study Plan</h1>
      </div>

      {plan.length === 0 && !loading && (
        <div className="space-y-4">
          <input
            value={topic}
            onChange={e => setTopic(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && generate()}
            placeholder="What do you need to study? (e.g. Year 7 Maths exam, APSMO olympiad...)"
            className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-4 py-2.5 text-sm text-[#e8e8e8] placeholder-[#444] outline-none focus:border-[#7c6af7]/50"
          />
          <div className="flex items-center gap-3">
            <label className="text-xs text-[#888]">Days:</label>
            {[3, 5, 7, 14, 30].map(n => (
              <button key={n} onClick={() => setDays(n)}
                className={`w-10 h-8 rounded-lg text-xs ${days === n ? 'bg-[#7c6af7] text-white' : 'bg-[#1a1a1a] border border-[#2a2a2a] text-[#888]'}`}>
                {n}
              </button>
            ))}
          </div>
          <button onClick={generate} disabled={!topic.trim()}
            className="w-full py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-40">
            Create Study Plan
          </button>
        </div>
      )}

      {loading && (
        <div className="flex flex-col items-center py-16 gap-3">
          <div className="w-8 h-8 border-2 border-[#7c6af7] border-t-transparent rounded-full animate-spin" />
          <p className="text-[#888] text-sm">Building your study plan...</p>
        </div>
      )}

      {plan.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-[#e8e8e8] font-medium">{topic}</h2>
              <p className="text-xs text-[#888] mt-0.5">{doneTasks}/{totalTasks} tasks completed</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-20">
                <div className="w-full bg-[#2a2a2a] rounded-full h-1.5">
                  <div className="bg-[#7c6af7] h-1.5 rounded-full transition-all"
                    style={{ width: `${totalTasks ? (doneTasks / totalTasks) * 100 : 0}%` }} />
                </div>
              </div>
              <button onClick={exportICS}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] text-xs text-[#888] hover:text-[#e8e8e8] hover:border-[#7c6af7]/50 transition-colors">
                <Download size={12} /> Export to Calendar
              </button>
            </div>
          </div>

          <div className="space-y-3">
            {plan.map((day, di) => (
              <div key={di} className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <span className="text-xs text-[#7c6af7] font-semibold">Day {day.day}</span>
                    <p className="text-sm text-[#e8e8e8] mt-0.5">{day.title}</p>
                  </div>
                  <span className="text-xs text-[#555]">{day.time_minutes} min</span>
                </div>
                <div className="space-y-2">
                  {(day.tasks || []).map((task, ti) => {
                    const key = `${di}-${ti}`
                    const done = checked[key]
                    return (
                      <button key={ti} onClick={() => toggleTask(di, ti)}
                        className="w-full flex items-center gap-2.5 text-left text-xs group">
                        {done
                          ? <CheckCircle size={14} className="text-green-400 flex-shrink-0" />
                          : <Circle size={14} className="text-[#444] group-hover:text-[#7c6af7] flex-shrink-0" />}
                        <span className={done ? 'text-[#555] line-through' : 'text-[#aaa]'}>{task}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
          <button onClick={() => setPlan([])} className="mt-4 text-xs text-[#555] hover:text-[#888] w-full text-center">
            ↺ Create new plan
          </button>
        </div>
      )}
    </div>
  )
}
