import { useEffect } from 'react'

/** Premium replacement for window.confirm — accessible, styled, safe. */
export default function ConfirmModal({ open, title = 'Are you sure?', body = '', confirmLabel = 'Delete', cancelLabel = 'Cancel', danger = true, onConfirm, onCancel }) {
  useEffect(() => {
    if (!open) return
    const onKey = (e) => { if (e.key === 'Escape') onCancel?.() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onCancel])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={title}>
      <button aria-label="Close dialog" onClick={onCancel} className="absolute inset-0 bg-black/60" />
      <div className="card relative w-full max-w-sm p-5 animate-fade-slide">
        <h3 className="text-[15px] font-semibold text-aria-text mb-1">{title}</h3>
        {body ? <p className="text-[13px] text-aria-muted mb-4">{body}</p> : null}
        <div className="flex justify-end gap-2">
          <button onClick={onCancel} className="touch-target px-4 py-2 rounded-pill text-[13px] bg-aria-variant hover:bg-aria-border-light text-aria-text transition-colors">
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            autoFocus
            className={`touch-target px-4 py-2 rounded-pill text-[13px] text-white transition-colors ${danger ? 'bg-red-500 hover:bg-red-400' : 'btn-primary'}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
