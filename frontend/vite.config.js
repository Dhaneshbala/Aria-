import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import { visualizer } from 'rollup-plugin-visualizer'
import viteCompression from 'vite-plugin-compression'

export default defineConfig({
  plugins: [react(), VitePWA({
    registerType: 'autoUpdate',
    includeAssets: ['favicon.ico'],
    manifest: {
      name: 'ARIA - AI Study Assistant',
      short_name: 'ARIA',
      id: '/',
      description: 'Your offline-friendly AI study companion',
      lang: 'en',
      dir: 'ltr',
      theme_color: '#7c6af7',
      background_color: '#0f0f0f',
      display: 'standalone',
      orientation: 'any',
      categories: ['education', 'productivity'],
      icons: [
        { src: '/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
        { src: '/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
        { src: '/icon-512-maskable.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
      ],
      shortcuts: [
        { name: 'Chat with ARIA', url: '/chat', icons: [{ src: '/icon-192.png', sizes: '192x192' }] },
        { name: 'Review flashcards', url: '/spaced', icons: [{ src: '/icon-192.png', sizes: '192x192' }] },
        { name: 'Voice tutor', url: '/voice', icons: [{ src: '/icon-192.png', sizes: '192x192' }] },
      ],
    },
    workbox: {
      navigateFallback: '/index.html',
      navigateFallbackDenylist: [/^\/api\//],
      // Precache KaTeX WOFF2 fonts + webfonts so maths renders fully offline
      globPatterns: ['**/*.{js,css,html,ico,png,svg,woff,woff2}'],
      maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
      runtimeCaching: [
        // KaTeX CSS/fonts now ship in the build (offline-safe) — no CDN rule needed
        { urlPattern: /\/api\/v2\/study\/sr-stats/, handler: 'NetworkFirst', options: { cacheName: 'sr-stats', expiration: { maxEntries: 10, maxAgeSeconds: 300 } } }
      ]
    }
  }),
  // Bundle treemap: ANALYZE=1 npm run build → dist/stats.html
  process.env.ANALYZE && visualizer({ filename: 'dist/stats.html', gzipSize: true, brotliSize: true }),
  // Precompressed .gz/.br for servers that serve them (Caddy: encode gzip zstd)
  viteCompression({ threshold: 10240 }),
  viteCompression({ threshold: 10240, algorithm: 'brotliCompress', ext: '.br' }),
  ].filter(Boolean),
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            // markdown libs share the react runtime — keep them in vendor
            // to avoid markdown->vendor->markdown circular chunks
            if (id.includes('jspdf') || id.includes('html2canvas')) return 'pdf'
            if (id.includes('lucide-react')) return 'icons'
            if (id.includes('react-markdown') || id.includes('remark-') || id.includes('rehype-') || id.includes('katex')) return 'markdown'
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
