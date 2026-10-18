import { get, set, del, keys } from 'idb-keyval'

// Offline review queue — failed flashcard reviews wait in IndexedDB and
// sync when connectivity returns. Survives reloads (unlike memory).

const PREFIX = 'aria-offline-review:'

export async function queueReview(card_id, quality) {
  try {
    await set(`${PREFIX}${card_id}:${Date.now()}`, { card_id, quality, ts: Date.now() })
  } catch {
    // IndexedDB unavailable (private mode) — review is lost, caller toasts
  }
}

async function pendingReviews() {
  try {
    const all = await keys()
    return all.filter(k => String(k).startsWith(PREFIX))
  } catch {
    return []
  }
}

export async function pendingReviewCount() {
  return (await pendingReviews()).length
}

/**
 * POST every queued review via `send`, deleting each success.
 * Returns { synced, failed }. Never throws.
 */
export async function flushReviews(send) {
  let synced = 0, failed = 0
  for (const key of await pendingReviews()) {
    try {
      const { card_id, quality } = await get(key)
      await send(card_id, quality)
      await del(key)
      synced++
    } catch {
      failed++
    }
  }
  return { synced, failed }
}

// Auto-flush when the browser regains connectivity. The sender is injected
// late to avoid a circular import with services/api.
let sender = null
export function setReviewSender(fn) {
  sender = fn
}
if (typeof window !== 'undefined') {
  window.addEventListener('online', async () => {
    if (!sender) return
    const { synced } = await flushReviews(sender)
    if (synced > 0) {
      const { showToast } = await import('../components/Toast')
      showToast(`Synced ${synced} offline review${synced > 1 ? 's' : ''}`, 'success', 2500)
    }
  })
}
