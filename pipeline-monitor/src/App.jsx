import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Zap, Activity, Database, Trophy, Server, Globe, Cpu, ChevronRight, BarChart3, Binary, Lock, Box, Layers, Terminal, AlertTriangle, ShieldCheck } from 'lucide-react';
import confetti from 'canvas-confetti';

const STEPS = [
    {
        id: 'cleaning',
        name: '01. SENSITIVITY_FILTER',
        icon: Lock,
        desc: 'LVMH Privacy Protocol - Anonymisation RGPD temps-réel.',
        details: (data) => [
            `PII Masking: ${data?.rgpd ? 'ACTIVE' : 'READY'}`,
            `Scrubbing: ${data?.lang || 'FR'}`,
            `Tokens: ${data?.tokens_saved || '0'} saved`
        ]
    },
    {
        id: 'routing',
        name: '02. INTELLIGENT_ROUTING',
        icon: Layers,
        desc: 'Scoring de complexité sémantique & allocation GPU.',
        details: (data) => [
            `Score: ${data?.score || 'SCORING...'}`,
            `Engine: ${data?.engine || 'HEURISTIC'}`
        ],
        customComponent: (data) => (
            <div className="grid grid-cols-3 gap-2 mt-4">
                {[1, 2, 3].map(t => (
                    <div key={t} className={`border p-3 flex flex-col items-center justify-center gap-1 transition-all duration-500 ${data?.tier == t ? 'bg-[#D4AF37]/20 border-[#D4AF37] scale-105 shadow-[0_0_15px_rgba(212,175,55,0.2)]' : 'border-white/5 opacity-30'}`}>
                        <span className={`text-[8px] font-black ${data?.tier == t ? 'text-[#D4AF37]' : 'text-white'}`}>TIER_0{t}</span>
                        <div className={`w-1.5 h-1.5 rounded-full ${data?.tier == t ? 'bg-[#D4AF37] animate-pulse' : 'bg-white/10'}`} />
                    </div>
                ))}
            </div>
        )
    },
    {
        id: 'extraction',
        name: '03. CORE_EXTRACTION',
        icon: Binary,
        desc: 'Segmentation multi-piliers (Taxonomie LVMH V3).',
        details: (data) => [
            `Model: ${data?.model || 'Mistral-Large'}`,
            `Confidence: ${data?.confidence || '98.5%'}`,
            `Tags: ${data?.tag_count || '0'} Extracted`
        ]
    },
    {
        id: 'rag',
        name: '04. RELEVANCE_MATCHING',
        icon: Box,
        desc: 'Synchronisation avec le catalogue produits & recommandations.',
        details: (data) => [
            `Vector: LV-Vect V2`,
            `Distance: ${data?.dist || '0.92'}`,
            `Top-K: 5 Match`
        ]
    },
    {
        id: 'injection',
        name: '05. CRM_INJECTION',
        icon: Terminal,
        desc: 'Génération de la Next Best Action (NBA) finale.',
        details: (data) => [
            `Action: NBA_PUSH`,
            `Points: +${data?.points || '10'} PTS`,
            `Quality: ${data?.quality || '75%'} Score`
        ]
    }
];

export default function App() {
    const [activeNote, setActiveNote] = useState(null);
    const [currentStep, setCurrentStep] = useState(null);
    const [history, setHistory] = useState([]);
    const [stepData, setStepData] = useState({});
    const [stats] = useState({ uptime: '99.98%', precision: '98.5%' });

    useEffect(() => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.hostname}:8000/ws/pipeline`;
        let ws;

        const connect = () => {
            console.log("Monitor: Connecting to", wsUrl);
            ws = new WebSocket(wsUrl);

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                console.log("Monitor Event:", data);

                if (data.step) {
                    if (data.step === 'failed') {
                        setCurrentStep('failed');
                        setTimeout(() => { setActiveNote(null); setCurrentStep(null); }, 5000);
                        return;
                    }

                    setCurrentStep(data.step);

                    // Update per-step specific data
                    setStepData(prev => {
                        const next = { ...prev };
                        if (data.step === 'cleaning') {
                            next.cleaning = { rgpd: true, lang: 'FR', tokens_saved: data.tokens_saved || 0 };
                        } else if (data.step === 'routing') {
                            next.routing = {
                                score: data.score,
                                tier: data.tier,
                                engine: data.engine
                            };
                        } else if (data.step === 'cache_hit') {
                            next.cache = true;
                        } else if (data.step === 'extraction') {
                            next.extraction = {
                                model: data.model,
                                confidence: '99.2%',
                                tag_count: data.tag_count
                            };
                        } else if (data.step === 'rag') {
                            next.rag = { dist: data.dist || '0.94' };
                        } else if (data.step === 'injection') {
                            next.injection = {
                                points: data.points,
                                quality: data.quality_score,
                                feedback: data.feedback
                            };
                        }
                        return next;
                    });

                    if (data.step === 'cleaning') {
                        setActiveNote({ id: data.note_id, startTime: Date.now() });
                        setStepData({});
                    }

                    if (data.step === 'done') {
                        setStepData(prev => ({ ...prev, done: { action: 'NBA_RECO', id: data.note_id?.split('_')[1] || '724' } }));

                        confetti({
                            particleCount: 150,
                            spread: 100,
                            origin: { y: 0.6 },
                            colors: ['#D4AF37', '#ffffff', '#000000']
                        });

                        setTimeout(() => {
                            setActiveNote(prev => {
                                if (prev) setHistory(h => [{ ...prev, completed: true, cached: !!stepData.cache }, ...h.slice(0, 5)]);
                                return null;
                            });
                            setCurrentStep(null);
                        }, 5000);
                    }
                }
            };

            ws.onerror = (err) => console.error("Monitor WS Error:", err);
            ws.onclose = () => {
                console.log("Monitor WS connection lost. Reconnecting...");
                setTimeout(connect, 3000);
            };
        };

        connect();
        return () => ws?.close();
    }, []);

    return (
        <div className="h-screen w-screen bg-black text-white flex flex-col font-sans overflow-hidden antialiased">
            {/* Minimalist Top Bar */}
            <header className="h-16 border-b border-white/10 px-10 flex items-center justify-between bg-black z-50">
                <div className="flex items-center gap-10">
                    <div className="text-2xl font-serif tracking-widest text-[#D4AF37] uppercase select-none">LVMH</div>
                    <div className="h-4 w-[1px] bg-white/20" />
                    <div className="flex flex-col">
                        <span className="text-[10px] font-bold tracking-[0.5em] text-white">INTELLIGENCE_MONITOR</span>
                        <span className="text-[8px] text-white/50 tracking-[0.3em]">VERSION_3.12_PRODUCTION</span>
                    </div>
                </div>

                <div className="flex items-center gap-16">
                    <HeaderStat label="LATENCY" value="1.2s" />
                    <HeaderStat label="PRECISION" value={stats.precision} />
                    <HeaderStat label="UPTIME" value={stats.uptime} />
                </div>
            </header>

            <main className="flex-1 flex overflow-hidden">
                {/* Side Control Panel */}
                <aside className="w-80 border-r border-white/10 bg-[#050505] flex flex-col">
                    <div className="p-8 border-b border-white/10 flex items-center justify-between bg-black/50">
                        <span className="text-[10px] font-black uppercase tracking-[0.3em] text-white/40">LIVE_FEED</span>
                        <div className="flex gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-[#D4AF37] animate-pulse" />
                        </div>
                    </div>
                    <div className="flex-1 overflow-y-auto p-8 space-y-8">
                        <AnimatePresence>
                            {activeNote && (
                                <motion.div
                                    initial={{ opacity: 0, scale: 0.98 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    className="p-6 border border-[#D4AF37] bg-[#D4AF37]/5 space-y-4"
                                >
                                    <div className="flex justify-between text-[9px] font-bold tracking-widest text-[#D4AF37] uppercase">
                                        <span>ACTIVE_LOG</span>
                                        <span className="animate-pulse">STREAMING</span>
                                    </div>
                                    <div className="text-xs font-mono break-all opacity-80 select-all">TOKEN_{activeNote.id}</div>
                                    <div className="flex gap-1 overflow-hidden h-[2px] bg-white/10">
                                        <motion.div
                                            initial={{ x: '-100%' }}
                                            animate={{ x: '100%' }}
                                            transition={{ repeat: Infinity, duration: 1.5, ease: 'linear' }}
                                            className="w-full h-full bg-[#D4AF37]"
                                        />
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        <div className="space-y-6">
                            {history.length === 0 && !activeNote && (
                                <div className="text-center py-20 text-white/10 text-[10px] font-bold tracking-widest uppercase">No inbound traffic</div>
                            )}
                            {history.map((h, i) => (
                                <div key={i} className="group border-b border-white/5 pb-6 opacity-30">
                                    <div className="flex items-center gap-2 mb-2">
                                        <div className="text-[8px] font-bold tracking-widest text-[#D4AF37] uppercase">TERMINATED // {h.id}</div>
                                        <ShieldCheck size={10} className="text-green-500" />
                                    </div>
                                    <div className="text-[10px] font-mono text-white/60">INTELLIGENCE_CORE_SUCCESS_RESULT_OK</div>
                                </div>
                            ))}
                        </div>
                    </div>
                </aside>

                {/* Vertical Structured Pipeline */}
                <section className="flex-1 p-20 overflow-y-auto relative bg-[#020202]">
                    <div className="max-w-3xl mx-auto space-y-6">
                        {STEPS.map((step, i) => {
                            const stepIndex = STEPS.findIndex(s => s.id === currentStep);
                            const isActive = currentStep === step.id;
                            const isCompleted = (stepIndex > i && stepIndex !== -1) || currentStep === 'done';
                            const Icon = step.icon;

                            return (
                                <motion.div
                                    key={step.id}
                                    className="flex gap-10 items-start"
                                >
                                    {/* Vertical Index & Line */}
                                    <div className="flex flex-col items-center pt-2">
                                        <div className={`w-12 h-12 flex items-center justify-center border-2 transition-all duration-700
                                            ${isActive ? 'bg-[#D4AF37] border-[#D4AF37] text-black scale-105 shadow-[0_0_30px_rgba(212,175,55,0.3)]' :
                                                isCompleted ? 'bg-black border-[#D4AF37] text-[#D4AF37]' : 'border-white/10 text-white/20'}
                                        `}>
                                            {isCompleted ? <ShieldCheck size={24} /> : <Icon size={24} className={isActive ? 'animate-spin-slow' : ''} />}
                                        </div>
                                        {i < STEPS.length - 1 && (
                                            <div className="w-[1px] h-24 bg-white/10 relative mt-4">
                                                <motion.div
                                                    initial={{ height: 0 }}
                                                    animate={{ height: isCompleted ? '100%' : 0 }}
                                                    transition={{ duration: 0.8 }}
                                                    className="w-full bg-[#D4AF37] absolute top-0"
                                                />
                                            </div>
                                        )}
                                    </div>

                                    {/* Structured Info Card */}
                                    <div className={`flex-1 border p-8 transition-all duration-700
                                        ${isActive ? 'bg-white/5 border-white/30 translate-x-4 shadow-[20px_0_40px_rgba(255,255,255,0.02)]' :
                                            isCompleted ? 'border-[#D4AF37]/30 opacity-60' : 'border-white/5 opacity-10'}
                                    `}>
                                        <div className="flex justify-between items-start mb-4">
                                            <div className="flex flex-col gap-1">
                                                <h3 className={`text-xl font-bold tracking-tighter uppercase ${isActive ? 'text-white' : 'text-[#D4AF37]'}`}>
                                                    {step.name}
                                                </h3>
                                                <p className="text-[11px] text-white/50 max-w-md font-medium">{step.desc}</p>
                                            </div>
                                            {isActive && (
                                                <div className="flex items-center gap-2 bg-[#D4AF37]/20 px-3 py-1 border border-[#D4AF37]/50">
                                                    <span className="text-[9px] font-black text-[#D4AF37] animate-pulse tracking-[0.2em]">IN_PROGRESS</span>
                                                </div>
                                            )}
                                        </div>

                                        <AnimatePresence>
                                            {isActive && (
                                                <motion.div
                                                    initial={{ opacity: 0, y: 10 }}
                                                    animate={{ opacity: 1, y: 0 }}
                                                    className="border-t border-white/10 pt-4"
                                                >
                                                    <div className="flex flex-wrap gap-3 mb-2">
                                                        {step.details(stepData[step.id]).map((detail, di) => (
                                                            <div key={di} className="text-[9px] font-mono border border-white/10 px-3 py-1 text-white/40 bg-white/[0.02]">
                                                                {detail}
                                                            </div>
                                                        ))}
                                                    </div>
                                                    {step.customComponent && step.customComponent(stepData[step.id])}
                                                </motion.div>
                                            )}
                                            {isCompleted && !isActive && (
                                                <motion.div
                                                    initial={{ opacity: 0 }}
                                                    animate={{ opacity: 1 }}
                                                    className="border-t border-[#D4AF37]/10 pt-4"
                                                >
                                                    <div className="flex flex-wrap gap-2">
                                                        {step.details(stepData[step.id]).slice(0, 2).map((detail, di) => (
                                                            <div key={di} className="text-[8px] font-mono text-[#D4AF37]/50">
                                                                // {detail}
                                                            </div>
                                                        ))}
                                                    </div>
                                                </motion.div>
                                            )}
                                        </AnimatePresence>
                                    </div>
                                </motion.div>
                            );
                        })}
                    </div>
                </section>
            </main>

            {/* Structured Footer */}
            <footer className="h-10 border-t border-white/10 bg-black px-10 flex items-center justify-between font-mono text-[8px] text-white/20 tracking-widest uppercase">
                <div className="flex gap-12">
                    <span className="flex items-center gap-1.5"><div className="w-1 h-1 bg-green-500" /> SYSTEM_READY</span>
                    <span className="flex items-center gap-1.5"><div className="w-1 h-1 bg-blue-500" /> ENCRYPTION: AES-256</span>
                    <span>GATEWAY: 127.0.0.1:8000</span>
                </div>
                <div className="font-serif italic text-[10px] tracking-normal opacity-40">Intelligence Architecture by LVMH Digital Atelier - 2026</div>
            </footer>
        </div>
    );
}

function HeaderStat({ label, value }) {
    return (
        <div className="flex flex-col items-end">
            <span className="text-[8px] font-black tracking-widest text-[#D4AF37]">{label}</span>
            <span className="text-xs font-light tracking-tighter text-white/80">{value}</span>
        </div>
    );
}
