import React, { useState, useEffect } from 'react'
import { ArrowLeft, LayoutDashboard, Trophy, Users, Star, Download, Search } from 'lucide-react'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'

export default function ManagerView({ onBack }) {
    const [currentTab, setCurrentTab] = useState('overview')
    const [stats, setStats] = useState({ total_notes: 0, avg_quality: 0, tier_distribution: { 1: 0, 2: 0, 3: 0 } })
    const [leaderboard, setLeaderboard] = useState([])
    const [history, setHistory] = useState([])

    const tabs = [
        { id: 'overview', name: 'Overview', icon: LayoutDashboard },
        { id: 'leaderboard', name: 'Leaderboard', icon: Trophy },
        { id: 'vip', name: 'Clients VIP', icon: Star },
        { id: 'quality', name: 'Qualité Notes', icon: Users }
    ]

    useEffect(() => {
        fetchData()
    }, [])

    const fetchData = async () => {
        try {
            const sRes = await fetch('/api/stats')
            setStats(await sRes.json())

            const lRes = await fetch('/api/leaderboard')
            setLeaderboard(await lRes.json())

            const hRes = await fetch('/api/search?q=')
            const hData = await hRes.json()
            setHistory(hData.results)
        } catch (e) { console.error(e) }
    }

    const chartData = [
        { name: 'Tier 1', value: stats?.tier_distribution?.[1] || 0, color: '#888888' },
        { name: 'Tier 2', value: stats?.tier_distribution?.[2] || 0, color: '#D4AF37' },
        { name: 'Tier 3', value: stats?.tier_distribution?.[3] || 0, color: '#FF5252' }
    ]

    return (
        <div className="flex h-screen bg-lvmh-dark text-white overflow-hidden">
            {/* Sidebar */}
            <div className="w-64 border-r border-white/5 bg-lvmh-black h-full flex flex-col p-6">
                <div className="flex items-center gap-3 mb-12 p-2">
                    <button onClick={onBack} className="hover:text-lvmh-gold transition-colors"><ArrowLeft size={20} /></button>
                    <h1 className="gold-text font-black text-lg tracking-tighter">LVMH ANALYTICS</h1>
                </div>

                <nav className="flex-1 space-y-2">
                    {tabs.map(tab => (
                        <button
                            key={tab.id}
                            onClick={() => setCurrentTab(tab.id)}
                            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${currentTab === tab.id ? 'bg-lvmh-gold text-black font-bold shadow-lg shadow-lvmh-gold/20' : 'text-lvmh-gray hover:bg-white/5'
                                }`}
                        >
                            <tab.icon size={20} />
                            {tab.name}
                        </button>
                    ))}
                </nav>

                <div className="mt-auto pt-6 border-t border-white/5">
                    <div className="flex items-center gap-3 text-sm text-lvmh-gray px-4">
                        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
                        Serveur Live
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 overflow-y-auto p-10">
                <div className="flex justify-between items-center mb-10">
                    <div>
                        <h2 className="text-3xl font-black mb-1">Boutique Paris Rivoli</h2>
                        <p className="text-lvmh-gray">Pilotage de la performance Client Advisor</p>
                    </div>
                    <button className="glass flex items-center gap-2 px-6 py-3 hover:bg-white/10 transition-colors uppercase text-xs font-bold tracking-widest">
                        <Download size={16} /> Export Salesforce
                    </button>
                </div>

                {currentTab === 'overview' && (
                    <div className="space-y-10 animate-in fade-in duration-500">
                        {/* KPI Cards */}
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                            <KPICard title="Notes Totales" value={stats.total_notes} trend="+12% vs hier" />
                            <KPICard title="Qualité Moyenne" value={`${stats.avg_quality}%`} trend="Mode: Expert 🌟" gold />
                            <KPICard title="Alertes VIP" value={history.filter(x => x.tier === 3).length} trend="À traiter urgent" red />
                            <KPICard title="Notes/CA/Jour" value="4.7" trend="Cible: 5.0 🚀" />
                        </div>

                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
                            <div className="glass p-8">
                                <h3 className="text-xl font-bold mb-6 flex items-center gap-2"><Trophy size={20} className="text-lvmh-gold" /> Top Advisors</h3>
                                <table className="w-full text-left">
                                    <thead className="text-lvmh-gray text-xs uppercase tracking-widest border-b border-white/5">
                                        <tr>
                                            <th className="pb-4">Advisor</th>
                                            <th className="pb-4">Engagement</th>
                                            <th className="pb-4 text-right">Performance</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5">
                                        {leaderboard.map((adv, i) => (
                                            <tr key={adv.id} className="group hover:bg-white/2 transition-colors">
                                                <td className="py-4 font-bold">{adv.id}</td>
                                                <td className="py-4 text-sm text-lvmh-gray">{adv.notes} notes</td>
                                                <td className="py-4 text-right font-black text-lvmh-gold">{adv.score} pts</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>

                            <div className="glass p-8 flex flex-col h-[400px]">
                                <h3 className="text-xl font-bold mb-6">Distribution Qualité (Tiers)</h3>
                                <div className="flex-1">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <PieChart>
                                            <Pie
                                                data={chartData}
                                                innerRadius={80}
                                                outerRadius={120}
                                                paddingAngle={5}
                                                dataKey="value"
                                            >
                                                {chartData.map((entry, index) => (
                                                    <Cell key={`cell-${index}`} fill={entry.color} />
                                                ))}
                                            </Pie>
                                            <Tooltip
                                                contentStyle={{ backgroundColor: '#1A1A1A', border: '1px solid #333', borderRadius: '8px' }}
                                            />
                                            <Legend />
                                        </PieChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {currentTab === 'leaderboard' && (
                    <div className="glass p-10 animate-in slide-in-from-right duration-500">
                        <h3 className="text-2xl font-black gold-text mb-8">Performance Retail Mondiale</h3>
                        <div className="space-y-4">
                            {leaderboard.map((adv, i) => (
                                <div key={adv.id} className="flex items-center gap-6 glass p-6 hover:border-lvmh-gold/30 transition-all border-l-4 border-l-transparent hover:border-l-lvmh-gold">
                                    <span className="text-4xl font-black text-white/10">{i + 1}</span>
                                    <div className="flex-1">
                                        <div className="font-bold text-xl">{adv.id}</div>
                                        <div className="text-lvmh-gray text-sm">{adv.notes} interactions capturées</div>
                                    </div>
                                    <div className="text-3xl font-black text-lvmh-gold">{adv.score} <span className="text-xs uppercase">points</span></div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {currentTab === 'vip' && (
                    <div className="space-y-6 animate-in slide-in-from-right duration-500">
                        <div className="flex items-center gap-2 mb-4">
                            <Star className="text-red-500 fill-red-500" size={24} />
                            <h3 className="text-2xl font-black">Segment Discovery (Tier 3)</h3>
                        </div>
                        <div className="grid grid-cols-1 gap-4">
                            {history.filter(x => x.tier === 3).map((r, i) => (
                                <div key={i} className="glass p-6 border-l-4 border-red-500 hover:bg-white/5 transition-all">
                                    <div className="flex justify-between items-start mb-4">
                                        <span className="text-xl font-bold">{r.ID}</span>
                                        <span className="text-xs bg-red-500/20 text-red-500 px-3 py-1 rounded-full font-bold">ALERTE MISTRAL</span>
                                    </div>
                                    <p className="text-lvmh-gray text-sm mb-4">"{r.Transcription?.substring(0, 100)}..."</p>
                                    <div className="bg-white/5 p-4 rounded-lg border border-white/5">
                                        <div className="text-[10px] text-lvmh-gold uppercase font-bold mb-2">Opportunité détectée</div>
                                        <div className="font-medium">{r.pilier_4_action_business.next_best_action?.description}</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}

function KPICard({ title, value, trend, gold, red }) {
    return (
        <div className="glass p-6 relative overflow-hidden group hover:scale-[1.02] transition-transform">
            {gold && <div className="absolute top-0 right-0 w-32 h-32 bg-lvmh-gold/5 rounded-full -mr-16 -mt-16 blur-3xl group-hover:bg-lvmh-gold/10 transition-colors"></div>}
            <div className="text-lvmh-gray text-xs uppercase tracking-widest font-bold mb-4">{title}</div>
            <div className={`text-4xl font-black mb-2 ${gold ? 'gold-text' : (red ? 'text-red-500' : 'text-white')}`}>{value}</div>
            <div className={`text-[10px] font-bold ${trend.includes('↑') ? 'text-green-500' : 'text-lvmh-gray'}`}>{trend}</div>
        </div>
    )
}
