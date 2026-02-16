import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
    AlertTriangle,
    CheckCircle,
    Database,
    Loader2,
    ShieldCheck,
    ShoppingBag,
    Trophy,
    Wifi,
    WifiOff,
    Zap,
    Clock,
    User,
    Building2,
    Tag,
    Package,
    MessageSquare,
    ChevronRight,
    Circle,
    Activity
} from 'lucide-react'

const STEPS = [
    { id: 'cleaning', name: 'Cleaning', icon: Loader2, description: 'Nettoyage texte' },
    { id: 'rgpd', name: 'RGPD', icon: ShieldCheck, description: 'Filtrage donnees' },
    { id: 'routing', name: 'Routing', icon: Zap, description: 'Tier decision' },
    { id: 'extraction', name: 'Extraction', icon: Database, description: 'Taxonomie' },
    { id: 'rag', name: 'RAG', icon: ShoppingBag, description: 'Produits' },
    { id: 'nba', name: 'NBA', icon: Trophy, description: 'Recommandation' }
]

const normalizeStep = (step) => {
    const raw = String(step || '').toLowerCase()
    if (!raw) return null
    if (raw === 'failed' || raw.includes('error')) return 'failed'
    if (raw === 'done' || raw === 'cache_hit' || raw === 'semantic_cache_hit') return 'done'
    if (raw === 'cleaning') return 'cleaning'
    if (raw === 'rgpd') return 'rgpd'
    if (raw === 'routing') return 'routing'
    if (raw.includes('tier') || raw === 'cross_validation' || raw === 'extraction') return 'extraction'
    if (raw === 'rag') return 'rag'
    if (raw === 'injection' || raw === 'nba') return 'nba'
    return raw
}

const normalizeScore = (value) => {
    if (value === null || value === undefined || Number.isNaN(value)) return 0
    return value <= 1 ? value * 100 : value
}

const getStepIndex = (normalizedStep) => {
    const map = {
        'cleaning': 0,
        'rgpd': 1,
        'routing': 2,
        'extraction': 3,
        'tier1_extraction': 3,
        'tier2_extraction': 3,
        'tier3_extraction': 3,
        'rag': 4,
        'nba': 5,
        'done': 5
    }
    return map[normalizedStep] ?? -1
}

const formatTime = (ms) => {
    if (!ms) return '-'
    if (ms < 1000) return `${Math.round(ms)}ms`
    return `${(ms / 1000).toFixed(2)}s`
}

const formatProgressHint = (normalizedStep, progress) => {
    if (!progress) return null

    if (normalizedStep === 'cleaning') {
        if (progress.tokens_saved !== undefined) return `${progress.tokens_saved} tokens nettoyés`
        if (progress.status) return String(progress.status)
        return null
    }
    if (normalizedStep === 'rgpd') {
        if (progress.contains_sensitive !== undefined) {
            return progress.contains_sensitive ? '⚠ Données sensibles' : '✓ Conforme'
        }
        if (progress.categories_detected?.length) return progress.categories_detected.join(', ')
        return 'En cours...'
    }
    if (normalizedStep === 'routing') {
        const details = []
        if (progress.tier !== undefined) details.push(`Tier ${progress.tier}`)
        if (progress.score) details.push(`Score ${progress.score}`)
        if (progress.priority) details.push(String(progress.priority))
        if (progress.engine) details.push(progress.engine)
        return details.length ? details.join(' | ') : null
    }
    if (normalizedStep === 'extraction') {
        const details = []
        if (progress.tag_count !== undefined) details.push(`${progress.tag_count} tags`)
        if (progress.model) details.push(String(progress.model))
        if (progress.progress_percent !== undefined) details.push(`${progress.progress_percent}%`)
        return details.length ? details.join(' | ') : null
    }
    if (normalizedStep === 'rag') {
        if (progress.matches !== undefined) return `${progress.matches} produits matchés`
        if (progress.best_score) return `Meilleur score: ${Math.round(progress.best_score * 100)}%`
        if (progress.status) return String(progress.status)
        return null
    }
    if (normalizedStep === 'nba') {
        const details = []
        if (progress.points !== undefined) details.push(`+${progress.points} pts`)
        if (progress.quality_score) details.push(`Qualite ${progress.quality_score}`)
        return details.length ? details.join(' | ') : null
    }
    if (normalizedStep === 'failed') {
        return progress.error ? String(progress.error) : 'Echec pipeline'
    }
    return null
}

export default function PipelineVisualizer({
    isProcessing,
    currentStep,
    result,
    progress = null,
    connectionState = null,
    elapsedMs = 0,
    inputData = null
}) {
    const [activeStepIndex, setActiveStepIndex] = useState(-1)
    const [showDetails, setShowDetails] = useState(true)

    const normalizedStep = normalizeStep(currentStep)

    useEffect(() => {
        setActiveStepIndex(getStepIndex(normalizedStep))
    }, [normalizedStep])

    const progressHint = formatProgressHint(normalizedStep, progress)
    const qualityScore = normalizeScore(result?.meta_analysis?.quality_score ?? progress?.quality_score)
    const scoreLabel = qualityScore > 0 ? `${qualityScore.toFixed(0)}%` : '-'

    const extraction = result?.extraction
    const tags = extraction?.tags || []
    const pilier1 = extraction?.pilier_1_univers_produit || {}
    const pilier2 = extraction?.pilier_2_profil_client || {}
    const pilier3 = extraction?.pilier_3_hospitalite_care || {}
    const pilier4 = extraction?.pilier_4_action_business || {}
    const nba = pilier4?.next_best_action || result?.next_best_action
    const rgpd = result?.rgpd || progress
    const routing = result?.routing || progress
    const matchedProducts = pilier1?.matched_products || []

    const timings = result?.stage_timings_ms || {}

    let processingLabel = null
    if (normalizedStep === 'failed') {
        processingLabel = 'ECHEC'
    } else if (isProcessing) {
        processingLabel = elapsedMs > 0 ? `${(elapsedMs / 1000).toFixed(1)}s` : 'EN COURS'
    } else if (result?.processing_time_ms) {
        processingLabel = `${(result.processing_time_ms / 1000).toFixed(1)}s`
    }

    if (!isProcessing && !result && !progress) return null

    return (
        <div className="space-y-4">
            {/* Header avec timeline */}
            <div className="glass p-4 rounded-xl border border-white/10">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lvmh-gold font-bold flex items-center gap-2">
                        <Activity size={18} className={isProcessing ? 'animate-pulse' : ''} />
                        Pipeline IA V3.0
                    </h3>
                    <div className="flex items-center gap-2">
                        {connectionState && (
                            <div className={`text-[10px] px-2 py-1 rounded-full border inline-flex items-center gap-1 ${
                                connectionState === 'connected' ? 'border-green-500/40 text-green-400 bg-green-500/10' : 
                                connectionState === 'connecting' ? 'border-lvmh-gold/40 text-lvmh-gold bg-lvmh-gold/10' : 
                                'border-red-500/40 text-red-400 bg-red-500/10'
                            }`}>
                                {connectionState === 'connected' ? <Wifi size={11} /> : <WifiOff size={11} />}
                                {connectionState === 'connected' ? 'WS OK' : connectionState === 'connecting' ? 'WS CONNECT' : 'WS OFF'}
                            </div>
                        )}
                        {processingLabel && (
                            <div className={`text-[10px] px-2 py-1 rounded-full font-bold ${
                                normalizedStep === 'failed' ? 'bg-red-500/20 text-red-400' : 'bg-lvmh-gold/20 text-lvmh-gold'
                            }`}>
                                {processingLabel}
                            </div>
                        )}
                    </div>
                </div>

                {/* Timeline horizontale */}
                <div className="flex items-center justify-between gap-1 overflow-x-auto pb-2">
                    {STEPS.map((step, index) => {
                        const isActive = index === activeStepIndex
                        const isCompleted = index < activeStepIndex || normalizedStep === 'done'
                        const Icon = step.icon
                        const stepTime = timings[step.id] || timings[step.id.replace('extraction', 'tier')] || null

                        return (
                            <div key={step.id} className="flex flex-col items-center min-w-[80px]">
                                <div className={`w-10 h-10 rounded-full flex items-center justify-center transition-all ${
                                    isCompleted ? 'bg-lvmh-gold text-black' : 
                                    isActive ? 'bg-white text-black animate-pulse shadow-lg shadow-lvmh-gold/30' : 
                                    'bg-white/10 text-gray-500'
                                }`}>
                                    {isCompleted ? <CheckCircle size={16} /> : <Icon size={16} />}
                                </div>
                                <div className={`text-[10px] mt-2 text-center ${isActive ? 'text-white font-bold' : isCompleted ? 'text-lvmh-gold' : 'text-gray-500'}`}>
                                    {step.name}
                                </div>
                                {stepTime && (
                                    <div className="text-[9px] text-lvmh-gray">{formatTime(stepTime)}</div>
                                )}
                            </div>
                        )
                    })}
                </div>

                {/* Progress hint */}
                {progressHint && isProcessing && (
                    <div className="mt-3 text-center text-xs text-lvmh-gold/70">
                        {progressHint}
                    </div>
                )}
            </div>

            {/* Grid: Input + Details + Result */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {/* Colonne 1: Input */}
                <div className="glass p-4 rounded-xl border border-white/10">
                    <h4 className="text-xs uppercase tracking-widest text-lvmh-gray mb-3 flex items-center gap-2">
                        <User size={14} /> Input
                    </h4>
                    {inputData ? (
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <span className="text-xs text-lvmh-gray">Client</span>
                                <span className="text-sm font-semibold">{inputData.clientName || 'Inconnu'}</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-xs text-lvmh-gray">Store</span>
                                <span className="text-sm">{inputData.store || 'N/A'}</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-xs text-lvmh-gray">Advisor</span>
                                <span className="text-sm">{inputData.advisor || 'N/A'}</span>
                            </div>
                            <div className="border-t border-white/10 pt-2 mt-2">
                                <span className="text-[10px] text-lvmh-gray uppercase">Transcription</span>
                                <div className="text-xs text-lvmh-gray mt-1 line-clamp-4 bg-white/5 p-2 rounded">
                                    "{inputData.transcription || '...'}"
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="text-xs text-lvmh-gray italic">
                            En attente d'une note...
                        </div>
                    )}
                </div>

                {/* Colonne 2: Details */}
                <div className="glass p-4 rounded-xl border border-white/10">
                    <h4 className="text-xs uppercase tracking-widest text-lvmh-gray mb-3 flex items-center gap-2">
                        <Database size={14} /> Details
                    </h4>
                    
                    <div className="space-y-3">
                        {/* RGPD */}
                        <div className="bg-white/5 rounded-lg p-2">
                            <div className="flex items-center justify-between">
                                <span className="text-[10px] uppercase text-lvmh-gray">RGPD</span>
                                <span className={`text-xs font-bold ${rgpd?.contains_sensitive ? 'text-red-400' : 'text-green-400'}`}>
                                    {rgpd?.contains_sensitive ? '⚠ Sensible' : '✓ Conforme'}
                                </span>
                            </div>
                            {rgpd?.categories_detected?.length > 0 && (
                                <div className="text-[9px] text-red-300 mt-1">
                                    {rgpd.categories_detected.join(', ')}
                                </div>
                            )}
                        </div>

                        {/* Routing */}
                        <div className="bg-white/5 rounded-lg p-2">
                            <div className="flex items-center justify-between">
                                <span className="text-[10px] uppercase text-lvmh-gray">Routing</span>
                                <span className={`text-xs font-bold ${
                                    routing?.tier === 3 ? 'text-red-400' : 
                                    routing?.tier === 2 ? 'text-lvmh-gold' : 'text-gray-400'
                                }`}>
                                    Tier {routing?.tier || 1}
                                </span>
                            </div>
                            {routing?.score && (
                                <div className="text-[9px] text-lvmh-gray mt-1">
                                    Score: {routing.score} | {routing.priority}
                                </div>
                            )}
                            {routing?.engine && (
                                <div className="text-[9px] text-lvmh-gold">
                                    Moteur: {routing.engine}
                                </div>
                            )}
                        </div>

                        {/* Extraction */}
                        <div className="bg-white/5 rounded-lg p-2">
                            <div className="flex items-center justify-between">
                                <span className="text-[10px] uppercase text-lvmh-gray">Extraction</span>
                                <span className="text-xs font-bold text-white">{tags.length} tags</span>
                            </div>
                            <div className="text-[9px] text-lvmh-gray mt-1">
                                Confiance: {scoreLabel}
                            </div>
                        </div>

                        {/* RAG */}
                        <div className="bg-white/5 rounded-lg p-2">
                            <div className="flex items-center justify-between">
                                <span className="text-[10px] uppercase text-lvmh-gray">RAG</span>
                                <span className="text-xs font-bold text-white">{matchedProducts.length} produits</span>
                            </div>
                            {matchedProducts.length > 0 && (
                                <div className="text-[9px] text-lvmh-gray mt-1 truncate">
                                    Best: {matchedProducts[0]?.name || 'N/A'}
                                </div>
                            )}
                        </div>

                        {/* Quality Gate */}
                        <div className="bg-white/5 rounded-lg p-2">
                            <div className="flex items-center justify-between">
                                <span className="text-[10px] uppercase text-lvmh-gray">Quality Gate</span>
                                <span className={`text-xs font-bold ${
                                    result?.quality_gate_passed !== false ? 'text-green-400' : 'text-red-400'
                                }`}>
                                    {result?.quality_gate_passed !== false ? '✓ PASS' : '✗ FAIL'}
                                </span>
                            </div>
                            {result?.quality_gate_reason && (
                                <div className="text-[9px] text-red-300 mt-1 truncate">
                                    {result.quality_gate_reason}
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Colonne 3: Result */}
                <div className="glass p-4 rounded-xl border border-white/10">
                    <h4 className="text-xs uppercase tracking-widest text-lvmh-gray mb-3 flex items-center gap-2">
                        <Trophy size={14} /> Resultat
                    </h4>

                    {/* Score + Points */}
                    <div className="flex items-center gap-4 mb-4">
                        <div className="flex-1 bg-white/5 rounded-lg p-3 text-center">
                            <div className="text-[10px] uppercase text-lvmh-gray">Qualite</div>
                            <div className="text-2xl font-bold text-lvmh-gold">{scoreLabel}</div>
                        </div>
                        <div className="flex-1 bg-white/5 rounded-lg p-3 text-center">
                            <div className="text-[10px] uppercase text-lvmh-gray">Points</div>
                            <div className="text-2xl font-bold text-green-400">+{progress?.points || 0}</div>
                        </div>
                    </div>

                    {/* Tags */}
                    {tags.length > 0 && (
                        <div className="mb-4">
                            <div className="text-[10px] uppercase text-lvmh-gray mb-2 flex items-center gap-1">
                                <Tag size={10} /> Tags ({tags.length})
                            </div>
                            <div className="flex flex-wrap gap-1">
                                {tags.slice(0, 8).map((tag, i) => (
                                    <span key={i} className="text-[9px] bg-lvmh-gold/20 text-lvmh-gold px-2 py-0.5 rounded-full">
                                        {tag}
                                    </span>
                                ))}
                                {tags.length > 8 && (
                                    <span className="text-[9px] text-lvmh-gray">+{tags.length - 8}</span>
                                )}
                            </div>
                        </div>
                    )}

                    {/* 4 Piliers summary */}
                    <div className="space-y-2 mb-4">
                        <div className="text-[10px] uppercase text-lvmh-gray">4 Piliers</div>
                        <div className="grid grid-cols-2 gap-2 text-[10px]">
                            <div className="bg-white/5 p-2 rounded">
                                <span className="text-lvmh-gray">Produit:</span> {pilier1?.categories?.[0] || '-'}
                            </div>
                            <div className="bg-white/5 p-2 rounded">
                                <span className="text-lvmh-gray">Client:</span> {pilier2?.purchase_context?.type || '-'}
                            </div>
                            <div className="bg-white/5 p-2 rounded">
                                <span className="text-lvmh-gray">Care:</span> {pilier3?.occasion || '-'}
                            </div>
                            <div className="bg-white/5 p-2 rounded">
                                <span className="text-lvmh-gray">Budget:</span> {pilier4?.budget_potential || '-'}
                            </div>
                        </div>
                    </div>

                    {/* NBA */}
                    {nba?.description && (
                        <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-3">
                            <div className="text-[10px] uppercase text-green-400 mb-1 flex items-center gap-1">
                                <Zap size={10} /> Next Best Action
                            </div>
                            <div className="text-xs text-green-300/80 line-clamp-3">
                                {nba.description}
                            </div>
                        </div>
                    )}

                    {/* Feedback */}
                    {progress?.feedback && (
                        <div className="mt-3 text-[10px] text-lvmh-gray italic">
                            "{progress.feedback}"
                        </div>
                    )}
                </div>
            </div>

            {/* Error display */}
            <AnimatePresence>
                {normalizedStep === 'failed' && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="glass p-4 rounded-xl border border-red-500/30 bg-red-500/10"
                    >
                        <div className="flex items-center gap-2 text-red-400">
                            <AlertTriangle size={18} />
                            <span className="font-bold">Erreur Pipeline</span>
                        </div>
                        <div className="text-xs text-red-300 mt-2">
                            {progress?.error || 'Une erreur est survenue durant le traitement.'}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Matched Products */}
            <AnimatePresence>
                {matchedProducts.length > 0 && normalizedStep === 'done' && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="glass p-4 rounded-xl border border-white/10"
                    >
                        <h4 className="text-xs uppercase tracking-widest text-lvmh-gray mb-3 flex items-center gap-2">
                            <Package size={14} /> Produits Recommandes ({matchedProducts.length})
                        </h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                            {matchedProducts.slice(0, 6).map((product, i) => (
                                <div key={i} className="bg-white/5 p-3 rounded-lg border border-white/5">
                                    <div className="text-sm font-semibold text-lvmh-gold">{product.name || product.ID}</div>
                                    <div className="text-[10px] text-lvmh-gray uppercase">{product.category || 'Produit'}</div>
                                    {product.match_score && (
                                        <div className="text-[10px] text-lvmh-gold mt-1">
                                            Score: {Math.round(product.match_score * 100)}%
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}
