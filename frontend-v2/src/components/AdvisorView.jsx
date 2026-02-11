import React, { useState, useEffect } from 'react'
import { ArrowLeft, Mic, Search, Trophy, X, CheckCircle, Menu, LogOut, History, FileText, ShoppingBag, Lightbulb } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { apiFetch, wsUrl } from '../lib/api'
import confetti from 'canvas-confetti'
import PipelineVisualizer from './PipelineVisualizer'

export default function AdvisorView({ onBack }) {
    const { user, logout, updateUser } = useAuth()
    const [isRecording, setIsRecording] = useState(false)
    const [currentResult, setCurrentResult] = useState(null)
    const [leaderboard, setLeaderboard] = useState([])
    const [searchQuery, setSearchQuery] = useState("")
    const [isMenuOpen, setIsMenuOpen] = useState(false)
    const [activeView, setActiveView] = useState("record") // 'record', 'history', 'search', 'csv'
    const [clientResults, setClientResults] = useState([])
    const [searchingClients, setSearchingClients] = useState(false)

    const [isProcessing, setIsProcessing] = useState(false)
    const [currentStep, setCurrentStep] = useState(null)
    const [history, setHistory] = useState([])
    const [loadingHistory, setLoadingHistory] = useState(false)

    // CSV Results State
    const [csvFiles, setCsvFiles] = useState([])
    const [csvData, setCsvData] = useState([])
    const [selectedCsv, setSelectedCsv] = useState('')
    const [loadingCsv, setLoadingCsv] = useState(false)
    const [csvTotal, setCsvTotal] = useState(0)

    const formatPercent = (value) => {
        if (value === null || value === undefined || Number.isNaN(value)) return '—'
        const normalized = value <= 1 ? value * 100 : value
        return `${Math.round(normalized)}%`
    }

    const formatCurrency = (value) => {
        if (value === null || value === undefined || Number.isNaN(value)) return '—'
        try {
            return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(value)
        } catch {
            return `${value}€`
        }
    }

    const normalizeScore = (value) => {
        if (value === null || value === undefined || Number.isNaN(value)) return 0
        return value <= 1 ? value * 100 : value
    }

    const resultId = currentResult?.ID || currentResult?.id || 'Client'
    const resultRouting = currentResult?.routing || {}
    const resultRgpd = currentResult?.rgpd || {}
    const resultMeta = currentResult?.meta_analysis || {}
    const resultP1 = currentResult?.pilier_1_univers_produit || {}
    const resultP2 = currentResult?.pilier_2_profil_client || {}
    const resultP3 = currentResult?.pilier_3_hospitalite_care || {}
    const resultP4 = currentResult?.pilier_4_action_business || {}
    const resultTags = currentResult?.tags || []
    const resultAllergies = [
        ...(resultP3?.allergies?.food || []),
        ...(resultP3?.allergies?.contact || [])
    ]
    const vipStatus = currentResult?.extraction?.vip_status || resultP2?.purchase_context?.behavior

    // WebSocket for real-time pipeline visualization
    useEffect(() => {
        const socketUrl = wsUrl('/ws/pipeline')
        let ws;

        const connect = () => {
            ws = new WebSocket(socketUrl);
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'leaderboard') {
                    // Update leaderboard with 'isMe' flag
                    const enriched = data.data.map(adv => ({
                        ...adv,
                        isMe: adv.id === user.name
                    }));
                    setLeaderboard(enriched);
                } else if (data.step) {
                    console.log("WS Pipeline Step:", data.step);
                    setCurrentStep(data.step);
                }
            };
            ws.onclose = () => {
                setTimeout(connect, 3000); // Reconnect
            };
        };

        connect();
        return () => ws?.close();
    }, []);

    useEffect(() => {
        fetchLeaderboard()
    }, [user])

    const fetchLeaderboard = async () => {
        try {
            const realData = [
                { id: user.name, score: user.points || user.score || 0, isMe: true }
            ]
            setLeaderboard(realData)
        } catch (e) { }
    }

    // Fetch history when view changes to history
    useEffect(() => {
        if (activeView === 'history') {
            loadHistory()
        }
        if (activeView === 'csv') {
            loadCsvFiles()
        }
    }, [activeView])

    const loadCsvFiles = async () => {
        setLoadingCsv(true)
        try {
            const res = await apiFetch('/api/batch-results')
            if (res.ok) {
                const data = await res.json()
                setCsvFiles(data.files || [])
                if (data.files?.length > 0 && !selectedCsv) {
                    setSelectedCsv(data.files[0])
                    loadCsvData(data.files[0])
                }
            }
        } catch (e) {
            console.error(e)
        } finally {
            setLoadingCsv(false)
        }
    }

    const loadCsvData = async (filename) => {
        if (!filename) return
        setLoadingCsv(true)
        try {
            const res = await apiFetch(`/api/batch-results?file=${encodeURIComponent(filename)}`)
            if (res.ok) {
                const data = await res.json()
                setCsvData(data.data || [])
                setCsvTotal(data.total || 0)
            }
        } catch (e) {
            console.error(e)
        } finally {
            setLoadingCsv(false)
        }
    }

    const handleCsvSelect = (e) => {
        const file = e.target.value
        setSelectedCsv(file)
        loadCsvData(file)
    }

    const loadHistory = async () => {
        setLoadingHistory(true)
        try {
            const token = localStorage.getItem('token')
            const res = await apiFetch('/api/history', {
                headers: { 'Authorization': `Bearer ${token}` }
            })
            if (res.ok) {
                const data = await res.json()
                setHistory(data)
            }
        } catch (e) {
            console.error(e)
        } finally {
            setLoadingHistory(false)
        }
    }

    const handleMenuNavigation = (view) => {
        setActiveView(view)
        setIsMenuOpen(false)
        if (view === 'search') {
            setSearchQuery("")
            setClientResults([])
        }
    }

    const handleViewDetail = (note) => {
        // We might need to fetch full JSON if not in history
        if (note.analysis_json) {
            setCurrentResult(JSON.parse(note.analysis_json))
        } else {
            // If it's the history list, we can fetch detail
            fetchNoteDetail(note.id)
        }
    }

    const fetchNoteDetail = async (id) => {
        setIsProcessing(true)
        try {
            const res = await apiFetch(`/api/results/${id}`)
            if (res.ok) {
                const data = await res.json()
                setCurrentResult(data)
            }
        } catch (e) { console.error(e) }
        finally { setIsProcessing(false) }
    }

    const searchClients = async (query) => {
        if (!query) {
            setClientResults([])
            return
        }
        setSearchingClients(true)
        try {
            const res = await apiFetch(`/api/clients/search?q=${query}`)
            if (res.ok) {
                const data = await res.json()
                setClientResults(data)
            }
        } catch (e) { console.error(e) }
        finally { setSearchingClients(false) }
    }

    useEffect(() => {
        const timer = setTimeout(() => {
            if (activeView === 'search') {
                searchClients(searchQuery)
            }
        }, 300)
        return () => clearTimeout(timer)
    }, [searchQuery, activeView])

    const handleLogout = () => {
        logout()
        onBack() // Redirects to landing/login
    }

    const [mediaRecorder, setMediaRecorder] = useState(null)
    const [audioChunks, setAudioChunks] = useState([])

    const toggleRecord = async () => {
        if (!isRecording) {
            // Start Recording
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
                const recorder = new MediaRecorder(stream)
                let chunks = []

                recorder.ondataavailable = (e) => chunks.push(e.data)
                recorder.onstop = async () => {
                    setIsProcessing(true) // Start loading
                    // Use webm which is standard for MediaRecorder in Chrome/Firefox
                    const blob = new Blob(chunks, { type: 'audio/webm' })
                    await processAudio(blob)
                    setIsProcessing(false) // Stop loading
                }

                recorder.start()
                setMediaRecorder(recorder)
                setIsRecording(true)
            } catch (err) {
                alert("Microphone accès refusé")
            }
        } else {
            // Stop Recording
            mediaRecorder.stop()
            setIsRecording(false)
        }
    }

    const processAudio = async (audioBlob) => {
        // ... (processAudio code remains similar but we handle errors inside)
        // 1. Transcribe (Whisper)
        const formData = new FormData()
        // OpenAI requires a filename with extension to detect format
        formData.append('file', audioBlob, 'recording.webm')

        try {
            const transRes = await apiFetch('/api/transcribe', {
                method: 'POST',
                body: formData // No headers for multipart
            })
            if (!transRes.ok) throw new Error("Transcription failed")

            const { transcription } = await transRes.json()

            // 2. Intelligence Pipeline
            // Get token from auth context/local storage if needed for Auth header
            const token = localStorage.getItem('token')
            const res = await apiFetch('/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    text: transcription,
                    language: 'FR',
                    advisor_id: user.id || 1,
                    store_id: user.store || "PARIS_HQ"
                })
            })
            if (!res.ok) throw new Error("Analysis failed")

            const data = await res.json()
            setCurrentResult(data)

            // Refresh leaderboard to update score locally (optimistic or re-fetch)
            const qualityScore = normalizeScore(data.meta_analysis?.quality_score || 0)
            const newScore = (user.points || user.score || 0) + (qualityScore >= 80 ? 15 : 10)
            updateUser({ score: newScore, points: newScore })
            // fetchLeaderboard will run via useEffect dependency on `user`

            if (qualityScore >= 80) {
                confetti({
                    particleCount: 150,
                    spread: 70,
                    origin: { y: 0.6 },
                    colors: ['#D4AF37', '#ffffff']
                })
            }
        } catch (e) {
            alert("Erreur système : " + e.message)
        } finally {
            setIsProcessing(false)
        }
    }

    return (
        <div className="max-w-md mx-auto min-h-screen flex flex-col p-6 bg-lvmh-black text-white relative overflow-hidden">
            {/* Loading Overlay */}
            {isProcessing && !isRecording && !currentResult && (
                <div className="absolute inset-x-6 top-24 z-50 flex flex-col items-center justify-center animate-in fade-in duration-500">
                    <div className="w-12 h-12 border-4 border-lvmh-gold border-t-transparent rounded-full animate-spin mb-4" />
                    <div className="text-lvmh-gold font-bold tracking-widest uppercase text-[10px] animate-pulse">Intelligence Flow...</div>
                </div>
            )}

            {/* Menu Drawer */}
            {isMenuOpen && (
                <div className="absolute inset-0 z-40 flex">
                    {/* Backdrop */}
                    <div className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-in fade-in" onClick={() => setIsMenuOpen(false)}></div>

                    {/* Drawer Content */}
                    <div className="relative w-3/4 max-w-sm bg-[#1a1a1a] shadow-2xl h-full p-6 animate-in slide-in-from-left duration-300 border-r border-white/10 flex flex-col">
                        <div className="mb-8 pt-4">
                            <h2 className="text-2xl font-didot text-lvmh-gold mb-1">LVMH</h2>
                            <p className="text-xs text-gray-400 uppercase tracking-widest">Assistant Vendeur</p>
                        </div>

                        <div className="flex items-center gap-4 mb-8 p-4 glass rounded-xl">
                            <div className="w-12 h-12 rounded-full bg-lvmh-gold flex items-center justify-center text-black font-bold text-xl">
                                {user.name.charAt(0)}
                            </div>
                            <div>
                                <div className="font-bold">{user.name}</div>
                                <div className="text-xs text-lvmh-gold">{user.store || "Boutique Paris"}</div>
                            </div>
                        </div>

                        <nav className="space-y-2 flex-1">
                            <button onClick={() => handleMenuNavigation('record')} className={`w-full flex items-center gap-4 p-4 rounded-xl transition-colors text-left ${activeView === 'record' ? 'bg-lvmh-gold/20 text-lvmh-gold' : 'hover:bg-white/5'}`}>
                                <Mic size={20} className={activeView === 'record' ? 'text-lvmh-gold' : ''} />
                                <span>Nouvelle Dictée</span>
                            </button>
                            <button onClick={() => handleMenuNavigation('history')} className={`w-full flex items-center gap-4 p-4 rounded-xl transition-colors text-left ${activeView === 'history' ? 'bg-lvmh-gold/20 text-lvmh-gold' : 'hover:bg-white/5'}`}>
                                <History size={20} className={activeView === 'history' ? 'text-lvmh-gold' : ''} />
                                <span>Mes Enregistrements</span>
                            </button>
                            <button onClick={() => handleMenuNavigation('search')} className={`w-full flex items-center gap-4 p-4 rounded-xl transition-colors text-left ${activeView === 'search' ? 'bg-lvmh-gold/20 text-lvmh-gold' : 'hover:bg-white/5'}`}>
                                <Search size={20} className={activeView === 'search' ? 'text-lvmh-gold' : ''} />
                                <span>Rechercher</span>
                            </button>
                            <button onClick={() => handleMenuNavigation('csv')} className={`w-full flex items-center gap-4 p-4 rounded-xl transition-colors text-left ${activeView === 'csv' ? 'bg-lvmh-gold/20 text-lvmh-gold' : 'hover:bg-white/5'}`}>
                                <FileText size={20} className={activeView === 'csv' ? 'text-lvmh-gold' : ''} />
                                <span>Résultats CSV</span>
                            </button>
                        </nav>

                        <button onClick={handleLogout} className="w-full flex items-center gap-4 p-4 hover:bg-red-500/10 text-red-400 rounded-xl transition-colors text-left mt-auto">
                            <LogOut size={20} />
                            <span>Déconnexion</span>
                        </button>
                    </div>
                </div>
            )}

            <div className="flex justify-between items-center mb-6 relative z-10">
                <button onClick={() => setIsMenuOpen(true)} className="p-2 -ml-2 hover:text-lvmh-gold transition-colors">
                    <Menu size={24} />
                    {/* Notification dot example */}
                    {/* <span className="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full"></span> */}
                </button>
                <div className="text-center">
                    <div className="text-[10px] text-lvmh-gold uppercase tracking-tighter">{user.store || "LVMH Paris Rivoli"}</div>
                    <div className="font-bold text-sm">{user.name}</div>
                </div>
                <div className="glass px-3 py-1 text-sm font-bold text-lvmh-gold">{user.points || user.score || 0} pts</div>
            </div>

            {/* VIEWS */}

            {/* RECORD VIEW */}
            {activeView === 'record' && (
                <>
                    <div className="relative mb-6">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-lvmh-gray" size={18} />
                        <input
                            type="text"
                            placeholder="Rechercher un client..."
                            className="w-full bg-white/5 border-none rounded-xl py-4 pl-12 pr-4 text-white focus:ring-1 focus:ring-lvmh-gold transition-all"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>

                    <div className="mb-6">
                        <PipelineVisualizer
                            isProcessing={isProcessing}
                            currentStep={currentStep}
                            result={currentResult}
                        />
                    </div>

                    {!currentResult ? (
                        <div className="flex-1 flex flex-col items-center justify-center text-center">
                            <h2 className="gold-text text-4xl font-bold mb-4 tracking-tighter">
                                {isRecording ? "Capture Live..." : "Insight Client"}
                            </h2>
                            <p className="text-lvmh-gray text-xs uppercase tracking-[0.2em] mb-12">
                                {isRecording ? "Le moteur Whisper vous écoute" : "Appuyez pour commencer"}
                            </p>

                            <div className="relative mb-16">
                                {isRecording && (
                                    <div className="absolute inset-0 rounded-full bg-red-500/20 animate-ping" />
                                )}
                                <button
                                    onClick={toggleRecord}
                                    className={`relative z-10 w-24 h-24 rounded-full flex items-center justify-center transition-all duration-300 shadow-[0_0_50px_rgba(0,0,0,0.5)] border-2 ${isRecording ? 'bg-red-500 border-red-400 scale-110' : 'bg-white border-white/20 hover:scale-105'}`}
                                >
                                    <Mic size={40} className={isRecording ? "text-white animate-pulse" : "text-black"} />
                                </button>

                                {isRecording && (
                                    <div className="absolute -bottom-10 left-1/2 -translate-x-1/2 text-red-500 font-mono text-xs font-bold flex items-center gap-2">
                                        <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                                        LIVE RECORDING
                                    </div>
                                )}
                            </div>

                            <div className="glass w-full p-5">
                                <div className="flex items-center gap-2 text-lvmh-gold text-xs font-bold uppercase mb-4 tracking-widest leading-none">
                                    <Trophy size={14} /> Leaderboard Live
                                </div>
                                <div className="space-y-3">
                                    {leaderboard.length > 0 ? leaderboard.map((adv, i) => (
                                        <div key={i} className={`flex justify-between py-2 border-b border-white/5 last:border-0 items-center ${adv.isMe ? 'bg-white/5 -mx-2 px-2 rounded' : ''}`}>
                                            <span className="text-sm font-medium flex items-center gap-2">
                                                {i + 1}. {adv.id} {adv.isMe && <span className="text-[10px] bg-lvmh-gold text-black px-1 rounded font-bold">MOI</span>}
                                            </span>
                                            <span className="font-bold text-sm text-lvmh-gold">{adv.score} pts</span>
                                        </div>
                                    )) : (
                                        <div className="text-center text-xs text-lvmh-gray py-4">Aucune donnée</div>
                                    )}
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="fixed inset-0 bg-lvmh-black z-50 p-6 overflow-y-auto animate-in slide-in-from-bottom duration-500">
                            <div className="flex flex-wrap justify-between items-start gap-4 mb-8">
                                <div>
                                    <h2 className="gold-text text-3xl font-display font-black">Expertise IA</h2>
                                    <p className="text-sm text-lvmh-gray">Synthèse client et recommandations</p>
                                </div>
                                <button onClick={() => setCurrentResult(null)} className="p-2"><X size={32} /></button>
                            </div>

                            <div className="glass p-5 border-l-4 border-lvmh-gold mb-8 bg-lvmh-gold/5">
                                <div className="data-label">Récompense</div>
                                <div className="text-lg font-bold leading-tight">{resultMeta?.advisor_feedback || "Note traitée !"}</div>
                            </div>

                            <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_0.8fr] gap-6">
                                <div className="glass p-6 border-l-4 border-lvmh-gold">
                                    <div className="flex flex-wrap items-start justify-between gap-4">
                                        <div>
                                            <div className="data-label">Client</div>
                                            <div className="text-2xl font-display gold-text">{resultId}</div>
                                            <div className="mt-2 flex flex-wrap gap-2">
                                                {vipStatus && (
                                                    <span className="text-[10px] px-2 py-1 rounded-full bg-lvmh-gold/20 text-lvmh-gold">
                                                        {String(vipStatus).toUpperCase()}
                                                    </span>
                                                )}
                                                <span className="text-[10px] px-2 py-1 rounded-full bg-white/10 text-lvmh-gray">
                                                    Tier {resultRouting.tier || '—'}
                                                </span>
                                                <span className="text-[10px] px-2 py-1 rounded-full bg-white/10 text-lvmh-gray">
                                                    Confiance {formatPercent(resultRouting.confidence ?? currentResult?.confidence)}
                                                </span>
                                                {currentResult?.cache_hit && (
                                                    <span className="text-[10px] px-2 py-1 rounded-full bg-green-500/20 text-green-300">
                                                        Cache
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                        <div className="text-right">
                                            <div className="data-label">Modèle</div>
                                            <div className="text-sm font-semibold">{currentResult?.model_used || '—'}</div>
                                            <div className="text-xs text-lvmh-gray">Traitement {Math.round(currentResult?.processing_time_ms || 0)}ms</div>
                                        </div>
                                    </div>

                                    <div className="mt-6">
                                        <div className="data-label">Transcription</div>
                                        <div className="bg-white/5 p-4 rounded-lg text-sm leading-relaxed">
                                            "{currentResult?.processed_text || currentResult?.original_text || "..."}"
                                        </div>
                                    </div>

                                    <div className="mt-6">
                                        <div className="data-label">Tags</div>
                                        <div className="flex flex-wrap gap-2 mt-2">
                                            {resultTags.length ? (
                                                <>
                                                    {resultTags.slice(0, 12).map((tag, i) => (
                                                        <span key={i} className="text-xs bg-lvmh-gold/15 text-lvmh-gold px-2 py-1 rounded-full">
                                                            {tag}
                                                        </span>
                                                    ))}
                                                    {resultTags.length > 12 && (
                                                        <span className="text-xs text-lvmh-gray">+{resultTags.length - 12}</span>
                                                    )}
                                                </>
                                            ) : (
                                                <span className="text-xs text-lvmh-gray">Aucun tag</span>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                <div className="space-y-4">
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="glass p-4">
                                            <div className="data-label">Qualité</div>
                                            <div className="text-xl font-semibold">{formatPercent(resultMeta?.quality_score)}</div>
                                            <div className="text-xs text-lvmh-gray">
                                                Confiance {formatPercent(resultRouting.confidence ?? currentResult?.confidence)}
                                            </div>
                                        </div>
                                        <div className="glass p-4">
                                            <div className="data-label">Budget</div>
                                            <div className="text-lg font-semibold">{resultP4?.budget_potential || 'N/A'}</div>
                                            <div className="text-xs text-lvmh-gray">
                                                {resultP4?.budget_specific ? formatCurrency(resultP4.budget_specific) : 'Budget spécifique N/A'}
                                            </div>
                                        </div>
                                        <div className="glass p-4">
                                            <div className="data-label">RGPD</div>
                                            <div className={`text-sm font-semibold ${resultRgpd?.contains_sensitive ? 'text-red-400' : 'text-green-400'}`}>
                                                {resultRgpd?.contains_sensitive ? 'Sensibles détectées' : 'Conforme'}
                                            </div>
                                            <div className="text-xs text-lvmh-gray">
                                                {resultRgpd?.categories_detected?.length ? resultRgpd.categories_detected.join(', ') : 'Aucune catégorie'}
                                            </div>
                                        </div>
                                        <div className="glass p-4">
                                            <div className="data-label">Traitement</div>
                                            <div className="text-lg font-semibold">{Math.round(currentResult?.processing_time_ms || 0)}ms</div>
                                            <div className="text-xs text-lvmh-gray">
                                                {currentResult?.model_used || 'Modèle inconnu'}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
                                <div className="glass p-6">
                                    <h4 className="text-lg font-display font-bold mb-4">Pilier 1 - Univers Produit</h4>
                                    <div className="space-y-3 text-sm">
                                        <div>
                                            <div className="data-label">Catégories</div>
                                            <div className="mt-2 flex flex-wrap gap-2">
                                                {(resultP1.categories || []).length ? resultP1.categories.map((cat, i) => (
                                                    <span key={i} className="text-xs bg-white/10 px-2 py-1 rounded">{cat}</span>
                                                )) : <span className="text-xs text-lvmh-gray">N/A</span>}
                                            </div>
                                        </div>
                                        <div>
                                            <div className="data-label">Produits mentionnés</div>
                                            <div className="mt-2 text-sm text-lvmh-gray">{(resultP1.produits_mentionnes || []).join(', ') || 'N/A'}</div>
                                        </div>
                                        <div className="grid grid-cols-2 gap-4">
                                            <div>
                                                <div className="data-label">Couleurs</div>
                                                <div className="text-sm text-lvmh-gray">{(resultP1.preferences?.colors || []).join(', ') || 'N/A'}</div>
                                            </div>
                                            <div>
                                                <div className="data-label">Matières</div>
                                                <div className="text-sm text-lvmh-gray">{(resultP1.preferences?.materials || []).join(', ') || 'N/A'}</div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div className="glass p-6">
                                    <h4 className="text-lg font-display font-bold mb-4">Pilier 2 - Profil Client</h4>
                                    <div className="space-y-3 text-sm">
                                        <div className="grid grid-cols-2 gap-4">
                                            <div>
                                                <div className="data-label">Type d'achat</div>
                                                <div className="text-sm text-lvmh-gray">{resultP2?.purchase_context?.type || 'N/A'}</div>
                                            </div>
                                            <div>
                                                <div className="data-label">Comportement</div>
                                                <div className="text-sm text-lvmh-gray">{resultP2?.purchase_context?.behavior || 'N/A'}</div>
                                            </div>
                                        </div>
                                        <div>
                                            <div className="data-label">Profession</div>
                                            <div className="text-sm text-lvmh-gray">{resultP2?.profession?.sector || resultP2?.profession?.status || 'N/A'}</div>
                                        </div>
                                        <div>
                                            <div className="data-label">Lifestyle</div>
                                            <div className="text-sm text-lvmh-gray">{resultP2?.lifestyle?.family || 'N/A'}</div>
                                        </div>
                                    </div>
                                </div>

                                <div className="glass p-6">
                                    <h4 className="text-lg font-display font-bold mb-4">Pilier 3 - Hospitalité & Care</h4>
                                    <div className="space-y-3 text-sm">
                                        <div>
                                            <div className="data-label">Allergies</div>
                                            <div className={`text-sm ${resultAllergies.length ? 'text-red-400' : 'text-green-400'}`}>
                                                {resultAllergies.length ? resultAllergies.join(', ') : 'Aucune détectée'}
                                            </div>
                                        </div>
                                        <div>
                                            <div className="data-label">Régime</div>
                                            <div className="text-sm text-lvmh-gray">{(resultP3?.diet || []).join(', ') || 'N/A'}</div>
                                        </div>
                                        <div>
                                            <div className="data-label">Occasion</div>
                                            <div className="text-sm text-lvmh-gray">{resultP3?.occasion || 'N/A'}</div>
                                        </div>
                                    </div>
                                </div>

                                <div className="glass p-6">
                                    <h4 className="text-lg font-display font-bold mb-4">Pilier 4 - Action Business</h4>
                                    <div className="space-y-3 text-sm">
                                        <div>
                                            <div className="data-label">Budget</div>
                                            <div className="text-sm text-lvmh-gray">{resultP4?.budget_potential || 'N/A'}</div>
                                        </div>
                                        <div>
                                            <div className="data-label">Urgence</div>
                                            <div className="text-sm text-lvmh-gray">{resultP4?.urgency || 'N/A'}</div>
                                        </div>
                                        <div>
                                            <div className="data-label">Température du lead</div>
                                            <div className="text-sm text-lvmh-gray">{resultP4?.lead_temperature || 'N/A'}</div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {resultP1?.matched_products?.length > 0 && (
                                <div className="glass p-6 mt-6">
                                    <div className="flex items-center gap-2 mb-4">
                                        <ShoppingBag size={20} className="text-lvmh-gold" />
                                        <h4 className="font-display font-bold">Produits recommandés (RAG)</h4>
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                        {resultP1.matched_products.map((product, i) => (
                                            <div key={i} className="bg-white/5 p-4 rounded-lg border border-white/10">
                                                <div className="font-bold text-lvmh-gold mb-1">{product.name || product.ID}</div>
                                                <div className="text-xs text-lvmh-gray uppercase">{product.category || 'Catégorie'}</div>
                                                {product.description && (
                                                    <div className="text-xs text-lvmh-gray mt-2 line-clamp-2">{product.description}</div>
                                                )}
                                                {product.match_score && (
                                                    <div className="text-[10px] text-lvmh-gray mt-3">Score {Math.round(product.match_score * 100)}%</div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {resultP4?.next_best_action && (
                                <div className="glass p-6 border-l-4 border-green-500 mt-6">
                                    <div className="flex items-center gap-2 mb-4">
                                        <Lightbulb size={20} className="text-green-500" />
                                        <h4 className="font-display font-bold">Next Best Action</h4>
                                    </div>
                                    <p className="text-sm mb-4">{resultP4.next_best_action.description || 'Action recommandée'}</p>
                                    {resultP4.next_best_action.target_products?.length > 0 && (
                                        <div>
                                            <div className="data-label mb-2">Produits suggérés</div>
                                            <div className="flex flex-wrap gap-2">
                                                {resultP4.next_best_action.target_products.map((p, i) => (
                                                    <span key={i} className="text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded">
                                                        {p}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}

                            <button onClick={() => setCurrentResult(null)} className="w-full bg-lvmh-gold text-black font-black py-4 rounded-xl hover:bg-lvmh-gold/90 transition-all shadow-[0_15px_40px_rgba(212,175,55,0.3)] flex items-center justify-center gap-2 uppercase tracking-widest mt-6">
                                <CheckCircle size={20} aria-hidden="true" />
                                Terminer
                            </button>
                        </div>
                    )}
                </>
            )}

            {/* HISTORY VIEW */}
            {activeView === 'history' && (
                <div className="flex-1 overflow-y-auto animate-in fade-in">
                    <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
                        <History size={24} className="text-lvmh-gold" />
                        Historique
                    </h2>
                    {loadingHistory ? (
                        <div className="text-center py-10 text-lvmh-gray">Chargement...</div>
                    ) : (
                        <div className="space-y-4">
                            {history.length > 0 ? history.map(note => (
                                <div key={note.id} onClick={() => handleViewDetail(note)} className="glass p-4 border-l-2 border-lvmh-gold cursor-pointer hover:bg-white/10 transition-colors">
                                    <div className="flex justify-between items-start mb-2">
                                        <span className="font-bold text-white">{note.client}</span>
                                        <span className="text-xs text-lvmh-gray">{new Date(note.date).toLocaleDateString()}</span>
                                    </div>
                                    <p className="text-sm text-gray-400 line-clamp-2 mb-2">"{note.transcription}"</p>
                                    <div className="flex justify-end">
                                        <span className="text-xs font-bold text-lvmh-gold">+{note.points} pts</span>
                                    </div>
                                </div>
                            )) : (
                                <div className="text-center py-10 text-lvmh-gray italic">Aucun enregistrement</div>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* SEARCH VIEW */}
            {activeView === 'search' && (
                <div className="flex-1 animate-in fade-in">
                    <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
                        <Search size={24} className="text-lvmh-gold" />
                        Recherche Client
                    </h2>
                    <div className="relative mb-6">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-lvmh-gray" size={18} />
                        <input
                            type="text"
                            placeholder="Nom du client..."
                            className="w-full bg-white/5 border-none rounded-xl py-4 pl-12 pr-4 text-white focus:ring-1 focus:ring-lvmh-gold transition-all"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            autoFocus
                        />
                    </div>

                    {searchingClients ? (
                        <div className="flex justify-center py-10">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-lvmh-gold"></div>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {clientResults.length > 0 ? clientResults.map(client => (
                                <div key={client.id} className="glass p-4 border-l-2 border-lvmh-gold hover:bg-white/5 transition-colors">
                                    <div className="flex justify-between items-center">
                                        <div>
                                            <div className="font-bold text-white flex items-center gap-2">
                                                {client.name}
                                                {client.vic_status !== 'Standard' && <span className="text-[10px] bg-lvmh-gold text-black px-1 rounded font-black">{client.vic_status}</span>}
                                            </div>
                                            <div className="text-xs text-lvmh-gray">{client.total_notes} enregistrements</div>
                                        </div>
                                        <button onClick={() => { setActiveView('record'); setSearchQuery(client.name); }} className="text-lvmh-gold text-xs font-bold uppercase hover:underline">
                                            Nouvelle dictée
                                        </button>
                                    </div>
                                </div>
                            )) : searchQuery.length > 2 && (
                                <div className="text-center text-lvmh-gray text-sm mt-10">
                                    Aucun client trouvé pour "{searchQuery}".
                                </div>
                            )}

                            {!searchQuery && (
                                <div className="text-center text-lvmh-gray text-sm mt-10">
                                    Entrez un nom pour rechercher dans la base CRM LVMH.
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* CSV RESULTS VIEW */}
            {activeView === 'csv' && (
                <div className="flex-1 overflow-y-auto animate-in fade-in">
                    <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
                        <FileText size={24} className="text-lvmh-gold" />
                        Résultats CSV
                    </h2>

                    {/* File Selector */}
                    <div className="mb-6">
                        <label className="text-xs text-lvmh-gray uppercase tracking-widest font-bold mb-2 block">Fichier</label>
                        <select
                            value={selectedCsv}
                            onChange={handleCsvSelect}
                            className="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-white focus:ring-1 focus:ring-lvmh-gold transition-all appearance-none cursor-pointer"
                        >
                            {csvFiles.map(file => (
                                <option key={file} value={file} className="bg-lvmh-black">{file}</option>
                            ))}
                        </select>
                    </div>

                    {loadingCsv ? (
                        <div className="flex justify-center py-10">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-lvmh-gold"></div>
                        </div>
                    ) : (
                        <>
                            <div className="text-xs text-lvmh-gray mb-4">{csvTotal} résultats</div>
                            <div className="space-y-3">
                                {csvData.length > 0 ? csvData.map((row, i) => (
                                    <div key={i} className="glass p-4 border-l-2 border-lvmh-gold hover:bg-white/5 transition-colors">
                                        <div className="flex justify-between items-start mb-2">
                                            <span className="font-bold text-white">{row.id}</span>
                                            <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${row.tier === 1 ? 'bg-white/10 text-white' :
                                                    row.tier === 2 ? 'bg-lvmh-gold/20 text-lvmh-gold' :
                                                        'bg-red-500/20 text-red-500'
                                                }`}>
                                                TIER {row.tier}
                                            </span>
                                        </div>
                                        <div className="flex flex-wrap gap-1 mb-2">
                                            {(row.tags || []).slice(0, 4).map((tag, ti) => (
                                                <span key={ti} className="text-[9px] bg-white/5 border border-white/10 px-1.5 py-0.5 rounded text-lvmh-gray uppercase">
                                                    {tag.replace(/_/g, ' ')}
                                                </span>
                                            ))}
                                            {(row.tags || []).length > 4 && (
                                                <span className="text-[9px] text-lvmh-gray">+{row.tags.length - 4}</span>
                                            )}
                                        </div>
                                        <div className="flex justify-between items-center text-xs">
                                            <span className="text-lvmh-gray">{row.budget_range || 'Budget N/A'}</span>
                                            <span className="text-lvmh-gold font-bold">{Math.round(row.confidence * 100)}%</span>
                                        </div>
                                        {row.reasoning && (
                                            <p className="text-[10px] text-lvmh-gray mt-2 italic line-clamp-2">"{row.reasoning}"</p>
                                        )}
                                    </div>
                                )) : (
                                    <div className="text-center text-lvmh-gray text-sm py-10 italic">
                                        Aucun résultat dans ce fichier
                                    </div>
                                )}
                            </div>
                        </>
                    )}
                </div>
            )}
        </div>
    )
}
