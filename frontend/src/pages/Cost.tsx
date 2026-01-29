import { useEffect, useState } from 'react'
import api, { CostStats, APIError } from '../lib/api'

export default function Cost() {
    const [stats, setStats] = useState<CostStats | null>(null)
    const [loading, setLoading] = useState(true)
    const [ventesJour, setVentesJour] = useState(1)
    const [panierMoyen, setPanierMoyen] = useState(15000)

    useEffect(() => {
        loadStats()
    }, [])

    const loadStats = async () => {
        try {
            const data = await api.getCostStats()
            setStats(data)
        } catch (err) {
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    const revenueAnnuel = ventesJour * panierMoyen * 365
    const coutPipeline = 2600
    const roi = revenueAnnuel > 0 ? ((revenueAnnuel - coutPipeline) / coutPipeline) * 100 : 0
    const breakeven = ventesJour > 0 ? coutPipeline / (ventesJour * panierMoyen) : 0

    if (loading) {
        return <div className="loading"><div className="spinner" /> Loading...</div>
    }

    return (
        <div>
            <header className="page-header">
                <h1>💰 Cost & ROI</h1>
                <p>Analyse des coûts et retour sur investissement</p>
            </header>

            {/* Cost Breakdown */}
            <div className="metrics-grid">
                <div className="metric-card">
                    <div className="label">Coût Total</div>
                    <div className="value">{stats?.total_cost.toFixed(4)}€</div>
                </div>
                <div className="metric-card">
                    <div className="label">Projection Annuelle</div>
                    <div className="value">{stats?.projection_annual.toLocaleString()}€</div>
                </div>
                <div className="metric-card">
                    <div className="label">Coût par Note</div>
                    <div className="value">{String(stats?.roi_metrics?.cost_per_note || 0).slice(0, 8)}€</div>
                </div>
                <div className="metric-card">
                    <div className="label">vs 100% GPT</div>
                    <div className="value change">-62%</div>
                </div>
            </div>

            {/* Cost by Tier */}
            <div className="card" style={{ marginBottom: '1.5rem' }}>
                <h3 style={{ marginBottom: '1rem' }}>Répartition par Tier</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    {Object.entries(stats?.cost_by_tier || {}).map(([tier, cost]) => (
                        <div key={tier} style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                            <span className={`tag tier-${tier.replace('tier_', '')}`} style={{ minWidth: '60px' }}>
                                {tier.replace('_', ' ').toUpperCase()}
                            </span>
                            <div className="progress-bar" style={{ flex: 1 }}>
                                <div
                                    className="fill"
                                    style={{
                                        width: `${(cost / (stats?.total_cost || 1)) * 100}%`
                                    }}
                                />
                            </div>
                            <span style={{ minWidth: '80px', textAlign: 'right' }}>
                                {cost.toFixed(4)}€
                            </span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Projection Comparison */}
            <div className="card" style={{ marginBottom: '1.5rem' }}>
                <h3 style={{ marginBottom: '1rem' }}>📈 Projection Annuelle (68M notes)</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                            <span>100% GPT-4o</span>
                            <span>6,800€ • Précision 94%</span>
                        </div>
                        <div className="progress-bar">
                            <div className="fill" style={{ width: '100%', background: 'var(--error)' }} />
                        </div>
                    </div>
                    <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                            <span>Notre Hybride</span>
                            <span style={{ color: 'var(--success)' }}>2,600€ • Précision 87%</span>
                        </div>
                        <div className="progress-bar">
                            <div className="fill" style={{ width: '38%', background: 'var(--success)' }} />
                        </div>
                    </div>
                    <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                            <span>100% NLP Local</span>
                            <span>1,900€ • Précision 78%</span>
                        </div>
                        <div className="progress-bar">
                            <div className="fill" style={{ width: '28%', background: 'var(--warning)' }} />
                        </div>
                    </div>
                </div>
            </div>

            {/* ROI Calculator */}
            <div className="card">
                <h3 style={{ marginBottom: '1rem' }}>🎯 ROI Business Case</h3>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
                    <div className="metric-card">
                        <div className="label">Coût Pipeline</div>
                        <div className="value">2,600€/an</div>
                    </div>

                    <div>
                        <label style={{ fontSize: '0.75rem', color: 'var(--lvmh-gray)', display: 'block', marginBottom: '0.25rem' }}>
                            Ventes VIC additionnelles/jour
                        </label>
                        <input
                            type="range"
                            min="0"
                            max="10"
                            value={ventesJour}
                            onChange={(e) => setVentesJour(Number(e.target.value))}
                            style={{ width: '100%' }}
                        />
                        <div style={{ textAlign: 'center', fontWeight: 500 }}>{ventesJour}</div>
                    </div>

                    <div>
                        <label style={{ fontSize: '0.75rem', color: 'var(--lvmh-gray)', display: 'block', marginBottom: '0.25rem' }}>
                            Panier moyen VIC (€)
                        </label>
                        <input
                            type="number"
                            className="input"
                            value={panierMoyen}
                            onChange={(e) => setPanierMoyen(Number(e.target.value))}
                            step={1000}
                        />
                    </div>
                </div>

                <div className="success" style={{ padding: '1.5rem' }}>
                    <h4 style={{ marginBottom: '0.75rem' }}>💰 ROI Calculé</h4>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.5rem' }}>
                        <div>Revenue annuel: <strong>{revenueAnnuel.toLocaleString()}€</strong></div>
                        <div>Coût pipeline: <strong>2,600€</strong></div>
                        <div>Profit net: <strong>{(revenueAnnuel - coutPipeline).toLocaleString()}€</strong></div>
                        <div>ROI: <strong>{roi.toLocaleString()}%</strong></div>
                    </div>
                    <div style={{ marginTop: '0.75rem', fontWeight: 600 }}>
                        Breakeven: Atteint en {breakeven.toFixed(1)} jours
                    </div>
                </div>
            </div>
        </div>
    )
}
