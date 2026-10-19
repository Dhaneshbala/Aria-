/**
 * Accounts auth (Section 13) — session token + auth API client.
 *
 * The session token lives in localStorage under 'aria_session' and rides
 * every API call via apiFetch (services/api.js). Admin dashboards the
 * user sees are cosmetic only — the backend independently enforces every
 * permission; a student poking /admin URLs gets a 403 page, not data.
 */

import { API_BASE } from './api'

const KEY = 'aria_session'

export function getToken() {
  try { return localStorage.getItem(KEY) || '' } catch { return '' }
}
export function setToken(token) {
  try { token ? localStorage.setItem(KEY, token) : localStorage.removeItem(KEY) } catch {}
}
export function clearToken() {
  try { localStorage.removeItem(KEY) } catch {}
}

/** JSON call that adds the session token and never leaks stack traces. */
async function authJson(path, options = {}, expectOk = true) {
  const resp = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
      ...(options.headers || {}),
    },
  })
  if (!resp.ok && expectOk) {
    let detail = resp.statusText
    try {
      const body = await resp.json()
      detail = body.detail || body.error?.message || detail
    } catch {}
    const error = new Error(detail)
    error.status = resp.status
    throw error
  }
  return resp.json()
}

/** Who is signed in (works in both modes — local returns the owner). */
export function fetchMe() {
  return authJson('/auth/me')
}

export function login(username, password) {
  return authJson('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export function register(username, password, displayName = '') {
  return authJson('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, password, display_name: displayName }),
  })
}

export function logout() {
  return authJson('/auth/logout', { method: 'POST' })
}

/** Step-up: re-verify password to unlock admin mutations for 15 min. */
export function adminUnlock(username, password) {
  return authJson('/auth/admin/unlock', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

/** The signed-in student's wallet (ledger from the back end). */
export function getWallet() {
  return authJson('/auth/me/wallet')
}

export function changePassword(currentPassword, newPassword) {
  return authJson('/auth/me', {
    method: 'PATCH',
    body: JSON.stringify({ current_password: currentPassword, password: newPassword }),
  })
}

export function renameMe(displayName) {
  return authJson('/auth/me', {
    method: 'PATCH',
    body: JSON.stringify({ display_name: displayName }),
  })
}

export function deleteMe(password) {
  return authJson('/auth/me', {
    method: 'DELETE',
    body: JSON.stringify({ password }),
  })
}

export function sendFeedback(kind, message) {
  return authJson('/v2/feedback', {
    method: 'POST',
    body: JSON.stringify({ kind, message }),
  })
}
