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
                    manualChunks(id) {
                        if (!id.includes('node_modules')) return undefined

                        if (
                            id.includes('node_modules/react')
                            || id.includes('node_modules/scheduler')
                            || id.includes('node_modules/prop-types')
                        ) {
                            return 'vendor-react'
                        }
                        if (id.includes('node_modules/recharts') || id.includes('node_modules/victory-vendor')) {
                            return 'vendor-recharts'
                        }
                        if (id.includes('node_modules/d3-')) {
                            return 'vendor-d3'
                        }
                        if (id.includes('node_modules/framer-motion') || id.includes('node_modules/motion-dom')) {
                            return 'vendor-motion'
                        }
                        if (id.includes('node_modules/lucide-react')) {
                            return 'vendor-icons'
                        }
                        if (id.includes('node_modules/canvas-confetti')) {
                            return 'vendor-confetti'
                        }

                        return undefined
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
