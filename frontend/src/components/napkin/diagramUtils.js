/**
 * NapkinDiagram pure helpers — canvas sizing, text wrapping, number parsing,
 * colours, filename slugs. No React, fully unit-testable.
 */

export const W = 640
export const BASE_H = 420

// Dynamic canvas height per layout so 6-8 nodes never clip.
// Flowchart stacks vertically; comparison/bar grow per row.
export function canvasHeight(vtype, n) {
  if (vtype === 'flowchart') return Math.max(BASE_H, 120 + n * 86)
  if (vtype === 'comparison') return Math.max(BASE_H, 120 + Math.ceil(n / 2) * 80)
  if (vtype === 'bar') return Math.max(BASE_H, 130 + n * 52)
  if (vtype === 'steps') return n > 3 ? 460 : BASE_H
  if (vtype === 'pyramid') return Math.max(BASE_H, 130 + Math.min(n, 6) * 58)
  return BASE_H
}

export function wrap(text, max = 20) {
  const words = String(text || '').split(/\s+/)
  const lines = []
  let cur = ''
  for (const w of words) {
    if ((cur + ' ' + w).trim().length > max && cur) { lines.push(cur); cur = w }
    else cur = (cur + ' ' + w).trim()
  }
  if (cur) lines.push(cur)
  return lines.slice(0, 3)
}

export function numFrom(label, fallback) {
  const m = String(label).match(/(\d+(?:\.\d+)?)\s*%/)
  if (m) return parseFloat(m[1])
  const m2 = String(label).match(/(\d+(?:\.\d+)?)/)
  if (m2) return parseFloat(m2[1])
  return fallback
}

export function colorFor(theme, i) {
  return theme.palette[i % theme.palette.length]
}

export function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

export function slugify(t) {
  const s = String(t || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
  return s || 'aria-visual'
}

// Strip only an explicit trailing percent ("Oceans 71%", "Share 42 percent").
// Bare trailing numbers are KEPT ("Year 7", "Score 42") — stripping them
// mangles names, while duplicating the value at the bar end is harmless.
export function barLabel(label) {
  const s = String(label)
    .replace(/\s+\d+(\.\d+)?\s*%\s*$/, '')
    .replace(/\s+\d+(\.\d+)?\s*percent\s*$/i, '')
    .trim().slice(0, 20)
  return s || label
}
