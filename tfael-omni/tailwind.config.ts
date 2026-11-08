import type { Config } from 'tailwindcss'
import tailwindAnimate from 'tailwindcss-animate'

// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Tactical Dark Theme
// Shadcn/ui + Tailwind configuration — air-gap ready
// ═══════════════════════════════════════════════════════════════════════

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      // ── Color System ─────────────────────────────────────────────────
      colors: {
        // Backgrounds — deep tactical layers
        background: {
          DEFAULT: '#0c0a06',
          deep:    '#0c0a06',
          panel:   '#141210',
          card:    '#1a1814',
          hover:   '#22201a',
          surface: '#181610',
          muted:   '#0e0c08',
        },
        // Foreground / text
        foreground: {
          DEFAULT: '#e8e2d4',
          muted:   '#8a8070',
          dim:     '#5c5448',
        },
        // Borders
        border: {
          DEFAULT: '#2a2620',
          dim:     '#1e1c16',
          accent:  '#3a362e',
        },
        // Ring (focus)
        ring: {
          DEFAULT: '#8c9663',
        },
        // Input fields
        input: {
          DEFAULT: '#1e1c16',
          focus:   '#2a2620',
        },
        // Primary — olive drab / tactical green
        primary: {
          DEFAULT:    '#8c9663',
          foreground: '#0c0a06',
          hover:      '#a0ac74',
          muted:      '#5f6744',
        },
        // Secondary — amber / phosphor
        secondary: {
          DEFAULT:    '#f2a93b',
          foreground: '#0c0a06',
          hover:      '#f4b854',
          muted:      '#c48a2e',
        },
        // Destructive — warm red / alarm
        destructive: {
          DEFAULT:    '#d9573d',
          foreground: '#fef2f0',
          hover:      '#e06b54',
          muted:      '#b4452e',
        },
        // Accent colors for domain-specific use
        accent: {
          DEFAULT:    '#22201a',
          foreground: '#e8e2d4',
          olive:      '#93ad57',
          emerald:    '#93ad57',
          amber:      '#f2a93b',
          crimson:    '#d9573d',
          purple:     '#9d82b4',
          steel:      '#6f93a0',
          gold:       '#f2a93b',
          cyan:       '#8c9663',
        },
        // Popover / dropdown
        popover: {
          DEFAULT:    '#181610',
          foreground: '#e8e2d4',
        },
        // Muted surfaces
        muted: {
          DEFAULT:    '#1a1814',
          foreground: '#8a8070',
        },
        // Card
        card: {
          DEFAULT:    '#1a1814',
          foreground: '#e8e2d4',
        },
        // Severity scale (SIEM / alerts)
        severity: {
          critical: '#d9573d',
          high:     '#e87040',
          medium:   '#f2a93b',
          low:      '#93ad57',
          info:     '#6f93a0',
        },
      },

      // ── Typography ───────────────────────────────────────────────────
      fontFamily: {
        sans: ['"Chivo"', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"SFMono-Regular"', 'Consolas', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.875rem' }],  // 10px
      },

      // ── Border Radius (Shadcn convention) ────────────────────────────
      borderRadius: {
        lg: '8px',
        md: '6px',
        sm: '4px',
      },

      // ── Animations (Shadcn/ui) ───────────────────────────────────────
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' },
        },
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-up': {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'pulse-red': {
          '0%, 100%': { transform: 'scale(1)', opacity: '1' },
          '50%': { transform: 'scale(1.35)', opacity: '0.55' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
        'fade-in': 'fade-in 0.18s ease',
        'slide-up': 'slide-up 0.3s ease',
        'pulse-red': 'pulse-red 2s ease-in-out infinite',
      },

      // ── Spacing ──────────────────────────────────────────────────────
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
      },
    },
  },
  plugins: [tailwindAnimate],
} satisfies Config
