import React, { useState, useEffect } from 'react'
import { ArrowLeft, Mic, Search, Trophy, X, CheckCircle } from 'lucide-react'
import confetti from 'canvas-confetti'

export default function AdvisorView({ onBack }) {
    const [user] = useState({ name: "Aurélie Dupont", score: 245 })
    const [isRecording, setIsRecording] = useState(false)
    const [currentResult, setCurrentResult] = useState(null)
    const [leaderboard, setLeaderboard] = useState([])
    const [searchQuery, setSearchQuery] = useState("")

    useEffect(() => {
        fetchLeaderboard()
    }, [])

    const fetchLeaderboard = async () => {
        try {
            const res = await fetch('/api/leaderboard')
            const data = await res.json()
            setLeaderboard(data)
        } catch (e) { }
    }

    const toggleRecord = async () => {
        setIsRecording(!isRecording)
        if (isRecording) {
            // Simulating ingestion process
            const mockNotes = [
                "Mme Dupont cherche un sac rouge pour son anniversaire demain.",
                "M. Martin veut voir les nouvelles montres, il a un gros budget.",
                "Mlle Lopez s'intéresse au cuir exotique pour un cadeau."
            ]
            const text = mockNotes[Math.floor(Math.random() * mockNotes.length)]

            try {
                const res = await fetch('/ingest', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        transcription: text,
                        advisor_id: "CA_001",
                        store_id: "PARIS_RIVOLI"
                    })
                })
                const data = await res.json()
                setCurrentResult(data.data)
                if (data.data.meta_analysis.quality_score >= 80) {
                    confetti({
                        particleCount: 150,
                        spread: 70,
                        origin: { y: 0.6 },
                        colors: ['#D4AF37', '#ffffff']
                    })
                }
            } catch (e) {
                alert("Erreur API (Vérifiez qu'uvicorn est lancé)")
            }
        }
    }

    return (
        <div className="max-w-md mx-auto min-h-screen flex flex-col p-6 bg-lvmh-black text-white">
            <div className="flex justify-between items-center mb-6">
                <button onClick={onBack} className="p-2 -ml-2 hover:text-lvmh-gold transition-colors"><ArrowLeft size={24} /></button>
                <div className="text-center">
                    <div className="text-[10px] text-lvmh-gold uppercase tracking-tighter">LVMH Paris Rivoli</div>
                    <div className="font-bold text-sm">{user.name}</div>
                </div>
                <div className="glass px-3 py-1 text-sm font-bold text-lvmh-gold">{user.score} pts</div>
            </div>

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
                    <h2 className="gold-text text-3xl font-bold mb-2">
                        {isRecording ? "À l'écoute..." : "Dictée Client"}
                    </h2>
                    <p className="text-lvmh-gray mb-12">Décrivez l'interaction en quelques secondes</p>

                    <button onClick={toggleRecord} className="btn-record mb-16">
                        <Mic size={48} className={isRecording ? "animate-pulse text-white" : "text-white"} />
                    </button>

                    <div className="glass w-full p-5">
                        <div className="flex items-center gap-2 text-lvmh-gold text-xs font-bold uppercase mb-4 tracking-widest leading-none">
                            <Trophy size={14} /> Leaderboard Live
                        </div>
                        <div className="space-y-3">
                            {leaderboard.slice(0, 3).map((adv, i) => (
                                <div key={adv.id} className="flex justify-between py-2 border-b border-white/5 last:border-0 items-center">
                                    <span className="text-sm font-medium">{i + 1}. {adv.id}</span>
                                    <span className="font-bold text-sm text-lvmh-gold">{adv.score} pts</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            ) : (
                <div className="fixed inset-0 bg-lvmh-black z-50 p-6 overflow-y-auto animate-in slide-in-from-bottom duration-500">
                    <div className="flex justify-between items-center mb-8">
                        <h2 className="gold-text text-3xl font-bold">Expertise IA</h2>
                        <button onClick={() => setCurrentResult(null)} className="p-2"><X size={32} /></button>
                    </div>

                    <div className="glass p-5 border-l-4 border-lvmh-gold mb-8 bg-lvmh-gold/5">
                        <div className="text-xs text-lvmh-gold font-bold mb-1 uppercase tracking-widest">Récompense</div>
                        <div className="text-lg font-bold leading-tight">{currentResult.meta_analysis?.advisor_feedback || "Note traitée !"}</div>
                    </div>

                    <div className="mb-10">
                        <div className="text-[10px] text-lvmh-gray uppercase tracking-widest mb-2 font-bold">Profil Extrait</div>
                        <div className="flex items-center gap-3 mb-4">
                            <span className="text-2xl font-bold">{currentResult.ID}</span>
                            <span className="bg-lvmh-gold text-black text-[10px] font-black px-2 py-0.5 rounded-full shadow-lg">VIP</span>
                        </div>

                        <div className="flex flex-wrap gap-2">
                            {currentResult.pilier_1_univers_produit?.categories?.map(tag => (
                                <span key={tag} className="bg-white/10 px-3 py-1 rounded-full text-xs font-medium border border-white/5">{tag}</span>
                            ))}
                        </div>
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

                    <button className="w-full bg-lvmh-gold text-black font-black py-4 rounded-xl hover:bg-lvmh-gold/90 transition-all shadow-[0_15px_40px_rgba(212,175,55,0.3)] flex items-center justify-center gap-2 uppercase tracking-widest">
                        <CheckCircle size={20} aria-hidden="true" />
                        Planifier Action
                    </button>
                </div>
            )}
        </div>
    )
}
