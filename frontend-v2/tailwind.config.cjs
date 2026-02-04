/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                // Quiet Luxury - "LVMH Navy" Palette
                obsidian: '#0D1A2D',        // Primary background (LVMH Navy)
                surface: '#152238',         // Cards, secondary surfaces
                'surface-light': '#1D2E4A', // Hover states
                champagne: '#D4AF37',       // Active accents, notifications
                'champagne-light': '#F5E0A3', // Gradients, highlights
                ivory: '#FAFAF8',           // Primary text
                mist: '#7A8BA3',            // Secondary text (blue-tinted)
                // Legacy (for compatibility)
                lvmh: {
                    gold: '#D4AF37',
                    black: '#0D1A2D',
                    dark: '#091320',
                    cream: '#F5F5F0',
                    gray: '#7A8BA3',
                },
            },
            fontFamily: {
                serif: ['Cormorant Garamond', 'Georgia', 'serif'],
                sans: ['Inter', 'system-ui', 'sans-serif'],
                mono: ['Roboto Mono', 'monospace'],
            },
            backdropBlur: {
                'luxury': '20px',
            },
            transitionDuration: {
                'luxury': '300ms',
            },
            animation: {
                'fade-in': 'fadeIn 300ms ease-out',
                'slide-up': 'slideUp 300ms ease-out',
                'pulse-subtle': 'pulseSlight 2s ease-in-out infinite',
            },
            keyframes: {
                fadeIn: {
                    '0%': { opacity: '0' },
                    '100%': { opacity: '1' },
                },
                slideUp: {
                    '0%': { opacity: '0', transform: 'translateY(10px)' },
                    '100%': { opacity: '1', transform: 'translateY(0)' },
                },
                pulseSlight: {
                    '0%, 100%': { opacity: '1' },
                    '50%': { opacity: '0.7' },
                },
            },
        },
    },
    plugins: [],
}
