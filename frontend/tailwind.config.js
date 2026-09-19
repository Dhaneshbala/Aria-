/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Unified with src/index.css :root vars — single dark system.
        // bg #131314 / surface #1e1f20 / variant #2d2e30 (was 3 competing darks).
        aria: {
          bg: '#131314',
          surface: '#1e1f20',
          variant: '#2d2e30',
          border: '#2d2e30',
          'border-light': '#3c4043',
          accent: '#7c6af7',
          'accent-light': '#a89bf8',
          'accent-blue': '#8ab4f8',
          text: '#e3e3e3',
          muted: '#9aa0a6', // fixed from #888 for 4.5:1 contrast on #131314
          green: '#4ade80',
          yellow: '#fbbf24',
          red: '#f87171',
          blue: '#60a5fa',
        }
      },
      fontFamily: {
        sans: ['Inter', 'Google Sans', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        glow: '0 0 20px rgba(138,180,248,0.12), 0 0 40px rgba(124,106,247,0.05)',
        card: '0 1px 6px rgba(0,0,0,0.15)',
        'card-hover': '0 4px 20px rgba(0,0,0,0.25), 0 0 15px rgba(124,106,247,0.08)',
      },
      borderRadius: {
        card: '16px',
        xl2: '24px',
        pill: '28px',
      },
      keyframes: {
        fadeSlideIn: {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to: { opacity: '1', transform: 'none' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-400px 0' },
          '100%': { backgroundPosition: '400px 0' },
        },
      },
      animation: {
        'fade-slide': 'fadeSlideIn 0.25s ease',
        shimmer: 'shimmer 1.4s linear infinite',
      },
    }
  },
  plugins: [],
}
