import React from 'react'
import { Activity, Database, LayoutDashboard, Mic, ShieldCheck } from 'lucide-react'

export default function LandingPage({ onNavigate }) {
    return (
        <div className="flex flex-col items-center justify-center min-h-screen px-6 py-12">
            <div className="text-center mb-12">
                <h1 className="gold-text text-4xl font-display font-bold mb-2">LVMH VOICE-TO-TAG</h1>
                <p className="text-lvmh-gray uppercase tracking-widest text-sm">Intelligence Artificielle Native</p>
            </div>

            <div className="w-full max-w-5xl space-y-8">
                <button
                    onClick={() => onNavigate('admin')}
                    className="w-full glass p-12 flex flex-col items-center group hover:bg-white/10 transition-all duration-300 transform hover:-translate-y-2 relative overflow-hidden"
                >
                    <div className="absolute inset-0 bg-gradient-to-r from-lvmh-gold/5 via-transparent to-lvmh-gold/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                    <div className="relative z-10">
                        <div className="w-24 h-24 bg-lvmh-gold/20 rounded-full flex items-center justify-center mb-6 group-hover:bg-lvmh-gold/40 transition-colors">
                            <Database className="text-lvmh-gold w-12 h-12" />
                        </div>
                        <h2 className="text-3xl font-bold mb-2 gold-text">Admin Total</h2>
                        <p className="text-lvmh-gray text-center text-sm max-w-md">Monitoring global, couts, alertes, RGPD et sante systeme</p>
                    </div>
                </button>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <button
                        onClick={() => onNavigate('advisor')}
                        className="glass p-8 flex flex-col items-center group hover:bg-white/10 transition-all duration-300 transform hover:-translate-y-2"
                    >
                        <div className="w-16 h-16 bg-lvmh-gold/20 rounded-full flex items-center justify-center mb-4 group-hover:bg-lvmh-gold/40 transition-colors">
                            <Mic className="text-lvmh-gold w-8 h-8" />
                        </div>
                        <h2 className="text-xl font-bold mb-2">Espace Vendeur</h2>
                        <p className="text-lvmh-gray text-center text-xs">Dictee vocale, gamification et recommandations</p>
                    </button>

                    <button
                        onClick={() => onNavigate('manager')}
                        className="glass p-8 flex flex-col items-center group hover:bg-white/10 transition-all duration-300 transform hover:-translate-y-2"
                    >
                        <div className="w-16 h-16 bg-white/10 rounded-full flex items-center justify-center mb-4 group-hover:bg-white/20 transition-colors">
                            <LayoutDashboard className="text-white w-8 h-8" />
                        </div>
                        <h2 className="text-xl font-bold mb-2">Espace Manager</h2>
                        <p className="text-lvmh-gray text-center text-xs">Analytics boutique et pilotage CRM</p>
                    </button>

                    <button
                        onClick={() => onNavigate('pipeline')}
                        className="glass p-8 flex flex-col items-center group hover:bg-white/10 transition-all duration-300 transform hover:-translate-y-2"
                    >
                        <div className="w-16 h-16 bg-lvmh-gold/10 rounded-full flex items-center justify-center mb-4 group-hover:bg-lvmh-gold/30 transition-colors">
                            <Activity className="text-lvmh-gold w-8 h-8" />
                        </div>
                        <h2 className="text-xl font-bold mb-2">Pipeline Live</h2>
                        <p className="text-lvmh-gray text-center text-xs">Visualisation temps reel du flux IA</p>
                    </button>
                </div>
            </div>

            <div className="mt-16 flex items-center gap-2 text-lvmh-gray text-xs">
                <ShieldCheck size={14} />
                <span>SOUVERAINETE EU & RGPD COMPLIANT</span>
            </div>
        </div>
    )
}
