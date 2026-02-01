/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                'lvmh-gold': '#D4AF37',
                'lvmh-black': '#000000',
                'lvmh-gray': '#8e8e8e',
            },
            fontFamily: {
                'didot': ['Didot', 'serif'],
            },
        },
    },
    plugins: [],
}
