import { useEffect, useState } from 'react'
import { isSafeUrl } from './utils'

/* Zoom modal: mouse users dismiss by clicking anywhere; keyboard users get
   Escape via the window listener below. The a11y rules that require an
   interactive role + keyboard handler on that div are disabled for this
   file only because the dialog is a full-screen image overlay. */
/* eslint-disable jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/click-events-have-key-events */
/**
 * ZoomableImage — lazy-loaded thumbnail, tap for fullscreen.
 * Download link only for http(s) URLs (blob:/data: stay in-page).
 */
export default function ZoomableImage({ src, alt, className = '', downloadName = 'aria-image.png' }) {
  const [zoom, setZoom] = useState(false)

  // Escape closes the fullscreen zoom — window-level so no focus juggling needed
  useEffect(() => {
    if (!zoom) return
    const onKey = (e) => { if (e.key === 'Escape') setZoom(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [zoom])
  if (!src) return null
  return (
    <div className="w-full">
      <button onClick={() => setZoom(true)} className="block text-left" aria-label={`Enlarge image: ${alt}`}>
        <img src={src} alt={alt} loading="lazy" decoding="async" className={className} />
      </button>
      {isSafeUrl(src) && (
        <a href={src} download={downloadName}
          className="text-xs text-[#888] hover:text-[#aaa] mt-1 block">
          ↓ Download image
        </a>
      )}
      {zoom && (
        <div className="fixed inset-0 z-40 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setZoom(false)} role="dialog" aria-label={alt}>
          <img src={src} alt={alt} className="max-w-full max-h-full rounded-xl shadow-2xl" />
        </div>
      )}
    </div>
  )
}
