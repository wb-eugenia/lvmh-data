import React, { useEffect, useRef, useState } from 'react'
import { ArrowLeft, Play, RotateCcw, Wifi, WifiOff, LogOut, Send } from 'lucide-react'
import PipelineVisualizer from './PipelineVisualizer'
import { wsUrl, apiFetch } from '../lib/api'
import { useAuth } from '../context/AuthContext'

const DEFAULT_RESULT = {
    meta_analysis: {
        quality_score: 92
    },
    pilier_4_action_business: {
        next_best_action: {
            description: 'Relancer le client sous 48h avec une proposition personnalisee.'
        }
    },
    extraction: {
        tags: ['sac', 'cuir', 'beige', 'cadeau'],
        pilier_1_univers_produit: {
            categories: ['Maroquinerie', 'Sacs a main'],
            matched_products: [
                { name: 'Neverfull MM', category: 'Sacs', match_score: 0.92 },
                { name: 'Speedy 30', category: 'Sacs', match_score: 0.85 }
            ]
        },
        pilier_2_profil_client: {
            purchase_context: { type: 'Cadeau', behavior: 'Decouverte' },
            profession: { sector: 'Cadiration' }
        },
        pilier_3_hospitalite_care: {
            occasion: 'Anniversaire',
            diet: [],
            allergies: []
        },
        pilier_4_action_business: {
            budget_potential: '3k-5k',
            urgency: 'medium',
            lead_temperature: 'warm'
        }
    },
    routing: { tier: 2, score: '65/100', priority: 'MEDIUM', engine: 'Machine Learning' },
    rgpd: { contains_sensitive: false, categories_detected: [] },
    stage_timings_ms: { cleaning: 120, rgpd: 45, routing: 80, tier: 2100, rag: 320, nba: 150 },
    quality_gate_passed: true,
    quality_gate_reason: null
}

const SIMULATION_STEPS = [
    { step: 'cleaning', delayMs: 500, data: { tokens_saved: 15 } },
    { step: 'rgpd', delayMs: 900, data: { contains_sensitive: false, categories_detected: [] } },
    { step: 'routing', delayMs: 1400, data: { tier: 2, score: '65/100', priority: 'MEDIUM', engine: 'Machine Learning' } },
    { step: 'tier2_extraction', delayMs: 2200, data: { tag_count: 4, model: 'Mistral' } },
    { step: 'rag', delayMs: 2800, data: { matches: 2, best_score: 0.92 } },
    { step: 'nba', delayMs: 3400, data: { points: 10, quality_score: '92%' } },
    { step: 'injection', delayMs: 3800, data: { points: 10, quality_score: '92%', feedback: 'Excellente note!' } },
    { step: 'done', delayMs: 4200, data: { quality_gate_passed: true } }
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
    const [inputData, setInputData] = useState(null)
    const [manualText, setManualText] = useState('')
    const [sendingManual, setSendingManual] = useState(false)

    const simulationTimersRef = useRef([])
    const isSimulatingRef = useRef(false)
    const wsRef = useRef(null)

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
        resetToIdle()
        isSimulatingRef.current = true
        setIsProcessing(true)
        setCurrentStep('cleaning')
        setPipelineProgress({ step: 'cleaning', source: 'simulation' })
        setPipelineStartedAt(Date.now())
        setResult(null)
        
        const demoInput = {
            clientName: 'Marie Dupont',
            store: 'Paris Rivoli',
            advisor: 'Sophie L.',
            transcription: 'Bonjour, j\'aimerais offrir un sac pour l\'anniversaire de ma fille. Elle aime les couleurs neutres et le cuir.'
        }
        setInputData(demoInput)

        SIMULATION_STEPS.forEach(({ step, delayMs, data }, index) => {
            const timerId = setTimeout(() => {
                setCurrentStep(step)
                setPipelineProgress((prev) => ({ ...prev, step, ...data }))

                if (step === 'done') {
                    setIsProcessing(false)
                    setResult({
                        ...DEFAULT_RESULT,
                        extraction: {
                            ...DEFAULT_RESULT.extraction,
                            pilier_1_univers_produit: {
                                ...DEFAULT_RESULT.extraction.pilier_1_univers_produit,
                                matched_products: data.matches > 0 ? DEFAULT_RESULT.extraction.pilier_1_univers_produit.matched_products : []
                            }
                        }
                    })
                    setPipelineStartedAt(null)
                    isSimulatingRef.current = false
                }
            }, delayMs)
            simulationTimersRef.current.push(timerId)
        })
    }

    const sendManualNote = async () => {
        if (!manualText.trim() || sendingManual) return
        
        setSendingManual(true)
        try {
            const res = await apiFetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: manualText,
                    language: 'fr'
                })
            })
            
            if (res.ok) {
                const data = await res.json()
                setResult(data)
                setPipelineProgress({ step: 'done', ...data })
                setCurrentStep('done')
                setInputData({
                    clientName: data.client?.name || 'Inconnu',
                    store: data.advisor?.store || 'N/A',
                    advisor: data.advisor?.name || 'N/A',
                    transcription: manualText
                })
            }
        } catch (e) {
            console.error('Error sending note:', e)
        } finally {
            setSendingManual(false)
        }
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
            wsRef.current = ws

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
            <div className="max-w-6xl mx-auto">
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
                            <p className="text-xs text-lvmh-gray uppercase tracking-widest">Traitement temps reel</p>
                        </div>
                    </div>
                </div>

                {/* Input Manuel */}
                <div className="glass p-4 mb-6 rounded-xl border border-white/10">
                    <div className="flex flex-wrap items-center gap-3">
                        <div className="flex-1 min-w-[200px]">
                            <input
                                type="text"
                                value={manualText}
                                onChange={(e) => setManualText(e.target.value)}
                                placeholder="Entrez une note a traiter..."
                                className="w-full bg-white/5 border border-white/10 rounded-lg py-2 px-4 text-sm text-white placeholder:text-lvmh-gray focus:ring-1 focus:ring-lvmh-gold"
                                onKeyDown={(e) => e.key === 'Enter' && sendManualNote()}
                            />
                        </div>
                        <button
                            onClick={sendManualNote}
                            disabled={!manualText.trim() || sendingManual || isProcessing}
                            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-lvmh-gold text-black font-bold text-xs uppercase tracking-widest hover:bg-lvmh-gold/90 transition-colors disabled:opacity-50"
                        >
                            <Send size={14} />
                            {sendingManual ? 'Envoi...' : 'Envoyer'}
                        </button>
                        <div className="h-8 w-[1px] bg-white/20"></div>
                        <div className="flex items-center gap-2">
                            <span className={`text-[10px] px-3 py-2 rounded-full border inline-flex items-center gap-1 ${
                                socketState === 'connected' ? 'border-green-500/40 text-green-400 bg-green-500/10' : 
                                socketState === 'connecting' ? 'border-lvmh-gold/40 text-lvmh-gold bg-lvmh-gold/10' : 
                                'border-red-500/40 text-red-400 bg-red-500/10'
                            }`}>
                                {socketState === 'connected' ? <Wifi size={11} /> : <WifiOff size={11} />}
                                {socketState === 'connected' ? ' Connecte' : ' Deconnecte'}
                            </span>
                        </div>
                        <button
                            onClick={startSimulation}
                            disabled={isProcessing}
                            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-lvmh-gold text-black font-bold text-xs uppercase tracking-widest hover:bg-lvmh-gold/90 transition-colors disabled:opacity-50"
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
                    inputData={inputData}
                />
            </div>
        </div>
    )
}
