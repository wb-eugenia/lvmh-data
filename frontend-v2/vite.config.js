import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    server: {
        port: 3000,
        proxy: {
            '/api': 'http://localhost:8001',
            '/ws': {
                target: 'ws://localhost:8001',
                ws: true
            },
            '/ingest': 'http://localhost:8001'
        }
    }
})
