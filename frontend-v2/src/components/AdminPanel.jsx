import React, { useEffect, useMemo, useState } from 'react'
import {
    Activity,
    AlertTriangle,
    BarChart3,
    CalendarDays,
    Clock3,
    Coins,
    Database,
    Download,
    Home,
    LogOut,
    Mic,
    RefreshCcw,
    Server,
    ShieldAlert,
    ShieldCheck,
    ShoppingBag,
    Trash2,
    Trophy,
    Users,
    Wifi,
    WifiOff,
    X,
    ChevronLeft,
    ChevronRight,
    Search
} from 'lucide-react'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { apiFetch, wsUrl } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import AdminProductsView from './AdminProductsView'

const REFRESH_INTERVAL_MS = 30000
const WINDOW_PRESETS = [
    { label: '24h', days: 1 },
    { label: '7 jours', days: 7 },
    { label: '30 jours', days: 30 },
    { label: '90 jours', days: 90 }
]

const componentStatus = (value) => {
    if (!value || typeof value !== 'object') return { label: 'Unknown', tone: 'text-lvmh-gray border-white/10 bg-white/5' }
    if (value.error) return { label: 'Error', tone: 'text-red-300 border-red-500/30 bg-red-500/10' }
    if (value.enabled === false) return { label: 'Disabled', tone: 'text-lvmh-gray border-white/10 bg-white/5' }
    return { label: 'OK', tone: 'text-green-300 border-green-500/30 bg-green-500/10' }
}

export default function AdminPanel({ onBack }) {
    const { logout } = useAuth()
    const [activeTab, setActiveTab] = useState('accueil')
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
    const [noteSummary, setNoteSummary] = useState(null)
    const [noteRouting, setNoteRouting] = useState(null)
    const [noteQuality, setNoteQuality] = useState(null)
    const [noteRgpd, setNoteRgpd] = useState(null)
    const [noteNba, setNoteNba] = useState(null)
    const [noteProducts, setNoteProducts] = useState([])
    const [noteAudio, setNoteAudio] = useState(null)
    const [noteTags, setNoteTags] = useState([])
    const [dailyNotes, setDailyNotes] = useState([])
    const [adminUsers, setAdminUsers] = useState([])
    const [usersLoading, setUsersLoading] = useState(false)
    const [usersError, setUsersError] = useState(null)
    const [usersTotal, setUsersTotal] = useState(0)
    const [advisorsCount, setAdvisorsCount] = useState(0)
    const [managersCount, setManagersCount] = useState(0)
    const [adminsCount, setAdminsCount] = useState(0)
    const [products, setProducts] = useState([])
    const [productsLoading, setProductsLoading] = useState(false)
    const [productsTotal, setProductsTotal] = useState(0)
    const [productsPage, setProductsPage] = useState(1)
    const [productsSearch, setProductsSearch] = useState('')
    const [productsCategory, setProductsCategory] = useState('')
    const [productStats, setProductStats] = useState(null)
    const [adminActionLoading, setAdminActionLoading] = useState(null)
    const [adminActionMessage, setAdminActionMessage] = useState(null)
    const [socketState, setSocketState] = useState('offline')
    const [lastRefreshAt, setLastRefreshAt] = useState(null)

    const { pipeline, healthScore, healthTone, trendRows, trendTotals, mergedCost, componentRows } = useMemo(() => {
        const pipeline = summary?.pipeline
        const healthScore = Math.round((metrics?.health_score ?? summary?.health_score ?? 0))
        const healthTone = healthScore >= 80 ? 'border-green-500/40 text-green-400 bg-green-500/10' : healthScore >= 50 ? 'border-lvmh-gold/40 text-lvmh-gold bg-lvmh-gold/10' : 'border-red-500/40 text-red-400 bg-red-500/10'
        const trendRows = (timeseries?.daily ?? []).map((row) => ({
            ...row,
            label: row.date?.slice(5) ?? '',
            fullLabel: row.date ?? ''
        }))
        const trendTotals = timeseries?.totals
        const cost = metrics?.cost
        const summaryCost = summary?.cost
        const mergedCost = { ...summaryCost, ...cost }
        const componentRows = Object.entries(metrics?.components ?? summary?.components ?? {})
        return { pipeline, healthScore, healthTone, trendRows, trendTotals, mergedCost, componentRows }
    }, [metrics, summary, timeseries])

    const currentWindowLabel = WINDOW_PRESETS.find((preset) => preset.days === windowDays)?.label || `${windowDays} jours`

    const fetchDashboard = async () => {
        setLoading(true)
        setError(null)
        try {
            const [metricsRes, summaryRes, timeseriesRes] = await Promise.all([
                apiFetch(`/api/admin/metrics?days=${windowDays}`),
                apiFetch('/api/admin/summary'),
                apiFetch(`/api/admin/timeseries?days=${windowDays}`)
            ])
            if (metricsRes.ok) {
                const metricsData = await metricsRes.json()
                setMetrics(metricsData)
            }
            if (summaryRes.ok) {
                const summaryData = await summaryRes.json()
                setSummary(summaryData)
            }
            if (timeseriesRes.ok) {
                const timeseriesData = await timeseriesRes.json()
                setTimeseries(timeseriesData)
            }
            setLastRefreshAt(new Date())
        } catch (e) {
            setError(e.message)
        } finally {
            setLoading(false)
        }
    }

    const fetchAdminUsers = async () => {
        setUsersLoading(true)
        setUsersError(null)
        try {
            const res = await apiFetch('/api/admin/users')
            if (res.ok) {
                const data = await res.json()
                setAdminUsers(data.users ?? [])
                setUsersTotal(data.total ?? 0)
                setAdvisorsCount(data.advisors_count ?? 0)
                setManagersCount(data.managers_count ?? 0)
                setAdminsCount(data.admins_count ?? 0)
            } else {
                setUsersError(`Erreur: ${res.status}`)
            }
        } catch (e) {
            setUsersError(e.message)
        } finally {
            setUsersLoading(false)
        }
    }

    const fetchDailyNotes = async () => {
        try {
            const res = await apiFetch(`/api/admin/notes?days=${windowDays}&limit=50`)
            if (res.ok) {
                const data = await res.json()
                setDailyNotes(data.notes ?? [])
            }
        } catch (e) {
            console.error('Failed to fetch daily notes:', e)
        }
    }

    const fetchProducts = async (page = 1) => {
        setProductsLoading(true)
        try {
            const params = new URLSearchParams()
            params.set('page', String(page))
            params.set('limit', '12')
            if (productsSearch) params.set('search', productsSearch)
            if (productsCategory) params.set('category', productsCategory)
            const res = await apiFetch(`/api/products?${params}`)
            if (res.ok) {
                const data = await res.json()
                setProducts(data.products ?? [])
                setProductsTotal(data.total ?? 0)
            }
        } catch (e) {
            console.error('Failed to fetch products:', e)
        } finally {
            setProductsLoading(false)
        }
    }

    const fetchProductStats = async () => {
        try {
            const res = await apiFetch('/api/admin/products/stats')
            if (res.ok) {
                const data = await res.json()
                setProductStats(data)
            }
        } catch (e) {
            console.error('Failed to fetch product stats:', e)
        }
    }

    useEffect(() => {
        fetchDashboard()
        fetchAdminUsers()
        fetchDailyNotes()
        fetchProducts()
        fetchProductStats()
        const interval = setInterval(fetchDashboard, REFRESH_INTERVAL_MS)
        return () => clearInterval(interval)
    }, [windowDays])

    useEffect(() => {
        if (!loading && activeTab === 'produits') {
            fetchProducts(1)
            fetchProductStats()
        }
    }, [activeTab, productsSearch, productsCategory])

    useEffect(() => {
        const wsUrlValue = wsUrl('/ws/admin')
        let ws = null
        let reconnectTimeout = null
        const connect = () => {
            setSocketState('connecting')
            ws = new WebSocket(wsUrlValue)
            ws.onopen = () => setSocketState('connected')
            ws.onclose = () => {
                setSocketState('offline')
                reconnectTimeout = setTimeout(connect, 3000)
            }
            ws.onerror = () => ws.close()
            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data)
                    if (data.type === 'metrics_update') {
                        setMetrics(data.payload)
                        setLastRefreshAt(new Date())
                    }
                } catch (e) {
                    console.error('WS message error:', e)
                }
            }
        }
        connect()
        return () => {
            if (ws) ws.close()
            if (reconnectTimeout) clearTimeout(reconnectTimeout)
        }
    }, [])

    useEffect(() => {
        if (selectedNoteId) {
            setNoteDetailsLoading(true)
            setNoteDetailsError(null)
            Promise.all([
                apiFetch(`/api/admin/notes/${selectedNoteId}`),
                apiFetch(`/api/admin/notes/${selectedNoteId}/summary`),
                apiFetch(`/api/admin/notes/${selectedNoteId}/routing`),
                apiFetch(`/api/admin/notes/${selectedNoteId}/quality`),
                apiFetch(`/api/admin/notes/${selectedNoteId}/rgpd`),
                apiFetch(`/api/admin/notes/${selectedNoteId}/nba`),
                apiFetch(`/api/admin/notes/${selectedNoteId}/products`),
                apiFetch(`/api/admin/notes/${selectedNoteId}/audio`),
                apiFetch(`/api/admin/notes/${selectedNoteId}/tags`)
            ]).then(([detailsRes, summaryRes, routingRes, qualityRes, rgpdRes, nbaRes, productsRes, audioRes, tagsRes]) => {
                if (detailsRes.ok) setNoteDetails(detailsRes.json())
                else setNoteDetailsError(`Erreur: ${detailsRes.status}`)
                if (summaryRes.ok) setNoteSummary(summaryRes.json())
                if (routingRes.ok) setNoteRouting(routingRes.json())
                if (qualityRes.ok) setNoteQuality(qualityRes.json())
                if (rgpdRes.ok) setNoteRgpd(rgpdRes.json())
                if (nbaRes.ok) setNoteNba(nbaRes.json())
                if (productsRes.ok) productsRes.json().then(d => setNoteProducts(d.products ?? []))
                if (audioRes.ok) setNoteAudio(audioRes.json())
                if (tagsRes.ok) tagsRes.json().then(d => setNoteTags(d.tags ?? []))
                setNoteDetailsLoading(false)
            }).catch(e => {
                setNoteDetailsError(e.message)
                setNoteDetailsLoading(false)
            })
        }
    }, [selectedNoteId])

    const exportMetrics = async (format) => {
        setExporting(format)
        try {
            const res = await apiFetch(`/api/admin/metrics/export?format=${format}`)
            if (res.ok) {
                const blob = await res.blob()
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `lvmh-metrics-${new Date().toISOString().split('T')[0]}.${format}`
                a.click()
                URL.revokeObjectURL(url)
            }
        } catch (e) {
            console.error('Export error:', e)
        } finally {
            setExporting(null)
        }
    }

    const handleTrendChartClick = (data) => {
        if (data && data.activePayload && data.activePayload[0]) {
            const date = data.activePayload[0].payload.fullLabel || data.activePayload[0].payload.date
            if (date) {
                setSelectedTrendDate(date)
                setDayDetailsLoading(true)
                setDayDetailsError(null)
                apiFetch(`/api/admin/timeseries/${date}`).then((res) => {
                    if (res.ok) {
                        res.json().then(setDayDetails)
                    } else {
                        setDayDetailsError(`Erreur: ${res.status}`)
                    }
                    setDayDetailsLoading(false)
                })
            }
        }
    }

    const handleProductsSearch = (e) => {
        e.preventDefault()
        setProductsPage(1)
        fetchProducts(1)
    }

    const handleResetAllPoints = async () => {
        if (!window.confirm('Voulez-vous vraiment réinitialiser tous les points des advisors?')) return
        setAdminActionLoading('reset-points')
        setAdminActionMessage(null)
        try {
            const res = await apiFetch('/api/admin/users/reset-points', { method: 'POST' })
            if (res.ok) {
                setAdminActionMessage('Points réinitialisés avec succès')
                fetchAdminUsers()
            } else {
                setAdminActionMessage(`Erreur: ${res.status}`)
            }
        } catch (e) {
            setAdminActionMessage(e.message)
        } finally {
            setAdminActionLoading(null)
            setTimeout(() => setAdminActionMessage(null), 5000)
        }
    }

    const handlePurgeRecordings = async () => {
        if (!window.confirm('Voulez-vous vraiment supprimer tous les enregistrements et réinitialiser les points? Cette action est irréversible.')) return
        setAdminActionLoading('purge-recordings')
        setAdminActionMessage(null)
        try {
            const res = await apiFetch('/api/admin/purge-recordings', { method: 'POST' })
            if (res.ok) {
                setAdminActionMessage('Enregistrements supprimés avec succès')
                fetchAdminUsers()
                fetchDailyNotes()
            } else {
                setAdminActionMessage(`Erreur: ${res.status}`)
            }
        } catch (e) {
            setAdminActionMessage(e.message)
        } finally {
            setAdminActionLoading(null)
            setTimeout(() => setAdminActionMessage(null), 5000)
        }
    }

    const formatPercent = (value) => {
        if (value == null || isNaN(value)) return '0%'
        return `${Math.round(value * 100)}%`
    }

    const formatCurrency = (value) => {
        if (value == null || isNaN(value)) return '0 €'
        return `${value.toFixed(4)} €`
    }

    const formatDuration = (ms) => {
        if (ms == null || isNaN(ms)) return '0ms'
        if (ms < 1000) return `${Math.round(ms)}ms`
        return `${(ms / 1000).toFixed(1)}s`
    }

    const formatDateTime = (value) => {
        if (!value) return '-'
        const date = new Date(value)
        return date.toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    }

    const formatDateOnly = (value) => {
        if (!value) return '-'
        const date = new Date(value)
        return date.toLocaleDateString('fr-FR')
    }

    const openNoteDetails = (noteId) => {
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

    const adminTabs = [
        { id: 'accueil', label: 'Accueil', icon: Home },
        { id: 'enregistrement', label: 'Enregistrement', icon: Mic },
        { id: 'classement', label: 'Classement', icon: Trophy },
        { id: 'users', label: 'User & Credentials', icon: Users },
        { id: 'produits', label: 'Produits', icon: ShoppingBag }
    ]

    const currentTab = adminTabs.find(t => t.id === activeTab)

    return (
        <div className="min-h-screen bg-lvmh-black text-white">
            <div className="flex">
                <div className="w-56 min-h-screen bg-black/50 border-r border-white/10 p-4 flex flex-col">
                    <div className="mb-6">
                        <h1 className="text-xl font-display font-black gold-text">Admin</h1>
                        <p className="text-[10px] text-lvmh-gray uppercase tracking-widest">Panel</p>
                    </div>
                    <nav className="flex-1 space-y-1">
                        {adminTabs.map((tab) => {
                            const Icon = tab.icon
                            const isActive = activeTab === tab.id
                            return (
                                <button
                                    key={tab.id}
                                    onClick={() => setActiveTab(tab.id)}
                                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                                        isActive
                                            ? 'bg-lvmh-gold/10 text-lvmh-gold border border-lvmh-gold/30'
                                            : 'text-lvmh-gray hover:text-white hover:bg-white/5 border border-transparent'
                                    }`}
                                >
                                    <Icon size={18} />
                                    {tab.label}
                                </button>
                            )
                        })}
                    </nav>
                    <button
                        onClick={handleLogout}
                        className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors text-red-300 hover:bg-red-500/10 border border-transparent"
                    >
                        <LogOut size={18} />
                        Deconnexion
                    </button>
                </div>
                <div className="flex-1 p-6 md:p-8 overflow-visible">
                    <div className="max-w-7xl mx-auto space-y-6">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                            <div>
                                <h1 className="text-2xl md:text-3xl font-display font-black gold-text">{currentTab?.label || 'Admin'}</h1>
                                <p className="text-xs uppercase tracking-widest text-lvmh-gray">
                                    {activeTab === 'accueil' && 'Monitoring plateforme'}
                                    {activeTab === 'enregistrement' && 'Liste des notes'}
                                    {activeTab === 'classement' && 'Classement des advisors'}
                                    {activeTab === 'users' && 'Gestion utilisateurs'}
                                    {activeTab === 'produits' && 'Catalogue produits'}
                                </p>
                            </div>
                            <p className="text-[11px] text-lvmh-gray mt-1">Fenetre active: {currentWindowLabel}</p>
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
                            </div>
                        </div>

                        {error && (
                            <div className="glass p-4 border border-red-500/30 bg-red-500/10 text-sm text-red-200">
                                {error}
                            </div>
                        )}

                        {activeTab === 'produits' && (
                            <AdminProductsView />
                        )}

                        {activeTab === 'enregistrement' && (
                            <div className="glass p-6">
                                <h3 className="text-lg font-bold mb-4">Liste des enregistrements</h3>
                                {dailyNotes.length > 0 ? (
                                    <div className="space-y-2 max-h-[600px] overflow-y-auto">
                                        {dailyNotes.map((row) => (
                                            <div 
                                                key={row.note_id} 
                                                className="rounded-lg border border-white/10 bg-white/[0.03] p-4 hover:border-lvmh-gold/40 cursor-pointer"
                                                onClick={() => openNoteDetails(row.note_id)}
                                            >
                                                <div className="flex justify-between">
                                                    <div className="font-semibold">#{row.note_id}</div>
                                                    <div className="text-xs text-lvmh-gray">{formatDateTime(row.timestamp)}</div>
                                                </div>
                                                <div className="text-sm text-lvmh-gray mt-2">{row.transcription_preview || 'No preview'}</div>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="text-sm text-lvmh-gray">Aucun enregistrement.</div>
                                )}
                            </div>
                        )}

                        {activeTab === 'classement' && (
                            <div className="glass p-6">
                                <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                                    <Trophy size={18} className="text-lvmh-gold" />
                                    Classement des Advisors
                                </h3>
                                <div className="space-y-2">
                                    {adminUsers.filter(u => u?.role === 'advisor').sort((a, b) => (b?.score || 0) - (a?.score || 0)).map((user, index) => (
                                        <div key={user.id} className="flex items-center justify-between p-4 rounded-lg border border-white/10 bg-white/[0.03]">
                                            <div className="flex items-center gap-4">
                                                <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${index === 0 ? 'bg-lvmh-gold text-black' : 'bg-white/10 text-white'}`}>
                                                    {index + 1}
                                                </div>
                                                <div>
                                                    <div className="font-semibold">{user.full_name || user.email}</div>
                                                    <div className="text-xs text-lvmh-gray">{user.store || 'No store'}</div>
                                                </div>
                                            </div>
                                            <div className="text-right">
                                                <div className="text-xl font-bold text-lvmh-gold">{user.score || 0}</div>
                                                <div className="text-xs text-lvmh-gray">points</div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {activeTab === 'users' && (
                            <div className="space-y-6">
                                <div className="glass p-6">
                                    <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                                        <Users size={18} className="text-lvmh-gold" />
                                        Gestion des Utilisateurs
                                    </h3>
                                    <div className="grid grid-cols-3 gap-4 mb-6">
                                        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4 text-center">
                                            <div className="text-2xl font-black text-lvmh-gold">{advisorsCount}</div>
                                            <div className="text-xs text-lvmh-gray uppercase">Advisors</div>
                                        </div>
                                        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4 text-center">
                                            <div className="text-2xl font-black text-white">{managersCount}</div>
                                            <div className="text-xs text-lvmh-gray uppercase">Managers</div>
                                        </div>
                                        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4 text-center">
                                            <div className="text-2xl font-black text-white">{adminsCount}</div>
                                            <div className="text-xs text-lvmh-gray uppercase">Admins</div>
                                        </div>
                                    </div>
                                    <button
                                        onClick={fetchAdminUsers}
                                        disabled={usersLoading}
                                        className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-white/10 text-xs uppercase tracking-widest hover:border-lvmh-gold/40 hover:text-lvmh-gold transition-colors disabled:opacity-50"
                                    >
                                        <RefreshCcw size={12} />
                                        {usersLoading ? 'Refresh...' : 'Refresh Users'}
                                    </button>
                                    <button
                                        onClick={handleResetAllPoints}
                                        disabled={adminActionLoading === 'reset-points'}
                                        className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-lvmh-gold/30 text-lvmh-gold text-xs uppercase tracking-widest hover:bg-lvmh-gold/10 transition-colors disabled:opacity-50 ml-2"
                                    >
                                        <ShieldAlert size={12} />
                                        {adminActionLoading === 'reset-points' ? 'Reset...' : 'Reset Points'}
                                    </button>
                                    <button
                                        onClick={handlePurgeRecordings}
                                        disabled={adminActionLoading === 'purge-recordings'}
                                        className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-red-500/40 text-red-300 text-xs uppercase tracking-widest hover:bg-red-500/10 transition-colors disabled:opacity-50 ml-2"
                                    >
                                        <Trash2 size={12} />
                                        {adminActionLoading === 'purge-recordings' ? 'Purge...' : 'Purge Recordings + Points'}
                                    </button>
                                    {adminActionMessage && (
                                        <div className="mt-4 text-sm text-green-300 border border-green-500/30 rounded-lg p-3 bg-green-500/10">
                                            {adminActionMessage}
                                        </div>
                                    )}
                                    {usersError && (
                                        <div className="mt-4 text-sm text-red-200 border border-red-500/30 rounded-lg p-3 bg-red-500/10">
                                            {usersError}
                                        </div>
                                    )}
                                    <div className="overflow-x-auto border border-white/10 rounded-xl mt-4">
                                        <table className="w-full text-sm min-w-[980px]">
                                            <thead className="bg-white/[0.03] text-lvmh-gray uppercase text-[10px] tracking-widest">
                                                <tr>
                                                    <th className="text-left px-4 py-3">User</th>
                                                    <th className="text-left px-4 py-3">Role</th>
                                                    <th className="text-left px-4 py-3">Store</th>
                                                    <th className="text-right px-4 py-3">Points</th>
                                                    <th className="text-right px-4 py-3">Notes</th>
                                                    <th className="text-left px-4 py-3">Last Note</th>
                                                    <th className="text-left px-4 py-3">Credentials</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {adminUsers.length > 0 ? adminUsers.map((user) => (
                                                    <tr key={user.id} className="border-t border-white/10 hover:bg-white/[0.02]">
                                                        <td className="px-4 py-3">
                                                            <div className="font-semibold">{user.full_name || user.email}</div>
                                                            <div className="text-xs text-lvmh-gray">{user.email}</div>
                                                        </td>
                                                        <td className="px-4 py-3">
                                                            <span className={`text-[10px] px-2 py-1 rounded-full border uppercase tracking-widest ${
                                                                user.role === 'admin'
                                                                    ? 'border-red-500/30 text-red-300 bg-red-500/10'
                                                                    : user.role === 'manager'
                                                                        ? 'border-lvmh-gold/30 text-lvmh-gold bg-lvmh-gold/10'
                                                                        : 'border-green-500/30 text-green-300 bg-green-500/10'
                                                            }`}>
                                                                {user.role}
                                                            </span>
                                                        </td>
                                                        <td className="px-4 py-3 text-lvmh-gray">{user.store || '-'}</td>
                                                        <td className="px-4 py-3 text-right font-semibold">{user.score ?? 0}</td>
                                                        <td className="px-4 py-3 text-right">{user.notes_count ?? 0}</td>
                                                        <td className="px-4 py-3 text-xs text-lvmh-gray">{formatDateTime(user.last_note_at)}</td>
                                                        <td className="px-4 py-3 text-xs">
                                                            <div className="font-mono text-lvmh-gold break-all">
                                                                {user?.credentials?.username || user.email}
                                                            </div>
                                                            <div className="text-lvmh-gray break-all">
                                                                {user?.credentials?.password
                                                                    ? `password: ${user.credentials.password}`
                                                                    : 'password: non lisible (hash uniquement)'}
                                                            </div>
                                                        </td>
                                                    </tr>
                                                )) : (
                                                    <tr>
                                                        <td colSpan={7} className="px-4 py-6 text-center text-lvmh-gray">
                                                            {usersLoading ? 'Chargement utilisateurs...' : 'Aucun utilisateur trouve.'}
                                                        </td>
                                                    </tr>
                                                )}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                        )}

                        {activeTab === 'accueil' && (
                        <>
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
                                    {dayDetailsLoading ? (
                                        <div className="text-sm text-lvmh-gray">Chargement...</div>
                                    ) : dayDetailsError ? (
                                        <div className="text-sm text-red-200">{dayDetailsError}</div>
                                    ) : dayDetails ? (
                                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                                                <div className="text-[10px] uppercase tracking-widest text-lvmh-gray mb-1">Notes</div>
                                                <div className="text-xl font-black">{dayDetails.total_notes ?? 0}</div>
                                            </div>
                                            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                                                <div className="text-[10px] uppercase tracking-widest text-lvmh-gray mb-1">Avg Latency</div>
                                                <div className="text-xl font-black">{formatDuration(dayDetails.avg_processing_time_ms ?? 0)}</div>
                                            </div>
                                            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                                                <div className="text-[10px] uppercase tracking-widest text-lvmh-gray mb-1">Success Rate</div>
                                                <div className="text-xl font-black">{formatPercent(dayDetails.success_rate ?? 0)}</div>
                                            </div>
                                            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                                                <div className="text-[10px] uppercase tracking-widest text-lvmh-gray mb-1">Cost</div>
                                                <div className="text-xl font-black">{formatCurrency(dayDetails.cost_eur ?? 0)}</div>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="text-sm text-lvmh-gray">Cliquez sur un point dans les graphiques pour voir les details.</div>
                                    )}
                                </div>
                            )}

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
                        </>
                        )}

                        {loading && (
                            <div className="text-sm text-lvmh-gray text-center py-4">Chargement du dashboard admin...</div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}
