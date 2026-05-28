/**
 * ResearchHQ Studio — Tailwind config.
 *
 * Design-token source of truth for the frontend dashboard. Components
 * read colours, durations, easings, and shadows from these tokens; the
 * design invariants table in the MVP spec maps 1:1 to the values below.
 */

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Indigo-family brand ramp.
        brand: {
          50:  '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          300: '#a5b4fc',
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          800: '#3730a3',
          900: '#312e81',
        },
        // Layered surface tokens — deeper to lighter.
        surface: {
          950: '#070711',
          900: '#0c0c1a',
          800: '#111120',
          700: '#181828',
          600: '#1e1e30',
          500: '#252538',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      animation: {
        'fade-in':     'fadeIn 0.2s ease-out both',
        'fade-in-up':  'fadeInUp 0.3s cubic-bezier(0.16, 1, 0.3, 1) both',
        'slide-up':    'slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1) both',
        'slide-in':    'slideIn 0.25s cubic-bezier(0.16, 1, 0.3, 1) both',
        'slide-right': 'slideRight 0.25s cubic-bezier(0.16, 1, 0.3, 1) both',
        'pulse-slow':  'pulse 3s cubic-bezier(0.4,0,0.6,1) infinite',
        'spin-slow':   'spin 3s linear infinite',
        'glow':        'glow 2s ease-in-out infinite alternate',
        'shimmer':     'shimmer 1.8s linear infinite',
        'bounce-dots': 'bounceDots 1.2s ease-in-out infinite',
        'scale-in':    'scaleIn 0.2s cubic-bezier(0.16, 1, 0.3, 1) both',
      },
      keyframes: {
        fadeIn:     { from: { opacity: '0' }, to: { opacity: '1' } },
        fadeInUp:   { from: { opacity: '0', transform: 'translateY(16px)' },
                      to:   { opacity: '1', transform: 'translateY(0)' } },
        slideUp:    { from: { opacity: '0', transform: 'translateY(12px)' },
                      to:   { opacity: '1', transform: 'translateY(0)' } },
        slideIn:    { from: { opacity: '0', transform: 'translateX(-12px)' },
                      to:   { opacity: '1', transform: 'translateX(0)' } },
        slideRight: { from: { opacity: '0', transform: 'translateX(12px)' },
                      to:   { opacity: '1', transform: 'translateX(0)' } },
        glow:       { from: { boxShadow: '0 0 20px rgba(99,102,241,0.3)' },
                      to:   { boxShadow: '0 0 50px rgba(99,102,241,0.65)' } },
        shimmer: {
          '0%':   { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(200%)' },
        },
        bounceDots: {
          '0%, 80%, 100%': { transform: 'scale(0.6)', opacity: '0.4' },
          '40%':           { transform: 'scale(1)',   opacity: '1'   },
        },
        scaleIn: { from: { opacity: '0', transform: 'scale(0.94)' },
                   to:   { opacity: '1', transform: 'scale(1)' } },
      },
      boxShadow: {
        'glass':     '0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.06)',
        'glass-sm':  '0 2px 12px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.04)',
        'glass-lg':  '0 24px 64px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.07)',
        'brand':     '0 0 20px rgba(99,102,241,0.4)',
        'brand-lg':  '0 0 40px rgba(99,102,241,0.55)',
        'glow':      '0 0 50px rgba(99,102,241,0.5)',
        'emerald':   '0 0 20px rgba(16,185,129,0.3)',
        'red':       '0 0 20px rgba(239,68,68,0.3)',
        'inset-top': 'inset 0 1px 0 rgba(255,255,255,0.06)',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic':  'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
        // Subtle dot/grid background for the workspace.
        'grid-dark':       'linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px)',
        // Brand identity gradients.
        'brand-gradient':  'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
        'hero-gradient':   'radial-gradient(ellipse 80% 60% at 50% -20%, rgba(99,102,241,0.12) 0%, transparent 60%)',
      },
      backgroundSize: {
        'grid': '40px 40px',
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.5rem',
        '4xl': '2rem',
      },
      transitionTimingFunction: {
        // Used on every page transition + collapsible animation.
        'spring': 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
};
