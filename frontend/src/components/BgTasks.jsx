import { useNavigate, useLocation } from 'react-router-dom'
import { useStore } from '../store'
import { cancelTask } from '../services/tasks'
import { Loader, Check, AlertTriangle, X } from 'lucide-react'

/**
 * BgTasks — global background-task pill, visible on every page.
 * Running tasks keep going when you navigate; this pill shows them with
 * Cancel and View (jump back to the origin page). Finished tasks show
 * briefly, then auto-dismiss.
 */
export default function BgTasks() {
  const bgTasks = useStore(s => s.bgTasks)
  const navigate = useNavigate()
  const location = useLocation()

  const entries = Object.entries(bgTasks || {})
  if (!entries.length) return null

  const elapsed = (t) => {
    const s = Math.max(0, Math.round((Date.now() - (t.startedAt || Date.now())) / 1000))
    return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`
  }

  return (
    <div className="fixed bottom-4 left-4 z-50 flex flex-col gap-2 max-w-xs">
      {entries.map(([key, t]) => (
        <div key={key}
          className="flex items-center gap-2.5 pl-3 pr-2 py-2 rounded-2xl border shadow-xl backdrop-blur-md bg-[#161616]/95 border-[#2a2a2a]">
          {t.status === 'running' && <Loader size={14} className="animate-spin text-[#7c6af7] flex-shrink-0" />}
          {t.status === 'done' && <Check size={14} className="text-green-400 flex-shrink-0" />}
          {(t.status === 'error' || t.status === 'cancelled') && (
            <AlertTriangle size={14} className="text-amber-400 flex-shrink-0" />
          )}
          <div className="min-w-0 flex-1">
            <p className="text-xs text-[#e8e8e8] truncate">{t.label || 'Task'}</p>
            <p className="text-[10px] text-[#666]">
              {t.status === 'running' ? `Running in background · ${elapsed(t)}` :
               t.status === 'done' ? 'Finished — tap View' :
               t.error || t.status}
            </p>
          </div>
          {t.page && (t.status === 'running' || t.status === 'done') && location.pathname !== t.page && (
            <button onClick={() => navigate(t.page)}
              className="text-[11px] px-2.5 py-1 rounded-full bg-[#7c6af7] text-white hover:bg-[#6a59e0] flex-shrink-0">
              View
            </button>
          )}
          {t.status === 'running' && (
            <button onClick={() => cancelTask(key)} title="Cancel task"
              className="p-1.5 rounded-full text-[#666] hover:text-white hover:bg-[#2a2a2a] flex-shrink-0">
              <X size={13} />
            </button>
          )}
          {t.status !== 'running' && (
            <button onClick={() => useStore.getState().clearBgTask(key)} title="Dismiss"
              className="p-1.5 rounded-full text-[#555] hover:text-white hover:bg-[#2a2a2a] flex-shrink-0">
              <X size={13} />
            </button>
          )}
        </div>
      ))}
    </div>
  )
}
