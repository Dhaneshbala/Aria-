/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        aria: {
          bg: '#131314',
          surface: '#1e1f20',
          border: '#2a2a2a',
          accent: '#7c6af7',
          'accent-light': '#a89bf8',
          text: '#e3e3e3',
          muted: '#9aa0a6',
          green: '#4ade80',
          yellow: '#fbbf24',
          red: '#f87171',
          blue: '#60a5fa',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      }
    }
  },
  plugins: [],
}
