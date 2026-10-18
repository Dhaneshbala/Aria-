import { onLCP, onINP, onCLS } from 'web-vitals'

const KEY = 'aria-web-vitals'
const MAX = 20

function record(metric) {
  try {
    const entry = {
      name: metric.name,
      value: Math.round(metric.value * 100) / 100,
      rating: metric.rating,
      ts: Date.now(),
    }
    const prev = JSON.parse(localStorage.getItem(KEY) || '[]')
    prev.push(entry)
    localStorage.setItem(KEY, JSON.stringify(prev.slice(-MAX)))
  } catch {}
}

export function initWebVitals() {
  if (typeof window === 'undefined') return
  try {
    onLCP(record)
    onINP(record)
    onCLS(record)
  } catch {}
}

export function getWebVitals() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]')
  } catch {
    return []
  }
}

export function clearWebVitals() {
  try {
    localStorage.removeItem(KEY)
  } catch {}
}
