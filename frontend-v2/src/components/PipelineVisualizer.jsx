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
    Zap
} from 'lucide-react'

const STEPS = [
    { id: 'cleaning', name: 'Data Cleaning', icon: Loader2 },
    { id: 'routing', name: 'Smart Routing', icon: Zap },
    { id: 'extraction', name: 'Taxonomy Extraction', icon: Database },
    { id: 'rag', name: 'RAG Matching', icon: ShoppingBag },
    { id: 'nba', name: 'CRM Insights', icon: Trophy }
]

const normalizeStep = (step) => {
    const raw = String(step || '').toLowerCase()
    if (!raw) return null
    if (raw === 'failed' || raw.includes('error')) return 'failed'
    if (raw === 'done' || raw === 'cache_hit' || raw === 'semantic_cache_hit') return 'done'
    if (raw === 'cleaning' || raw === 'rgpd') return 'cleaning'
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

const formatProgressHint = (normalizedStep, progress) => {
    if (!progress) return null

    if (normalizedStep === 'cleaning') {
        if (progress.tokens_saved !== undefined) return `${progress.tokens_saved} tokens nettoyes`
        if (progress.status) return String(progress.status)
        return null
    }
    if (normalizedStep === 'routing') {
        const details = []
        if (progress.tier !== undefined) details.push(`Tier ${progress.tier}`)
        if (progress.score) details.push(`Score ${progress.score}`)
        if (progress.priority) details.push(String(progress.priority))
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
        if (progress.matches !== undefined) return `${progress.matches} matchs`
        if (progress.status) return String(progress.status)
        return null
    }
    if (normalizedStep === 'nba') {
        const details = []
        if (progress.points !== undefined) details.push(`+${progress.points} pts`)
        if (progress.quality_score) details.push(String(progress.quality_score))
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
    elapsedMs = 0
}) {
    const [activeStepIndex, setActiveStepIndex] = useState(-1)

    const normalizedStep = normalizeStep(currentStep)

    useEffect(() => {
        if (normalizedStep === 'cleaning') setActiveStepIndex(0)
        else if (normalizedStep === 'routing') setActiveStepIndex(1)
        else if (normalizedStep === 'extraction') setActiveStepIndex(2)
        else if (normalizedStep === 'rag') setActiveStepIndex(3)
        else if (normalizedStep === 'nba' || normalizedStep === 'done') setActiveStepIndex(STEPS.length - 1)
        else if (!isProcessing) setActiveStepIndex(-1)
    }, [normalizedStep, isProcessing])

    const progressHint = formatProgressHint(normalizedStep, progress)
    const qualityScore = normalizeScore(result?.meta_analysis?.quality_score ?? progress?.quality_score)
    const scoreLabel = qualityScore > 0 ? `${qualityScore.toFixed(0)}%` : '-'
    const recommendation = result?.pilier_4_action_business?.next_best_action?.description || '-'

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
        <div className="w-full bg-black/40 backdrop-blur-xl rounded-2xl sm:rounded-3xl p-4 sm:p-6 border border-white/10 shadow-2xl overflow-hidden relative">
            <div className="flex flex-wrap justify-between items-start gap-3 mb-6 sm:mb-8">
                <div>
                    <h3 className="text-lvmh-gold font-bold text-base sm:text-lg flex items-center gap-2">
                        <Zap size={18} className={isProcessing ? 'animate-pulse' : ''} />
                        Pipeline IA V3.0
                    </h3>
                    <p className="text-[10px] text-lvmh-gray uppercase tracking-widest mt-1">Traitement cognitif temps reel</p>
                </div>
                <div className="flex flex-col items-end gap-2">
                    {connectionState && (
                        <div className={`text-[10px] px-2 py-1 rounded-full border inline-flex items-center gap-1.5 ${connectionState === 'connected' ? 'border-green-500/40 text-green-400 bg-green-500/10' : connectionState === 'connecting' ? 'border-lvmh-gold/40 text-lvmh-gold bg-lvmh-gold/10' : 'border-red-500/40 text-red-400 bg-red-500/10'}`}>
                            {connectionState === 'connected' ? <Wifi size={11} /> : <WifiOff size={11} />}
                            {connectionState === 'connected' ? 'WS OK' : connectionState === 'connecting' ? 'WS CONNECT' : 'WS OFF'}
                        </div>
                    )}
                    {processingLabel && (
                        <div className={`text-[10px] px-2 py-1 rounded-full font-bold ${normalizedStep === 'failed' ? 'bg-red-500/20 text-red-400' : 'bg-lvmh-gold/20 text-lvmh-gold'}`}>
                            {processingLabel}
                        </div>
                    )}
                </div>
            </div>

            <div className="relative space-y-4 sm:space-y-6">
                <div className="absolute left-[15px] sm:left-[19px] top-2 bottom-2 w-[2px] bg-white/5 z-0" />
                <div
                    className="absolute left-[15px] sm:left-[19px] top-2 w-[2px] bg-lvmh-gold z-0 transition-all duration-500"
                    style={{ height: `${Math.max(0, (activeStepIndex / (STEPS.length - 1)) * 100)}%` }}
                />

                {STEPS.map((step, index) => {
                    const isActive = index === activeStepIndex
                    const isCompleted = index < activeStepIndex || normalizedStep === 'done'
                    const Icon = step.icon

                    return (
                        <motion.div
                            key={step.id}
                            initial={{ opacity: 0, x: -18 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: index * 0.08 }}
                            className={`relative z-10 flex items-center gap-3 sm:gap-4 ${isActive ? 'scale-[1.01]' : 'scale-100'} transition-all`}
                        >
                            <div className={`w-8 h-8 sm:w-10 sm:h-10 rounded-full flex items-center justify-center transition-colors shadow-lg ${isCompleted ? 'bg-lvmh-gold text-black' : isActive ? 'bg-white text-black animate-pulse' : 'bg-[#1a1a1a] text-gray-500'}`}>
                                {isCompleted ? <CheckCircle size={16} /> : <Icon size={16} className={isActive ? 'rotate-spin' : ''} />}
                            </div>

                            <div className="flex-1 min-w-0">
                                <div className={`text-xs sm:text-sm font-bold ${isActive ? 'text-white' : isCompleted ? 'text-lvmh-gold' : 'text-gray-500'}`}>
                                    {step.name}
                                </div>
                                {isActive && progressHint && (
                                    <motion.div
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        className="text-[10px] text-lvmh-gold/70 font-medium truncate"
                                    >
                                        {progressHint}
                                    </motion.div>
                                )}
                            </div>
                        </motion.div>
                    )
                })}
            </div>

            <AnimatePresence>
                {normalizedStep === 'failed' && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="mt-6 pt-5 border-t border-red-500/20"
                    >
                        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-start gap-3">
                            <AlertTriangle size={18} className="text-red-400 mt-0.5" />
                            <div className="text-xs text-red-300">
                                {progress?.error || 'Une erreur est survenue durant le pipeline.'}
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            <AnimatePresence>
                {result && normalizedStep !== 'failed' && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="mt-6 sm:mt-8 pt-5 sm:pt-6 border-t border-white/10"
                    >
                        <div className="flex items-center gap-3 mb-4">
                            <div className="bg-green-500/20 text-green-500 p-2 rounded-lg">
                                <ShieldCheck size={20} />
                            </div>
                            <div>
                                <div className="text-[10px] text-lvmh-gray uppercase font-bold tracking-widest">Score de qualite</div>
                                <div className="text-lg sm:text-xl font-bold text-white">{scoreLabel}</div>
                            </div>
                        </div>

                        <div className="bg-white/5 rounded-xl p-4 border border-white/5">
                            <div className="text-[10px] text-lvmh-gold uppercase font-bold mb-2">Recommandation expert</div>
                            <div className="text-xs sm:text-sm italic text-gray-300">"{recommendation}"</div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}

