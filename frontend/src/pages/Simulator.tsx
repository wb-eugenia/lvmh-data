import { useState } from 'react'
import api, { ExtractionResult, APIError } from '../lib/api'

const PRESETS = {
    'Custom...': '',
    'Note Simple (Tier 1)': 'Je cherche un sac noir, budget 2000 euros.',
    'Note VIC Complexe (Tier 3)': 'Client VIC M. Arnault. Cadeau pour sa fille. Attention allergie sévère aux noix. Budget illimité.',
    'Note RGPD Sensible': 'La cliente est en rémission de cancer, elle veut une écharpe douce.',
    'Note Budget Implicite': 'Je veux quelque chose de pas trop cher, moins de 5k.'
}

export default function Simulator() {
    const [text, setText] = useState('')
    const [language, setLanguage] = useState<'FR' | 'EN' | 'IT'>('FR')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [result, setResult] = useState<ExtractionResult | null>(null)

    const handlePresetChange = (preset: string) => {
        setText(PRESETS[preset as keyof typeof PRESETS] || '')
    }

    const handleAnalyze = async () => {
        if (text.length < 10) {
            setError('Le texte doit contenir au moins 10 caractères')
            return
        }

        setLoading(true)
        setError(null)
        setResult(null)

        try {
            const data = await api.analyzeNote(text, language)
            setResult(data)
        } catch (err) {
            if (err instanceof APIError) {
                if (err.status === 429) {
                    setError('Trop de requêtes. Attendez 1 minute.')
                } else {
                    setError(err.message)
                }
            } else {
                setError('Erreur de connexion')
            }
        } finally {
            setLoading(false)
        }
    }

    return (
        <div>
            <header className="page-header">
                <h1>🧪 Simulator</h1>
                <p>Testez l'extraction de tags en temps réel</p>
            </header>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                {/* Input Panel */}
                <div className="card">
                    <h3 style={{ marginBottom: '1rem' }}>Input</h3>

                    <div style={{ marginBottom: '1rem' }}>
                        <label style={{ fontSize: '0.75rem', color: 'var(--lvmh-gray)', display: 'block', marginBottom: '0.25rem' }}>
                            Exemples préconfigurés
                        </label>
                        <select
                            className="input"
                            onChange={(e) => handlePresetChange(e.target.value)}
                        >
                            {Object.keys(PRESETS).map(preset => (
                                <option key={preset} value={preset}>{preset}</option>
                            ))}
                        </select>
                    </div>

                    <div style={{ marginBottom: '1rem' }}>
                        <label style={{ fontSize: '0.75rem', color: 'var(--lvmh-gray)', display: 'block', marginBottom: '0.25rem' }}>
                            Note vocale client
                        </label>
                        <textarea
                            className="input textarea"
                            placeholder="Ex: Cliente cherche sac cuir vegan, budget 3000€, pour anniversaire de mariage..."
                            value={text}
                            onChange={(e) => setText(e.target.value)}
                            style={{ minHeight: '150px' }}
                        />
                    </div>

                    <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end' }}>
                        <div>
                            <label style={{ fontSize: '0.75rem', color: 'var(--lvmh-gray)', display: 'block', marginBottom: '0.25rem' }}>
                                Langue
                            </label>
                            <select
                                className="input"
                                style={{ width: '100px' }}
                                value={language}
                                onChange={(e) => setLanguage(e.target.value as 'FR' | 'EN' | 'IT')}
                            >
                                <option value="FR">🇫🇷 FR</option>
                                <option value="EN">🇬🇧 EN</option>
                                <option value="IT">🇮🇹 IT</option>
                            </select>
                        </div>

                        <button
                            className="btn btn-primary"
                            onClick={handleAnalyze}
                            disabled={loading || text.length < 10}
                            style={{ flex: 1 }}
                        >
                            {loading ? (
                                <>
                                    <div className="spinner" style={{ width: '16px', height: '16px' }} />
                                    Analyse en cours...
                                </>
                            ) : (
                                '🚀 Analyser'
                            )}
                        </button>
                    </div>

                    {error && <div className="error" style={{ marginTop: '1rem' }}>{error}</div>}
                </div>

                {/* Result Panel */}
                <div className="card">
                    <h3 style={{ marginBottom: '1rem' }}>Résultat</h3>

                    {!result ? (
                        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--lvmh-gray)' }}>
                            Entrez une note et cliquez sur Analyser
                        </div>
                    ) : (
                        <>
                            {/* Metrics */}
                            <div className="metrics-grid" style={{ marginBottom: '1rem' }}>
                                <div className="metric-card">
                                    <div className="label">Tier</div>
                                    <div className="value">
                                        <span className={`tag tier-${result.routing.tier}`} style={{ fontSize: '1.25rem' }}>
                                            Tier {result.routing.tier}
                                        </span>
                                    </div>
                                </div>
                                <div className="metric-card">
                                    <div className="label">Confidence</div>
                                    <div className="value">{(result.routing.confidence * 100).toFixed(0)}%</div>
                                </div>
                                <div className="metric-card">
                                    <div className="label">Temps</div>
                                    <div className="value">{result.processing_time_ms.toFixed(0)}ms</div>
                                </div>
                            </div>

                            {/* Tags */}
                            <div style={{ marginBottom: '1rem' }}>
                                <h4 style={{ fontSize: '0.875rem', marginBottom: '0.5rem' }}>🏷️ Tags Extraits</h4>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
                                    {result.tags.map((tag, i) => (
                                        <span key={i} className="tag">{tag}</span>
                                    ))}
                                </div>
                            </div>

                            {/* RGPD */}
                            {result.rgpd.contains_sensitive && (
                                <div style={{
                                    background: 'rgba(245, 158, 11, 0.1)',
                                    border: '1px solid var(--warning)',
                                    borderRadius: '6px',
                                    padding: '0.75rem',
                                    marginBottom: '1rem'
                                }}>
                                    <strong>⚠️ RGPD Sensitive</strong>
                                    <p style={{ fontSize: '0.875rem', margin: '0.5rem 0 0' }}>
                                        Categories: {result.rgpd.categories_detected.join(', ')}
                                    </p>
                                </div>
                            )}

                            {/* Cache Hit */}
                            {result.cache_hit && (
                                <div className="success" style={{ fontSize: '0.875rem' }}>
                                    ⚡ Cache hit - résultat instantané
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>
        </div>
    )
}
