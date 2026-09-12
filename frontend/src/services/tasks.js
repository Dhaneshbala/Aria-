/**
 * tasks.js — background task manager.
 *
 * Problem: page-level work (quiz / flashcards / mind map / exam plan /
 * visuals) lived in component state. Navigate away mid-generation and the
 * fetch kept running but its result died with the unmounted component —
 * from the user's view the task "crashed and stopped".
 *
 * Fix: tasks run here, at module scope (survives route changes + tab
 * switches inside Create). Status lives in the Zustand store so any page
 * can show progress, and results are written to the store (studyTools /
 * messages) so returning later shows the finished work.
 *
 * Only manual cancel (Cancel button / starting the same task again) aborts.
 * Voice Tutor is intentionally NOT migrated — mic/audio must stop on leave.
 */
import { useStore } from '../store'
import { showToast } from '../components/Toast'

const controllers = new Map() // key -> AbortController (manager-owned, not tied to unmount)
const runIds = new Map()      // key -> latest run id (stale completions are ignored)
let seq = 0

/** Reactive subscription to one task's status (running|done|error|cancelled). */
export function useBgTask(key) {
  return useStore(s => s.bgTasks?.[key])
}

/**
 * Run a task in the background.
 *   key   — stable id ('quiz', 'flashcards', 'examplan', `viz-${msgId}`)
 *   label — shown in the global pill, e.g. 'Quiz: Fractions'
 *   page  — where "View" navigates, e.g. '/create'
 *   run   — async (signal) => result. Respect the signal for real cancel.
 *   onDone— (result) => void. Persist result to the store (runs even if page gone).
 * Returns the result (or throws). Starting the same key cancels the old run.
 */
export async function startTask(key, { label, page, topic, run, onDone }) {
  cancelTask(key, { silent: true })
  const ctrl = new AbortController()
  controllers.set(key, ctrl)
  const runId = ++seq
  runIds.set(key, runId)
  const store = useStore.getState()
  store.setBgTask(key, { label, page, topic, status: 'running', startedAt: Date.now(), runId, error: '' })

  const stillCurrent = () => runIds.get(key) === runId && controllers.get(key) === ctrl

  try {
    const result = await run(ctrl.signal)
    if (!stillCurrent()) return result // superseded or user-cancelled — don't touch UI
    useStore.getState().setBgTask(key, { status: 'done', finishedAt: Date.now() })
    try { await onDone?.(result) } catch (e) { console.warn('task onDone failed', e) }
    return result
  } catch (e) {
    if (!stillCurrent()) throw e // superseded — stay quiet
    const cancelled = e?.name === 'AbortError' || ctrl.signal.aborted
    useStore.getState().setBgTask(key, {
      status: cancelled ? 'cancelled' : 'error',
      error: cancelled ? 'Cancelled' : (e?.message || 'Failed'),
      finishedAt: Date.now(),
    })
    if (!cancelled) showToast(`${label} failed: ${e?.message || 'error'}`, 'error')
    throw e
  } finally {
    if (controllers.get(key) === ctrl) controllers.delete(key)
    // Don't linger: clear finished entries after 30s (pill auto-dismisses)
    setTimeout(() => {
      const cur = useStore.getState().bgTasks?.[key]
      if (cur && cur.runId === runId && cur.status !== 'running') {
        useStore.getState().clearBgTask(key)
      }
    }, 30000)
  }
}

/** Manual cancel only — never called on unmount. Late results are ignored. */
export function cancelTask(key, { silent } = {}) {
  const cur = useStore.getState().bgTasks?.[key]
  runIds.set(key, ++seq) // invalidate any late settlement
  const ctrl = controllers.get(key)
  if (ctrl) {
    controllers.delete(key)
    try { ctrl.abort() } catch {}
  }
  if (cur?.status === 'running') {
    useStore.getState().setBgTask(key, { status: 'cancelled', error: 'Cancelled', finishedAt: Date.now() })
    if (!silent) showToast(`${cur.label || 'Task'} cancelled`, 'info')
  }
}
