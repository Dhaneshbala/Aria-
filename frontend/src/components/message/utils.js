export function isSafeUrl(url) {
  try {
    const u = new URL(url, window.location.origin)
    return u.protocol === 'http:' || u.protocol === 'https:'
  } catch {
    return false
  }
}
