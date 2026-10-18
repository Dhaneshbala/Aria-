import { useEffect, useState } from 'react'

/**
 * OfflineBadge — tells the user when the PWA shell is running without
 * network. AI features need the backend; cached pages still work.
 */
export default function OfflineBadge() {
  const [online, setOnline] = useState(() =>
    typeof navigator === 'undefined' ? true : navigator.onLine
  )

  useEffect(() => {
    const goOffline = () => setOnline(false)
    const goOnline = () => setOnline(true)
    window.addEventListener('offline', goOffline)
    window.addEventListener('online', goOnline)
    return () => {
      window.removeEventListener('offline', goOffline)
      window.removeEventListener('online', goOnline)
    }
  }, [])

  if (online) return null

  return (
    <div role="status" className="flex items-center justify-center gap-2 px-4 py-1.5 bg-amber-500/15 border-b border-amber-500/25 text-xs text-amber-300">
      <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
      You're offline — saved pages work, AI answers need connection
    </div>
  )
}
