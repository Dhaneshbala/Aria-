import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [react(), VitePWA({
    registerType: 'autoUpdate',
    includeAssets: ['favicon.ico'],
    manifest: {
      name: 'ARIA - AI Study Assistant',
      short_name: 'ARIA',
      description: 'Your offline-friendly AI study companion',
      theme_color: '#7c6af7',
      background_color: '#0f0f0f',
      display: 'standalone',
      icons: [
        { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
        { src: '/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
        { src: '/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
      ]
    },
    workbox: {
      runtimeCaching: [
        { urlPattern: /^https:\/\/.*katex.*/, handler: 'CacheFirst', options: { cacheName: 'katex', expiration: { maxEntries: 20, maxAgeSeconds: 30 * 24 * 3600 } } },
        { urlPattern: /\/api\/v2\/study\/sr-stats/, handler: 'NetworkFirst', options: { cacheName: 'sr-stats', expiration: { maxEntries: 10, maxAgeSeconds: 300 } } }
      ]
    }
  })],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('react-markdown') || id.includes('remark-') || id.includes('rehype-') || id.includes('katex')) return 'markdown'
            if (id.includes('jspdf') || id.includes('html2canvas')) return 'pdf'
            if (id.includes('react-router') || id.includes('zustand')) return 'vendor'
            if (id.includes('lucide-react')) return 'icons'
            return 'vendor'
          }
        },
      },
    },
    chunkSizeWarningLimit: 500,
  },
  server: {
    port: 5173,
    // Restrict Host header check to local dev hosts (safer than allowedHosts:true
    // which disables DNS-rebinding protection). For LAN access (phone on same
    // WiFi), pass extra hosts: VITE_ALLOWED_HOSTS=10.89.128.89 npm run dev -- --host 0.0.0.0
    allowedHosts: ['localhost', '127.0.0.1',
      ...(process.env.VITE_ALLOWED_HOSTS || '').split(',').map(s => s.trim()).filter(Boolean)],
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true, // Day 16: proxy WS upgrades so /api/voice/ws-transcribe works in dev
        timeout: 600_000,
        proxyTimeout: 600_000,
        configure: (proxy) => {
          proxy.on('error', (err, _req, res) => {
            if (res && !res.headersSent) {
              res.writeHead(502, { 'Content-Type': 'application/json' })
              res.end(JSON.stringify({ detail: 'Backend unavailable (proxy error)' }))
            }
          })
        },
      },
    },
  },
})
