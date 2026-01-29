import { useEffect, useState } from 'react'
import api, { OverviewStats, APIError } from '../lib/api'

export default function Dashboard() {
    const [stats, setStats] = useState<OverviewStats | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        loadStats()
    }, [])

    const loadStats = async () => {
        setLoading(true)
        setError(null)

        try {
            const data = await api.getOverviewStats()
            setStats(data)
        } catch (err) {
            if (err instanceof APIError) {
                setError(err.message)
            } else {
                setError('Failed to load stats')
            }
        } finally {
            setLoading(false)
        }
    }

    if (loading) {
        return (
            <div className="loading">
                <div className="spinner" /> Loading...
            </div>
        )
    }

    if (error) {
        return (
            <div className="error">
                {error}
                <button className="btn btn-secondary" onClick={loadStats} style={{ marginLeft: '1rem' }}>
                    Retry
                </button>
            </div>
        )
    }

    return (
        <div>
            <header className="page-header">
                <h1>📊 Dashboard Overview</h1>
                <p>Vue d'ensemble des performances du pipeline</p>
            </header>

            {/* KPI Metrics */}
            <div className="metrics-grid">
                <div className="metric-card">
                    <div className="label">Notes Traitées</div>
                    <div className="value">{stats?.total_notes.toLocaleString() || 0}</div>
                </div>

                <div className="metric-card">
                    <div className="label">Tags Extraits</div>
                    <div className="value">{stats?.total_tags.toLocaleString() || 0}</div>
                </div>

                <div className="metric-card">
                    <div className="label">Confiance Moyenne</div>
                    <div className="value">{((stats?.avg_confidence || 0) * 100).toFixed(1)}%</div>
                </div>

                <div className="metric-card">
                    <div className="label">Temps Moyen</div>
                    <div className="value">{stats?.avg_processing_time_ms.toFixed(0) || 0}ms</div>
                </div>

                <div className="metric-card">
                    <div className="label">Cache Hit Rate</div>
                    <div className="value">{((stats?.cache_hit_rate || 0) * 100).toFixed(1)}%</div>
                    <div className="change">✓ Optimized</div>
                </div>
            </div>

            {/* Charts */}
            <div className="charts-grid">
                {/* Tier Distribution */}
                <div className="card">
                    <h3 style={{ marginBottom: '1rem' }}>Distribution par Tier</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        {stats?.tier_distribution.map(tier => (
                            <div key={tier.tier} style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                <span className={`tag tier-${tier.tier}`} style={{ minWidth: '60px' }}>
                                    Tier {tier.tier}
                                </span>
                                <div className="progress-bar" style={{ flex: 1 }}>
                                    <div className="fill" style={{ width: `${tier.percentage}%` }} />
                                </div>
                                <span style={{ minWidth: '80px', textAlign: 'right' }}>
                                    {tier.count} ({tier.percentage.toFixed(1)}%)
                                </span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Top Tags */}
                <div className="card">
                    <h3 style={{ marginBottom: '1rem' }}>Top 10 Tags</h3>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                        {Object.entries(stats?.top_tags || {}).map(([tag, count]) => (
                            <span key={tag} className="tag" style={{ fontSize: '0.875rem' }}>
                                {tag} ({count})
                            </span>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    )
}
