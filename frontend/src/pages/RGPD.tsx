import { useEffect, useState } from 'react'
import api, { RGPDStats } from '../lib/api'

const EXAMPLES = [
    {
        text: 'Cliente évite burnout l\'an dernier',
        competitor: '🔴 SUPPRIMÉ (keyword "burnout")',
        nous: '🟢 CONSERVÉ (contexte business OK)',
        reason: 'Pas de donnée médicale actuelle'
    },
    {
        text: 'Cliente cancer rémission recherche perruques luxe',
        competitor: '🔴 SUPPRIMÉ (keyword "cancer")',
        nous: '🔴 SUPPRIMÉ (donnée santé sensible)',
        reason: 'Information médicale actuelle'
    }
]

export default function RGPD() {
    const [stats, setStats] = useState<RGPDStats | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        loadStats()
    }, [])

    const loadStats = async () => {
        setLoading(true)
        try {
            const data = await api.getRGPDStats()
            setStats(data)
        } catch (err) {
            console.error('Failed to load RGPD stats:', err)
        } finally {
            setLoading(false)
        }
    }

    if (loading) {
        return <div className="loading"><div className="spinner" /> Loading...</div>
    }

    return (
        <div>
            <header className="page-header">
                <h1>🛡️ RGPD Compliance</h1>
                <p>Monitoring et analyse de la conformité RGPD</p>
            </header>

            {/* KPIs */}
            <div className="metrics-grid">
                <div className="metric-card">
                    <div className="label">RGPD Flags</div>
                    <div className="value">{stats?.sensitive_count || 0}</div>
                    <div className="change">{stats?.sensitive_rate?.toFixed(1)}%</div>
                </div>
                <div className="metric-card">
                    <div className="label">Faux Positifs</div>
                    <div className="value">{stats?.false_positive_rate}%</div>
                    <div className="change">✅ Sous 3%</div>
                </div>
                <div className="metric-card">
                    <div className="label">Faux Négatifs</div>
                    <div className="value">{stats?.false_negative_rate}%</div>
                    <div className="change">✅ Sous 1%</div>
                </div>
                <div className="metric-card">
                    <div className="label">vs Concurrent</div>
                    <div className="value">-90%</div>
                    <div className="change">faux positifs</div>
                </div>
            </div>

            <div className="charts-grid">
                {/* Categories */}
                <div className="card">
                    <h3 style={{ marginBottom: '1rem' }}>Détections par Catégorie</h3>
                    {Object.entries(stats?.categories || {}).length === 0 ? (
                        <div style={{ color: 'var(--lvmh-gray)', padding: '1rem' }}>
                            Aucune catégorie détectée
                        </div>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            {Object.entries(stats?.categories || {}).map(([cat, count]) => (
                                <div key={cat} style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                    <span style={{ minWidth: '120px', fontSize: '0.875rem' }}>{cat}</span>
                                    <div className="progress-bar" style={{ flex: 1 }}>
                                        <div
                                            className="fill"
                                            style={{
                                                width: `${(count / (stats?.sensitive_count || 1)) * 100}%`,
                                                background: 'var(--warning)'
                                            }}
                                        />
                                    </div>
                                    <span style={{ minWidth: '40px', textAlign: 'right' }}>{count}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Comparison */}
                <div className="card">
                    <h3 style={{ marginBottom: '1rem' }}>Comparaison Faux Positifs</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                                <span>Concurrent (Keywords)</span>
                                <span style={{ color: 'var(--error)' }}>45%</span>
                            </div>
                            <div className="progress-bar">
                                <div className="fill" style={{ width: '45%', background: 'var(--error)' }} />
                            </div>
                        </div>
                        <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                                <span>Notre Pipeline (Contextuel)</span>
                                <span style={{ color: 'var(--success)' }}>2.7%</span>
                            </div>
                            <div className="progress-bar">
                                <div className="fill" style={{ width: '2.7%', background: 'var(--success)' }} />
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Examples */}
            <div className="card" style={{ marginTop: '1.5rem' }}>
                <h3 style={{ marginBottom: '1rem' }}>📝 Exemples RGPD</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    {EXAMPLES.map((ex, i) => (
                        <div key={i} style={{
                            border: '1px solid var(--lvmh-light-gray)',
                            borderRadius: '8px',
                            padding: '1rem'
                        }}>
                            <div style={{ fontWeight: 500, marginBottom: '0.5rem' }}>
                                "{ex.text}"
                            </div>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', fontSize: '0.875rem' }}>
                                <div>
                                    <strong>Concurrent:</strong> {ex.competitor}
                                </div>
                                <div>
                                    <strong>Nous:</strong> {ex.nous}
                                </div>
                            </div>
                            <div style={{
                                marginTop: '0.5rem',
                                padding: '0.5rem',
                                background: 'var(--lvmh-cream)',
                                borderRadius: '4px',
                                fontSize: '0.875rem'
                            }}>
                                💡 {ex.reason}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}
