import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react-swc'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, process.cwd(), '')
    const backendTarget = env.VITE_BACKEND_PROXY_TARGET || 'http://localhost:8080'

    return {
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
                '/api': backendTarget,
                '/ws': {
                    target: backendTarget.replace(/^http/, 'ws'),
                    ws: true
                },
                '/ingest': backendTarget
            }
        }
    }
})
