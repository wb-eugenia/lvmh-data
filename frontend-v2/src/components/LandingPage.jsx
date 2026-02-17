import React, { useEffect, useState } from 'react'
import { Activity, Database, LayoutDashboard, Mic, ShieldCheck, Sparkles } from 'lucide-react'

function GoldParticles() {
    const particles = Array.from({ length: 20 }, (_, i) => ({
        id: i,
        left: `${Math.random() * 100}%`,
        delay: `${Math.random() * 15}s`,
        duration: `${15 + Math.random() * 10}s`,
        size: `${2 + Math.random() * 4}px`,
    }))

    return (
        <div className="gold-particles">
            {particles.map(p => (
                <div
                    key={p.id}
                    className="gold-particle"
                    style={{
                        left: p.left,
                        animationDelay: p.delay,
                        animationDuration: p.duration,
                        width: p.size,
                        height: p.size,
                    }}
                />
            ))}
        </div>
    )
}

export default function LandingPage({ onNavigate }) {
    const [mounted, setMounted] = useState(false)

    useEffect(() => {
        setMounted(true)
    }, [])

    return (
        <div className="relative min-h-screen flex flex-col items-center justify-center px-6 py-12 overflow-hidden">
            <GoldParticles />
            
            <div className={`relative z-10 text-center mb-16 transition-all duration-1000 ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
                <div className="flex items-center justify-center gap-3 mb-4">
                    <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-lvmh-gold to-[#a68520] flex items-center justify-center shadow-lg shadow-lvmh-gold/30">
                        <Sparkles className="text-black w-6 h-6" />
                    </div>
                </div>
                <h1 className="text-5xl md:text-6xl font-display font-bold mb-4 gold-text">
                    LVMH VOICE-TO-TAG
                </h1>
                <p className="text-lvmh-gray uppercase tracking-[0.3em] text-sm font-medium">
                    Intelligence Artificielle Native
                </p>
            </div>

            <div className={`relative z-10 w-full max-w-5xl space-y-8 transition-all duration-1000 delay-300 ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
                <button
                    onClick={() => onNavigate('admin')}
                    className="w-full glass-card p-10 flex flex-col items-center group cursor-pointer relative overflow-hidden"
                >
                    <div className="absolute inset-0 bg-gradient-to-r from-lvmh-gold/5 via-transparent to-lvmh-gold/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                    <div className="relative z-10 flex flex-col items-center">
                        <div className="w-20 h-20 bg-gradient-to-br from-lvmh-gold/20 to-lvmh-gold/5 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 group-hover:rotate-3 transition-all duration-500 shadow-lg shadow-lvmh-gold/20">
                            <Database className="text-lvmh-gold w-10 h-10" />
                        </div>
                        <h2 className="text-3xl font-display font-bold mb-3 gold-text">Admin Total</h2>
                        <p className="text-lvmh-gray text-center text-sm max-w-md leading-relaxed">
                            Monitoring global, couts, alertes, RGPD et sante systeme en temps reel
                        </p>
                    </div>
                </button>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {[
                        {
                            id: 'advisor',
                            icon: Mic,
                            title: 'Espace Vendeur',
                            desc: 'Dictee vocale, gamification et recommandations',
                            gold: true,
                        },
                        {
                            id: 'manager',
                            icon: LayoutDashboard,
                            title: 'Espace Manager',
                            desc: 'Analytics boutique et pilotage CRM',
                            gold: false,
                        },
                        {
                            id: 'pipeline',
                            icon: Activity,
                            title: 'Pipeline Live',
                            desc: 'Visualisation temps reel du flux IA',
                            gold: true,
                        },
                    ].map((item, idx) => (
                        <button
                            key={item.id}
                            onClick={() => onNavigate(item.id)}
                            className="glass-card p-8 flex flex-col items-center group cursor-pointer transition-all duration-500"
                            style={{ transitionDelay: `${idx * 100}ms` }}
                        >
                            <div className={`w-16 h-16 rounded-xl flex items-center justify-center mb-5 transition-all duration-500 group-hover:scale-110 ${
                                item.gold 
                                    ? 'bg-gradient-to-br from-lvmh-gold/20 to-lvmh-gold/5 group-hover:from-lvmh-gold/30 group-hover:to-lvmh-gold/10' 
                                    : 'bg-white/5 group-hover:bg-white/10'
                            }`}>
                                <item.icon className={`w-8 h-8 transition-colors duration-300 ${
                                    item.gold ? 'text-lvmh-gold' : 'text-white/70 group-hover:text-white'
                                }`} />
                            </div>
                            <h2 className="text-xl font-bold mb-2 text-white group-hover:text-lvmh-gold transition-colors duration-300">
                                {item.title}
                            </h2>
                            <p className="text-lvmh-gray text-center text-xs leading-relaxed">
                                {item.desc}
                            </p>
                        </button>
                    ))}
                </div>
            </div>

            <div className={`relative z-10 mt-16 flex items-center gap-3 text-lvmh-gray text-xs transition-all duration-1000 delay-500 ${mounted ? 'opacity-100' : 'opacity-0'}`}>
                <ShieldCheck size={14} className="text-lvmh-gold" />
                <span className="tracking-wider">SOUVERAINETE EU & RGPD COMPLIANT</span>
            </div>

            <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-lvmh-gold/20 to-transparent" />
        </div>
    )
}
