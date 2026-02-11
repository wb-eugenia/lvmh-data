import React, { useEffect, useMemo, useState } from 'react'
import {
    Activity,
    AlertTriangle,
    ArrowLeft,
    BarChart3,
    CalendarDays,
    Clock3,
    Coins,
    Database,
    Download,
    RefreshCcw,
    Server,
    ShieldAlert,
    ShieldCheck,
    Wifi,
    WifiOff,
    LogOut,
    X
} from 'lucide-react'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { apiFetch, wsUrl } from '../lib/api'
import { useAuth } from '../context/AuthContext'

const REFRESH_INTERVAL_MS = 30000
const WINDOW_PRESETS = [
    { label: '24h', days: 1 },
    { label: '7 jours', days: 7 },
    { label: '30 jours', days: 30 },
    { label: '90 jours', days: 90 }
]

const normalizePipelineStep = (step) => {
    const raw = String(step || '').toLowerCase()
    if (!raw) return null
    if (raw === 'failed' || raw.includes('error')) return 'failed'
    if (raw === 'done' || raw === 'cache_hit' || raw === 'semantic_cache_hit') return 'done'
    if (raw === 'cleaning' || raw === 'rgpd') return 'cleaning'
    if (raw === 'routing') return 'routing'
    if (raw.includes('tier') || raw === 'cross_validation' || raw === 'extraction') return 'extraction'
    if (raw === 'rag') return 'rag'
    if (raw === 'injection' || raw === 'nba') return 'nba'
    return raw
}

const formatPercent = (value) => {
    if (value === null || value === undefined || Number.isNaN(value)) return '-'
    const normalized = value <= 1 ? value * 100 : value
    return `${Math.round(normalized)}%`
}

const formatCurrency = (value) => {
    if (value === null || value === undefined || Number.isNaN(value)) return '-'
    try {
        return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 2 }).format(value)
    } catch {
        return `${value} EUR`
    }
}

const formatDuration = (ms) => {
    if (ms === null || ms === undefined || Number.isNaN(ms)) return '-'
    if (ms < 1000) return `${Math.round(ms)}ms`
    return `${(ms / 1000).toFixed(1)}s`
}

const formatDateTime = (value) => {
    if (!value) return '-'
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return '-'
    return date.toLocaleString('fr-FR')
}

const formatDateOnly = (value) => {
    if (!value) return '-'
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return value
    return date.toLocaleDateString('fr-FR')
}

const buildLiveEvent = (payload) => {
    const step = normalizePipelineStep(payload?.step)
    if (!step) return null

    if (step === 'failed') {
        return {
            severity: 'critical',
            title: 'Pipeline failed',
            message: payload?.error || 'Echec de traitement detecte',
            timestamp: new Date().toISOString()
        }
    }

    if (step === 'routing' && Number(payload?.tier || 0) === 3) {
        return {
            severity: 'warning',
            title: 'Escalade Tier 3',
            message: payload?.score ? `Note complexe (score ${payload.score})` : 'Note complexe routee',
            timestamp: new Date().toISOString()
        }
    }

    if (step === 'done') {
        return {
            severity: 'info',
            title: 'Pipeline complete',
            message: payload?.quality_score ? `Qualite ${formatPercent(payload.quality_score)}` : 'Traitement termine',
            timestamp: new Date().toISOString()
        }
    }

    return {
        severity: 'info',
        title: `Etape ${step}`,
        message: payload?.status || 'Evenement pipeline recu',
        timestamp: new Date().toISOString()
    }
}

const componentStatus = (value) => {
    if (!value || typeof value !== 'object') return { label: 'Unknown', tone: 'text-lvmh-gray border-white/10 bg-white/5' }
    if (value.error) return { label: 'Error', tone: 'text-red-300 border-red-500/30 bg-red-500/10' }
    if (value.enabled === false) return { label: 'Disabled', tone: 'text-lvmh-gray border-white/10 bg-white/5' }
    return { label: 'OK', tone: 'text-green-300 border-green-500/30 bg-green-500/10' }
}

export default function AdminView({ onBack }) {
    const { logout } = useAuth()
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [windowDays, setWindowDays] = useState(30)
    const [exporting, setExporting] = useState(null)
    const [metrics, setMetrics] = useState(null)
    const [summary, setSummary] = useState(null)
    const [timeseries, setTimeseries] = useState(null)
    const [selectedTrendDate, setSelectedTrendDate] = useState(null)
    const [dayDetails, setDayDetails] = useState(null)
    const [dayDetailsLoading, setDayDetailsLoading] = useState(false)
    const [dayDetailsError, setDayDetailsError] = useState(null)
    const [selectedNoteId, setSelectedNoteId] = useState(null)
    const [noteDetails, setNoteDetails] = useState(null)
    const [noteDetailsLoading, setNoteDetailsLoading] = useState(false)
    const [noteDetailsError, setNoteDetailsError] = useState(null)
    const [components, setComponents] = useState(null)
    const [rgpdStats, setRgpdStats] = useState(null)
    const [costStats, setCostStats] = useState(null)
    const [liveEvents, setLiveEvents] = useState([])
    const [socketState, setSocketState] = useState('connecting')
    const [lastRefreshAt, setLastRefreshAt] = useState(null)

    const buildQuery = () => {
        const params = new URLSearchParams()
        if (windowDays) params.set('days', String(windowDays))
        const queryString = params.toString()
        return queryString ? `?${queryString}` : ''
    }

    const fetchDashboard = async () => {
        setError(null)
        try {
            const query = buildQuery()
            const [metricsRes, summaryRes, timeseriesRes, componentsRes, rgpdRes, costRes] = await Promise.all([
                apiFetch(`/api/dashboard/metrics${query}`),
                apiFetch(`/api/dashboard/metrics/summary${query}`),
                apiFetch(`/api/dashboard/metrics/timeseries${query}`),
                apiFetch('/api/dashboard/components/status'),
                apiFetch(`/api/stats/rgpd${query}`),
                apiFetch(`/api/stats/cost${query}`)
            ])

            if (metricsRes.ok) setMetrics(await metricsRes.json())
            if (summaryRes.ok) setSummary(await summaryRes.json())
            if (timeseriesRes.ok) setTimeseries(await timeseriesRes.json())
            if (componentsRes.ok) setComponents(await componentsRes.json())
            if (rgpdRes.ok) setRgpdStats(await rgpdRes.json())
            if (costRes.ok) setCostStats(await costRes.json())

            setLastRefreshAt(new Date().toISOString())
        } catch (fetchError) {
            setError(fetchError.message || 'Erreur de chargement dashboard')
        } finally {
            setLoading(false)
        }
    }

    const exportMetrics = async (format) => {
        setError(null)
        setExporting(format)
        try {
            const query = buildQuery()
            const separator = query ? '&' : '?'
            const response = await apiFetch(`/api/dashboard/metrics/export${query}${separator}format=${format}`)
            if (!response.ok) {
                const body = await response.text()
                throw new Error(body || `Export ${format} indisponible`)
            }

            const blob = await response.blob()
            const objectUrl = URL.createObjectURL(blob)
            const filename = `admin_metrics_${windowDays}d.${format}`

            const anchor = document.createElement('a')
            anchor.href = objectUrl
            anchor.download = filename
            document.body.appendChild(anchor)
            anchor.click()
            anchor.remove()
            URL.revokeObjectURL(objectUrl)
        } catch (exportError) {
            setError(exportError.message || 'Erreur export')
        } finally {
            setExporting(null)
        }
    }

    useEffect(() => {
        fetchDashboard()
        const timer = setInterval(fetchDashboard, REFRESH_INTERVAL_MS)
        return () => clearInterval(timer)
    }, [windowDays])

    useEffect(() => {
        const rows = timeseries?.series || []
        if (rows.length === 0) {
            setSelectedTrendDate(null)
            setDayDetails(null)
            setDayDetailsError(null)
            setSelectedNoteId(null)
            setNoteDetails(null)
            setNoteDetailsError(null)
            return
        }

        const selectedStillPresent = selectedTrendDate && rows.some((item) => item.date === selectedTrendDate)
        if (!selectedStillPresent) {
            setSelectedTrendDate(rows[rows.length - 1]?.date || null)
        }
    }, [timeseries, selectedTrendDate])

    useEffect(() => {
        if (!selectedTrendDate) {
            setDayDetails(null)
            setDayDetailsError(null)
            setSelectedNoteId(null)
            setNoteDetails(null)
            setNoteDetailsError(null)
            return
        }

        let isActive = true
        const fetchDayDetails = async () => {
            setDayDetailsLoading(true)
            setDayDetailsError(null)
            try {
                const response = await apiFetch(`/api/dashboard/metrics/day-details?date=${encodeURIComponent(selectedTrendDate)}&limit=40`)
                if (!response.ok) {
                    const body = await response.text()
                    throw new Error(body || 'Erreur detail journalier')
                }
                const payload = await response.json()
                if (!isActive) return
                setDayDetails(payload)
            } catch (fetchError) {
                if (!isActive) return
                setDayDetailsError(fetchError.message || 'Erreur detail journalier')
                setDayDetails(null)
            } finally {
                if (!isActive) return
                setDayDetailsLoading(false)
            }
        }

        fetchDayDetails()
        return () => {
            isActive = false
        }
    }, [selectedTrendDate])

    useEffect(() => {
        if (!selectedNoteId) {
            setNoteDetails(null)
            setNoteDetailsError(null)
            return
        }

        let isActive = true
        const fetchNoteDetails = async () => {
            setNoteDetailsLoading(true)
            setNoteDetailsError(null)
            try {
                const response = await apiFetch(`/api/dashboard/metrics/note-details/${selectedNoteId}`)
                if (!response.ok) {
                    const body = await response.text()
                    throw new Error(body || 'Erreur detail note')
                }
                const payload = await response.json()
                if (!isActive) return
                setNoteDetails(payload)
            } catch (fetchError) {
                if (!isActive) return
                setNoteDetails(null)
                setNoteDetailsError(fetchError.message || 'Erreur detail note')
            } finally {
                if (!isActive) return
                setNoteDetailsLoading(false)
            }
        }

        fetchNoteDetails()
        return () => {
            isActive = false
        }
    }, [selectedNoteId])

    useEffect(() => {
        if (!selectedNoteId) return
        const onKeyDown = (event) => {
            if (event.key === 'Escape') {
                closeNoteDetails()
            }
        }
        window.addEventListener('keydown', onKeyDown)
        return () => window.removeEventListener('keydown', onKeyDown)
    }, [selectedNoteId])

    useEffect(() => {
        const socketUrl = wsUrl('/ws/pipeline')
        let ws
        let reconnectTimer
        let isActive = true

        const connect = () => {
            if (!isActive) return
            setSocketState('connecting')
            ws = new WebSocket(socketUrl)

            ws.onopen = () => {
                if (!isActive) return
                setSocketState('connected')
            }

            ws.onmessage = (event) => {
                if (!isActive) return
                try {
                    const payload = JSON.parse(event.data || '{}')
                    if (!payload?.step) return
                    const nextEvent = buildLiveEvent(payload)
                    if (!nextEvent) return
                    setLiveEvents((previous) => [nextEvent, ...previous].slice(0, 40))
                } catch (parseError) {
                    console.error('Admin WS parse error:', parseError)
                }
            }

            ws.onerror = () => {
                if (!isActive) return
                setSocketState('disconnected')
            }

            ws.onclose = () => {
                if (!isActive) return
                setSocketState('disconnected')
                reconnectTimer = setTimeout(connect, 3000)
            }
        }

        connect()

        return () => {
            isActive = false
            if (reconnectTimer) clearTimeout(reconnectTimer)
            ws?.close()
        }
    }, [])

    const pipeline = metrics?.pipeline_stats || {}
    const quality = metrics?.quality_metrics || {}
    const cache = metrics?.cache_stats || {}
    const mergedCost = metrics?.cost_stats || costStats || {}
    const alerts = summary?.alerts || metrics?.alerts || []

    const componentRows = useMemo(
        () => Object.entries(components || {}),
        [components]
    )
    const trendRows = useMemo(() => {
        return (timeseries?.series || []).map((item) => {
            const date = new Date(item.date)
            const label = Number.isNaN(date.getTime())
                ? item.date
                : date.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })

            return {
                ...item,
                label,
                fullLabel: Number.isNaN(date.getTime()) ? item.date : date.toLocaleDateString('fr-FR')
            }
        })
    }, [timeseries])

    const healthScore = Math.round(summary?.health_score || 0)
    const healthTone = summary?.health_status === 'healthy'
        ? 'text-green-300 border-green-500/30 bg-green-500/10'
        : summary?.health_status === 'warning'
            ? 'text-lvmh-gold border-lvmh-gold/30 bg-lvmh-gold/10'
            : 'text-red-300 border-red-500/30 bg-red-500/10'

    const liveCritical = liveEvents.filter((event) => event.severity === 'critical').length
    const liveWarning = liveEvents.filter((event) => event.severity === 'warning').length
    const liveInfo = liveEvents.filter((event) => event.severity === 'info').length
    const currentWindowLabel = WINDOW_PRESETS.find((preset) => preset.days === windowDays)?.label || `${windowDays} jours`
    const trendTotals = timeseries?.totals || {}
    const dailySummary = dayDetails?.summary || {}
    const dailyNotes = dayDetails?.notes || []
    const noteSummary = noteDetails?.note || {}
    const noteRouting = noteDetails?.routing || {}
    const noteQuality = noteDetails?.quality || {}
    const noteRgpd = noteDetails?.rgpd || {}
    const noteNba = noteDetails?.next_best_action || {}
    const noteProducts = noteDetails?.matched_products || []
    const noteTags = noteDetails?.tags || []
    const noteAudio = noteDetails?.audio || { available: false, sources: [] }

    const handleTrendChartClick = (state) => {
        const clickedDate = state?.activePayload?.[0]?.payload?.date
        if (clickedDate) {
            setSelectedTrendDate(clickedDate)
        }
    }

    const openNoteDetails = (noteId) => {
        if (!noteId) return
        setSelectedNoteId(noteId)
    }

    const closeNoteDetails = () => {
        setSelectedNoteId(null)
        setNoteDetails(null)
        setNoteDetailsError(null)
    }

    const handleLogout = () => {
        logout()
        if (onBack) onBack()
        else window.location.assign('/login')
    }

    return (
        <div className="min-h-screen bg-lvmh-black text-white p-6 md:p-8">
            <div className="max-w-7xl mx-auto space-y-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                        <button
                            onClick={() => (onBack ? onBack() : window.history.back())}
                            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-white/10 hover:border-lvmh-gold/40 hover:text-lvmh-gold transition-colors"
                        >
                            <ArrowLeft size={16} />
                            Retour
                        </button>
                        <div>
                            <h1 className="text-2xl md:text-3xl font-display font-black gold-text">Admin Total</h1>
                            <p className="text-xs uppercase tracking-widest text-lvmh-gray">Monitoring plateforme, couts, rgpd, sante systeme</p>
                            <p className="text-[11px] text-lvmh-gray mt-1">Fenetre active: {currentWindowLabel}</p>
                        </div>
                    </div>

                    <div className="flex flex-wrap items-center justify-end gap-2">
                        <div className="inline-flex items-center gap-2 px-2 py-1.5 rounded-lg border border-white/10 bg-white/[0.02]">
                            <CalendarDays size={13} className="text-lvmh-gold" />
                            <select
                                value={windowDays}
                                onChange={(event) => setWindowDays(Number(event.target.value))}
                                className="bg-transparent text-xs uppercase tracking-widest text-white focus:outline-none"
                            >
                                {WINDOW_PRESETS.map((preset) => (
                                    <option key={preset.days} value={preset.days} className="bg-lvmh-black">
                                        {preset.label}
                                    </option>
                                ))}
                            </select>
                        </div>

                        <span className={`text-[10px] px-2 py-1 rounded-full border inline-flex items-center gap-1 ${socketState === 'connected' ? 'border-green-500/40 text-green-400 bg-green-500/10' : socketState === 'connecting' ? 'border-lvmh-gold/40 text-lvmh-gold bg-lvmh-gold/10' : 'border-red-500/40 text-red-400 bg-red-500/10'}`}>
                            {socketState === 'connected' ? <Wifi size={11} /> : <WifiOff size={11} />}
                            {socketState === 'connected' ? 'WS LIVE' : socketState === 'connecting' ? 'WS CONNECT' : 'WS OFF'}
                        </span>

                        <button
                            onClick={() => exportMetrics('json')}
                            disabled={Boolean(exporting)}
                            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-white/10 text-xs uppercase tracking-widest hover:border-lvmh-gold/40 hover:text-lvmh-gold transition-colors disabled:opacity-50"
                        >
                            <Download size={12} />
                            {exporting === 'json' ? 'Export JSON...' : 'Export JSON'}
                        </button>
                        <button
                            onClick={() => exportMetrics('csv')}
                            disabled={Boolean(exporting)}
                            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-white/10 text-xs uppercase tracking-widest hover:border-lvmh-gold/40 hover:text-lvmh-gold transition-colors disabled:opacity-50"
                        >
                            <Download size={12} />
                            {exporting === 'csv' ? 'Export CSV...' : 'Export CSV'}
                        </button>

                        <button
                            onClick={fetchDashboard}
                            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-white/10 text-xs uppercase tracking-widest hover:border-lvmh-gold/40 hover:text-lvmh-gold transition-colors"
                        >
                            <RefreshCcw size={12} />
                            Refresh
                        </button>
                        <button
                            onClick={handleLogout}
                            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-red-500/40 text-red-300 text-xs uppercase tracking-widest hover:bg-red-500/10 transition-colors"
                        >
                            <LogOut size={12} />
                            Deconnexion
                        </button>
                    </div>
                </div>

                {error && (
                    <div className="glass p-4 border border-red-500/30 bg-red-500/10 text-sm text-red-200">
                        {error}
                    </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                    <div className="glass p-5">
                        <div className="text-[10px] uppercase tracking-widest text-lvmh-gray mb-2">Health Score</div>
                        <div className={`inline-flex px-3 py-1 rounded-full border text-sm font-bold ${healthTone}`}>
                            {healthScore}/100
                        </div>
                        <div className="mt-3 text-xs text-lvmh-gray">Updated: {formatDateTime(lastRefreshAt)}</div>
                    </div>

                    <div className="glass p-5">
                        <div className="text-[10px] uppercase tracking-widest text-lvmh-gray mb-2 flex items-center gap-1">
                            <Database size={12} /> Notes Processed
                        </div>
                        <div className="text-3xl font-black">{pipeline?.total_processed ?? 0}</div>
                        <div className="text-xs text-lvmh-gray mt-2">Success rate: {formatPercent(pipeline?.success_rate || 0)}</div>
                    </div>

                    <div className="glass p-5">
                        <div className="text-[10px] uppercase tracking-widest text-lvmh-gray mb-2 flex items-center gap-1">
                            <Clock3 size={12} /> Processing
                        </div>
                        <div className="text-3xl font-black">{formatDuration(pipeline?.avg_processing_time_ms || 0)}</div>
                        <div className="text-xs text-lvmh-gray mt-2">Confidence: {formatPercent(pipeline?.avg_confidence || 0)}</div>
                    </div>

                    <div className="glass p-5">
                        <div className="text-[10px] uppercase tracking-widest text-lvmh-gray mb-2 flex items-center gap-1">
                            <Coins size={12} /> Cost
                        </div>
                        <div className="text-3xl font-black">{formatCurrency(mergedCost?.total_cost_eur ?? mergedCost?.total_cost ?? 0)}</div>
                        <div className="text-xs text-lvmh-gray mt-2">Per note: {formatCurrency(mergedCost?.cost_per_note ?? mergedCost?.roi_metrics?.cost_per_note ?? 0)}</div>
                    </div>
                </div>

                <div className="glass p-6">
                    <div className="flex flex-wrap items-center justify-between gap-2 mb-5">
                        <h3 className="text-lg font-bold flex items-center gap-2">
                            <Activity size={18} className="text-lvmh-gold" />
                            Trends ({currentWindowLabel})
                        </h3>
                        <div className="text-xs text-lvmh-gray">
                            {trendRows.length} points • {trendTotals?.alerts_count ?? 0} alertes total
                        </div>
                    </div>

                    {trendRows.length > 0 ? (
                        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                            <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
                                <div className="text-[10px] uppercase tracking-widest text-lvmh-gray mb-2">Cost / day</div>
                                <div className="text-xl font-black mb-3">{formatCurrency(trendTotals?.cost_eur ?? 0)}</div>
                                <div className="h-44">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <AreaChart data={trendRows} onClick={handleTrendChartClick}>
                                            <defs>
                                                <linearGradient id="costFill" x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="5%" stopColor="#D4AF37" stopOpacity={0.45} />
                                                    <stop offset="95%" stopColor="#D4AF37" stopOpacity={0} />
                                                </linearGradient>
                                            </defs>
                                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                                            <XAxis dataKey="label" tick={{ fill: '#A3A3A3', fontSize: 11 }} />
                                            <YAxis tick={{ fill: '#A3A3A3', fontSize: 11 }} width={38} />
                                            <Tooltip
                                                contentStyle={{ background: '#0b0b0b', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '0.5rem' }}
                                                formatter={(value) => [formatCurrency(Number(value)), 'Cost']}
                                                labelFormatter={(_, payload) => payload?.[0]?.payload?.fullLabel || '-'}
                                            />
                                            <Area type="monotone" dataKey="cost_eur" stroke="#D4AF37" fillOpacity={1} fill="url(#costFill)" strokeWidth={2} />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>

                            <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
                                <div className="text-[10px] uppercase tracking-widest text-lvmh-gray mb-2">Latency / day</div>
                                <div className="text-xl font-black mb-3">{formatDuration(trendTotals?.avg_processing_time_ms ?? 0)}</div>
                                <div className="h-44">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <AreaChart data={trendRows} onClick={handleTrendChartClick}>
                                            <defs>
                                                <linearGradient id="latencyFill" x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="5%" stopColor="#60A5FA" stopOpacity={0.4} />
                                                    <stop offset="95%" stopColor="#60A5FA" stopOpacity={0} />
                                                </linearGradient>
                                            </defs>
                                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                                            <XAxis dataKey="label" tick={{ fill: '#A3A3A3', fontSize: 11 }} />
                                            <YAxis tick={{ fill: '#A3A3A3', fontSize: 11 }} width={38} />
                                            <Tooltip
                                                contentStyle={{ background: '#0b0b0b', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '0.5rem' }}
                                                formatter={(value) => [formatDuration(Number(value)), 'Latency']}
                                                labelFormatter={(_, payload) => payload?.[0]?.payload?.fullLabel || '-'}
                                            />
                                            <Area type="monotone" dataKey="avg_processing_time_ms" stroke="#60A5FA" fillOpacity={1} fill="url(#latencyFill)" strokeWidth={2} />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>

                            <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
                                <div className="text-[10px] uppercase tracking-widest text-lvmh-gray mb-2">Alerts / day</div>
                                <div className="text-xl font-black mb-3">{trendTotals?.alerts_count ?? 0}</div>
                                <div className="h-44">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={trendRows} onClick={handleTrendChartClick}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                                            <XAxis dataKey="label" tick={{ fill: '#A3A3A3', fontSize: 11 }} />
                                            <YAxis tick={{ fill: '#A3A3A3', fontSize: 11 }} width={38} allowDecimals={false} />
                                            <Tooltip
                                                contentStyle={{ background: '#0b0b0b', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '0.5rem' }}
                                                formatter={(value) => [Number(value), 'Alerts']}
                                                labelFormatter={(_, payload) => payload?.[0]?.payload?.fullLabel || '-'}
                                            />
                                            <Bar dataKey="alerts_count" fill="#F87171" radius={[4, 4, 0, 0]} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="text-sm text-lvmh-gray border border-white/10 rounded-lg p-4 bg-white/[0.02]">
                            Pas encore de donnees de tendance sur cette fenetre.
                        </div>
                    )}
                </div>

                {trendRows.length > 0 && (
                    <div className="glass p-6">
                        <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                            <h3 className="text-lg font-bold">Daily Drilldown</h3>
                            <div className="text-xs text-lvmh-gray">
                                Selection: {selectedTrendDate ? formatDateOnly(selectedTrendDate) : '-'}
                            </div>
                        </div>

                        <div className="flex flex-wrap gap-2 mb-4">
                            {trendRows.slice(-12).map((item) => (
                                <button
                                    key={item.date}
                                    onClick={() => setSelectedTrendDate(item.date)}
                                    className={`px-3 py-1.5 rounded-full border text-[11px] transition-colors ${selectedTrendDate === item.date ? 'border-lvmh-gold text-lvmh-gold bg-lvmh-gold/10' : 'border-white/10 text-lvmh-gray hover:border-white/30 hover:text-white'}`}
                                >
                                    {item.label}
                                </button>
                            ))}
                        </div>

                        {dayDetailsError && (
                            <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200 mb-4">
                                {dayDetailsError}
                            </div>
                        )}

                        {dayDetailsLoading ? (
                            <div className="text-sm text-lvmh-gray border border-white/10 rounded-lg p-4 bg-white/[0.02]">
                                Chargement du detail journalier...
                            </div>
                        ) : (
                            <div className="space-y-4">
                                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                                    <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                                        <div className="text-[10px] uppercase tracking-widest text-lvmh-gray mb-1">Notes</div>
                                        <div className="font-black text-lg">{dailySummary?.total_notes ?? 0}</div>
                                    </div>
                                    <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                                        <div className="text-[10px] uppercase tracking-widest text-lvmh-gray mb-1">Success</div>
                                        <div className="font-black text-lg">{formatPercent(dailySummary?.success_rate ?? 0)}</div>
                                    </div>
                                    <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                                        <div className="text-[10px] uppercase tracking-widest text-lvmh-gray mb-1">Latency</div>
                                        <div className="font-black text-lg">{formatDuration(dailySummary?.avg_processing_time_ms ?? 0)}</div>
                                    </div>
                                    <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                                        <div className="text-[10px] uppercase tracking-widest text-lvmh-gray mb-1">Cost</div>
                                        <div className="font-black text-lg">{formatCurrency(dailySummary?.cost_eur ?? 0)}</div>
                                    </div>
                                    <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                                        <div className="text-[10px] uppercase tracking-widest text-lvmh-gray mb-1">Alerts</div>
                                        <div className="font-black text-lg">{dailySummary?.alerts_count ?? 0}</div>
                                    </div>
                                </div>

                                <div className="space-y-2 max-h-[360px] overflow-y-auto pr-1">
                                    {dailyNotes.length > 0 ? dailyNotes.map((row) => (
                                        <div
                                            key={row.note_id}
                                            className="rounded-lg border border-white/10 bg-white/[0.03] p-3 hover:border-lvmh-gold/40 transition-colors cursor-pointer"
                                            onClick={() => openNoteDetails(row.note_id)}
                                        >
                                            <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                                                <div className="font-semibold text-white">#{row.note_id}</div>
                                                <div className="flex items-center gap-2">
                                                    <div className="text-lvmh-gray">{formatDateTime(row.timestamp)}</div>
                                                    <button
                                                        onClick={(event) => {
                                                            event.stopPropagation()
                                                            openNoteDetails(row.note_id)
                                                        }}
                                                        className="px-2 py-1 rounded-full border border-white/15 text-[10px] uppercase tracking-widest text-lvmh-gray hover:border-lvmh-gold/40 hover:text-lvmh-gold transition-colors"
                                                    >
                                                        Detail
                                                    </button>
                                                </div>
                                            </div>
                                            <div className="flex flex-wrap items-center gap-2 mt-2 text-[11px]">
                                                <span className="px-2 py-0.5 rounded-full border border-white/15 text-lvmh-gray">
                                                    {row.advisor_name || 'Unknown advisor'}
                                                </span>
                                                <span className={`px-2 py-0.5 rounded-full border ${row.tier === 3 ? 'border-red-500/30 text-red-300 bg-red-500/10' : row.tier === 2 ? 'border-lvmh-gold/30 text-lvmh-gold bg-lvmh-gold/10' : 'border-white/15 text-white bg-white/[0.04]'}`}>
                                                    Tier {row.tier || 1}
                                                </span>
                                                <span className="text-lvmh-gray">Latency {formatDuration(row.processing_time_ms)}</span>
                                                <span className="text-lvmh-gray">Conf {formatPercent(row.confidence)}</span>
                                                {row.from_cache && (
                                                    <span className="px-2 py-0.5 rounded-full border border-green-500/30 text-green-300 bg-green-500/10">
                                                        Cache
                                                    </span>
                                                )}
                                            </div>
                                            <div className="text-xs text-lvmh-gray mt-2 leading-relaxed">
                                                {row.transcription_preview || 'No transcription preview.'}
                                            </div>
                                        </div>
                                    )) : (
                                        <div className="text-sm text-lvmh-gray border border-white/10 rounded-lg p-4 bg-white/[0.02]">
                                            Aucune note pour cette journee.
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                )}

                <div className="grid grid-cols-1 xl:grid-cols-[1.05fr_0.95fr] gap-6">
                    <div className="glass p-6">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-bold flex items-center gap-2">
                                <ShieldAlert size={18} className="text-lvmh-gold" />
                                System Alerts
                            </h3>
                            <span className="text-xs text-lvmh-gray">{alerts.length} alertes</span>
                        </div>
                        <div className="space-y-3">
                            {alerts.length > 0 ? alerts.map((alert, index) => (
                                <div key={`${alert}-${index}`} className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-200 flex items-start gap-2">
                                    <AlertTriangle size={14} className="text-red-400 mt-0.5" />
                                    <span>{alert}</span>
                                </div>
                            )) : (
                                <div className="rounded-lg border border-green-500/20 bg-green-500/10 p-3 text-sm text-green-200 flex items-center gap-2">
                                    <ShieldCheck size={14} />
                                    Aucun signal critique.
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="glass p-6">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-bold flex items-center gap-2">
                                <Activity size={18} className="text-lvmh-gold" />
                                Live Pipeline Feed
                            </h3>
                            <button
                                onClick={() => setLiveEvents([])}
                                className="text-[10px] uppercase tracking-widest px-2 py-1 rounded-full border border-white/10 hover:border-white/30 transition-colors"
                            >
                                Clear
                            </button>
                        </div>

                        <div className="grid grid-cols-3 gap-2 mb-4">
                            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-2 text-center">
                                <div className="text-[10px] uppercase tracking-widest text-red-300">Critical</div>
                                <div className="font-bold text-red-300">{liveCritical}</div>
                            </div>
                            <div className="bg-lvmh-gold/10 border border-lvmh-gold/20 rounded-lg p-2 text-center">
                                <div className="text-[10px] uppercase tracking-widest text-lvmh-gold">Warning</div>
                                <div className="font-bold text-lvmh-gold">{liveWarning}</div>
                            </div>
                            <div className="bg-white/5 border border-white/10 rounded-lg p-2 text-center">
                                <div className="text-[10px] uppercase tracking-widest text-lvmh-gray">Info</div>
                                <div className="font-bold text-white">{liveInfo}</div>
                            </div>
                        </div>

                        <div className="space-y-2 max-h-[260px] overflow-y-auto pr-1">
                            {liveEvents.length > 0 ? liveEvents.slice(0, 12).map((event, index) => (
                                <div
                                    key={`${event.timestamp}-${index}`}
                                    className={`rounded-lg p-3 border ${event.severity === 'critical' ? 'border-red-500/30 bg-red-500/10' : event.severity === 'warning' ? 'border-lvmh-gold/30 bg-lvmh-gold/10' : 'border-white/10 bg-white/[0.03]'}`}
                                >
                                    <div className="flex items-center justify-between gap-2">
                                        <div className={`text-xs font-semibold ${event.severity === 'critical' ? 'text-red-300' : event.severity === 'warning' ? 'text-lvmh-gold' : 'text-white'}`}>
                                            {event.title}
                                        </div>
                                        <div className="text-[10px] text-lvmh-gray">{formatDateTime(event.timestamp)}</div>
                                    </div>
                                    <div className="text-xs text-lvmh-gray mt-1">{event.message}</div>
                                </div>
                            )) : (
                                <div className="text-sm text-lvmh-gray border border-white/10 rounded-lg p-4 bg-white/[0.02]">
                                    Aucun evenement live.
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                    <div className="glass p-6">
                        <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                            <Coins size={18} className="text-lvmh-gold" />
                            Cost Breakdown
                        </h3>
                        <div className="space-y-3 text-sm">
                            <div className="flex items-center justify-between">
                                <span className="text-lvmh-gray">Tier 1</span>
                                <span>{formatCurrency(mergedCost?.tier_costs?.tier1 ?? mergedCost?.cost_by_tier?.tier_1 ?? 0)}</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-lvmh-gray">Tier 2</span>
                                <span>{formatCurrency(mergedCost?.tier_costs?.tier2 ?? mergedCost?.cost_by_tier?.tier_2 ?? 0)}</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-lvmh-gray">Tier 3</span>
                                <span>{formatCurrency(mergedCost?.tier_costs?.tier3 ?? mergedCost?.cost_by_tier?.tier_3 ?? 0)}</span>
                            </div>
                            <div className="pt-3 mt-2 border-t border-white/10 flex items-center justify-between">
                                <span className="text-lvmh-gray">Monthly estimate</span>
                                <span className="font-bold text-lvmh-gold">{formatCurrency(mergedCost?.estimated_monthly ?? mergedCost?.projection_annual ?? 0)}</span>
                            </div>
                        </div>
                    </div>

                    <div className="glass p-6">
                        <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                            <ShieldCheck size={18} className="text-lvmh-gold" />
                            RGPD Monitoring
                        </h3>
                        <div className="space-y-3 text-sm">
                            <div className="flex items-center justify-between">
                                <span className="text-lvmh-gray">Sensitive notes</span>
                                <span>{rgpdStats?.sensitive_count ?? 0}</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-lvmh-gray">Sensitive rate</span>
                                <span>{formatPercent(rgpdStats?.sensitive_rate || 0)}</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-lvmh-gray">Accuracy score</span>
                                <span>{formatPercent(quality?.accuracy_rate || 0)}</span>
                            </div>
                            <div className="pt-3 mt-2 border-t border-white/10">
                                <div className="text-xs text-lvmh-gray uppercase tracking-widest mb-2">Top categories</div>
                                <div className="space-y-1">
                                    {Object.entries(rgpdStats?.categories || {}).slice(0, 3).map(([category, count]) => (
                                        <div key={category} className="flex items-center justify-between text-xs">
                                            <span className="text-lvmh-gray">{category}</span>
                                            <span>{count}</span>
                                        </div>
                                    ))}
                                    {Object.keys(rgpdStats?.categories || {}).length === 0 && (
                                        <div className="text-xs text-lvmh-gray">No sensitive category logged.</div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="glass p-6">
                        <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                            <Server size={18} className="text-lvmh-gold" />
                            Components Status
                        </h3>
                        <div className="space-y-2">
                            {componentRows.length > 0 ? componentRows.map(([key, value]) => {
                                const status = componentStatus(value)
                                return (
                                    <div key={key} className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                                        <div className="flex items-center justify-between gap-2">
                                            <div className="text-sm font-semibold flex items-center gap-2">
                                                <BarChart3 size={13} className="text-lvmh-gold" />
                                                {key}
                                            </div>
                                            <span className={`text-[10px] px-2 py-0.5 rounded-full border ${status.tone}`}>
                                                {status.label}
                                            </span>
                                        </div>
                                        {value?.error && (
                                            <div className="text-[11px] text-red-200 mt-2 break-all">{value.error}</div>
                                        )}
                                    </div>
                                )
                            }) : (
                                <div className="text-sm text-lvmh-gray border border-white/10 rounded-lg p-4 bg-white/[0.02]">
                                    Aucune information composant.
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {selectedNoteId && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                        <button
                            aria-label="Close modal backdrop"
                            className="absolute inset-0 bg-black/80"
                            onClick={closeNoteDetails}
                        />
                        <div className="relative w-full max-w-5xl max-h-[90vh] overflow-y-auto rounded-2xl border border-white/10 bg-lvmh-black shadow-2xl">
                            <div className="sticky top-0 z-10 backdrop-blur bg-lvmh-black/90 border-b border-white/10 px-5 py-4 flex items-center justify-between">
                                <div>
                                    <div className="text-xs uppercase tracking-widest text-lvmh-gray">Note Detail</div>
                                    <div className="text-lg font-black">#{selectedNoteId}</div>
                                </div>
                                <button
                                    onClick={closeNoteDetails}
                                    className="inline-flex items-center justify-center w-8 h-8 rounded-full border border-white/15 text-lvmh-gray hover:border-lvmh-gold/40 hover:text-lvmh-gold transition-colors"
                                >
                                    <X size={14} />
                                </button>
                            </div>

                            <div className="p-5 space-y-5">
                                {noteDetailsLoading ? (
                                    <div className="text-sm text-lvmh-gray border border-white/10 rounded-lg p-4 bg-white/[0.02]">
                                        Chargement du detail note...
                                    </div>
                                ) : noteDetailsError ? (
                                    <div className="text-sm text-red-200 border border-red-500/30 rounded-lg p-4 bg-red-500/10">
                                        {noteDetailsError}
                                    </div>
                                ) : noteDetails ? (
                                    <>
                                        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
                                            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                                                <div className="text-[10px] uppercase tracking-widest text-lvmh-gray mb-1">Advisor</div>
                                                <div className="font-semibold">{noteSummary?.advisor?.name || 'Unknown'}</div>
                                                <div className="text-xs text-lvmh-gray mt-1">{noteSummary?.advisor?.store || '-'}</div>
                                            </div>
                                            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                                                <div className="text-[10px] uppercase tracking-widest text-lvmh-gray mb-1">Client</div>
                                                <div className="font-semibold">{noteSummary?.client?.name || 'Unknown'}</div>
                                                <div className="text-xs text-lvmh-gray mt-1">{noteSummary?.client?.vic_status || '-'}</div>
                                            </div>
                                            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                                                <div className="text-[10px] uppercase tracking-widest text-lvmh-gray mb-1">Routing</div>
                                                <div className="font-semibold">Tier {noteRouting?.tier || 1}</div>
                                                <div className="text-xs text-lvmh-gray mt-1">Conf {formatPercent(noteRouting?.confidence)}</div>
                                            </div>
                                            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                                                <div className="text-[10px] uppercase tracking-widest text-lvmh-gray mb-1">Quality</div>
                                                <div className="font-semibold">{formatPercent(noteQuality?.quality_score)}</div>
                                                <div className="text-xs text-lvmh-gray mt-1">{formatDateTime(noteSummary?.timestamp)}</div>
                                            </div>
                                        </div>

                                        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                                            <div className="text-xs uppercase tracking-widest text-lvmh-gray mb-2">Tags</div>
                                            <div className="flex flex-wrap gap-2">
                                                {noteTags.length > 0 ? noteTags.map((tag) => (
                                                    <span key={tag} className="text-[11px] px-2 py-1 rounded-full border border-lvmh-gold/30 text-lvmh-gold bg-lvmh-gold/10">
                                                        {tag}
                                                    </span>
                                                )) : (
                                                    <span className="text-sm text-lvmh-gray">No tag extracted.</span>
                                                )}
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                                            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                                                <div className="text-xs uppercase tracking-widest text-lvmh-gray mb-2">Next Best Action</div>
                                                {Object.keys(noteNba || {}).length > 0 ? (
                                                    <div className="space-y-2 text-sm">
                                                        <div className="font-semibold">{noteNba?.title || noteNba?.action_type || noteNba?.action || 'Action'}</div>
                                                        {(noteNba?.description || noteNba?.rationale) && (
                                                            <div className="text-lvmh-gray leading-relaxed">{noteNba?.description || noteNba?.rationale}</div>
                                                        )}
                                                        <div className="flex flex-wrap gap-2 text-[11px]">
                                                            {noteNba?.channel && (
                                                                <span className="px-2 py-1 rounded-full border border-white/15 text-lvmh-gray">Channel: {noteNba.channel}</span>
                                                            )}
                                                            {noteNba?.timeline && (
                                                                <span className="px-2 py-1 rounded-full border border-white/15 text-lvmh-gray">Timeline: {noteNba.timeline}</span>
                                                            )}
                                                            {noteNba?.priority && (
                                                                <span className="px-2 py-1 rounded-full border border-white/15 text-lvmh-gray">Priority: {noteNba.priority}</span>
                                                            )}
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <div className="text-sm text-lvmh-gray">No NBA available.</div>
                                                )}
                                            </div>

                                            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                                                <div className="text-xs uppercase tracking-widest text-lvmh-gray mb-2">RGPD</div>
                                                <div className="flex flex-wrap gap-2 text-[11px] mb-2">
                                                    <span className={`px-2 py-1 rounded-full border ${noteRgpd?.contains_sensitive ? 'border-red-500/30 text-red-300 bg-red-500/10' : 'border-green-500/30 text-green-300 bg-green-500/10'}`}>
                                                        {noteRgpd?.contains_sensitive ? 'Sensitive data detected' : 'No sensitive data'}
                                                    </span>
                                                    {Array.isArray(noteRgpd?.categories_detected) && noteRgpd.categories_detected.slice(0, 4).map((category) => (
                                                        <span key={category} className="px-2 py-1 rounded-full border border-white/15 text-lvmh-gray">
                                                            {category}
                                                        </span>
                                                    ))}
                                                </div>
                                                {Array.isArray(noteQuality?.risk_flags) && noteQuality.risk_flags.length > 0 && (
                                                    <div className="text-xs text-lvmh-gray">
                                                        Risk flags: {noteQuality.risk_flags.join(', ')}
                                                    </div>
                                                )}
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                                            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                                                <div className="text-xs uppercase tracking-widest text-lvmh-gray mb-2">Matched Products</div>
                                                <div className="space-y-2 max-h-44 overflow-y-auto pr-1">
                                                    {noteProducts.length > 0 ? noteProducts.slice(0, 8).map((product, index) => (
                                                        <div key={`${product?.name || 'p'}-${index}`} className="rounded-lg border border-white/10 bg-white/[0.02] p-2">
                                                            <div className="text-sm font-semibold">{product?.name || `Produit ${index + 1}`}</div>
                                                            {product?.url && (
                                                                <a href={product.url} target="_blank" rel="noreferrer" className="text-xs text-lvmh-gold hover:underline break-all">
                                                                    {product.url}
                                                                </a>
                                                            )}
                                                        </div>
                                                    )) : (
                                                        <div className="text-sm text-lvmh-gray">No matched product.</div>
                                                    )}
                                                </div>
                                            </div>

                                            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                                                <div className="text-xs uppercase tracking-widest text-lvmh-gray mb-2">Audio Sources</div>
                                                {noteAudio?.available ? (
                                                    <div className="space-y-2 max-h-44 overflow-y-auto pr-1">
                                                        {(noteAudio?.sources || []).map((source, index) => (
                                                            <div key={`${source.path}-${index}`} className="rounded-lg border border-white/10 bg-white/[0.02] p-2">
                                                                <div className="text-[11px] text-lvmh-gray mb-1">{source.path}</div>
                                                                <a href={source.value} target="_blank" rel="noreferrer" className="text-xs text-lvmh-gold hover:underline break-all">
                                                                    {source.value}
                                                                </a>
                                                            </div>
                                                        ))}
                                                    </div>
                                                ) : (
                                                    <div className="text-sm text-lvmh-gray">No audio source available on this note.</div>
                                                )}
                                            </div>
                                        </div>

                                        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                                            <div className="text-xs uppercase tracking-widest text-lvmh-gray mb-2">Transcription</div>
                                            <div className="text-sm text-lvmh-gray leading-relaxed whitespace-pre-wrap">
                                                {noteSummary?.transcription || noteSummary?.transcription_preview || 'No transcription available.'}
                                            </div>
                                        </div>
                                    </>
                                ) : (
                                    <div className="text-sm text-lvmh-gray border border-white/10 rounded-lg p-4 bg-white/[0.02]">
                                        Aucun detail a afficher.
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                )}

                {loading && (
                    <div className="text-sm text-lvmh-gray text-center py-4">Chargement du dashboard admin...</div>
                )}
            </div>
        </div>
    )
}
