import React, { useState, useEffect } from 'react'
import { ArrowLeft, Mic, Search, Trophy, X, CheckCircle, Menu, LogOut, History, FileText } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
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

    // WebSocket for real-time pipeline visualization
    useEffect(() => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/pipeline`;
        let ws;

        const connect = () => {
            ws = new WebSocket(wsUrl);
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
            const res = await fetch('/api/batch-results')
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
            const res = await fetch(`/api/batch-results?file=${encodeURIComponent(filename)}`)
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
            const res = await fetch('/api/history', {
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
            const res = await fetch(`/api/results/${id}`)
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
            const res = await fetch(`/api/clients/search?q=${query}`)
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
            const transRes = await fetch('/api/transcribe', {
                method: 'POST',
                body: formData // No headers for multipart
            })
            if (!transRes.ok) throw new Error("Transcription failed")

            const { transcription } = await transRes.json()

            // 2. Intelligence Pipeline
            // Get token from auth context/local storage if needed for Auth header
            const token = localStorage.getItem('token')
            const res = await fetch('/api/analyze', {
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
            const newScore = (user.points || user.score || 0) + (data.meta_analysis?.quality_score > 0.8 ? 15 : 10)
            updateUser({ score: newScore, points: newScore })
            // fetchLeaderboard will run via useEffect dependency on `user`

            if (data.meta_analysis?.quality_score >= 80) {
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
                            {/* RESULT MODAL (Same as before) */}
                            <div className="flex justify-between items-center mb-8">
                                <h2 className="gold-text text-3xl font-bold">Expertise IA</h2>
                                <button onClick={() => setCurrentResult(null)} className="p-2"><X size={32} /></button>
                            </div>

                            <div className="glass p-5 border-l-4 border-lvmh-gold mb-8 bg-lvmh-gold/5">
                                <div className="text-xs text-lvmh-gold font-bold mb-1 uppercase tracking-widest">Récompense</div>
                                <div className="text-lg font-bold leading-tight">{currentResult.meta_analysis?.advisor_feedback || "Note traitée !"}</div>
                            </div>


                            <div className="mb-8">
                                <div className="text-[10px] text-lvmh-gray uppercase tracking-widest mb-2 font-bold">Transcription</div>
                                <div className="glass p-4 text-sm text-lvmh-gray italic">
                                    "{currentResult.processed_text || currentResult.original_text || "..."}"
                                </div>
                            </div>

                            <div className="mb-10">
                                <div className="text-[10px] text-lvmh-gray uppercase tracking-widest mb-2 font-bold">Profil Extrait</div>
                                <div className="flex items-center gap-3 mb-4">
                                    <span className="text-2xl font-bold">{currentResult.ID}</span>
                                    <span className="bg-lvmh-gold text-black text-[10px] font-black px-2 py-0.5 rounded-full shadow-lg">VIP</span>
                                </div>

                                <div className="flex flex-wrap gap-2 mb-6">
                                    {currentResult.pilier_1_univers_produit?.categories?.map(tag => (
                                        <span key={tag} className="bg-white/10 px-3 py-1 rounded-full text-xs font-medium border border-white/5">{tag}</span>
                                    ))}
                                </div>

                                {currentResult.pilier_1_univers_produit?.matched_products?.length > 0 && (
                                    <div className="mb-0">
                                        <div className="text-[10px] text-lvmh-gray uppercase tracking-widest mb-3 font-bold">🛍️ Produits Catalogués</div>
                                        <div className="flex gap-3 overflow-x-auto pb-4">
                                            {currentResult.pilier_1_univers_produit.matched_products.map((prod, pi) => (
                                                <div key={pi} className="flex-shrink-0 w-32 glass p-3 border-lvmh-gold/20">
                                                    <div className="text-[10px] font-black text-lvmh-gold mb-1 truncate">{prod.name || prod.ID}</div>
                                                    <div className="text-[9px] text-lvmh-gray uppercase tracking-tighter">{prod.category}</div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>

                            {currentResult.pilier_4_action_business?.next_best_action && (
                                <div className="mb-10">
                                    <div className="text-[10px] text-lvmh-gold uppercase tracking-widest mb-3 font-bold">🚀 Next Best Action</div>
                                    <div className="glass p-6 border-l-4 border-green-500 shadow-[0_10px_30px_rgba(0,0,0,0.5)]">
                                        <div className="font-bold mb-3 text-lg">{currentResult.pilier_4_action_business.next_best_action?.description}</div>
                                        {currentResult.pilier_4_action_business.next_best_action?.target_products?.length > 0 && (
                                            <div className="text-sm text-lvmh-gray italic">
                                                Suggérer : <span className="text-white font-medium italic underline decoration-lvmh-gold/50">{currentResult.pilier_4_action_business.next_best_action.target_products.join(', ')}</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}

                            <button onClick={() => setCurrentResult(null)} className="w-full bg-lvmh-gold text-black font-black py-4 rounded-xl hover:bg-lvmh-gold/90 transition-all shadow-[0_15px_40px_rgba(212,175,55,0.3)] flex items-center justify-center gap-2 uppercase tracking-widest">
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
