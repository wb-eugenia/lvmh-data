/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                lvmh: {
                    gold: '#D4AF37',
                    black: '#1A1A1A',
                    dark: '#0F0F0F',
                    cream: '#F5F5F0',
                    gray: '#888888',
                },
                expert: '#FFD700',
                senior: '#C0C0C0',
                junior: '#CD7F32',
            },
            fontFamily: {
                sans: ['Manrope', 'system-ui', 'sans-serif'],
                display: ['"Playfair Display"', 'serif'],
                didot: ['"Playfair Display"', 'serif'],
                mono: ['"JetBrains Mono"', 'monospace'],
            },
        },
    },
    plugins: [],
}
