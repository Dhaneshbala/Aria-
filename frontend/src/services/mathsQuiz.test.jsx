import { describe, it, expect } from 'vitest'
import { mathsQuestionToQuiz, mathsSetToQuiz, numberVariants, TIER_TO_LEVEL } from './mathsQuiz'

const SOLVE = {
  question: 'Solve for $x$: $2x + 7 = 19$. Show every step.',
  marks: 2,
  solution_steps: ['Undo +7 (both sides): $2x = 12$', 'Undo ×2: $x = 6$', 'Check: $2(6) + 7 = 19$'],
  trap: 'Always reverse BODMAS.',
  shortcut: 'Substitute back to check.',
  answer: '$x = 6$',
}

describe('mathsQuestionToQuiz', () => {
  it('builds 4 unique options with the correct letter on the answer', () => {
    const q = mathsQuestionToQuiz(SOLVE)
    expect(q.options.length).toBe(4)
    expect(new Set(q.options).size).toBe(4)
    expect(q.options['ABCD'.indexOf(q.correct)]).toBe('x = 6')
  })

  it('strips KaTeX delimiters for the plain-text quiz tab', () => {
    const q = mathsQuestionToQuiz(SOLVE)
    expect(q.question).not.toMatch(/\$/)
    expect(q.explanation).toContain('Undo +7')
  })

  it('returns null when the answer has no numbers to vary', () => {
    expect(mathsQuestionToQuiz({ question: 'Define it', answer: 'See worked example' })).toBe(null)
  })
})

describe('numberVariants', () => {
  it('produces 3 unique plausible variants', () => {
    const vs = numberVariants('$x=2$ or $x=3$')
    expect(vs.length).toBe(3)
    expect(new Set(vs).size).toBe(3)
    for (const v of vs) expect(v).not.toBe('$x=2$ or $x=3$')
  })
})

describe('mathsSetToQuiz', () => {
  it('converts what it can and counts skips', () => {
    const { items, skipped } = mathsSetToQuiz([SOLVE, { question: 'Essay task', answer: 'See proof' }])
    expect(items.length).toBe(1)
    expect(skipped).toBe(1)
  })
})

describe('TIER_TO_LEVEL', () => {
  it('maps accelerator tiers onto quiz difficulties', () => {
    expect(TIER_TO_LEVEL.stage4).toBe('medium')
    expect(TIER_TO_LEVEL.foundation).toBe('medium')
    expect(TIER_TO_LEVEL.selective).toBe('hard')
    expect(TIER_TO_LEVEL.extension).toBe('olympiad')
  })
})
