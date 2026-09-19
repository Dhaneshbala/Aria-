// Realtime voice helpers — mirrors backend/services/voice_service.py
// clean_for_speech() + chunk_for_speech() + verbalize_math().
// Keep the two in sync.
//
// Day 1: sentence-chunk queue so TTS starts on sentence 1 while the LLM
// still streams. Day 8: maths verbalization ("x squared").

const MATH_WORDS = { 0: 'zero', 1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six', 7: 'seven', 8: 'eight', 9: 'nine' }

export function verbalizeMath(text) {
  if (!text) return ''
  let out = text
  for (let i = 0; i < 3; i++) {
    const next = out.replace(/\\d?frac\{([^{}]+)\}\{([^{}]+)\}/g, '$1 over $2')
    if (next === out) break
    out = next
  }
  out = out.replace(/\\sqrt\{([^{}]+)\}/g, 'square root of $1')
  out = out.replace(/\\times/g, ' times ').replace(/\\div/g, ' divided by ')
  out = out.replace(/\\pm/g, ' plus or minus ').replace(/\\neq/g, ' is not equal to ')
  out = out.replace(/\\leq?/g, ' is less than or equal to ').replace(/\\geq?/g, ' is greater than or equal to ')
  out = out.replace(/\\cdot/g, ' times ')
  out = out.replace(/([A-Za-z0-9)\]])\s*\^\s*(\{?[A-Za-z0-9]+\}?)/g, (m, base, exp) => {
    const e = exp.replace(/[{} ]/g, '')
    if (e === '2') return `${base} squared`
    if (e === '3') return `${base} cubed`
    return `${base} to the power ${e}`
  })
  out = out.replace(/²/g, ' squared').replace(/³/g, ' cubed')
  out = out.replace(/√\s*([A-Za-z0-9(]+)/g, 'square root of $1')
  out = out.replace(/×/g, ' times ').replace(/÷/g, ' divided by ')
  out = out.replace(/±/g, ' plus or minus ').replace(/≠/g, ' is not equal to ')
  out = out.replace(/≤/g, ' is less than or equal to ').replace(/≥/g, ' is greater than or equal to ')
  out = out.replace(/\s=\s/g, ' equals ')
  out = out.replace(/\b1\s*\/\s*2\b/g, 'one half')
  out = out.replace(/\b1\s*\/\s*4\b/g, 'one quarter')
  out = out.replace(/\b3\s*\/\s*4\b/g, 'three quarters')
  out = out.replace(/\b([0-9])\s*\/\s*([0-9])\b/g, (m, a, b) => `${MATH_WORDS[a]} over ${MATH_WORDS[b]}`)
  out = out.replace(/(\d)\s*%/g, '$1 percent')
  out = out.replace(/\s{2,}/g, ' ')
  return out
}

export function cleanForSpeech(text) {
  if (!text) return ''
  let out = verbalizeMath(text)
  out = out.replace(/```[\s\S]*?```/g, ' [diagram shown on screen]. ')
  out = out.replace(/`([^`]+)`/g, '$1')
  out = out.replace(/\$\$[\s\S]*?\$\$/g, ' [equation shown on screen]. ')
  out = out.replace(/\$([^$]+)\$/g, '$1')
  out = out.replace(/^#{1,6}\s+/gm, '')
  out = out.replace(/\*\*([^*]+)\*\*/g, '$1')
  out = out.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
  out = out.replace(/^[\s]*[-*]\s+/gm, '')
  out = out.replace(/\n{2,}/g, '. ')
  out = out.replace(/\n/g, ' ')
  out = out.replace(/\s{2,}/g, ' ').trim()
  return out.slice(0, 3500)
}

export function chunkForSpeech(text, maxChars = 350) {
  const cleaned = cleanForSpeech(text)
  if (!cleaned) return []
  const parts = cleaned.split(/(?<=[.!?])\s+|\n+/)
  const chunks = []
  let buf = ''
  const flushWordy = (sentence) => {
    let part = sentence.trim()
    while (part.length > maxChars) {
      let cut = part.lastIndexOf(' ', maxChars)
      if (cut <= 0) cut = maxChars
      const piece = part.slice(0, cut).trim()
      if (buf) {
        if (buf.length + 1 + piece.length <= maxChars) buf = `${buf} ${piece}`
        else { chunks.push(buf); buf = piece }
      } else {
        chunks.push(piece)
      }
      part = part.slice(cut).trim()
    }
    return part
  }
  for (const raw of parts) {
    let part = flushWordy(raw)
    if (!part) continue
    if (!buf) buf = part
    else if (buf.length + 1 + part.length <= maxChars) buf = `${buf} ${part}`
    else { chunks.push(buf); buf = part }
  }
  if (buf) chunks.push(buf)
  return chunks
}
