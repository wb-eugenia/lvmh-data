import React, { useState, useEffect } from 'react'
import { Mic, Search, Trophy, X, CheckCircle, Menu, LogOut, History, FileText, ChevronDown, ChevronRight, Filter, Loader2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { apiFetch, normalizeAnalysisResult, wsUrl } from '../lib/api'
import { processTextEdge } from '../lib/edge-processor'
import { loadWhisperModel, transcribeAudio, isModelLoaded, setLoadProgressCallback } from '../lib/edge-transcriber'
import confetti from 'canvas-confetti'

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

    // Client Search State
    const [clientSearchQuery, setClientSearchQuery] = useState('')
    const [clientSuggestions, setClientSuggestions] = useState([])
    const [selectedClient, setSelectedClient] = useState(null)
    const [showClientDropdown, setShowClientDropdown] = useState(false)

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
    const [toast, setToast] = useState(null)
    const [isReviewingTranscription, setIsReviewingTranscription] = useState(false)
    const [transcriptionDraft, setTranscriptionDraft] = useState('')
    const [historyFilter, setHistoryFilter] = useState('all')
    const [historySearch, setHistorySearch] = useState('')
    const [searchOnlyVip, setSearchOnlyVip] = useState(false)
    const [expandedSections, setExpandedSections] = useState({
        product: true,
        profile: false,
        hospitality: false,
        business: true,
        rag: true,
        nba: true
    })

    // Whisper WASM state
    const [whisperLoading, setWhisperLoading] = useState(false)
    const [whisperProgress, setWhisperProgress] = useState(0)
    const [whisperReady, setWhisperReady] = useState(false)
    const [pipelineProgress, setPipelineProgress] = useState(null)
    const [pipelineSocketState, setPipelineSocketState] = useState('connecting')
    const [pipelineStartedAt, setPipelineStartedAt] = useState(null)
    const [pipelineElapsedMs, setPipelineElapsedMs] = useState(0)

    const formatPercent = (value) => {
        if (value === null || value === undefined || Number.isNaN(value)) return '-'
        const normalized = value <= 1 ? value * 100 : value
        return `${Math.round(normalized)}%`
    }

    const formatCurrency = (value) => {
        if (value === null || value === undefined || Number.isNaN(value)) return '-'
        try {
            return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(value)
        } catch {
            return `${value} EUR`
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
    const recordingStatus = isRecording
        ? {
            label: 'Enregistrement',
            helper: 'Appuyez pour arreter la dictee',
            tone: 'text-red-400',
            border: 'border-red-500/40',
            badge: 'bg-red-500/20 text-red-300'
        }
        : isReviewingTranscription
            ? {
                label: 'Validation',
                helper: 'Verifier puis lancer l analyse',
                tone: 'text-silver',
                border: 'border-silver/40',
                badge: 'bg-silver/20 text-silver'
            }
        : isProcessing
            ? {
                label: 'Analyse',
                helper: 'La pipeline traite la note',
                tone: 'text-silver',
                border: 'border-silver/40',
                badge: 'bg-silver/20 text-silver'
            }
            : currentResult
                ? {
                    label: 'Termine',
                    helper: 'Resultat disponible',
                    tone: 'text-green-400',
                    border: 'border-green-500/40',
                    badge: 'bg-green-500/20 text-green-300'
                }
                : {
                    label: 'Pret',
                    helper: 'Appuyez pour demarrer une dictee',
                    tone: 'text-white',
                    border: 'border-white/10',
                    badge: 'bg-white/10 text-white'
                }
    const primaryRecordLabel = isRecording ? 'Arreter la dictee' : 'Demarrer la dictee'
    const summaryBudget = resultP4?.budget_potential || (resultP4?.budget_specific ? formatCurrency(resultP4.budget_specific) : '-')
    const summaryUrgency = resultP4?.urgency || '-'
    const summaryNba = resultP4?.next_best_action?.description || 'Aucune action recommandee'
    const summaryVip = vipStatus ? String(vipStatus).toUpperCase() : 'STANDARD'

    const filteredClientResults = searchOnlyVip
        ? clientResults.filter((client) => client.vic_status && client.vic_status !== 'Standard')
        : clientResults

    const filteredHistory = history.filter((note) => {
        if (historyFilter === 'all') return true
        const createdAt = new Date(note.date)
        const now = new Date()
        const diffMs = now.getTime() - createdAt.getTime()
        const diffDays = diffMs / (1000 * 60 * 60 * 24)
        if (historyFilter === 'today') return diffDays < 1
        if (historyFilter === 'week') return diffDays < 7
        return true
    }).filter((note) => {
        if (!historySearch) return true
        const search = historySearch.toLowerCase()
        return (note.transcription || '').toLowerCase().includes(search) || 
               (note.client || '').toLowerCase().includes(search)
    })

    const normalizePipelineStep = (step) => {
        const raw = String(step || '').toLowerCase()
        if (!raw) return null
        if (raw === 'failed' || raw.includes('error')) return 'failed'
        if (raw === 'done' || raw === 'cache_hit' || raw === 'semantic_cache_hit') return 'done'
        if (raw === 'cleaning' || raw === 'rgpd') return 'cleaning'
        if (raw === 'routing') return 'routing'
        if (raw.includes('tier') || raw === 'cross_validation' || raw === 'extraction') return 'extraction'
        if (raw === 'rag') return 'rag'
        if (raw === 'injection') return 'nba'
        return raw
    }

    // WebSocket for real-time pipeline visualization
    useEffect(() => {
        const socketUrl = wsUrl('/ws/pipeline')
        let ws
        let reconnectTimer
        let isActive = true

        const connect = () => {
            if (!isActive) return
            setPipelineSocketState('connecting')
            ws = new WebSocket(socketUrl)

            ws.onopen = () => {
                if (!isActive) return
                setPipelineSocketState('connected')
            }

            ws.onmessage = (event) => {
                if (!isActive) return

                const data = JSON.parse(event.data || '{}')
                if (data.type === 'leaderboard') {
                    const enriched = (data.data || []).map((adv) => ({
                        ...adv,
                        isMe: adv.id === user.name
                    }))
                    setLeaderboard(enriched)
                    return
                }

                if (!data.step) return

                const eventUserId = data.user_id === undefined || data.user_id === null ? null : String(data.user_id)
                const currentUserId = user?.id === undefined || user?.id === null ? null : String(user.id)
                if (eventUserId && currentUserId && eventUserId !== currentUserId) return

                const normalizedStep = normalizePipelineStep(data.step)
                if (!normalizedStep) return

                setPipelineProgress(data)
                setCurrentStep(normalizedStep)

                if (normalizedStep === 'failed') {
                    setIsProcessing(false)
                }
            }

            ws.onerror = () => {
                if (!isActive) return
                setPipelineSocketState('disconnected')
            }

            ws.onclose = () => {
                if (!isActive) return
                setPipelineSocketState('disconnected')
                reconnectTimer = setTimeout(connect, 3000)
            }
        }

        connect()

        return () => {
            isActive = false
            if (reconnectTimer) clearTimeout(reconnectTimer)
            ws?.close()
        }
    }, [user?.id])

    useEffect(() => {
        fetchLeaderboard()
        fetchUserStats()
    }, [user])

    // Client Search Effect
    useEffect(() => {
        const searchClients = async () => {
            if (!clientSearchQuery || clientSearchQuery.length < 2) {
                setClientSuggestions([])
                return
            }
            try {
                const token = localStorage.getItem('token')
                const res = await apiFetch(`/api/clients/search?q=${encodeURIComponent(clientSearchQuery)}`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                })
                if (res.ok) {
                    const data = await res.json()
                    setClientSuggestions(data || [])
                }
            } catch (e) {
                console.error('Client search error:', e)
            }
        }
        const debounce = setTimeout(searchClients, 300)
        return () => clearTimeout(debounce)
    }, [clientSearchQuery])

    const handleSelectClient = (client) => {
        setSelectedClient(client)
        setClientSearchQuery(client.name)
        setShowClientDropdown(false)
    }

    const fetchLeaderboard = async () => {
        try {
            const res = await apiFetch('/api/dashboard/leaderboard')
            if (res.ok) {
                const data = await res.json()
                const leaderboardData = (data.users || data.leaderboard || []).map((u, i) => ({
                    id: u.full_name || u.email || u.name,
                    score: u.score || 0,
                    isMe: u.id === user?.id || u.email === user?.email
                }))
                
                const meIndex = leaderboardData.findIndex(u => u.isMe)
                setUserRank(meIndex >= 0 ? meIndex + 1 : null)
                setLeaderboard(leaderboardData)
            } else {
                setLeaderboard([{ id: user.name, score: user.points || user.score || 0, isMe: true }])
            }
        } catch (e) { 
            setLeaderboard([{ id: user.name, score: user.points || user.score || 0, isMe: true }])
        }
    }
    
    const [userRank, setUserRank] = useState(null)
    const [userStats, setUserStats] = useState(null)

    const generateQualityTips = (qualityScore, tags, extraction) => {
        const tips = []
        
        if (qualityScore < 60) {
            tips.push({ icon: '📝', text: 'Ajoutez plus de détails sur le client et ses préférences' })
        }
        if (!extraction?.products || extraction.products.length === 0) {
            tips.push({ icon: '🛍️', text: 'Mentionnez les produits intéressés (marque, modèle, couleur)' })
        }
        if (!extraction?.budget_potential && !extraction?.budget_specific) {
            tips.push({ icon: '💰', text: 'Précisez le budget du client pour de meilleures recommandations' })
        }
        if (!extraction?.purchase_context?.behavior) {
            tips.push({ icon: '👤', text: 'Indiquez le statut VIC/VIP ou le contexte d\'achat' })
        }
        if (!extraction?.urgency && !extraction?.next_best_action) {
            tips.push({ icon: '⏰', text: 'Mentionnez l\'urgence ou la date limite' })
        }
        
        if (qualityScore >= 80) {
            tips.push({ icon: '⭐', text: 'Excellente note ! Continuez ainsi' })
        } else if (qualityScore >= 60) {
            tips.push({ icon: '👍', text: 'Note correcte. Ajoutez plus de contexte pour améliorer' })
        }
        
        return tips
    }

    const fetchUserStats = async () => {
        try {
            const res = await apiFetch('/api/dashboard/advisor/stats')
            if (res.ok) {
                const data = await res.json()
                setUserStats(data)
            }
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
            setSearchOnlyVip(false)
        }
        if (view !== 'record') {
            setIsReviewingTranscription(false)
            setTranscriptionDraft('')
            setPipelineProgress(null)
            setCurrentStep(null)
            setPipelineStartedAt(null)
        }
    }

    const toggleSection = (key) => {
        setExpandedSections((prev) => ({ ...prev, [key]: !prev[key] }))
    }

    const handleViewDetail = (note) => {
        // We might need to fetch full JSON if not in history
        if (note.analysis_json) {
            try {
                const parsed = JSON.parse(note.analysis_json)
                setCurrentResult(normalizeAnalysisResult(parsed))
            } catch {
                setCurrentResult(null)
            }
            setCurrentStep('done')
            setPipelineProgress({ step: 'done', source: 'history' })
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
                setCurrentResult(normalizeAnalysisResult(data))
                setCurrentStep('done')
                setPipelineProgress({ step: 'done', source: 'history' })
            }
        } catch (e) { console.error(e) }
        finally { setIsProcessing(false) }
    }

    const searchClients = async (query) => {
        if (!query || query.trim().length < 2) {
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

    useEffect(() => {
        if (!toast) return
        const timer = setTimeout(() => setToast(null), 4000)
        return () => clearTimeout(timer)
    }, [toast])

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

    const showToast = (message, tone = 'error') => {
        setToast({
            id: Date.now(),
            message,
            tone
        })
    }

    const handleLogout = () => {
        logout()
        onBack() // Redirects to landing/login
    }

    const [mediaRecorder, setMediaRecorder] = useState(null)

    const toggleRecord = async () => {
        if (!isRecording) {
            // Start Recording
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
                const recorder = new MediaRecorder(stream)
                let chunks = []
                setCurrentResult(null)
                setIsReviewingTranscription(false)
                setTranscriptionDraft('')
                setPipelineProgress(null)
                setCurrentStep(null)
                setPipelineStartedAt(null)

                recorder.ondataavailable = (e) => chunks.push(e.data)
                recorder.onstop = async () => {
                    // Use webm which is standard for MediaRecorder in Chrome/Firefox
                    const blob = new Blob(chunks, { type: 'audio/webm' })
                    await processAudio(blob)
                }

                recorder.start()
                setMediaRecorder(recorder)
                setIsRecording(true)
            } catch (err) {
                showToast("Acces micro refuse. Verifiez les permissions du navigateur.")
            }
        } else {
            // Stop Recording
            if (!mediaRecorder) {
                showToast("Aucun enregistrement actif.")
                return
            }
            mediaRecorder.stop()
            setIsRecording(false)
        }
    }

    const processAudio = async (audioBlob) => {
        setIsProcessing(true)
        setCurrentStep('transcribing')
        setPipelineStartedAt(Date.now())
        setPipelineProgress({ step: 'transcribing', source: 'frontend' })

        try {
            // Load Whisper model if not loaded
            if (!isModelLoaded()) {
                setWhisperLoading(true)
                setLoadProgressCallback((info) => {
                    if (info.status === 'downloading') {
                        setWhisperProgress(info.progress)
                    }
                })
                await loadWhisperModel('base')
                setWhisperReady(true)
                setWhisperLoading(false)
            }

            // Transcribe with Whisper WASM
            const transResult = await transcribeAudio(audioBlob, 'fr')
            
            // Show ORIGINAL text to user (for review/edit)
            // Edge processing will happen in analyzeDraftTranscription
            setTranscriptionDraft(transResult.text || '')
            setIsReviewingTranscription(true)
            setCurrentStep('done')
            setPipelineProgress({ 
                step: 'done', 
                source: 'transcribe',
                provider: transResult.provider 
            })
        } catch (e) {
            console.error('Whisper error:', e)
            showToast(`Erreur transcription: ${e.message}. Fallback au serveur...`)
            
            // Fallback to server transcription
            try {
                const formData = new FormData()
                formData.append('file', audioBlob, 'recording.webm')
                
                const transRes = await apiFetch('/api/transcribe', {
                    method: 'POST',
                    body: formData
                })
                if (!transRes.ok) throw new Error("Transcription failed")
                
                const { transcription: serverTrans } = await transRes.json()
                setTranscriptionDraft(serverTrans || '')
                setIsReviewingTranscription(true)
                setCurrentStep('done')
                setPipelineProgress({ step: 'done', source: 'transcribe', provider: 'server' })
            } catch (fallbackError) {
                showToast(`Erreur systeme: ${fallbackError.message}`)
            }
        } finally {
            setIsProcessing(false)
            setPipelineStartedAt(null)
            setWhisperLoading(false)
        }
    }

    const analyzeDraftTranscription = async () => {
        const textToAnalyze = transcriptionDraft.trim()
        if (!textToAnalyze) {
            showToast('La transcription est vide.')
            return
        }

        setIsReviewingTranscription(false)
        setIsProcessing(true)
        setCurrentStep('routing')
        setPipelineStartedAt(Date.now())
        setPipelineProgress({ step: 'routing', source: 'frontend' })

        try {
            const edgeResult = processTextEdge(textToAnalyze, 'FR')

            const token = localStorage.getItem('token')
            const res = await apiFetch('/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    text: edgeResult.text,
                    text_preprocessed: true,
                    rgpd_risk: edgeResult.rgpd_risk,
                    language: 'FR',
                    advisor_id: user.id || 1,
                    store_id: user.store || "PARIS_HQ",
                    client_id: selectedClient?.external_client_id || null,
                    client_name: selectedClient?.name || null
                })
            })
            if (!res.ok) throw new Error('Analysis failed')

            const data = await res.json()
            const normalizedData = normalizeAnalysisResult(data)
            setCurrentResult(normalizedData)
            setTranscriptionDraft('')
            setCurrentStep('done')
            setPipelineProgress({
                step: 'done',
                quality_score: normalizedData?.meta_analysis?.quality_score,
                processing_time_ms: normalizedData?.processing_time_ms
            })
            
            // Reset client selection after analysis
            setSelectedClient(null)
            setClientSearchQuery('')
            setClientSuggestions([])

            const qualityScore = normalizeScore(normalizedData.meta_analysis?.quality_score || 0)
            const newScore = (user.points || user.score || 0) + (qualityScore >= 80 ? 15 : 10)
            updateUser({ score: newScore, points: newScore })

            if (qualityScore >= 80) {
                confetti({
                    particleCount: 150,
                    spread: 70,
                    origin: { y: 0.6 },
                    colors: ['#C0C0C0', '#ffffff']
                })
            }
        } catch (e) {
            setIsReviewingTranscription(true)
            setCurrentStep('failed')
            setPipelineProgress({ step: 'failed', error: e.message })
            showToast(`Erreur systeme: ${e.message}`)
        } finally {
            setIsProcessing(false)
            setPipelineStartedAt(null)
        }
    }

    const cancelDraftReview = () => {
        setIsReviewingTranscription(false)
        setTranscriptionDraft('')
        setCurrentStep(null)
        setPipelineProgress(null)
        setPipelineStartedAt(null)
        setSelectedClient(null)
        setClientSearchQuery('')
        setClientSuggestions([])
    }

    const activateTextMode = () => {
        if (isProcessing || isRecording) return
        setCurrentResult(null)
        setTranscriptionDraft('')
        setIsReviewingTranscription(true)
        setCurrentStep('cleaning')
        setPipelineProgress({ step: 'cleaning', source: 'text_mode' })
    }

    return (
        <div className={`max-w-md mx-auto min-h-screen flex flex-col p-6 bg-lvmh-black text-white relative overflow-hidden ${activeView === 'record' && !currentResult && !isReviewingTranscription ? 'pb-28' : ''}`}>
            {/* Loading Overlay */}
            {isProcessing && !isRecording && !currentResult && (
                <div className="absolute inset-x-6 top-24 z-50 flex flex-col items-center justify-center animate-in fade-in duration-500">
                    <div className="w-12 h-12 border-4 border-silver border-t-transparent rounded-full animate-spin mb-4" />
                    <div className="text-silver font-bold tracking-widest uppercase text-[10px] animate-pulse">Intelligence Flow...</div>
                </div>
            )}

            {toast && (
                <div className="fixed top-5 inset-x-6 z-[70] max-w-md mx-auto">
                    <div className={`glass px-4 py-3 flex items-start gap-3 border ${toast.tone === 'error' ? 'border-red-500/40' : 'border-green-500/40'}`}>
                        <div className={`w-2 h-2 rounded-full mt-1.5 ${toast.tone === 'error' ? 'bg-red-400' : 'bg-green-400'}`} />
                        <p className="text-sm text-white flex-1">{toast.message}</p>
                        <button
                            onClick={() => setToast(null)}
                            className="text-lvmh-gray hover:text-white transition-colors"
                            aria-label="Fermer la notification"
                        >
                            <X size={16} />
                        </button>
                    </div>
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
                            <h2 className="text-2xl font-didot text-silver mb-1">LVMH</h2>
                            <p className="text-xs text-gray-400 uppercase tracking-widest">Assistant Vendeur</p>
                        </div>

                        <div className="flex items-center gap-4 mb-8 p-4 glass rounded-xl">
                            <div className="w-12 h-12 rounded-full bg-silver flex items-center justify-center text-black font-bold text-xl">
                                {user.name.charAt(0)}
                            </div>
                            <div>
                                <div className="font-bold">{user.name}</div>
                                <div className="text-xs text-silver">{user.store || "Boutique Paris"}</div>
                            </div>
                        </div>

                        <nav className="space-y-2 flex-1">
                            <button onClick={() => handleMenuNavigation('record')} className={`w-full flex items-center gap-4 p-4 rounded-xl transition-colors text-left ${activeView === 'record' ? 'bg-silver/20 text-silver' : 'hover:bg-white/5'}`}>
                                <Mic size={20} className={activeView === 'record' ? 'text-silver' : ''} />
                                <span>Nouvelle dictee</span>
                            </button>
                            <button onClick={() => handleMenuNavigation('history')} className={`w-full flex items-center gap-4 p-4 rounded-xl transition-colors text-left ${activeView === 'history' ? 'bg-silver/20 text-silver' : 'hover:bg-white/5'}`}>
                                <History size={20} className={activeView === 'history' ? 'text-silver' : ''} />
                                <span>Mes Enregistrements</span>
                            </button>
                            <button onClick={() => handleMenuNavigation('classement')} className={`w-full flex items-center gap-4 p-4 rounded-xl transition-colors text-left ${activeView === 'classement' ? 'bg-silver/20 text-silver' : 'hover:bg-white/5'}`}>
                                <Trophy size={20} className={activeView === 'classement' ? 'text-silver' : ''} />
                                <span>Classement</span>
                            </button>
                            <button onClick={() => handleMenuNavigation('search')} className={`w-full flex items-center gap-4 p-4 rounded-xl transition-colors text-left ${activeView === 'search' ? 'bg-silver/20 text-silver' : 'hover:bg-white/5'}`}>
                                <Search size={20} className={activeView === 'search' ? 'text-silver' : ''} />
                                <span>Rechercher</span>
                            </button>
                            <button onClick={() => handleMenuNavigation('csv')} className={`w-full flex items-center gap-4 p-4 rounded-xl transition-colors text-left ${activeView === 'csv' ? 'bg-silver/20 text-silver' : 'hover:bg-white/5'}`}>
                                <FileText size={20} className={activeView === 'csv' ? 'text-silver' : ''} />
                                <span>Resultats CSV</span>
                            </button>
                        </nav>

                        <button onClick={handleLogout} className="w-full flex items-center gap-4 p-4 hover:bg-red-500/10 text-red-400 rounded-xl transition-colors text-left mt-auto">
                            <LogOut size={20} />
                            <span>Deconnexion</span>
                        </button>
                    </div>
                </div>
            )}

            <div className="flex justify-between items-center mb-6 relative z-10">
                <button onClick={() => setIsMenuOpen(true)} className="p-2 -ml-2 hover:text-silver transition-colors">
                    <Menu size={24} />
                    {/* Notification dot example */}
                    {/* <span className="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full"></span> */}
                </button>
                <div className="text-center">
                    <div className="text-[10px] text-silver uppercase tracking-tighter">{user.store || "LVMH Paris Rivoli"}</div>
                    <div className="font-bold text-sm">{user.name}</div>
                </div>
                <div className="flex items-center gap-2">
                    <div className="glass px-3 py-1 text-sm font-bold text-silver">{user.points || user.score || 0} pts</div>
                    <button
                        onClick={handleLogout}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-500/40 text-red-300 text-[10px] uppercase tracking-widest hover:bg-red-500/10 transition-colors"
                    >
                        <LogOut size={12} />
                        Deconnexion
                    </button>
                </div>
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
                            className="w-full bg-white/5 border-none rounded-xl py-4 pl-12 pr-4 text-white focus:ring-1 focus:ring-silver transition-all"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>

                    {!currentResult ? (
                        isReviewingTranscription ? (
                            <div className="glass p-5 border border-silver/30 animate-in fade-in">
                                <div className="flex items-center justify-between gap-3 mb-4">
                                    <div>
                                        <div className="data-label">Validation transcription</div>
                                        <h3 className="text-lg font-bold text-white">Verifier avant analyse IA</h3>
                                    </div>
                                    <button
                                        onClick={cancelDraftReview}
                                        className="text-xs uppercase tracking-widest text-lvmh-gray hover:text-white transition-colors"
                                    >
                                        Annuler
                                    </button>
                                </div>
                                {/* Client Search Field */}
                                <div className="mb-4 relative">
                                    <label className="block text-xs text-lvmh-gray uppercase tracking-widest mb-2">Client (optionnel)</label>
                                    <input
                                        type="text"
                                        value={clientSearchQuery}
                                        onChange={(e) => {
                                            setClientSearchQuery(e.target.value)
                                            setShowClientDropdown(true)
                                            setSelectedClient(null)
                                        }}
                                        onFocus={() => setShowClientDropdown(true)}
                                        className="w-full rounded-xl bg-white/5 border border-white/10 text-sm text-white p-3 focus:outline-none focus:border-silver"
                                        placeholder="Rechercher un client (nom ou ID)..."
                                    />
                                    {showClientDropdown && clientSuggestions.length > 0 && (
                                        <div className="absolute z-50 w-full mt-1 bg-gray-900 border border-white/20 rounded-lg shadow-lg max-h-48 overflow-auto">
                                            {clientSuggestions.map((client) => (
                                                <div
                                                    key={client.id}
                                                    onClick={() => handleSelectClient(client)}
                                                    className="p-3 hover:bg-white/10 cursor-pointer flex items-center justify-between"
                                                >
                                                    <div>
                                                        <div className="text-white text-sm">{client.name}</div>
                                                        <div className="text-lvmh-gray text-xs">{client.external_client_id || 'ID interne'}</div>
                                                    </div>
                                                    <div className="text-right">
                                                        <span className={`text-xs px-2 py-1 rounded ${client.category === 'VIC' || client.category === 'Ultimate' ? 'bg-silver/20 text-silver' : 'bg-white/10 text-lvmh-gray'}`}>
                                                            {client.category}
                                                        </span>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                    {selectedClient && (
                                        <div className="mt-2 flex items-center gap-2">
                                            <span className="text-xs text-silver">Client selectionne:</span>
                                            <span className="text-xs text-white">{selectedClient.name}</span>
                                            <button
                                                onClick={() => {
                                                    setSelectedClient(null)
                                                    setClientSearchQuery('')
                                                }}
                                                className="text-xs text-lvmh-gray hover:text-white"
                                            >
                                                (x)
                                            </button>
                                        </div>
                                    )}
                                </div>
                                <textarea
                                    value={transcriptionDraft}
                                    onChange={(e) => setTranscriptionDraft(e.target.value)}
                                    className="w-full min-h-[220px] rounded-xl bg-white/5 border border-white/10 text-sm text-white p-4 focus:outline-none focus:border-silver resize-y"
                                    placeholder="La transcription apparait ici..."
                                />
                                <div className="mt-4 flex items-center justify-between text-xs text-lvmh-gray">
                                    <span>{transcriptionDraft.trim().length} caracteres</span>
                                    <span>Conseil: corrigez les noms/produits avant analyse</span>
                                </div>
                                <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    <button
                                        onClick={cancelDraftReview}
                                        className="py-3 rounded-xl border border-white/15 text-white hover:border-white/35 transition-colors uppercase tracking-widest text-xs font-bold"
                                    >
                                        Refaire la dictee
                                    </button>
                                    <button
                                        onClick={analyzeDraftTranscription}
                                        disabled={isProcessing || !transcriptionDraft.trim()}
                                        className={`py-3 rounded-xl uppercase tracking-widest text-xs font-black transition-all ${isProcessing || !transcriptionDraft.trim()
                                            ? 'bg-silver/50 text-black/60 cursor-not-allowed'
                                            : 'bg-silver text-black hover:bg-silver/90'
                                            }`}
                                    >
                                        Lancer l analyse
                                    </button>
                                </div>
                            </div>
                        ) : (
                        <div className="flex-1 flex flex-col text-center">
                            <div className={`glass w-full p-4 mb-6 border ${recordingStatus.border}`}>
                                <div className="flex items-center justify-between gap-4">
                                    <div className="text-left">
                                        <div className="text-[10px] text-lvmh-gray uppercase tracking-widest">Statut</div>
                                        <div className={`text-sm font-bold ${recordingStatus.tone}`}>{recordingStatus.label}</div>
                                    </div>
                                    <div className={`text-[10px] px-2 py-1 rounded-full uppercase tracking-widest font-bold ${recordingStatus.badge}`}>
                                        {recordingStatus.helper}
                                    </div>
                                </div>
                            </div>

                            <div className="flex-1 flex flex-col items-center justify-center">
                            <h2 className="gold-text text-4xl font-bold mb-4 tracking-tighter">
                                {isRecording ? "Enregistrement en cours" : isProcessing ? "Analyse en cours" : "Pret"}
                            </h2>
                            <p className="text-lvmh-gray text-xs uppercase tracking-[0.2em] mb-12">
                                {isRecording ? "Le moteur Whisper vous ecoute" : isProcessing ? "La pipeline traite la note" : "Appuyez sur le microphone"}
                            </p>

                            <div className="relative mb-16">
                                {isRecording && (
                                    <div className="absolute inset-0 rounded-full bg-red-500/20 animate-ping" />
                                )}
                                <div
                                    className={`relative z-10 w-24 h-24 rounded-full flex items-center justify-center transition-all duration-300 shadow-[0_0_50px_rgba(0,0,0,0.5)] border-2 ${isRecording ? 'bg-red-500 border-red-400 scale-110' : isProcessing ? 'bg-silver/20 border-silver/40' : 'bg-white border-white/20'}`}
                                >
                                    <Mic size={40} className={isRecording ? "text-white animate-pulse" : isProcessing ? "text-silver" : "text-black"} />
                                </div>

                                {isRecording && (
                                    <div className="absolute -bottom-10 left-1/2 -translate-x-1/2 text-red-500 font-mono text-xs font-bold flex items-center gap-2">
                                        <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                                        LIVE
                                    </div>
                                )}
                            </div>
                        </div>

                            <div className="glass w-full p-5">
                                {userRank && (
                                    <div className="mb-3 text-xs text-lvmh-gray">
                                        Votre classement: <span className="text-silver font-bold">#{userRank}</span> sur {leaderboard.length} advisors
                                    </div>
                                )}
                                <div className="flex items-center gap-2 text-silver text-xs font-bold uppercase mb-4 tracking-widest leading-none">
                                    <Trophy size={14} /> Leaderboard Live
                                </div>
                                <div className="space-y-3">
                                    {leaderboard.length > 0 ? leaderboard.map((adv, i) => (
                                        <div key={i} className={`flex justify-between py-2 border-b border-white/5 last:border-0 items-center ${adv.isMe ? 'bg-white/5 -mx-2 px-2 rounded' : ''}`}>
                                            <span className="text-sm font-medium flex items-center gap-2">
                                                {i + 1}. {adv.id} {adv.isMe && <span className="text-[10px] bg-silver text-black px-1 rounded font-bold">MOI</span>}
                                            </span>
                                            <span className="font-bold text-sm text-silver">{adv.score} pts</span>
                                        </div>
                                    )) : (
                                        <div className="text-center text-xs text-lvmh-gray py-4">Aucune donnee</div>
                                    )}
                                </div>
                            </div>
                        </div>
                    )) : (
                        <div className="fixed inset-0 bg-lvmh-black z-50 p-6 overflow-y-auto animate-in slide-in-from-bottom duration-500">
                            <div className="flex flex-wrap justify-between items-start gap-4 mb-8">
                                <div>
                                    <h2 className="gold-text text-3xl font-display font-black">Expertise IA</h2>
                                    <p className="text-sm text-lvmh-gray">Synthese client et recommandations</p>
                                </div>
                                <button
                                    onClick={() => {
                                        setCurrentResult(null)
                                        setCurrentStep(null)
                                        setPipelineProgress(null)
                                    }}
                                    className="p-2"
                                >
                                    <X size={32} />
                                </button>
                            </div>

                            <div className="glass p-5 border-l-4 border-silver mb-8 bg-silver/5">
                                <div className="data-label">Recompense</div>
                                <div className="text-lg font-bold leading-tight">{resultMeta?.advisor_feedback || "Note traitee !"}</div>
                                <div className="mt-3 flex items-center gap-3">
                                    <div className="text-2xl font-black text-silver">{normalizeScore(resultMeta?.quality_score || 0)}%</div>
                                    <div className="text-xs text-lvmh-gray">qualite</div>
                                    <span className={`text-[10px] px-2 py-1 rounded-full ${
                                        (resultMeta?.quality_score || 0) >= 0.8 ? 'bg-green-500/20 text-green-300' :
                                        (resultMeta?.quality_score || 0) >= 0.5 ? 'bg-silver/20 text-silver' :
                                        'bg-red-500/20 text-red-300'
                                    }`}>
                                        {(resultMeta?.quality_score || 0) >= 0.8 ? 'Excellent' : (resultMeta?.quality_score || 0) >= 0.5 ? 'Correct' : 'A ameliorer'}
                                    </span>
                                </div>
                            </div>

                            {generateQualityTips(normalizeScore(resultMeta?.quality_score || 0), resultTags, currentResult?.extraction).length > 0 && (
                                <div className="glass p-4 mb-6 border border-silver/20">
                                    <div className="text-xs text-silver font-bold uppercase mb-3">Conseils pour ameliorer</div>
                                    <div className="space-y-2">
                                        {generateQualityTips(normalizeScore(resultMeta?.quality_score || 0), resultTags, currentResult?.extraction).map((tip, i) => (
                                            <div key={i} className="flex items-start gap-2 text-sm">
                                                <span>{tip.icon}</span>
                                                <span className="text-gray-300">{tip.text}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_0.8fr] gap-6">
                                <div className="glass p-6 border-l-4 border-silver">
                                    <div className="flex flex-wrap items-start justify-between gap-4">
                                        <div>
                                            <div className="data-label">Client</div>
                                            <div className="text-2xl font-display gold-text">{resultId}</div>
                                            <div className="mt-2 flex flex-wrap gap-2">
                                                {vipStatus && (
                                                    <span className="text-[10px] px-2 py-1 rounded-full bg-silver/20 text-silver">
                                                        {String(vipStatus).toUpperCase()}
                                                    </span>
                                                )}
                                                <span className="text-[10px] px-2 py-1 rounded-full bg-white/10 text-lvmh-gray">
                                                    Tier {resultRouting.tier || '-'}
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
                                            <div className="data-label">Modele</div>
                                            <div className="text-sm font-semibold">{currentResult?.model_used || '-'}</div>
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
                                                        <span key={i} className="text-xs bg-silver/15 text-silver px-2 py-1 rounded-full">
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
                                            <div className="data-label">Qualite</div>
                                            <div className="text-xl font-semibold">{formatPercent(resultMeta?.quality_score)}</div>
                                            <div className="text-xs text-lvmh-gray">
                                                Confiance {formatPercent(resultRouting.confidence ?? currentResult?.confidence)}
                                            </div>
                                        </div>
                                        <div className="glass p-4">
                                            <div className="data-label">Budget</div>
                                            <div className="text-lg font-semibold">{summaryBudget}</div>
                                            <div className="text-xs text-lvmh-gray">
                                                {resultP4?.budget_specific && resultP4?.budget_potential
                                                    ? `Estimation: ${resultP4.budget_potential}`
                                                    : (resultP4?.budget_specific ? 'Budget specifique detecte' : 'Budget specifique N/A')}
                                            </div>
                                        </div>
                                        <div className="glass p-4">
                                            <div className="data-label">RGPD</div>
                                            <div className={`text-sm font-semibold ${resultRgpd?.contains_sensitive ? 'text-red-400' : 'text-green-400'}`}>
                                                {resultRgpd?.contains_sensitive ? 'Sensibles detectees' : 'Conforme'}
                                            </div>
                                            <div className="text-xs text-lvmh-gray">
                                                {resultRgpd?.categories_detected?.length ? resultRgpd.categories_detected.join(', ') : 'Aucune categorie'}
                                            </div>
                                        </div>
                                        <div className="glass p-4">
                                            <div className="data-label">Traitement</div>
                                            <div className="text-lg font-semibold">{Math.round(currentResult?.processing_time_ms || 0)}ms</div>
                                            <div className="text-xs text-lvmh-gray">
                                                {currentResult?.model_used || 'Modele inconnu'}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className="glass p-5 mb-6 border border-silver/30 bg-silver/5">
                                <div className="data-label">Resume actionnable</div>
                                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-3">
                                    <div className="bg-white/5 rounded-lg p-3">
                                        <div className="text-[10px] uppercase tracking-widest text-lvmh-gray">Statut client</div>
                                        <div className="font-bold text-white mt-1">{summaryVip}</div>
                                    </div>
                                    <div className="bg-white/5 rounded-lg p-3">
                                        <div className="text-[10px] uppercase tracking-widest text-lvmh-gray">Budget</div>
                                        <div className="font-bold text-white mt-1">{summaryBudget}</div>
                                    </div>
                                    <div className="bg-white/5 rounded-lg p-3">
                                        <div className="text-[10px] uppercase tracking-widest text-lvmh-gray">Urgence</div>
                                        <div className="font-bold text-white mt-1">{summaryUrgency}</div>
                                    </div>
                                    <div className="bg-white/5 rounded-lg p-3 col-span-2 lg:col-span-1">
                                        <div className="text-[10px] uppercase tracking-widest text-lvmh-gray">NBA</div>
                                        <div className="text-sm text-white mt-1 line-clamp-2">{summaryNba}</div>
                                    </div>
                                </div>
                            </div>

                            <div className="space-y-4 mt-6">
                                <CollapsibleSection
                                    title="Pilier 1 - Univers Produit"
                                    isOpen={expandedSections.product}
                                    onToggle={() => toggleSection('product')}
                                >
                                    <div className="space-y-3 text-sm">
                                        <div>
                                            <div className="data-label">Categories</div>
                                            <div className="mt-2 flex flex-wrap gap-2">
                                                {(resultP1.categories || []).length ? resultP1.categories.map((cat, i) => (
                                                    <span key={i} className="text-xs bg-white/10 px-2 py-1 rounded">{cat}</span>
                                                )) : <span className="text-xs text-lvmh-gray">N/A</span>}
                                            </div>
                                        </div>
                                        <div>
                                            <div className="data-label">Produits mentionnes</div>
                                            <div className="mt-2 text-sm text-lvmh-gray">{(resultP1.produits_mentionnes || []).join(', ') || 'N/A'}</div>
                                        </div>
                                        <div className="grid grid-cols-2 gap-4">
                                            <div>
                                                <div className="data-label">Couleurs</div>
                                                <div className="text-sm text-lvmh-gray">{(resultP1.preferences?.colors || []).join(', ') || 'N/A'}</div>
                                            </div>
                                            <div>
                                                <div className="data-label">Matieres</div>
                                                <div className="text-sm text-lvmh-gray">{(resultP1.preferences?.materials || []).join(', ') || 'N/A'}</div>
                                            </div>
                                        </div>
                                    </div>
                                </CollapsibleSection>

                                <CollapsibleSection
                                    title="Pilier 2 - Profil Client"
                                    isOpen={expandedSections.profile}
                                    onToggle={() => toggleSection('profile')}
                                >
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
                                </CollapsibleSection>

                                <CollapsibleSection
                                    title="Pilier 3 - Hospitalite & Care"
                                    isOpen={expandedSections.hospitality}
                                    onToggle={() => toggleSection('hospitality')}
                                >
                                    <div className="space-y-3 text-sm">
                                        <div>
                                            <div className="data-label">Allergies</div>
                                            <div className={`text-sm ${resultAllergies.length ? 'text-red-400' : 'text-green-400'}`}>
                                                {resultAllergies.length ? resultAllergies.join(', ') : 'Aucune detectee'}
                                            </div>
                                        </div>
                                        <div>
                                            <div className="data-label">Regime</div>
                                            <div className="text-sm text-lvmh-gray">{(resultP3?.diet || []).join(', ') || 'N/A'}</div>
                                        </div>
                                        <div>
                                            <div className="data-label">Occasion</div>
                                            <div className="text-sm text-lvmh-gray">{resultP3?.occasion || 'N/A'}</div>
                                        </div>
                                    </div>
                                </CollapsibleSection>

                                <CollapsibleSection
                                    title="Pilier 4 - Action Business"
                                    isOpen={expandedSections.business}
                                    onToggle={() => toggleSection('business')}
                                >
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
                                            <div className="data-label">Temperature du lead</div>
                                            <div className="text-sm text-lvmh-gray">{resultP4?.lead_temperature || 'N/A'}</div>
                                        </div>
                                    </div>
                                </CollapsibleSection>

                                {resultP1?.matched_products?.length > 0 && (
                                    <CollapsibleSection
                                        title="Produits recommandes (RAG)"
                                        isOpen={expandedSections.rag}
                                        onToggle={() => toggleSection('rag')}
                                    >
                                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                            {resultP1.matched_products.map((product, i) => (
                                                <div key={i} className="bg-white/5 p-4 rounded-lg border border-white/10">
                                                    <div className="font-bold text-silver mb-1">{product.name || product.ID}</div>
                                                    <div className="text-xs text-lvmh-gray uppercase">{product.category || 'Categorie'}</div>
                                                    {product.description && (
                                                        <div className="text-xs text-lvmh-gray mt-2 line-clamp-2">{product.description}</div>
                                                    )}
                                                    {product.match_score && (
                                                        <div className="text-[10px] text-lvmh-gray mt-3">Score {Math.round(product.match_score * 100)}%</div>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    </CollapsibleSection>
                                )}

                                {resultP4?.next_best_action && (
                                    <CollapsibleSection
                                        title="Next Best Action"
                                        isOpen={expandedSections.nba}
                                        onToggle={() => toggleSection('nba')}
                                        accent="green"
                                    >
                                        <div className="space-y-3">
                                            <p className="text-sm">{resultP4.next_best_action.description || 'Action recommandee'}</p>
                                            {resultP4.next_best_action.target_products?.length > 0 && (
                                                <div>
                                                    <div className="data-label mb-2">Produits suggeres</div>
                                                    <div className="flex flex-wrap gap-2">
                                                        {resultP4.next_best_action.target_products.map((p, i) => (
                                                            <span key={i} className="text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded">
                                                                {p}
                                                            </span>
                                                        ))}
                                                    </div>
                </div>
            )}

            {/* CLASSEMENT VIEW */}
            {activeView === 'classement' && (
                <div className="flex-1 overflow-y-auto animate-in fade-in">
                    <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
                        <Trophy size={24} className="text-silver" />
                        Classement
                    </h2>

                    {userRank && (
                        <div className="glass p-6 mb-6 text-center border-l-4 border-silver">
                            <div className="text-xs text-lvmh-gray uppercase tracking-widest mb-2">Votre Position</div>
                            <div className="text-5xl font-black text-silver">#{userRank}</div>
                            <div className="text-sm text-lvmh-gray mt-2">sur {leaderboard.length} advisors</div>
                        </div>
                    )}

                    <div className="glass p-5">
                        <div className="space-y-3">
                            {leaderboard.length > 0 ? leaderboard.map((adv, i) => (
                                <div key={i} className={`flex justify-between py-3 border-b border-white/5 last:border-0 items-center ${adv.isMe ? 'bg-silver/10 -mx-3 px-3 rounded' : ''}`}>
                                    <div className="flex items-center gap-3">
                                        <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm ${
                                            i === 0 ? 'bg-yellow-500 text-black' :
                                            i === 1 ? 'bg-gray-400 text-black' :
                                            i === 2 ? 'bg-amber-700 text-white' :
                                            'bg-white/10 text-white'
                                        }`}>
                                            {i + 1}
                                        </div>
                                        <span className="font-medium">
                                            {adv.id} {adv.isMe && <span className="text-[10px] bg-silver text-black px-1 rounded font-bold ml-1">MOI</span>}
                                        </span>
                                    </div>
                                    <span className="font-bold text-lg text-silver">{adv.score} pts</span>
                                </div>
                            )) : (
                                <div className="text-center py-8 text-lvmh-gray">Aucune donnee</div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
                                    </CollapsibleSection>
                                )}
                            </div>

                            <button
                                onClick={() => {
                                    setCurrentResult(null)
                                    setCurrentStep(null)
                                    setPipelineProgress(null)
                                }}
                                className="w-full bg-silver text-black font-black py-5 rounded-xl hover:bg-silver/90 transition-all shadow-[0_15px_40px_rgba(212,175,55,0.3)] flex items-center justify-center gap-2 uppercase tracking-widest mt-6"
                            >
                                <CheckCircle size={20} aria-hidden="true" />
                                Terminer
                            </button>
                        </div>
                    )}
                </>
            )}

            {activeView === 'record' && !currentResult && !isReviewingTranscription && (
                <div className="fixed inset-x-0 bottom-0 z-30 px-6 pb-6">
                    <div className="max-w-md mx-auto">
                        <button
                            onClick={toggleRecord}
                            disabled={isProcessing}
                            className={`w-full py-5 rounded-xl transition-all shadow-[0_15px_40px_rgba(0,0,0,0.35)] border flex items-center justify-center gap-3 uppercase tracking-widest font-black ${isRecording
                                ? 'bg-red-500 text-white border-red-400 hover:bg-red-500/90'
                                : 'bg-silver text-black border-silver hover:bg-silver/90'
                                } ${isProcessing ? 'opacity-70 cursor-not-allowed' : ''}`}
                        >
                            <Mic size={20} />
                            {isProcessing ? 'Analyse en cours...' : primaryRecordLabel}
                        </button>
                    </div>
                </div>
            )}

            {/* HISTORY VIEW */}
            {activeView === 'history' && (
                <div className="flex-1 overflow-y-auto animate-in fade-in">
                    <div className="flex items-center justify-between gap-3 mb-4">
                        <h2 className="text-2xl font-bold flex items-center gap-2">
                            <History size={24} className="text-silver" />
                            Historique
                        </h2>
                    </div>

                    <div className="relative mb-4">
                        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-lvmh-gray" />
                        <input
                            type="text"
                            placeholder="Rechercher dans les transcriptions..."
                            value={historySearch}
                            onChange={(e) => setHistorySearch(e.target.value)}
                            className="w-full pl-10 pr-4 py-2 rounded-lg border border-white/10 bg-white/[0.02] text-white placeholder-lvmh-gray focus:outline-none focus:border-silver/40"
                        />
                    </div>

                    <div className="flex flex-wrap gap-2 mb-6">
                        {[
                            { id: 'all', label: 'Tout' },
                            { id: 'today', label: 'Aujourd hui' },
                            { id: 'week', label: '7 jours' }
                        ].map((item) => (
                            <button
                                key={item.id}
                                onClick={() => setHistoryFilter(item.id)}
                                className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${historyFilter === item.id
                                    ? 'border-silver bg-silver/20 text-silver'
                                    : 'border-white/10 text-lvmh-gray hover:border-white/30 hover:text-white'
                                    }`}
                            >
                                {item.label}
                            </button>
                        ))}
                        <span className="text-xs text-lvmh-gray py-1.5">{filteredHistory.length} resultats</span>
                    </div>

                    {loadingHistory ? (
                        <div className="space-y-3">
                            {[1, 2, 3].map((item) => (
                                <div key={item} className="glass p-4 animate-pulse">
                                    <div className="h-3 w-1/3 bg-white/10 rounded mb-3" />
                                    <div className="h-2 w-full bg-white/10 rounded mb-2" />
                                    <div className="h-2 w-4/5 bg-white/10 rounded" />
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {filteredHistory.length > 0 ? filteredHistory.map(note => (
                                <div key={note.id} onClick={() => handleViewDetail(note)} className="glass p-4 border-l-2 border-silver cursor-pointer hover:bg-white/10 transition-colors">
                                    <div className="flex justify-between items-start mb-2">
                                        <span className="font-bold text-white">{note.client}</span>
                                        <span className="text-xs text-lvmh-gray">{new Date(note.date).toLocaleDateString()}</span>
                                    </div>
                                    <p className="text-sm text-gray-400 line-clamp-2 mb-2">"{note.transcription}"</p>
                                    <div className="flex justify-end">
                                        <span className="text-xs font-bold text-silver">+{note.points} pts</span>
                                    </div>
                                </div>
                            )) : (
                                <div className="text-center py-10 text-lvmh-gray italic">Aucun enregistrement pour ce filtre</div>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* SEARCH VIEW */}
            {activeView === 'search' && (
                <div className="flex-1 animate-in fade-in">
                    <div className="flex items-center justify-between gap-3 mb-6">
                        <h2 className="text-2xl font-bold flex items-center gap-2">
                            <Search size={24} className="text-silver" />
                            Recherche Client
                        </h2>
                        <button
                            onClick={() => setSearchOnlyVip((prev) => !prev)}
                            className={`text-[10px] px-3 py-1.5 rounded-full uppercase tracking-widest border transition-colors ${searchOnlyVip
                                ? 'border-silver bg-silver/20 text-silver'
                                : 'border-white/10 text-lvmh-gray hover:border-white/30 hover:text-white'
                                }`}
                        >
                            VIC only
                        </button>
                    </div>
                    <div className="relative mb-6">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-lvmh-gray" size={18} />
                        <input
                            type="text"
                            placeholder="Nom du client..."
                            className="w-full bg-white/5 border-none rounded-xl py-4 pl-12 pr-4 text-white focus:ring-1 focus:ring-silver transition-all"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            autoFocus
                        />
                    </div>

                    {searchingClients ? (
                        <div className="space-y-3">
                            {[1, 2, 3].map((item) => (
                                <div key={item} className="glass p-4 animate-pulse">
                                    <div className="h-3 w-1/3 bg-white/10 rounded mb-3" />
                                    <div className="h-2 w-2/3 bg-white/10 rounded" />
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {filteredClientResults.length > 0 ? filteredClientResults.map(client => (
                                <div key={client.id} className="glass p-4 border-l-2 border-silver hover:bg-white/5 transition-colors">
                                    <div className="flex justify-between items-center">
                                        <div>
                                            <div className="font-bold text-white flex items-center gap-2">
                                                {client.name}
                                                {client.vic_status !== 'Standard' && <span className="text-[10px] bg-silver text-black px-1 rounded font-black">{client.vic_status}</span>}
                                            </div>
                                            <div className="text-xs text-lvmh-gray">{client.total_notes} enregistrements</div>
                                        </div>
                                        <button onClick={() => { setActiveView('record'); setSearchQuery(client.name); }} className="text-silver text-xs font-bold uppercase hover:underline">
                                            Nouvelle dictee
                                        </button>
                                    </div>
                                </div>
                            )) : searchQuery.length > 1 && (
                                <div className="text-center text-lvmh-gray text-sm mt-10">
                                    Aucun client trouve pour "{searchQuery}" {searchOnlyVip ? '(filtre VIC uniquement actif).' : '.'}
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
                        <FileText size={24} className="text-silver" />
                        Resultats CSV
                    </h2>

                    {/* File Selector */}
                    <div className="mb-6">
                        <label className="text-xs text-lvmh-gray uppercase tracking-widest font-bold mb-2 block">Fichier</label>
                        <select
                            value={selectedCsv}
                            onChange={handleCsvSelect}
                            className="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-white focus:ring-1 focus:ring-silver transition-all appearance-none cursor-pointer"
                        >
                            {csvFiles.map(file => (
                                <option key={file} value={file} className="bg-lvmh-black">{file}</option>
                            ))}
                        </select>
                    </div>

                    {loadingCsv ? (
                        <div className="flex justify-center py-10">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-silver"></div>
                        </div>
                    ) : (
                        <>
                            <div className="text-xs text-lvmh-gray mb-4">{csvTotal} resultats</div>
                            <div className="space-y-3">
                                {csvData.length > 0 ? csvData.map((row, i) => (
                                    <div key={i} className="glass p-4 border-l-2 border-silver hover:bg-white/5 transition-colors">
                                        <div className="flex justify-between items-start mb-2">
                                            <span className="font-bold text-white">{row.id}</span>
                                            <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${row.tier === 1 ? 'bg-white/10 text-white' :
                                                    row.tier === 2 ? 'bg-silver/20 text-silver' :
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
                                            <span className="text-silver font-bold">{Math.round(row.confidence * 100)}%</span>
                                        </div>
                                        {row.reasoning && (
                                            <p className="text-[10px] text-lvmh-gray mt-2 italic line-clamp-2">"{row.reasoning}"</p>
                                        )}
                                    </div>
                                )) : (
                                    <div className="text-center text-lvmh-gray text-sm py-10 italic">
                                        Aucun resultat dans ce fichier
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

function CollapsibleSection({ title, isOpen, onToggle, children, accent = 'gold' }) {
    const borderClass = accent === 'green' ? 'border-green-500/40' : 'border-white/10'
    const titleClass = accent === 'green' ? 'text-green-400' : 'text-white'

    return (
        <div className={`glass p-5 border ${borderClass}`}>
            <button
                onClick={onToggle}
                className="w-full flex items-center justify-between gap-3 text-left"
            >
                <h4 className={`text-base font-display font-bold ${titleClass}`}>{title}</h4>
                {isOpen ? <ChevronDown size={18} className="text-silver" /> : <ChevronRight size={18} className="text-lvmh-gray" />}
            </button>
            {isOpen && <div className="mt-4">{children}</div>}
        </div>
    )
}
