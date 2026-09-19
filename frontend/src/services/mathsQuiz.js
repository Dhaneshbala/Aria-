/** Maths → Quiz bridge: convert worked-solution maths questions into the
 *  MCQ shape the Quiz Generator tab expects:
 *  { question, options[4], correct: 'A'|'B'|'C'|'D', explanation }.
 *
 *  Distractors are built by perturbing every number in the answer
 *  (+1, −1, negate, +2), so wrong options look like authentic slips.
 *  Pure functions — safe to unit-test without React.
 */

export const TIER_TO_LEVEL = {
  stage4: 'medium',
  foundation: 'medium',
  selective: 'hard',
  extension: 'olympiad',
}

const LETTERS = ['A', 'B', 'C', 'D']

// Quiz tab renders plain text (no KaTeX) — drop $ delimiters.
export function plainTeX(s) {
  return String(s || '').replace(/\$/g, '')
}

function formatLike(raw, val) {
  if (/[.eE]/.test(raw)) return String(Math.round(val * 100) / 100)
  return String(Math.round(val))
}

/** Up to 3 unique plausible variants of a numeric answer string. */
export function numberVariants(text) {
  const src = String(text || '')
  const raws = [...src.matchAll(/-?\d+(?:\.\d+)?/g)].map((m) => m[0])
  const uniq = [...new Set(raws)]
  if (!uniq.length) return []
  const vals = uniq.map(Number)
  const transforms = [
    (vs) => vs.map((v) => v + 1),
    (vs) => vs.map((v) => v - 1),
    (vs) => vs.map((v) => -v),
    (vs) => vs.map((v) => v + 2),
  ]
  const lookup = new Map()
  const out = []
  for (const t of transforms) {
    const mapped = t(vals)
    uniq.forEach((r, k) => lookup.set(r, formatLike(r, mapped[k])))
    // Same tokenisation as matchAll, so every hit is in the map.
    const rep = src.replace(/-?\d+(?:\.\d+)?/g, (m) => lookup.get(m) ?? m)
    if (rep !== src && !out.includes(rep)) out.push(rep)
    if (out.length === 3) break
  }
  return out
}

function shuffle(arr) {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

/** One maths question → quiz MCQ, or null when no numeric answer to vary. */
export function mathsQuestionToQuiz(q) {
  const answer = plainTeX(q?.answer).trim()
  if (!answer || !/-?\d/.test(answer)) return null
  const variants = numberVariants(answer)
  if (variants.length < 3) return null
  const options = shuffle([answer, ...variants.slice(0, 3)])
  const correct = LETTERS[options.indexOf(answer)]
  const steps = [...(q.solution_steps || [])]
  if (q.trap) steps.push(`Trap: ${q.trap}`)
  const explanation = plainTeX(steps.join(' → ')).slice(0, 400) || answer
  return {
    question: plainTeX(q.question).trim().slice(0, 300) || 'Maths question',
    options,
    correct,
    explanation,
  }
}

/** Whole set → { items, skipped }. Non-convertible questions are dropped. */
export function mathsSetToQuiz(questions) {
  const items = []
  let skipped = 0
  for (const q of questions || []) {
    const converted = mathsQuestionToQuiz(q)
    if (converted) items.push(converted)
    else skipped++
  }
  return { items, skipped }
}
