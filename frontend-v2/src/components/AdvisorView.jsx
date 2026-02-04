import React, { useState, useEffect, useRef } from 'react'
import { Mic, Search, Trophy, X, CheckCircle, LogOut, History, Sparkles, User, Clock, Tag, TrendingUp, Star, Gift, Award, Target, Zap, Medal, ThumbsUp } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import confetti from 'canvas-confetti'

export default function AdvisorView({ onBack }) {
    const { user, logout, updateUser } = useAuth()
    const [isRecording, setIsRecording] = useState(false)
    const [currentResult, setCurrentResult] = useState(null)
    const [leaderboard, setLeaderboard] = useState([])
    const [searchQuery, setSearchQuery] = useState("")
    const [activeView, setActiveView] = useState("record")
    const [isProcessing, setIsProcessing] = useState(false)
    const [history, setHistory] = useState([])
    const [loadingHistory, setLoadingHistory] = useState(false)
    const [mediaRecorder, setMediaRecorder] = useState(null)

    // Calculate stats - Focus on QUALITY not quantity
    const avgClarity = history.length > 0
        ? Math.round(history.reduce((a, b) => a + (b.quality_score || 0.75), 0) / history.length * 100)
        : 0
    const bestNote = history.length > 0
        ? Math.round(Math.max(...history.map(h => h.quality_score || 0.75)) * 100)
        : 0
    const highQualityNotes = history.filter(h => (h.quality_score || 0.75) >= 0.8).length

    const stats = {
        todayNotes: history.filter(h => new Date(h.date).toDateString() === new Date().toDateString()).length,
        weekNotes: history.length,
        totalPoints: user.points || user.score || 0,
        avgClarity,
        bestNote,
        highQualityNotes,
        level: Math.floor((user.points || 0) / 100) + 1,
        nextLevel: 100 - ((user.points || 0) % 100)
    }

    // Achievements - Focus on QUALITY
    const achievements = [
        { id: 1, name: "Premier Pas", desc: "Première note enregistrée", icon: Star, unlocked: history.length >= 1, color: "text-yellow-400" },
        { id: 2, name: "Clarté Bronze", desc: "Note avec 75%+ de clarté", icon: ThumbsUp, unlocked: bestNote >= 75, color: "text-amber-600" },
        { id: 3, name: "Clarté Argent", desc: "Note avec 85%+ de clarté", icon: Award, unlocked: bestNote >= 85, color: "text-gray-300" },
        { id: 4, name: "Clarté Or", desc: "Note avec 95%+ de clarté", icon: Trophy, unlocked: bestNote >= 95, color: "text-[#D4AF37]" },
        { id: 5, name: "Expert", desc: "10 notes à 80%+ de clarté", icon: Zap, unlocked: highQualityNotes >= 10, color: "text-purple-400" },
        { id: 6, name: "Top Vendeur", desc: "Rang #1 du classement", icon: Medal, unlocked: false, color: "text-[#D4AF37]" },
    ]

    // WebSocket for real-time updates
    useEffect(() => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const wsUrl = `${protocol}//${window.location.host}/ws/pipeline`
        let ws

        const connect = () => {
            ws = new WebSocket(wsUrl)
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data)
                if (data.type === 'leaderboard') {
                    const enriched = data.data.map(adv => ({
                        ...adv,
                        isMe: adv.id === user.name
                    }))
                    setLeaderboard(enriched)
                }
            }
            ws.onclose = () => setTimeout(connect, 3000)
        }

        connect()
        return () => ws?.close()
    }, [])

    useEffect(() => {
        fetchLeaderboard()
        loadHistory()
    }, [user])

    const fetchLeaderboard = async () => {
        try {
            // Mock leaderboard for demo
            const mockData = [
                { id: user.name, score: user.points || user.score || 0, isMe: true },
                { id: "Marie Dupont", score: 890, isMe: false },
                { id: "Jean Martin", score: 720, isMe: false },
                { id: "Sophie Bernard", score: 650, isMe: false },
                { id: "Pierre Leblanc", score: 580, isMe: false },
            ].sort((a, b) => b.score - a.score)
            setLeaderboard(mockData)
        } catch (e) { }
    }

    const loadHistory = async () => {
        setLoadingHistory(true)
        try {
            const token = localStorage.getItem('token')
            const res = await fetch('/api/history', {
                headers: { 'Authorization': `Bearer ${token}` }
            })
            if (res.ok) setHistory(await res.json())
        } catch (e) { console.error(e) }
        finally { setLoadingHistory(false) }
    }

    const handleLogout = () => {
        logout()
        onBack()
    }

    const toggleRecord = async () => {
        if (!isRecording) {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
                const recorder = new MediaRecorder(stream)
                let chunks = []

                recorder.ondataavailable = (e) => chunks.push(e.data)
                recorder.onstop = async () => {
                    setIsProcessing(true)
                    const blob = new Blob(chunks, { type: 'audio/webm' })
                    await processAudio(blob)
                    setIsProcessing(false)
                }

                recorder.start()
                setMediaRecorder(recorder)
                setIsRecording(true)
            } catch (err) {
                alert("Accès microphone refusé")
            }
        } else {
            mediaRecorder.stop()
            setIsRecording(false)
        }
    }

    const processAudio = async (audioBlob) => {
        const formData = new FormData()
        formData.append('file', audioBlob, 'recording.webm')

        try {
            const transRes = await fetch('/api/transcribe', { method: 'POST', body: formData })
            if (!transRes.ok) throw new Error("Transcription failed")

            const { transcription } = await transRes.json()
            const token = localStorage.getItem('token')
            const res = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
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

            const newScore = (user.points || user.score || 0) + (data.meta_analysis?.quality_score > 0.8 ? 15 : 10)
            updateUser({ score: newScore, points: newScore })

            if (data.meta_analysis?.quality_score >= 80) {
                confetti({ particleCount: 100, spread: 60, origin: { y: 0.6 }, colors: ['#D4AF37', '#FFFFFF'] })
            }

            loadHistory()
        } catch (e) {
            alert("Erreur : " + e.message)
        } finally {
            setIsProcessing(false)
        }
    }

    // Filter history by search
    const filteredHistory = searchQuery
        ? history.filter(h =>
            h.client?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            h.transcription?.toLowerCase().includes(searchQuery.toLowerCase())
        )
        : history

    // ═══════════════════════════════════════════════════════════════
    // RENDER
    // ═══════════════════════════════════════════════════════════════

    return (
        <div className="min-h-screen bg-[#0D1A2D] text-white flex">
            {/* LVMH Chevron Pattern Background */}
            <div className="lvmh-pattern" />

            {/* ═══ SIDEBAR ═══ */}
            <aside className="sidebar">
                {/* Logo */}
                <div className="mb-6 w-10 h-10 rounded-lg bg-gradient-to-br from-[#D4AF37] to-[#B8960C] flex items-center justify-center text-[#0D1A2D] font-bold">
                    L
                </div>

                {/* Nav items - Only 3 now */}
                <div className="flex-1 flex flex-col gap-1">
                    <button
                        onClick={() => setActiveView('record')}
                        className={`sidebar-item ${activeView === 'record' ? 'active' : ''}`}
                        title="Enregistrer"
                    >
                        <Mic size={20} strokeWidth={1.5} />
                    </button>
                    <button
                        onClick={() => setActiveView('stats')}
                        className={`sidebar-item ${activeView === 'stats' ? 'active' : ''}`}
                        title="Statistiques"
                    >
                        <Trophy size={20} strokeWidth={1.5} />
                    </button>
                    <button
                        onClick={() => setActiveView('history')}
                        className={`sidebar-item ${activeView === 'history' ? 'active' : ''}`}
                        title="Historique"
                    >
                        <History size={20} strokeWidth={1.5} />
                    </button>
                </div>

                {/* Logout */}
                <button onClick={handleLogout} className="sidebar-item hover:!text-red-400" title="Déconnexion">
                    <LogOut size={20} strokeWidth={1.5} />
                </button>
            </aside>

            {/* ═══ MAIN CONTENT ═══ */}
            <main className="flex-1 flex flex-col max-w-4xl mx-auto w-full p-8 relative z-10">

                {/* Header */}
                <header className="flex justify-between items-center mb-8">
                    <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-[#1D2E4A] to-[#152238] border border-white/10 flex items-center justify-center">
                            <User size={20} className="text-white/70" />
                        </div>
                        <div>
                            <div className="text-subtitle">{user.store || "CHAMPS-ÉLYSÉES"}</div>
                            <div className="text-lg font-medium">{user.name}</div>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="badge flex items-center gap-1.5">
                            <ThumbsUp size={12} className="text-green-400" />
                            <span>{stats.avgClarity}% clarté</span>
                        </div>
                        <div className="relative group">
                            <div className="absolute inset-0 bg-gradient-to-r from-[#D4AF37] to-[#E5C45C] rounded-lg blur-sm opacity-50 group-hover:opacity-75 transition-opacity" />
                            <div className="relative bg-gradient-to-r from-[#D4AF37] to-[#E5C45C] text-[#0D1A2D] font-semibold px-5 py-2 rounded-lg flex items-center gap-2">
                                <Star size={14} fill="#0D1A2D" />
                                <span style={{ fontFamily: "'Playfair Display', serif" }}>{stats.totalPoints}</span>
                                <span className="text-xs opacity-70">pts</span>
                            </div>
                        </div>
                    </div>
                </header>

                {/* Loading State */}
                {isProcessing && (
                    <div className="fixed inset-0 bg-[#0D1A2D]/95 z-50 flex flex-col items-center justify-center fade-in">
                        <div className="relative mb-6">
                            <div className="w-20 h-20 rounded-full border-2 border-[#D4AF37]/30 flex items-center justify-center">
                                <Mic size={32} className="text-[#D4AF37]" />
                            </div>
                            <div className="absolute inset-0 rounded-full border-2 border-[#D4AF37] border-t-transparent animate-spin" />
                        </div>
                        <div className="text-title text-xl mb-2">Analyse en cours</div>
                        <div className="text-body">Notre IA traite votre enregistrement...</div>
                    </div>
                )}

                {/* ═══════════════════════════════════════════════════════════════
                    RECORD VIEW - Clean, focused on the action
                ═══════════════════════════════════════════════════════════════ */}
                {activeView === 'record' && !currentResult && (
                    <div className="flex-1 flex items-center justify-center fade-in">
                        {/* Main Record Card - Contains Everything */}
                        <div className="card p-10 max-w-xl w-full text-center">
                            {/* Title */}
                            <h1 className="text-title text-4xl mb-2">
                                {isRecording ? "Enregistrement..." : "Nouvelle Note"}
                            </h1>
                            <p className="text-body mb-10">
                                {isRecording
                                    ? "Décrivez les préférences et besoins du client"
                                    : "Appuyez sur le micro pour capturer une note client"}
                            </p>

                            {/* Record Button */}
                            <div className="relative inline-block mb-10">
                                {isRecording && (
                                    <>
                                        <div className="absolute inset-[-32px] rounded-full bg-[#D4AF37]/5 animate-ping" style={{ animationDuration: '2s' }} />
                                        <div className="absolute inset-[-20px] rounded-full bg-[#D4AF37]/10" />
                                        <div className="absolute inset-[-10px] rounded-full bg-[#D4AF37]/15" />
                                    </>
                                )}
                                <button
                                    onClick={toggleRecord}
                                    className={`w-24 h-24 rounded-full flex items-center justify-center transition-all duration-300
                                        ${isRecording
                                            ? 'bg-[#D4AF37] text-[#0D1A2D] scale-110'
                                            : 'bg-transparent border-2 border-white/30 hover:border-[#D4AF37] hover:bg-[#D4AF37]/10'
                                        }`}
                                >
                                    <Mic size={36} strokeWidth={1.5} />
                                </button>
                            </div>

                            {/* Voice Wave */}
                            {isRecording && (
                                <div className="flex justify-center items-end gap-1 h-8 mb-8">
                                    {[...Array(16)].map((_, i) => (
                                        <div
                                            key={i}
                                            className="w-1 bg-gradient-to-t from-[#D4AF37] to-[#D4AF37]/50 rounded-full"
                                            style={{
                                                height: `${8 + Math.random() * 24}px`,
                                                animation: 'pulse 0.5s ease-in-out infinite',
                                                animationDelay: `${i * 0.05}s`
                                            }}
                                        />
                                    ))}
                                </div>
                            )}

                            {/* Stats Row - Inside Card */}
                            <div className="border-t border-white/10 pt-6 mt-6">
                                <div className="flex items-center justify-center gap-10">
                                    <div>
                                        <div className="text-2xl font-semibold text-white" style={{ fontFamily: "'Playfair Display', serif" }}>{stats.todayNotes}</div>
                                        <div className="text-caption">Aujourd'hui</div>
                                    </div>
                                    <div className="w-px h-10 bg-white/10" />
                                    <div>
                                        <div className="text-2xl font-semibold text-white" style={{ fontFamily: "'Playfair Display', serif" }}>{stats.weekNotes}</div>
                                        <div className="text-caption">Cette semaine</div>
                                    </div>
                                    <div className="w-px h-10 bg-white/10" />
                                    <div>
                                        <div className="text-2xl font-semibold text-[#D4AF37]" style={{ fontFamily: "'Playfair Display', serif" }}>Niv. {stats.level}</div>
                                        <div className="text-caption">{stats.nextLevel} pts → Niv. {stats.level + 1}</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* ═══════════════════════════════════════════════════════════════
                    RESULT VIEW
                ═══════════════════════════════════════════════════════════════ */}
                {currentResult && (
                    <div className="fixed inset-0 bg-[#0D1A2D] z-50 overflow-y-auto fade-in">
                        <div className="lvmh-pattern" />
                        <div className="max-w-2xl mx-auto p-8 relative z-10">
                            {/* Header */}
                            <div className="flex justify-between items-center mb-10">
                                <div>
                                    <div className="text-subtitle text-[#D4AF37] mb-1">ANALYSE COMPLÈTE</div>
                                    <h2 className="text-title">Résultat</h2>
                                </div>
                                <button onClick={() => setCurrentResult(null)} className="w-10 h-10 rounded-lg bg-white/5 hover:bg-white/10 flex items-center justify-center transition-all">
                                    <X size={20} />
                                </button>
                            </div>

                            {/* Score Card */}
                            <div className="card border-l-4 border-l-[#D4AF37] mb-6">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-4">
                                        <div className="w-14 h-14 rounded-xl bg-[#D4AF37]/10 flex items-center justify-center">
                                            <Sparkles size={24} className="text-[#D4AF37]" />
                                        </div>
                                        <div>
                                            <div className="text-subtitle">RÉCOMPENSE</div>
                                            <div className="text-lg font-medium">+{currentResult.meta_analysis?.quality_score > 0.8 ? 15 : 10} points</div>
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <div className="text-3xl font-bold text-[#D4AF37]">
                                            {Math.round((currentResult.meta_analysis?.quality_score || 0.8) * 100)}%
                                        </div>
                                        <div className="text-caption">Qualité</div>
                                    </div>
                                </div>
                            </div>

                            {/* Feedback */}
                            <div className="card mb-6">
                                <div className="text-subtitle mb-2">FEEDBACK IA</div>
                                <p className="text-body">
                                    {currentResult.meta_analysis?.advisor_feedback || "Note enregistrée avec succès !"}
                                </p>
                            </div>

                            {/* Transcription */}
                            <div className="card mb-6">
                                <div className="text-subtitle mb-2">TRANSCRIPTION</div>
                                <p className="text-body italic bg-white/5 p-4 rounded-lg">
                                    "{currentResult.processed_text || currentResult.original_text || "..."}"
                                </p>
                            </div>

                            {/* Tags */}
                            {currentResult.pilier_1_univers_produit?.categories && (
                                <div className="card mb-6">
                                    <div className="flex items-center gap-2 text-subtitle mb-3">
                                        <Tag size={14} /> TAGS EXTRAITS
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                        {currentResult.pilier_1_univers_produit.categories.map(tag => (
                                            <span key={tag} className="badge">{tag}</span>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Next Best Action */}
                            {currentResult.pilier_4_action_business?.next_best_action && (
                                <div className="card border-l-4 border-l-green-500 mb-8">
                                    <div className="flex items-center gap-2 text-subtitle text-green-400 mb-2">
                                        <Gift size={14} /> ACTION RECOMMANDÉE
                                    </div>
                                    <p className="text-body">
                                        {currentResult.pilier_4_action_business.next_best_action?.description}
                                    </p>
                                </div>
                            )}

                            <button
                                onClick={() => setCurrentResult(null)}
                                className="btn-primary w-full flex items-center justify-center gap-2"
                            >
                                <CheckCircle size={18} />
                                Continuer
                            </button>
                        </div>
                    </div>
                )}

                {/* ═══════════════════════════════════════════════════════════════
                    STATS VIEW - Gamification
                ═══════════════════════════════════════════════════════════════ */}
                {activeView === 'stats' && (
                    <div className="flex-1 fade-in">
                        <h2 className="text-title mb-8">Vos Statistiques</h2>

                        {/* Level Progress */}
                        <div className="card mb-6">
                            <div className="flex items-center justify-between mb-4">
                                <div className="flex items-center gap-4">
                                    <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-[#D4AF37] to-[#B8960C] flex items-center justify-center text-[#0D1A2D] text-2xl font-bold">
                                        {stats.level}
                                    </div>
                                    <div>
                                        <div className="text-xl font-semibold">Niveau {stats.level}</div>
                                        <div className="text-body">{stats.nextLevel} pts pour le niveau suivant</div>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="text-3xl font-bold text-[#D4AF37]">{stats.totalPoints}</div>
                                    <div className="text-caption">Points totaux</div>
                                </div>
                            </div>
                            {/* Progress bar */}
                            <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-gradient-to-r from-[#D4AF37] to-[#E5C45C] rounded-full transition-all duration-500"
                                    style={{ width: `${((100 - stats.nextLevel) / 100) * 100}%` }}
                                />
                            </div>
                        </div>

                        {/* Stats Grid */}
                        <div className="grid grid-cols-3 gap-4 mb-8">
                            <div className="card text-center">
                                <div className="w-12 h-12 mx-auto mb-3 rounded-xl bg-green-500/10 flex items-center justify-center">
                                    <ThumbsUp size={24} className="text-green-400" />
                                </div>
                                <div className="text-2xl font-bold">{stats.avgClarity}%</div>
                                <div className="text-caption">Clarté moyenne</div>
                            </div>
                            <div className="card text-center">
                                <div className="w-12 h-12 mx-auto mb-3 rounded-xl bg-[#D4AF37]/10 flex items-center justify-center">
                                    <Star size={24} className="text-[#D4AF37]" />
                                </div>
                                <div className="text-2xl font-bold">{stats.bestNote}%</div>
                                <div className="text-caption">Meilleure note</div>
                            </div>
                            <div className="card text-center">
                                <div className="w-12 h-12 mx-auto mb-3 rounded-xl bg-purple-500/10 flex items-center justify-center">
                                    <Zap size={24} className="text-purple-400" />
                                </div>
                                <div className="text-2xl font-bold">{stats.highQualityNotes}</div>
                                <div className="text-caption">Notes 80%+</div>
                            </div>
                        </div>

                        {/* Achievements */}
                        <div className="mb-8">
                            <div className="text-subtitle mb-4">SUCCÈS</div>
                            <div className="grid grid-cols-2 gap-3">
                                {achievements.map(ach => (
                                    <div
                                        key={ach.id}
                                        className={`card flex items-center gap-4 ${ach.unlocked ? '' : 'opacity-40'}`}
                                    >
                                        <div className={`w-12 h-12 rounded-xl ${ach.unlocked ? 'bg-white/10' : 'bg-white/5'} flex items-center justify-center`}>
                                            <ach.icon size={22} className={ach.unlocked ? ach.color : 'text-white/30'} />
                                        </div>
                                        <div>
                                            <div className="font-medium flex items-center gap-2">
                                                {ach.name}
                                                {ach.unlocked && <CheckCircle size={14} className="text-green-400" />}
                                            </div>
                                            <div className="text-caption">{ach.desc}</div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Leaderboard */}
                        <div>
                            <div className="text-subtitle mb-4">CLASSEMENT MAGASIN</div>
                            <div className="card">
                                <div className="space-y-2">
                                    {leaderboard.map((adv, i) => (
                                        <div
                                            key={i}
                                            className={`flex justify-between items-center p-3 rounded-lg transition-all ${adv.isMe
                                                ? 'bg-[#D4AF37]/10 border border-[#D4AF37]/20'
                                                : 'hover:bg-white/5'
                                                }`}
                                        >
                                            <span className="flex items-center gap-3">
                                                <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold ${i === 0 ? 'bg-[#D4AF37] text-[#0D1A2D]' :
                                                    i === 1 ? 'bg-gray-400 text-[#0D1A2D]' :
                                                        i === 2 ? 'bg-amber-700 text-white' :
                                                            'bg-white/10'
                                                    }`}>
                                                    {i + 1}
                                                </span>
                                                <span className="font-medium">{adv.id}</span>
                                                {adv.isMe && <span className="text-[10px] text-[#D4AF37] font-medium px-2 py-0.5 bg-[#D4AF37]/10 rounded">VOUS</span>}
                                            </span>
                                            <span className="font-semibold">{adv.score} pts</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                )
                }

                {/* ═══════════════════════════════════════════════════════════════
                    HISTORY VIEW - With integrated search
                ═══════════════════════════════════════════════════════════════ */}
                {
                    activeView === 'history' && (
                        <div className="flex-1 fade-in">
                            <div className="flex items-center justify-between mb-6">
                                <h2 className="text-title">Historique</h2>
                                <div className="badge">{history.length} notes</div>
                            </div>

                            {/* Integrated Search */}
                            <div className="card p-4 mb-6">
                                <div className="relative">
                                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-[#718096]" size={18} />
                                    <input
                                        type="text"
                                        placeholder="Rechercher par client ou contenu..."
                                        className="input pl-12"
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                    />
                                </div>
                            </div>

                            {loadingHistory ? (
                                <div className="flex justify-center py-12">
                                    <div className="spinner-white" />
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {filteredHistory.length > 0 ? filteredHistory.map((note, idx) => (
                                        <div key={note.id || idx} className="card hover:border-[#D4AF37]/30 transition-all cursor-pointer group">
                                            <div className="flex items-start gap-4">
                                                {/* Avatar */}
                                                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#1D2E4A] to-[#152238] border border-white/10 flex items-center justify-center flex-shrink-0">
                                                    <User size={18} className="text-white/50" />
                                                </div>

                                                {/* Content */}
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center justify-between mb-2">
                                                        <div className="flex items-center gap-3">
                                                            <span className="font-medium">{note.client || 'Client Inconnu'}</span>
                                                            {note.vic_status && note.vic_status !== 'Standard' && (
                                                                <span className="badge text-[10px] py-0.5 bg-[#D4AF37]/10 text-[#D4AF37]">{note.vic_status}</span>
                                                            )}
                                                        </div>
                                                        <span className="text-caption flex items-center gap-1">
                                                            <Clock size={12} />
                                                            {new Date(note.date).toLocaleDateString('fr-FR')}
                                                        </span>
                                                    </div>
                                                    <p className="text-body line-clamp-2 mb-3">"{note.transcription}"</p>

                                                    {/* Tags & Points */}
                                                    <div className="flex items-center justify-between">
                                                        <div className="flex gap-2">
                                                            {(note.tags || []).slice(0, 3).map((tag, i) => (
                                                                <span key={i} className="badge text-[10px] py-0.5">{tag}</span>
                                                            ))}
                                                        </div>
                                                        <span className="text-sm font-semibold text-[#D4AF37] group-hover:scale-110 transition-transform">
                                                            +{note.points || 10} pts
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    )) : searchQuery ? (
                                        <div className="card text-center py-12">
                                            <Search size={40} className="mx-auto mb-4 text-white/20" />
                                            <div className="text-lg font-medium mb-2">Aucun résultat</div>
                                            <div className="text-body">Aucune note trouvée pour "{searchQuery}"</div>
                                        </div>
                                    ) : (
                                        <div className="card text-center py-12">
                                            <History size={40} className="mx-auto mb-4 text-white/20" />
                                            <div className="text-lg font-medium mb-2">Aucun enregistrement</div>
                                            <div className="text-body">Commencez par créer une note client</div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    )
                }
            </main >
        </div >
    )
}
