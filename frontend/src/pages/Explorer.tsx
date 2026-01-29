import { useEffect, useState } from 'react'
import api, { PaginatedResults, APIError } from '../lib/api'

export default function Explorer() {
    const [results, setResults] = useState<PaginatedResults | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [page, setPage] = useState(1)
    const [filters, setFilters] = useState({
        tier: undefined as number | undefined,
        search: '',
        sensitive_only: false
    })

    useEffect(() => {
        loadResults()
    }, [page, filters])

    const loadResults = async () => {
        setLoading(true)
        setError(null)

        try {
            const data = await api.getResults(page, 20, {
                tier: filters.tier,
                search: filters.search || undefined,
                sensitive_only: filters.sensitive_only
            })
            setResults(data)
        } catch (err) {
            if (err instanceof APIError) {
                setError(err.message)
            } else {
                setError('Failed to load results')
            }
        } finally {
            setLoading(false)
        }
    }

    return (
        <div>
            <header className="page-header">
                <h1>🔍 Data Explorer</h1>
                <p>Explorez et filtrez les résultats d'extraction</p>
            </header>

            {/* Filters */}
            <div className="card" style={{ marginBottom: '1.5rem', display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
                <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--lvmh-gray)', display: 'block', marginBottom: '0.25rem' }}>
                        Filter by Tier
                    </label>
                    <select
                        className="input"
                        style={{ width: '120px' }}
                        value={filters.tier || ''}
                        onChange={(e) => setFilters({ ...filters, tier: e.target.value ? Number(e.target.value) : undefined })}
                    >
                        <option value="">All</option>
                        <option value="1">Tier 1</option>
                        <option value="2">Tier 2</option>
                        <option value="3">Tier 3</option>
                    </select>
                </div>

                <div style={{ flex: 1, minWidth: '200px' }}>
                    <label style={{ fontSize: '0.75rem', color: 'var(--lvmh-gray)', display: 'block', marginBottom: '0.25rem' }}>
                        Search in Text
                    </label>
                    <input
                        type="text"
                        className="input"
                        placeholder="Search..."
                        value={filters.search}
                        onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                    />
                </div>

                <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--lvmh-gray)', display: 'block', marginBottom: '0.25rem' }}>
                        RGPD
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                        <input
                            type="checkbox"
                            checked={filters.sensitive_only}
                            onChange={(e) => setFilters({ ...filters, sensitive_only: e.target.checked })}
                        />
                        Sensitive Only
                    </label>
                </div>

                <button className="btn btn-secondary" onClick={loadResults}>
                    🔄 Refresh
                </button>
            </div>

            {/* Results Table */}
            {loading ? (
                <div className="loading"><div className="spinner" /> Loading...</div>
            ) : error ? (
                <div className="error">{error}</div>
            ) : (
                <div className="card">
                    <div style={{ marginBottom: '1rem', color: 'var(--lvmh-gray)', fontSize: '0.875rem' }}>
                        Showing {results?.items.length} of {results?.total} results
                    </div>

                    <div className="table-container">
                        <table>
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Tier</th>
                                    <th>Confidence</th>
                                    <th>Tags</th>
                                    <th>Time</th>
                                    <th>RGPD</th>
                                </tr>
                            </thead>
                            <tbody>
                                {results?.items.map((item) => (
                                    <tr key={item.id}>
                                        <td style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{item.id}</td>
                                        <td>
                                            <span className={`tag tier-${item.routing.tier}`}>
                                                Tier {item.routing.tier}
                                            </span>
                                        </td>
                                        <td>{(item.routing.confidence * 100).toFixed(0)}%</td>
                                        <td>
                                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '2px' }}>
                                                {item.tags.slice(0, 3).map((tag, i) => (
                                                    <span key={i} className="tag">{tag}</span>
                                                ))}
                                                {item.tags.length > 3 && (
                                                    <span className="tag">+{item.tags.length - 3}</span>
                                                )}
                                            </div>
                                        </td>
                                        <td>{item.processing_time_ms.toFixed(0)}ms</td>
                                        <td>
                                            {item.rgpd.contains_sensitive && (
                                                <span style={{ color: 'var(--warning)' }}>⚠️</span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {/* Pagination */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem' }}>
                        <button
                            className="btn btn-secondary"
                            disabled={page <= 1}
                            onClick={() => setPage(p => p - 1)}
                        >
                            ← Previous
                        </button>
                        <span>Page {page} of {results?.total_pages || 1}</span>
                        <button
                            className="btn btn-secondary"
                            disabled={page >= (results?.total_pages || 1)}
                            onClick={() => setPage(p => p + 1)}
                        >
                            Next →
                        </button>
                    </div>
                </div>
            )}
        </div>
    )
}
