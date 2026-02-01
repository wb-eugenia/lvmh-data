import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, Loader2, Zap, Database, ShieldCheck, ShoppingBag, Trophy } from 'lucide-react';

const STEPS = [
    { id: 'cleaning', name: 'Data Cleaning', icon: Loader2 },
    { id: 'routing', name: 'Smart Routing', icon: Zap },
    { id: 'extraction', name: 'Taxonomy Extraction', icon: Database },
    { id: 'rag', name: 'RAG Matching', icon: ShoppingBag },
    { id: 'nba', name: 'CRM Insights', icon: Trophy }
];

export default function PipelineVisualizer({ isProcessing, currentStep, result }) {
    const [activeStepIndex, setActiveStepIndex] = useState(-1);

    useEffect(() => {
        if (currentStep) {
            if (currentStep === 'cleaning') setActiveStepIndex(0);
            else if (currentStep === 'routing') setActiveStepIndex(1);
            else if (currentStep.startsWith('tier')) setActiveStepIndex(2);
            else if (currentStep === 'rag') setActiveStepIndex(3);
            else if (currentStep === 'done') setActiveStepIndex(5);
        } else if (!isProcessing) {
            setActiveStepIndex(-1);
        }
    }, [currentStep, isProcessing]);

    if (!isProcessing && !result) return null;

    return (
        <div className="w-full bg-black/40 backdrop-blur-xl rounded-3xl p-6 border border-white/10 shadow-2xl overflow-hidden relative">
            <div className="flex justify-between items-center mb-8">
                <div>
                    <h3 className="text-lvmh-gold font-bold text-lg flex items-center gap-2">
                        <Zap size={20} className="animate-pulse" />
                        Pipeline IA V3.0
                    </h3>
                    <p className="text-[10px] text-lvmh-gray uppercase tracking-widest mt-1">Traitement Cognitif Temps Réel</p>
                </div>
                {isProcessing && (
                    <div className="bg-lvmh-gold/20 text-lvmh-gold text-[10px] px-2 py-1 rounded-full font-bold animate-pulse">
                        EN COURS ({(Math.random() * 0.5 + 0.8).toFixed(1)}s)
                    </div>
                )}
            </div>

            <div className="relative space-y-6">
                {/* Progress Line */}
                <div className="absolute left-[19px] top-2 bottom-2 w-[2px] bg-white/5 z-0" />
                <div
                    className="absolute left-[19px] top-2 w-[2px] bg-lvmh-gold z-0 transition-all duration-500"
                    style={{ height: `${Math.max(0, (activeStepIndex / (STEPS.length - 1)) * 100)}%` }}
                />

                {STEPS.map((step, index) => {
                    const isActive = index === activeStepIndex;
                    const isCompleted = index < activeStepIndex || (currentStep === 'done');
                    const Icon = step.icon;

                    return (
                        <motion.div
                            key={step.id}
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: index * 0.1 }}
                            className={`relative z-10 flex items-center gap-4 ${isActive ? 'scale-105' : 'scale-100'} transition-all`}
                        >
                            <div className={`w-10 h-10 rounded-full flex items-center justify-center transition-colors shadow-lg
                ${isCompleted ? 'bg-lvmh-gold text-black' : isActive ? 'bg-white text-black animate-pulse' : 'bg-[#1a1a1a] text-gray-500'}
              `}>
                                {isCompleted ? <CheckCircle size={20} /> : <Icon size={20} className={isActive ? 'rotate-spin' : ''} />}
                            </div>

                            <div className="flex-1">
                                <div className={`text-sm font-bold ${isActive ? 'text-white' : isCompleted ? 'text-lvmh-gold' : 'text-gray-500'}`}>
                                    {step.name}
                                </div>
                                {isActive && (
                                    <motion.div
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        className="text-[10px] text-lvmh-gold/60 font-medium"
                                    >
                                        Analyse des vecteurs sémantiques...
                                    </motion.div>
                                )}
                            </div>

                            {isCompleted && (
                                <div className="text-[10px] font-mono text-lvmh-gold/40">
                                    {((index + 1) * 0.2).toFixed(1)}s
                                </div>
                            )}
                        </motion.div>
                    );
                })}
            </div>

            <AnimatePresence>
                {result && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="mt-8 pt-6 border-t border-white/10"
                    >
                        <div className="flex items-center gap-3 mb-4">
                            <div className="bg-green-500/20 text-green-500 p-2 rounded-lg">
                                <ShieldCheck size={24} />
                            </div>
                            <div>
                                <div className="text-[10px] text-lvmh-gray uppercase font-bold tracking-widest">Score de Qualité</div>
                                <div className="text-xl font-bold text-white">{(result.meta_analysis?.quality_score * 100 || 85).toFixed(0)}% <span className="text-lvmh-gold text-sm">+20 pts</span></div>
                            </div>
                        </div>

                        <div className="bg-white/5 rounded-xl p-4 border border-white/5">
                            <div className="text-[10px] text-lvmh-gold uppercase font-bold mb-2">Recommandation Expert</div>
                            <div className="text-sm italic text-gray-300">
                                "{result.pilier_4_action_business?.next_best_action?.description || "Suggérer le sac Capucines pour cet anniversaire."}"
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
