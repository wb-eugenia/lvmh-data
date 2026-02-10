import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    build: {
        rollupOptions: {
            output: {
                manualChunks: {
                    react: ['react', 'react-dom'],
                    charts: ['recharts'],
                    motion: ['framer-motion'],
                    icons: ['lucide-react'],
                    confetti: ['canvas-confetti']
                }
            }
        }
    },
    server: {
        port: 3000,
        proxy: {
            '/api': 'http://localhost:8080',
            '/ws': {
                target: 'ws://localhost:8080',
                ws: true
            },
            '/ingest': 'http://localhost:8080'
        }
    }
})
