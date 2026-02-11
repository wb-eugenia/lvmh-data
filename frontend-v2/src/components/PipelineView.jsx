import React, { useEffect, useRef, useState } from 'react'
import { ArrowLeft, Play, RotateCcw, Wifi, WifiOff, LogOut } from 'lucide-react'
import PipelineVisualizer from './PipelineVisualizer'
import { wsUrl } from '../lib/api'
import { useAuth } from '../context/AuthContext'

const DEFAULT_RESULT = {
    meta_analysis: {
        quality_score: 92
    },
    pilier_4_action_business: {
        next_best_action: {
            description: 'Relancer le client sous 48h avec une proposition personnalisee.'
        }
    }
}

const SIMULATION_STEPS = [
    { step: 'cleaning', delayMs: 500 },
    { step: 'routing', delayMs: 1200 },
    { step: 'tier2', delayMs: 2000 },
    { step: 'rag', delayMs: 2800 },
    { step: 'done', delayMs: 3600 }
]

export default function PipelineView({ onBack }) {
    const { logout } = useAuth()
    const [isProcessing, setIsProcessing] = useState(false)
    const [currentStep, setCurrentStep] = useState(null)
    const [result, setResult] = useState(null)
    const [pipelineProgress, setPipelineProgress] = useState(null)
    const [pipelineStartedAt, setPipelineStartedAt] = useState(null)
    const [pipelineElapsedMs, setPipelineElapsedMs] = useState(0)
    const [socketState, setSocketState] = useState('connecting')

    const simulationTimersRef = useRef([])
    const isSimulatingRef = useRef(false)

    const clearSimulationTimers = () => {
        simulationTimersRef.current.forEach((timerId) => clearTimeout(timerId))
        simulationTimersRef.current = []
    }

    const resetToIdle = () => {
        clearSimulationTimers()
        isSimulatingRef.current = false
        setIsProcessing(false)
        setCurrentStep(null)
        setResult(null)
        setPipelineProgress(null)
        setPipelineStartedAt(null)
    }

    const startSimulation = () => {
        clearSimulationTimers()
        isSimulatingRef.current = true
        setIsProcessing(true)
        setCurrentStep('cleaning')
        setPipelineProgress({ step: 'cleaning', source: 'simulation' })
        setPipelineStartedAt(Date.now())
        setResult(null)

        SIMULATION_STEPS.forEach(({ step, delayMs }) => {
            const timerId = setTimeout(() => {
                setCurrentStep(step)
                setPipelineProgress({ step, source: 'simulation' })

                if (step === 'done') {
                    setIsProcessing(false)
                    setResult(DEFAULT_RESULT)
                    setPipelineStartedAt(null)
                    isSimulatingRef.current = false
                }
            }, delayMs)
            simulationTimersRef.current.push(timerId)
        })
    }

    useEffect(() => {
        if (!isProcessing || !pipelineStartedAt) {
            setPipelineElapsedMs(0)
            return
        }

        const timer = setInterval(() => {
            setPipelineElapsedMs(Date.now() - pipelineStartedAt)
        }, 200)

        return () => clearInterval(timer)
    }, [isProcessing, pipelineStartedAt])

    useEffect(() => {
        const socketUrl = wsUrl('/ws/pipeline')
        let ws
        let reconnectTimer
        let isActive = true
        let shouldReconnect = true

        const connect = () => {
            ws = new WebSocket(socketUrl)

            ws.onopen = () => {
                if (!isActive) return
                setSocketState('connected')
            }

            ws.onmessage = (event) => {
                if (!isActive || isSimulatingRef.current) return

                try {
                    const data = JSON.parse(event.data)
                    if (!data?.step) return

                    setCurrentStep(data.step)
                    setPipelineProgress(data)

                    if (data.step === 'done') {
                        setIsProcessing(false)
                        setResult(data.result || null)
                        setPipelineStartedAt(null)
                    } else {
                        setPipelineStartedAt((previous) => previous || Date.now())
                        setIsProcessing(true)
                        setResult(null)
                    }
                } catch (error) {
                    console.error('Invalid WS payload:', error)
                }
            }

            ws.onerror = () => {
                if (!isActive) return
                setSocketState('disconnected')
            }

            ws.onclose = () => {
                if (!isActive) return
                setSocketState('disconnected')
                if (shouldReconnect) {
                    setSocketState('connecting')
                    reconnectTimer = setTimeout(connect, 3000)
                }
            }
        }

        connect()

        return () => {
            isActive = false
            shouldReconnect = false
            if (reconnectTimer) clearTimeout(reconnectTimer)
            clearSimulationTimers()
            ws?.close()
        }
    }, [])

    const handleLogout = () => {
        logout()
        if (onBack) onBack()
        else window.location.assign('/login')
    }

    return (
        <div className="min-h-screen bg-lvmh-black text-white p-6">
            <div className="max-w-3xl mx-auto">
                <div className="flex items-center justify-between gap-4 mb-8">
                    <button
                        onClick={() => (onBack ? onBack() : window.history.back())}
                        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-white/10 hover:border-lvmh-gold/40 hover:text-lvmh-gold transition-colors"
                    >
                        <ArrowLeft size={16} />
                        Retour
                    </button>

                    <div className="flex items-center gap-3">
                        <button
                            onClick={handleLogout}
                            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-red-500/40 text-red-300 text-xs uppercase tracking-widest hover:bg-red-500/10 transition-colors"
                        >
                            <LogOut size={12} />
                            Deconnexion
                        </button>
                        <div className="text-right">
                            <h1 className="text-2xl font-display font-bold gold-text">Pipeline Monitor</h1>
                            <p className="text-xs text-lvmh-gray uppercase tracking-widest">Route /pipeline</p>
                        </div>
                    </div>
                </div>

                <div className="glass p-4 mb-6 flex flex-wrap items-center justify-between gap-3">
                    <div className="inline-flex items-center gap-2 text-sm">
                        {socketState === 'connected' ? (
                            <>
                                <Wifi size={16} className="text-green-500" />
                                <span className="text-green-400">WebSocket connecte</span>
                            </>
                        ) : (
                            <>
                                <WifiOff size={16} className="text-red-500" />
                                <span className="text-red-400">WebSocket deconnecte</span>
                            </>
                        )}
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={startSimulation}
                            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-lvmh-gold text-black font-bold text-xs uppercase tracking-widest hover:bg-lvmh-gold/90 transition-colors"
                        >
                            <Play size={14} />
                            Simuler
                        </button>
                        <button
                            onClick={resetToIdle}
                            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-white/10 text-white text-xs uppercase tracking-widest hover:border-white/30 transition-colors"
                        >
                            <RotateCcw size={14} />
                            Reset
                        </button>
                    </div>
                </div>

                <PipelineVisualizer
                    isProcessing={isProcessing}
                    currentStep={currentStep}
                    result={result}
                    progress={pipelineProgress}
                    connectionState={socketState}
                    elapsedMs={pipelineElapsedMs}
                />
            </div>
        </div>
    )
}
