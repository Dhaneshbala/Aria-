/** Message shared helpers — URL safety + follow-up suggestions. No React. Extracted from Message.jsx. */

export function isSafeUrl(url) {
  try {
    const u = new URL(url, window.location.origin)
    return u.protocol === 'http:' || u.protocol === 'https:'
  } catch {
    return false
  }
}

export const FOLLOW_UPS = {
  explain:  ['Quiz me on this', 'Show me a mind map', 'Give me a practice question'],
  math:     ['Show me another method', 'Make it harder', 'Quiz me on this'],
  science:  ['Draw a diagram', 'Quiz me on this', 'Give me a real-world example'],
  history:  ['Make a timeline', 'Quiz me on this', 'Compare with another event'],
  coding:   ['Debug this code', 'Show me another example', 'Make a quiz on this'],
  quiz:     ['Make it harder', 'Try another topic', 'Review my mistakes'],
  default:  ['Quiz me on this', 'Make a mind map', 'Explain differently'],
}

export function getFollowUps(content) {
  const lower = (content || '').toLowerCase()
  if (lower.includes('quiz') || lower.includes('question')) return FOLLOW_UPS.quiz
  if (lower.includes('explain') || lower.includes('what is') || lower.includes('how does')) return FOLLOW_UPS.explain
  if (lower.includes('math') || lower.includes('equation') || lower.includes('calculate') || lower.includes('algebra')) return FOLLOW_UPS.math
  if (lower.includes('science') || lower.includes('biology') || lower.includes('chemistry') || lower.includes('physics')) return FOLLOW_UPS.science
  if (lower.includes('history') || lower.includes('war') || lower.includes('revolution')) return FOLLOW_UPS.history
  if (lower.includes('code') || lower.includes('function') || lower.includes('python') || lower.includes('javascript')) return FOLLOW_UPS.coding
  return FOLLOW_UPS.default
}
