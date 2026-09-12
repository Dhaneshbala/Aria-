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
      icons: [{ src: '/icon-192.png', sizes: '192x192', type: 'image/png' }]
    },
    workbox: {
      runtimeCaching: [
        { urlPattern: /^https:\/\/.*katex.*/, handler: 'CacheFirst', options: { cacheName: 'katex' } },
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
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        timeout: 600_000,
        proxyTimeout: 600_000,
      },
    },
  },
})
