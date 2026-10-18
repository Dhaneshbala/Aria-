import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
// KaTeX styles bundled locally (was a CDN <link> — maths now renders offline).
// WOFF2 fonts referenced by the CSS are emitted + precached by the build.
import 'katex/dist/katex.min.css'
import { initWebVitals } from './services/perf'

initWebVitals()

// PWA update notice — the SW self-registers (vite-plugin-pwa autoUpdate);
// this only announces when a new version takes control.
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  import('workbox-window').then(async ({ Workbox }) => {
    try {
      const wb = new Workbox('/sw.js')
      wb.addEventListener('controlling', async () => {
        const { showToast } = await import('./components/Toast')
        showToast('ARIA updated to the latest version', 'success', 3000)
      })
      wb.register()
    } catch {
      // SW registration is best-effort (private mode, denied storage)
    }
  }).catch(() => {})
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode><App /></React.StrictMode>
)
