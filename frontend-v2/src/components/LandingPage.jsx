import React from 'react'
import { Activity, Database, LayoutDashboard, Mic, ShieldCheck } from 'lucide-react'

export default function LandingPage({ onNavigate }) {
    return (
        <div className="flex flex-col items-center justify-center min-h-screen px-6">
            <div className="text-center mb-12">
                <h1 className="gold-text text-4xl font-display font-bold mb-2">LVMH VOICE-TO-TAG</h1>
                <p className="text-lvmh-gray uppercase tracking-widest text-sm">Intelligence Artificielle Native</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 w-full max-w-6xl">
                <button
                    onClick={() => onNavigate('advisor')}
                    className="glass p-10 flex flex-col items-center group hover:bg-white/10 transition-all duration-300 transform hover:-translate-y-2"
                >
                    <div className="w-20 h-20 bg-lvmh-gold/20 rounded-full flex items-center justify-center mb-6 group-hover:bg-lvmh-gold/40 transition-colors">
                        <Mic className="text-lvmh-gold w-10 h-10" />
                    </div>
                    <h2 className="text-2xl font-bold mb-2">Espace Vendeur</h2>
                    <p className="text-lvmh-gray text-center text-sm">Dictee vocale, gamification et recommandations en temps reel</p>
                </button>

                <button
                    onClick={() => onNavigate('manager')}
                    className="glass p-10 flex flex-col items-center group hover:bg-white/10 transition-all duration-300 transform hover:-translate-y-2"
                >
                    <div className="w-20 h-20 bg-white/10 rounded-full flex items-center justify-center mb-6 group-hover:bg-white/20 transition-colors">
                        <LayoutDashboard className="text-white w-10 h-10" />
                    </div>
                    <h2 className="text-2xl font-bold mb-2">Espace Manager</h2>
                    <p className="text-lvmh-gray text-center text-sm">Analytics boutique, KPIs qualite et pilotage CRM</p>
                </button>

                <button
                    onClick={() => onNavigate('pipeline')}
                    className="glass p-10 flex flex-col items-center group hover:bg-white/10 transition-all duration-300 transform hover:-translate-y-2"
                >
                    <div className="w-20 h-20 bg-lvmh-gold/10 rounded-full flex items-center justify-center mb-6 group-hover:bg-lvmh-gold/30 transition-colors">
                        <Activity className="text-lvmh-gold w-10 h-10" />
                    </div>
                    <h2 className="text-2xl font-bold mb-2">Pipeline Live</h2>
                    <p className="text-lvmh-gray text-center text-sm">Visualisation temps reel du flux IA V3</p>
                </button>

                <button
                    onClick={() => onNavigate('admin')}
                    className="glass p-10 flex flex-col items-center group hover:bg-white/10 transition-all duration-300 transform hover:-translate-y-2"
                >
                    <div className="w-20 h-20 bg-lvmh-gold/10 rounded-full flex items-center justify-center mb-6 group-hover:bg-lvmh-gold/30 transition-colors">
                        <Database className="text-lvmh-gold w-10 h-10" />
                    </div>
                    <h2 className="text-2xl font-bold mb-2">Admin Total</h2>
                    <p className="text-lvmh-gray text-center text-sm">Monitoring global, couts, alertes, RGPD et sante systeme</p>
                </button>
            </div>

            <div className="mt-16 flex items-center gap-2 text-lvmh-gray text-xs">
                <ShieldCheck size={14} />
                <span>SOUVERAINETE EU & RGPD COMPLIANT</span>
            </div>
        </div>
    )
}
