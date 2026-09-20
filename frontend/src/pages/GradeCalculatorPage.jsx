import { useMemo, useState, useEffect } from 'react'
import { Calculator, Plus, Trash2, Flame } from 'lucide-react'

const GRADE_PRESETS = [
  { label: 'Pass 50', value: 50 },
  { label: 'Credit 65', value: 65 },
  { label: 'Distinction 75', value: 75 },
  { label: 'HD 85', value: 85 },
  { label: '90+', value: 90 },
]

function uid() {
  return Math.random().toString(36).slice(2, 9)
}

function loadState() {
  try {
    const raw = localStorage.getItem('aria_grade_calc')
    if (raw) {
      const p = JSON.parse(raw)
      if (Array.isArray(p.rows)) return p
    }
  } catch {}
  return {
    rows: [
      { id: uid(), name: 'Assignment 1', score: 72, weight: 20 },
      { id: uid(), name: 'Mid-term', score: 65, weight: 30 },
    ],
    finalWeight: 50,
    finalName: 'Final exam',
    target: 70,
  }
}

function verdictFor(required) {
  if (required === null) return null
  if (required <= 0) return { emoji: '🔒', title: "Locked in — you've already hit it", tone: 'text-green-400', desc: 'You could score 0 on the final and still hit your target. Aim higher?' }
  if (required <= 40) return { emoji: '🔥', title: 'Easy. Free marks.', tone: 'text-green-400', desc: 'Light revision and you cruise past your target.' }
  if (required <= 60) return { emoji: '💪', title: 'Doable — lock in.', tone: 'text-[#8ab4f8]', desc: 'A solid study week gets you there. Weak topics first.' }
  if (required <= 75) return { emoji: '🌶️', title: 'Spicy but possible.', tone: 'text-amber-400', desc: 'Every mark counts now. Past papers + cheat sheet.' }
  if (required <= 100) return { emoji: '😤', title: 'Final-boss mode.', tone: 'text-orange-400', desc: 'You need near-perfect. Plan every day, no wasted sessions.' }
  return { emoji: '💀', title: "You're cooked.", tone: 'text-red-400', desc: 'Target is out of reach even with 100% on the final. Lower the target or talk to your teacher about extra credit.' }
}

export default function GradeCalculatorPage() {
  const [state, setState] = useState(loadState)
  const { rows, finalWeight, finalName, target } = state

  useEffect(() => {
    try { localStorage.setItem('aria_grade_calc', JSON.stringify(state)) } catch {}
  }, [state])

  const patch = (p) => setState(s => ({ ...s, ...p }))
  const setRow = (id, f, v) => setState(s => ({
    ...s,
    rows: s.rows.map(r => (r.id === id ? { ...r, [f]: v } : r)),
  }))
  const addRow = () => setState(s => ({
    ...s,
    rows: [...s.rows, { id: uid(), name: `Task ${s.rows.length + 1}`, score: 70, weight: 10 }],
  }))
  const delRow = (id) => setState(s => ({ ...s, rows: s.rows.filter(r => r.id !== id) }))

  const calc = useMemo(() => {
    const clean = rows.map(r => ({
      score: Math.min(100, Math.max(0, Number(r.score) || 0)),
      weight: Math.max(0, Number(r.weight) || 0),
    }))
    const doneWeight = clean.reduce((a, r) => a + r.weight, 0)
    const earned = clean.reduce((a, r) => a + (r.score / 100) * r.weight, 0)
    const fw = Math.max(0, Number(finalWeight) || 0)
    const total = doneWeight + fw
    const t = Math.min(100, Math.max(0, Number(target) || 0))
    const required = fw > 0 ? ((t - earned) / fw) * 100 : null
    const maxPossible = earned + fw // 100% on final
    const currentAvg = doneWeight > 0 ? (earned / doneWeight) * 100 : 0
    return { earned, doneWeight, fw, total, target: t, required, maxPossible, currentAvg }
  }, [rows, finalWeight, target])

  const v = verdictFor(calc.required)
  const totalBad = Math.abs(calc.total - 100) > 0.01

  const scenarios = [50, 65, 75, 85, 90].map(g => ({
    grade: g,
    need: calc.fw > 0 ? ((g - calc.earned) / calc.fw) * 100 : null,
  }))

  return (
    <div className="w-full max-w-2xl mx-auto px-6 py-8">
      <div className="flex items-center gap-2 mb-1">
        <Flame size={20} className="text-orange-400" />
        <h1 className="text-2xl font-bold text-[#e8e8e8]">Am I Cooked?</h1>
      </div>
      <p className="text-sm text-[#888] mb-6">Plug in your marks + weightings. Study Buddy tells you exactly what you need on the final to hit your target.</p>

      {/* Completed assessments */}
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl p-4 mb-4">
        <p className="text-xs font-semibold text-[#aaa] uppercase tracking-wide mb-3">Done so far</p>
        <div className="space-y-2">
          {rows.map(r => (
            <div key={r.id} className="grid grid-cols-[1fr_72px_72px_28px] gap-2 items-center">
              <input
                value={r.name}
                onChange={e => setRow(r.id, 'name', e.target.value)}
                placeholder="Assignment / test name"
                className="bg-[#141414] border border-[#2a2a2a] rounded-xl px-3 py-2 text-sm text-[#e8e8e8] outline-none focus:border-[#7c6af7]/60 min-w-0"
              />
              <label className="flex items-center gap-1 bg-[#141414] border border-[#2a2a2a] rounded-xl px-2 py-2">
                <input
                  type="number" min={0} max={100} value={r.score}
                  onChange={e => setRow(r.id, 'score', e.target.value)}
                  className="w-full bg-transparent text-sm text-[#e8e8e8] outline-none text-center"
                />
                <span className="text-[10px] text-[#555]">%</span>
              </label>
              <label className="flex items-center gap-1 bg-[#141414] border border-[#2a2a2a] rounded-xl px-2 py-2">
                <input
                  type="number" min={0} max={100} value={r.weight}
                  onChange={e => setRow(r.id, 'weight', e.target.value)}
                  className="w-full bg-transparent text-sm text-[#e8e8e8] outline-none text-center"
                />
                <span className="text-[10px] text-[#555]">wt</span>
              </label>
              <button onClick={() => delRow(r.id)} className="p-2 text-[#555] hover:text-red-400 transition-colors" title="Remove">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
        <button
          onClick={addRow}
          className="mt-3 flex items-center gap-1.5 text-xs px-3 py-2 rounded-xl bg-[#2a2a2a] hover:bg-[#35363a] text-[#e8e8e8] transition-colors"
        >
          <Plus size={13} /> Add assessment
        </button>
        <p className="text-[11px] text-[#555] mt-2">Score = your mark as %. Weight = % of the final grade (e.g. mid-term worth 30).</p>
      </div>

      {/* Final + target */}
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl p-4 mb-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <p className="text-xs font-semibold text-[#aaa] uppercase tracking-wide mb-1.5">Final exam</p>
            <input
              value={finalName}
              onChange={e => patch({ finalName: e.target.value })}
              className="w-full bg-[#141414] border border-[#2a2a2a] rounded-xl px-3 py-2 text-sm text-[#e8e8e8] outline-none focus:border-[#7c6af7]/60 mb-2"
            />
            <label className="flex items-center gap-2 bg-[#141414] border border-[#2a2a2a] rounded-xl px-3 py-2">
              <input
                type="number" min={0} max={100} value={finalWeight}
                onChange={e => patch({ finalWeight: e.target.value })}
                className="w-full bg-transparent text-sm text-[#e8e8e8] outline-none"
              />
              <span className="text-[11px] text-[#555]">% weight</span>
            </label>
          </div>
          <div>
            <p className="text-xs font-semibold text-[#aaa] uppercase tracking-wide mb-1.5">Target grade</p>
            <label className="flex items-center gap-2 bg-[#141414] border border-[#2a2a2a] rounded-xl px-3 py-2 mb-2">
              <Calculator size={14} className="text-[#7c6af7] shrink-0" />
              <input
                type="number" min={0} max={100} value={target}
                onChange={e => patch({ target: e.target.value })}
                className="w-full bg-transparent text-sm text-[#e8e8e8] outline-none"
              />
              <span className="text-[11px] text-[#555]">%</span>
            </label>
            <div className="flex flex-wrap gap-1.5">
              {GRADE_PRESETS.map(g => (
                <button
                  key={g.label}
                  onClick={() => patch({ target: g.value })}
                  className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${Number(target) === g.value ? 'bg-[#7c6af7] text-white border-[#7c6af7]' : 'bg-[#141414] text-[#999] border-[#2a2a2a] hover:border-[#7c6af7]/50'}`}
                >
                  {g.label}
                </button>
              ))}
            </div>
          </div>
        </div>
        {totalBad && (
          <p className="text-[11px] text-amber-400/90 mt-3">
            ⚠️ Weights add to {calc.total}% — they should total 100% (done {calc.doneWeight}% + final {calc.fw}%).
          </p>
        )}
      </div>

      {/* Result */}
      {calc.fw > 0 && calc.required !== null && v && (
        <div className="bg-gradient-to-br from-[#1e1b2e] to-[#1a1a1a] border border-[#7c6af7]/25 rounded-2xl p-5 mb-4 text-center">
          <p className="text-4xl mb-1">{v.emoji}</p>
          <p className="text-xs text-[#888] uppercase tracking-wide">You need on {finalName || 'the final'}</p>
          <p className={`text-5xl font-bold my-1 ${v.tone}`}>
            {calc.required <= 0 ? '0%' : calc.required > 100 ? `${calc.required.toFixed(1)}%` : `${calc.required.toFixed(1)}%`}
          </p>
          <p className={`text-sm font-semibold ${v.tone}`}>{v.title}</p>
          <p className="text-xs text-[#999] mt-1 leading-relaxed">{v.desc}</p>
          <div className="flex justify-center gap-4 mt-3 text-[11px] text-[#777]">
            <span>Earned so far: <b className="text-[#ccc]">{calc.earned.toFixed(1)} / 100</b></span>
            <span>Avg so far: <b className="text-[#ccc]">{calc.doneWeight ? calc.currentAvg.toFixed(1) + '%' : '—'}</b></span>
            <span>Max possible: <b className="text-[#ccc]">{calc.maxPossible.toFixed(1)}</b></span>
          </div>
          {calc.required > 100 && (
            <p className="text-[11px] text-[#888] mt-2">
              Even 100% on the final only gets you {calc.maxPossible.toFixed(1)}%. Consider aiming for {Math.floor(calc.maxPossible)}% instead.
            </p>
          )}
        </div>
      )}

      {/* What-if table */}
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl p-4">
        <p className="text-xs font-semibold text-[#aaa] uppercase tracking-wide mb-2">What do I need for…</p>
        <div className="grid grid-cols-5 gap-2 text-center">
          {scenarios.map(s => (
            <button
              key={s.grade}
              onClick={() => patch({ target: s.grade })}
              className={`rounded-xl border py-2 transition-colors ${Number(target) === s.grade ? 'border-[#7c6af7]/60 bg-[#7c6af7]/10' : 'border-[#2a2a2a] bg-[#141414] hover:border-[#3a3a3a]'}`}
              title={`Set target to ${s.grade}%`}
            >
              <span className="block text-[11px] text-[#888]">{s.grade}%</span>
              <span className={`block text-sm font-bold ${s.need === null ? 'text-[#555]' : s.need <= 0 ? 'text-green-400' : s.need > 100 ? 'text-red-400' : 'text-[#e8e8e8]'}`}>
                {s.need === null ? '—' : s.need <= 0 ? '✓' : s.need > 100 ? '💀' : `${s.need.toFixed(0)}%`}
              </span>
            </button>
          ))}
        </div>
        <p className="text-[11px] text-[#555] mt-2 text-center">Tap a grade to set it as your target. ✓ = already secured, 💀 = impossible.</p>
      </div>
    </div>
  )
}
