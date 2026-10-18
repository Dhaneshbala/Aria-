import { useEffect, useState } from 'react'
import { Download, X, Share } from 'lucide-react'

const DISMISSED_KEY = 'aria-install-dismissed'

function isIos() {
  if (typeof navigator === 'undefined') return false
  return /iphone|ipad|ipod/i.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
}

function isStandalone() {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true
}

/**
 * InstallPrompt — PWA install banner for Android (beforeinstallprompt)
 * + manual instructions for iOS (Share → Add to Home Screen).
 * Hidden when already installed or dismissed this week.
 */
export default function InstallPrompt() {
  const [deferred, setDeferred] = useState(null)
  const [visible, setVisible] = useState(false)
  const [isIosDevice, setIsIosDevice] = useState(false)

  useEffect(() => {
    if (isStandalone()) return
    try {
      const raw = localStorage.getItem(DISMISSED_KEY)
      if (raw && Date.now() - Number(raw) < 7 * 24 * 3600 * 1000) return
    } catch {}
    setIsIosDevice(isIos())
    const onBIP = (e) => {
      e.preventDefault()
      setDeferred(e)
      setVisible(true)
    }
    window.addEventListener('beforeinstallprompt', onBIP)
    // iOS has no beforeinstallprompt — show manual hint
    if (isIos()) setVisible(true)
    return () => window.removeEventListener('beforeinstallprompt', onBIP)
  }, [])

  if (!visible) return null

  const dismiss = () => {
    try { localStorage.setItem(DISMISSED_KEY, String(Date.now())) } catch {}
    setVisible(false)
  }

  const install = async () => {
    if (!deferred) return
    deferred.prompt()
    try { await deferred.userChoice } catch {}
    setDeferred(null)
    dismiss()
  }

  return (
    <div role="dialog" aria-label="Install ARIA app"
      className="fixed bottom-[calc(4.5rem+env(safe-area-inset-bottom))] md:bottom-4 left-4 right-4 sm:left-auto sm:right-6 sm:max-w-sm z-40 rounded-2xl border border-aria-border bg-aria-surface/95 backdrop-blur p-4 shadow-2xl">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#8b5cf6] to-[#4285f4] flex items-center justify-center text-white font-bold text-lg flex-shrink-0" aria-hidden="true">A</div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-aria-text">Install ARIA</p>
          {deferred && !isIosDevice ? (
            <p className="text-xs text-aria-muted mt-0.5">Add ARIA to your home screen for fullscreen + offline access.</p>
          ) : (
            <p className="text-xs text-aria-muted mt-0.5 flex items-center gap-1">
              Tap <Share size={12} aria-hidden="true" /> Share → “Add to Home Screen”.
            </p>
          )}
          <div className="flex gap-2 mt-2.5">
            {deferred && !isIosDevice && (
              <button onClick={install}
                className="px-3 py-1.5 rounded-lg bg-[#8ab4f8] text-[#062e6f] text-xs font-semibold flex items-center gap-1.5">
                <Download size={13} /> Install
              </button>
            )}
            <button onClick={dismiss}
              className="px-3 py-1.5 rounded-lg bg-[#2d2e30] text-aria-muted text-xs hover:text-aria-text">
              {isIosDevice && !deferred ? 'Got it' : 'Later'}
            </button>
          </div>
        </div>
        <button onClick={dismiss} aria-label="Dismiss install prompt"
          className="p-1 rounded-full text-aria-muted hover:text-aria-text hover:bg-[#2d2e30]">
          <X size={14} />
        </button>
      </div>
    </div>
  )
}
