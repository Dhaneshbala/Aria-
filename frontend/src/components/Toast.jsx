import { useState, useEffect } from 'react'
import { X, AlertCircle, CheckCircle, Info } from 'lucide-react'

let toastId = 0
const listeners = new Set()

export function showToast(message, type = 'error', duration = 5000, action = null) {
  const id = ++toastId
  const toast = { id, message, type, duration, action }
  listeners.forEach(fn => fn(toast))
  return id
}

export function ToastContainer() {
  const [toasts, setToasts] = useState([])

  useEffect(() => {
    const handler = (toast) => {
      setToasts(prev => [...prev, toast])
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== toast.id))
      }, toast.duration)
    }
    listeners.add(handler)
    return () => listeners.delete(handler)
  }, [])

  const dismiss = (id) => setToasts(prev => prev.filter(t => t.id !== id))

  if (!toasts.length) return null

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-[calc(4rem+env(safe-area-inset-bottom))] md:bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm"
    >
      {toasts.map(toast => (
        <div
          key={toast.id}
          className={`flex items-start gap-3 px-4 py-3 rounded-xl border shadow-lg backdrop-blur-sm animate-in slide-in-from-right-5 ${
            toast.type === 'error'
              ? 'bg-red-950/90 border-red-800/50 text-red-200'
              : toast.type === 'success'
              ? 'bg-green-950/90 border-green-800/50 text-green-200'
              : 'bg-[#1a1a1a]/90 border-aria-border text-[#e8e8e8]'
          }`}
        >
          {toast.type === 'error' && <AlertCircle size={16} className="mt-0.5 flex-shrink-0 text-red-400" />}
          {toast.type === 'success' && <CheckCircle size={16} className="mt-0.5 flex-shrink-0 text-green-400" />}
          {toast.type === 'info' && <Info size={16} className="mt-0.5 flex-shrink-0 text-blue-400" />}
          <p className="text-sm flex-1">{toast.message}</p>
          {toast.action && (
            <button
              onClick={() => { try { toast.action.onClick?.() } catch {} dismiss(toast.id) }}
              className="flex-shrink-0 text-xs font-semibold px-2.5 py-1 rounded-lg bg-white/10 hover:bg-white/20 transition-colors"
            >
              {toast.action.label}
            </button>
          )}
          <button onClick={() => dismiss(toast.id)} aria-label="Dismiss" className="text-current opacity-50 hover:opacity-100 mt-0.5">
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  )
}
