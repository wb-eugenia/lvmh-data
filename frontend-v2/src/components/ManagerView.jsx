import React, { useState, useEffect } from 'react'
import { ArrowLeft, LayoutDashboard, Trophy, Users, Star, Download, Search, FileText, Mic, Play, Pause, Tag, ShoppingBag, Zap, Sparkles, Trash2, Terminal } from 'lucide-react'
import DebugAnalyzer from './DebugAnalyzer'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'

export default function ManagerView({ onBack }) {
    const [currentTab, setCurrentTab] = useState('overview')
    const [stats, setStats] = useState({ total_notes: 0, avg_quality: 0, tier_distribution: { 1: 0, 2: 0, 3: 0 } })
    const [dashboardMetrics, setDashboardMetrics] = useState(null)
    const [dashboardSummary, setDashboardSummary] = useState(null)
    const [leaderboard, setLeaderboard] = useState([])
    const [history, setHistory] = useState([])
    const [rgpdStats, setRgpdStats] = useState(null)
    const [costStats, setCostStats] = useState(null)

    // CSV Results State
    const [csvFiles, setCsvFiles] = useState([])
    const [csvData, setCsvData] = useState([])
    const [selectedCsv, setSelectedCsv] = useState('')
    const [loadingCsv, setLoadingCsv] = useState(false)
    const [csvTotal, setCsvTotal] = useState(0)

    // Recordings State
    const [recordings, setRecordings] = useState([])
    const [loadingRecordings, setLoadingRecordings] = useState(false)
    const [recordingsPage, setRecordingsPage] = useState(1)
    const [recordingsTotal, setRecordingsTotal] = useState(0)
    const [recordingsSearch, setRecordingsSearch] = useState('')
    const [selectedRecording, setSelectedRecording] = useState(null)
    const [recordingsFilter, setRecordingsFilter] = useState('all') // all, tier1, tier2, tier3
    const [recordingsError, setRecordingsError] = useState(null)

    // Data Cleaning State
    const [cleaningFile, setCleaningFile] = useState(null)
    const [cleaningLoading, setCleaningLoading] = useState(false)
    const [cleaningResult, setCleaningResult] = useState(null)
    const [cleaningError, setCleaningError] = useState(null)
    const [availableColumns, setAvailableColumns] = useState([])
    const [selectedColumn, setSelectedColumn] = useState('')
    const [previewData, setPreviewData] = useState(null)

    const formatPercent = (value) => {
        if (value === null || value === undefined || Number.isNaN(value)) return '—'
        const normalized = value <= 1 ? value * 100 : value
        return `${Math.round(normalized)}%`
    }

    const formatCurrency = (value) => {
        if (value === null || value === undefined || Number.isNaN(value)) return '—'
        try {
            return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(value)
        } catch {
            return `${value}€`
        }
    }

    const formatDateTime = (value) => {
        if (!value) return '—'
        return new Date(value).toLocaleString('fr-FR')
    }

    const normalizeTierDistribution = (dist) => {
        if (!dist) return { 1: 0, 2: 0, 3: 0 }
        if (typeof dist.tier1 !== 'undefined' || typeof dist.tier2 !== 'undefined' || typeof dist.tier3 !== 'undefined') {
            return {
                1: dist.tier1 || 0,
                2: dist.tier2 || 0,
                3: dist.tier3 || 0
            }
        }
        return {
            1: dist[1] || 0,
            2: dist[2] || 0,
            3: dist[3] || 0
        }
    }

    const tabs = [
        { id: 'overview', name: 'Overview', icon: LayoutDashboard },
        { id: 'recordings', name: 'Enregistrements', icon: Mic },
        { id: 'datacleaning', name: 'Data Cleaning', icon: Sparkles },
        { id: 'leaderboard', name: 'Leaderboard', icon: Trophy },
        { id: 'vip', name: 'Clients VIP', icon: Star },
        { id: 'quality', name: 'Qualité Notes', icon: Users },
        { id: 'debug', name: 'Debug Pipeline', icon: Terminal }
    ]

    useEffect(() => {
        fetchData()
    }, [])

    useEffect(() => {
        if (currentTab === 'csv') {
            loadCsvFiles()
        }
        if (currentTab === 'recordings') {
            loadRecordings()
        }
    }, [currentTab, recordingsPage, recordingsSearch, recordingsFilter])

    const handleFileSelect = async (e) => {
        const file = e.target.files[0]
        if (!file) return
        
        setCleaningFile(file)
        setCleaningResult(null)
        setAvailableColumns([])
        setSelectedColumn('')
        setPreviewData(null)
        
        // Load preview
        try {
            const formData = new FormData()
            formData.append('file', file)
            
            const res = await fetch('/api/data-cleaning/preview', {
                method: 'POST',
                body: formData
            })
            
            if (res.ok) {
                const data = await res.json()
                setAvailableColumns(data.columns)
                setPreviewData(data)
                
                // Auto-select common transcription column names
                const commonNames = ['Transcription', 'transcription', 'text', 'Text', 'Note', 'note', 'Content', 'content']
                const found = data.columns.find(col => commonNames.includes(col))
                if (found) {
                    setSelectedColumn(found)
                }
            }
        } catch (e) {
            console.error('Preview error:', e)
        }
    }

    // Read file as array buffer to reuse it
    const readFileAsBuffer = (file) => {
        return new Promise((resolve, reject) => {
            const reader = new FileReader()
            reader.onload = () => resolve(reader.result)
            reader.onerror = reject
            reader.readAsArrayBuffer(file)
        })
    }

    const handleDataCleaning = async () => {
        if (!cleaningFile || !selectedColumn) return
        
        setCleaningLoading(true)
        setCleaningResult(null)
        setCleaningError(null)
        
        console.log('Starting cleaning with column:', selectedColumn)
        console.log('File:', cleaningFile.name, cleaningFile.size)
        
        try {
            // Create a new File object from the original to ensure it's readable
            const fileBuffer = await cleaningFile.arrayBuffer()
            const newFile = new File([fileBuffer], cleaningFile.name, { type: cleaningFile.type })
            
            const formData = new FormData()
            formData.append('file', newFile)
            formData.append('text_column', selectedColumn)
            
            console.log('Sending formData with text_column:', selectedColumn)
            
            const res = await fetch('/api/data-cleaning', {
                method: 'POST',
                body: formData
            })
            
            if (res.ok) {
                const data = await res.json()
                setCleaningResult(data)
            } else {
                const error = await res.text()
                alert('Erreur: ' + error)
            }
        } catch (e) {
            console.error('Data cleaning error:', e)
            alert('Erreur lors du nettoyage: ' + (e.message || 'Unknown error'))
            setCleaningError(e.message || 'Unknown error')
        } finally {
            setCleaningLoading(false)
        }
    }

    const downloadCleanedFile = () => {
        if (!cleaningResult?.cleaned_csv) return
        
        const blob = new Blob([cleaningResult.cleaned_csv], { type: 'text/csv' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = cleaningResult.filename
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
    }

    const loadRecordings = async () => {
        setLoadingRecordings(true)
        setRecordingsError(null)
        try {
            const params = new URLSearchParams({
                page: recordingsPage.toString(),
                limit: '10'
            })
            if (recordingsSearch) params.append('search', recordingsSearch)
            if (recordingsFilter !== 'all') params.append('tier', recordingsFilter.replace('tier', ''))
            
            console.log('Fetching recordings...', params.toString())
            const res = await fetch(`/api/recordings?${params}`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                }
            })
            console.log('Response status:', res.status)
            
            if (res.ok) {
                const data = await res.json()
                console.log('Recordings data:', data)
                setRecordings(data.recordings || [])
                setRecordingsTotal(data.total || 0)
            } else {
                const errorText = await res.text()
                console.error('Failed to load recordings:', res.status, errorText)
                setRecordingsError(`Erreur ${res.status}: ${errorText}`)
            }
        } catch (e) {
            console.error('Error loading recordings:', e)
            setRecordingsError(e.message)
        } finally {
            setLoadingRecordings(false)
        }
    }

    const loadCsvFiles = async () => {
        setLoadingCsv(true)
        try {
            const res = await fetch('/api/batch-results')
            if (res.ok) {
                const data = await res.json()
                setCsvFiles(data.files || [])
                if (data.files?.length > 0 && !selectedCsv) {
                    setSelectedCsv(data.files[0])
                    loadCsvData(data.files[0])
                }
            }
        } catch (e) {
            console.error(e)
        } finally {
            setLoadingCsv(false)
        }
    }

    const loadCsvData = async (filename) => {
        if (!filename) return
        setLoadingCsv(true)
        try {
            const res = await fetch(`/api/batch-results?file=${encodeURIComponent(filename)}`)
            if (res.ok) {
                const data = await res.json()
                setCsvData(data.data || [])
                setCsvTotal(data.total || 0)
            }
        } catch (e) {
            console.error(e)
        } finally {
            setLoadingCsv(false)
        }
    }

    const handleCsvSelect = (e) => {
        const file = e.target.value
        setSelectedCsv(file)
        loadCsvData(file)
    }

    const fetchData = async () => {
        try {
            const sRes = await fetch('/api/stats/overview')
            if (sRes.ok) {
                setStats(await sRes.json())
            }

            const lRes = await fetch('/api/leaderboard')
            if (lRes.ok) {
                setLeaderboard(await lRes.json())
            }

            const hRes = await fetch('/api/search?q=')
            if (hRes.ok) {
                const hData = await hRes.json()
                setHistory(hData.results || [])
            }

            const rRes = await fetch('/api/stats/rgpd')
            if (rRes.ok) {
                setRgpdStats(await rRes.json())
            }

            const cRes = await fetch('/api/stats/cost')
            if (cRes.ok) {
                setCostStats(await cRes.json())
            }

            const dRes = await fetch('/api/dashboard/metrics')
            if (dRes.ok) {
                setDashboardMetrics(await dRes.json())
            }

            const dsRes = await fetch('/api/dashboard/metrics/summary')
            if (dsRes.ok) {
                setDashboardSummary(await dsRes.json())
            }
        } catch (e) { console.error(e) }
    }

    const pipelineStats = dashboardMetrics?.pipeline_stats || {}
    const qualityStats = dashboardMetrics?.quality_metrics || {}
    const mergedCostStats = dashboardMetrics?.cost_stats || costStats
    const tierDistribution = normalizeTierDistribution(pipelineStats?.tier_distribution || stats?.tier_distribution)
    const processedToday = dashboardSummary?.summary?.processed_today
    const notesPerAdvisor = processedToday && leaderboard?.length ? (processedToday / leaderboard.length).toFixed(1) : '—'
    const avgQuality = qualityStats?.accuracy_rate ?? stats?.avg_quality ?? 0
    const totalCost = mergedCostStats?.total_cost_eur ?? mergedCostStats?.total_cost ?? 0
    const costPerNote = mergedCostStats?.cost_per_note ?? mergedCostStats?.roi_metrics?.cost_per_note ?? 0
    const savingsRate = mergedCostStats?.roi_metrics?.savings || '—'

    const chartData = [
        { name: 'Tier 1', value: tierDistribution?.[1] || 0, color: '#888888' },
        { name: 'Tier 2', value: tierDistribution?.[2] || 0, color: '#D4AF37' },
        { name: 'Tier 3', value: tierDistribution?.[3] || 0, color: '#FF5252' }
    ]

    const selectedP1 = selectedRecording?.pilier_1_univers_produit || {}
    const selectedP2 = selectedRecording?.pilier_2_profil_client || {}
    const selectedP3 = selectedRecording?.pilier_3_hospitalite_care || {}
    const selectedP4 = selectedRecording?.pilier_4_action_business || {}
    const selectedMeta = selectedRecording?.meta_analysis || {}
    const selectedRgpd = selectedRecording?.rgpd || {}
    const selectedAllergies = [
        ...(selectedP3?.allergies?.food || []),
        ...(selectedP3?.allergies?.contact || [])
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
                        <h2 className="text-3xl font-display font-black mb-1">Boutique Paris Rivoli</h2>
                        <p className="text-lvmh-gray">Pilotage de la performance Client Advisor</p>
                    </div>
                    <button className="glass flex items-center gap-2 px-6 py-3 hover:bg-white/10 transition-colors uppercase text-xs font-bold tracking-widest">
                        <Download size={16} /> Export Salesforce
                    </button>
                </div>

                {currentTab === 'recordings' && (
                    <div className="space-y-6 animate-in fade-in duration-500">
                        <div className="flex justify-between items-center">
                            <h3 className="text-2xl font-display font-black gold-text flex items-center gap-2">
                                <Mic size={24} /> Enregistrements Audio
                            </h3>
                            <span className="text-sm text-lvmh-gray">{recordingsTotal} enregistrements</span>
                        </div>

                        {/* Filters */}
                        <div className="glass p-4 flex flex-wrap gap-4">
                            <div className="flex-1 min-w-[200px]">
                                <div className="relative">
                                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-lvmh-gray" size={16} />
                                    <input
                                        type="text"
                                        placeholder="Rechercher dans les transcriptions..."
                                        className="w-full bg-white/5 border border-white/10 rounded-lg py-2 pl-10 pr-4 text-white text-sm focus:ring-1 focus:ring-lvmh-gold transition-all"
                                        value={recordingsSearch}
                                        onChange={(e) => setRecordingsSearch(e.target.value)}
                                    />
                                </div>
                            </div>
                            <select
                                value={recordingsFilter}
                                onChange={(e) => setRecordingsFilter(e.target.value)}
                                className="bg-white/5 border border-white/10 rounded-lg py-2 px-4 text-white text-sm focus:ring-1 focus:ring-lvmh-gold"
                            >
                                <option value="all">Tous les tiers</option>
                                <option value="tier1">Tier 1 (Simple)</option>
                                <option value="tier2">Tier 2 (Standard)</option>
                                <option value="tier3">Tier 3 (Premium)</option>
                            </select>
                        </div>

                        {loadingRecordings ? (
                            <div className="flex justify-center py-20">
                                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-lvmh-gold"></div>
                            </div>
                        ) : selectedRecording ? (
                            // Detail View
                            <div className="space-y-8 animate-in slide-in-from-right duration-300">
                                <button
                                    onClick={() => setSelectedRecording(null)}
                                    className="text-lvmh-gold text-sm hover:underline flex items-center gap-2"
                                >
                                    ← Retour à la liste
                                </button>

                                <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_0.8fr] gap-6">
                                    <div className="glass p-6 border-l-4 border-lvmh-gold">
                                        <div className="flex flex-wrap items-start justify-between gap-4">
                                            <div>
                                                <div className="data-label">Client</div>
                                                <div className="text-2xl font-display gold-text">
                                                    {selectedRecording.client?.name || 'Client inconnu'}
                                                </div>
                                                <div className="mt-2 flex flex-wrap gap-2">
                                                    <span className={`text-[10px] px-2 py-1 rounded-full ${selectedRecording.client?.vic_status !== 'Standard' ? 'bg-lvmh-gold/20 text-lvmh-gold' : 'bg-white/10 text-lvmh-gray'}`}>
                                                        {selectedRecording.client?.vic_status || 'Standard'}
                                                    </span>
                                                    <span className={`text-[10px] px-2 py-1 rounded-full ${selectedRecording.tier === 1 ? 'bg-white/10 text-white' : selectedRecording.tier === 2 ? 'bg-lvmh-gold/20 text-lvmh-gold' : 'bg-red-500/20 text-red-400'}`}>
                                                        Tier {selectedRecording.tier}
                                                    </span>
                                                    <span className="text-[10px] px-2 py-1 rounded-full bg-white/10 text-lvmh-gray">
                                                        Confiance {formatPercent(selectedRecording.confidence)}
                                                    </span>
                                                </div>
                                            </div>
                                            <div className="text-right">
                                                <div className="data-label">Conseiller</div>
                                                <div className="text-sm font-semibold">{selectedRecording.advisor?.name || 'Inconnu'}</div>
                                                <div className="text-xs text-lvmh-gray">{selectedRecording.advisor?.store || 'N/A'}</div>
                                                <div className="mt-2 text-xs text-lvmh-gray">{formatDateTime(selectedRecording.timestamp)}</div>
                                            </div>
                                        </div>

                                        <div className="mt-6">
                                            <div className="data-label">Transcription</div>
                                            <div className="bg-white/5 p-4 rounded-lg text-sm leading-relaxed max-h-56 overflow-auto">
                                                "{selectedRecording.transcription}"
                                            </div>
                                        </div>

                                        <div className="mt-6">
                                            <div className="data-label">Tags</div>
                                            <div className="flex flex-wrap gap-2 mt-2">
                                                {selectedRecording.tags?.slice(0, 12).map((tag, i) => (
                                                    <span key={i} className="text-xs bg-lvmh-gold/15 text-lvmh-gold px-2 py-1 rounded-full">
                                                        {tag}
                                                    </span>
                                                ))}
                                                {selectedRecording.tags?.length > 12 && (
                                                    <span className="text-xs text-lvmh-gray">+{selectedRecording.tags.length - 12}</span>
                                                )}
                                            </div>
                                        </div>
                                    </div>

                                    <div className="space-y-4">
                                        <div className="grid grid-cols-2 gap-4">
                                            <div className="glass p-4">
                                                <div className="data-label">Qualité</div>
                                                <div className="text-xl font-semibold">{formatPercent(selectedMeta.quality_score)}</div>
                                                <div className="text-xs text-lvmh-gray">
                                                    Complétude {formatPercent(selectedMeta.completeness_score)} / Confiance {formatPercent(selectedMeta.confidence_score)}
                                                </div>
                                            </div>
                                            <div className="glass p-4">
                                                <div className="data-label">Budget</div>
                                                <div className="text-lg font-semibold">{selectedP4?.budget_potential || 'N/A'}</div>
                                                <div className="text-xs text-lvmh-gray">
                                                    {selectedP4?.budget_specific ? formatCurrency(selectedP4.budget_specific) : 'Budget spécifique N/A'}
                                                </div>
                                            </div>
                                            <div className="glass p-4">
                                                <div className="data-label">Urgence</div>
                                                <div className="text-lg font-semibold capitalize">{selectedP4?.urgency || 'low'}</div>
                                            </div>
                                            <div className="glass p-4">
                                                <div className="data-label">RGPD</div>
                                                <div className={`text-sm font-semibold ${selectedRgpd?.contains_sensitive ? 'text-red-400' : 'text-green-400'}`}>
                                                    {selectedRgpd?.contains_sensitive ? 'Sensibles détectées' : 'Conforme'}
                                                </div>
                                                <div className="text-xs text-lvmh-gray">
                                                    {selectedRgpd?.categories_detected?.length ? selectedRgpd.categories_detected.join(', ') : 'Aucune catégorie'}
                                                </div>
                                            </div>
                                            <div className="glass p-4">
                                                <div className="data-label">Points</div>
                                                <div className="text-lg font-semibold text-lvmh-gold">+{selectedRecording.points_awarded || 0} pts</div>
                                            </div>
                                            <div className="glass p-4">
                                                <div className="data-label">Traitement</div>
                                                <div className="text-lg font-semibold">{Math.round(selectedRecording.processing_time_ms || 0)}ms</div>
                                            </div>
                                        </div>

                                        <div className="glass p-4">
                                            <div className="data-label">Contexte client</div>
                                            <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                                                <div>
                                                    <div className="text-xs text-lvmh-gray uppercase">Achat</div>
                                                    <div>{selectedP2?.purchase_context?.type || 'N/A'}</div>
                                                </div>
                                                <div>
                                                    <div className="text-xs text-lvmh-gray uppercase">Comportement</div>
                                                    <div>{selectedP2?.purchase_context?.behavior || 'N/A'}</div>
                                                </div>
                                                <div>
                                                    <div className="text-xs text-lvmh-gray uppercase">Profession</div>
                                                    <div>{selectedP2?.profession?.sector || selectedP2?.profession?.status || 'N/A'}</div>
                                                </div>
                                                <div>
                                                    <div className="text-xs text-lvmh-gray uppercase">Occasion</div>
                                                    <div>{selectedP3?.occasion || 'N/A'}</div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                    <div className="glass p-6">
                                        <h4 className="text-lg font-display font-bold mb-4">Pilier 1 - Univers Produit</h4>
                                        <div className="space-y-3 text-sm">
                                            <div>
                                                <div className="data-label">Catégories</div>
                                                <div className="mt-2 flex flex-wrap gap-2">
                                                    {(selectedP1.categories || []).length ? selectedP1.categories.map((cat, i) => (
                                                        <span key={i} className="text-xs bg-white/10 px-2 py-1 rounded">{cat}</span>
                                                    )) : <span className="text-xs text-lvmh-gray">N/A</span>}
                                                </div>
                                            </div>
                                            <div>
                                                <div className="data-label">Produits mentionnés</div>
                                                <div className="mt-2 text-sm text-lvmh-gray">{(selectedP1.produits_mentionnes || []).join(', ') || 'N/A'}</div>
                                            </div>
                                            <div className="grid grid-cols-2 gap-4">
                                                <div>
                                                    <div className="data-label">Couleurs</div>
                                                    <div className="text-sm text-lvmh-gray">{(selectedP1.preferences?.colors || []).join(', ') || 'N/A'}</div>
                                                </div>
                                                <div>
                                                <div className="data-label">Matières</div>
                                                    <div className="text-sm text-lvmh-gray">{(selectedP1.preferences?.materials || []).join(', ') || 'N/A'}</div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="glass p-6">
                                        <h4 className="text-lg font-display font-bold mb-4">Pilier 2 - Profil Client</h4>
                                        <div className="space-y-3 text-sm">
                                            <div className="grid grid-cols-2 gap-4">
                                                <div>
                                                    <div className="data-label">Type d'achat</div>
                                                    <div className="text-sm text-lvmh-gray">{selectedP2?.purchase_context?.type || 'N/A'}</div>
                                                </div>
                                                <div>
                                                    <div className="data-label">Statut</div>
                                                    <div className="text-sm text-lvmh-gray">{selectedRecording.client?.vic_status || 'Standard'}</div>
                                                </div>
                                            </div>
                                            <div>
                                                <div className="data-label">Lifestyle</div>
                                                <div className="text-sm text-lvmh-gray">{selectedP2?.lifestyle?.family || 'N/A'}</div>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="glass p-6">
                                        <h4 className="text-lg font-display font-bold mb-4">Pilier 3 - Hospitalité & Care</h4>
                                        <div className="space-y-3 text-sm">
                                            <div>
                                                <div className="data-label">Allergies</div>
                                                <div className={`text-sm ${selectedAllergies.length ? 'text-red-400' : 'text-green-400'}`}>
                                                    {selectedAllergies.length ? selectedAllergies.join(', ') : 'Aucune détectée'}
                                                </div>
                                            </div>
                                            <div>
                                                <div className="data-label">Régime</div>
                                                <div className="text-sm text-lvmh-gray">{(selectedP3?.diet || []).join(', ') || 'N/A'}</div>
                                            </div>
                                            <div>
                                                <div className="data-label">Occasion</div>
                                                <div className="text-sm text-lvmh-gray">{selectedP3?.occasion || 'N/A'}</div>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="glass p-6">
                                        <h4 className="text-lg font-display font-bold mb-4">Pilier 4 - Action Business</h4>
                                        <div className="space-y-3 text-sm">
                                            <div>
                                                <div className="data-label">Budget</div>
                                                <div className="text-sm text-lvmh-gray">{selectedP4?.budget_potential || 'N/A'}</div>
                                            </div>
                                            <div>
                                                <div className="data-label">Urgence</div>
                                                <div className="text-sm text-lvmh-gray">{selectedP4?.urgency || 'N/A'}</div>
                                            </div>
                                            <div>
                                                <div className="data-label">Température du lead</div>
                                                <div className="text-sm text-lvmh-gray">{selectedP4?.lead_temperature || 'N/A'}</div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* RAG Products */}
                                {selectedRecording.matched_products?.length > 0 && (
                                    <div className="glass p-6">
                                        <div className="flex items-center gap-2 mb-4">
                                            <ShoppingBag size={20} className="text-lvmh-gold" />
                                            <h4 className="font-display font-bold">Produits recommandés (RAG)</h4>
                                        </div>
                                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                            {selectedRecording.matched_products.map((product, i) => (
                                                <div key={i} className="bg-white/5 p-4 rounded-lg border border-white/10">
                                                    <div className="font-bold text-lvmh-gold mb-1">{product.name || product.ID}</div>
                                                    <div className="text-xs text-lvmh-gray uppercase">{product.category || 'Catégorie'}</div>
                                                    {product.description && (
                                                        <div className="text-xs text-lvmh-gray mt-2 line-clamp-2">{product.description}</div>
                                                    )}
                                                    {product.match_score && (
                                                        <div className="text-[10px] text-lvmh-gray mt-3">Score {Math.round(product.match_score * 100)}%</div>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* NBA */}
                                {selectedRecording.next_best_action && (
                                    <div className="glass p-6 border-l-4 border-green-500">
                                        <div className="flex items-center gap-2 mb-4">
                                            <Zap size={20} className="text-green-500" />
                                            <h4 className="font-display font-bold">Next Best Action</h4>
                                        </div>
                                        <p className="text-sm mb-4">{selectedRecording.next_best_action.description || 'Action recommandée'}</p>
                                        {selectedRecording.next_best_action.target_products?.length > 0 && (
                                            <div>
                                                <div className="data-label mb-2">Produits suggérés</div>
                                                <div className="flex flex-wrap gap-2">
                                                    {selectedRecording.next_best_action.target_products.map((p, i) => (
                                                        <span key={i} className="text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded">
                                                            {p}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        ) : (
                            // List View
                            <div className="space-y-4">
                                {recordings.length > 0 ? recordings.map((rec) => (
                                    <div
                                        key={rec.id}
                                        onClick={() => setSelectedRecording(rec)}
                                        className="glass p-5 hover:bg-white/5 transition-all cursor-pointer border-l-4 border-transparent hover:border-l-lvmh-gold"
                                    >
                                        <div className="flex items-start justify-between gap-4">
                                            <div className="flex items-start gap-3">
                                                <div className="w-10 h-10 rounded-full bg-lvmh-gold/15 flex items-center justify-center">
                                                    <Mic size={16} className="text-lvmh-gold" />
                                                </div>
                                                <div>
                                                    <div className="flex flex-wrap items-center gap-2">
                                                        <div className="font-semibold">{rec.client?.name || 'Client inconnu'}</div>
                                                        <span className={`text-[10px] px-2 py-0.5 rounded-full ${rec.client?.vic_status !== 'Standard' ? 'bg-lvmh-gold/20 text-lvmh-gold' : 'bg-white/10 text-lvmh-gray'}`}>
                                                            {rec.client?.vic_status || 'Standard'}
                                                        </span>
                                                    </div>
                                                    <div className="text-xs text-lvmh-gray">
                                                        Conseiller: {rec.advisor?.name || 'Inconnu'} | {rec.advisor?.store || 'N/A'}
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="text-right">
                                                <div className="text-xs text-lvmh-gray">{formatDateTime(rec.timestamp)}</div>
                                                <div className="mt-1 flex items-center justify-end gap-2">
                                                    <span className={`text-[10px] px-2 py-0.5 rounded-full ${rec.tier === 1 ? 'bg-white/10' : rec.tier === 2 ? 'bg-lvmh-gold/20 text-lvmh-gold' : 'bg-red-500/20 text-red-400'}`}>
                                                        T{rec.tier}
                                                    </span>
                                                    <span className="text-[10px] text-lvmh-gray">{formatPercent(rec.confidence)}</span>
                                                </div>
                                            </div>
                                        </div>

                                        <p className="text-sm text-lvmh-gray line-clamp-2 mt-3">"{rec.transcription}"</p>

                                        <div className="flex flex-wrap gap-2 mt-3">
                                            {rec.tags?.slice(0, 6).map((tag, i) => (
                                                <span key={i} className="text-[10px] bg-white/10 px-2 py-0.5 rounded text-lvmh-gray">
                                                    {tag}
                                                </span>
                                            ))}
                                            {rec.tags?.length > 6 && (
                                                <span className="text-[10px] text-lvmh-gray">+{rec.tags.length - 6}</span>
                                            )}
                                        </div>

                                        <div className="mt-3 flex flex-wrap gap-4 text-xs text-lvmh-gray">
                                            <span>Budget: {rec.pilier_4_action_business?.budget_potential || 'N/A'}</span>
                                            <span>Urgence: {rec.pilier_4_action_business?.urgency || 'low'}</span>
                                            {rec.matched_products?.length > 0 && (
                                                <span className="flex items-center gap-1 text-lvmh-gold">
                                                    <ShoppingBag size={12} />
                                                    {rec.matched_products.length} produits matchés
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                )) : recordingsError ? (
                                    <div className="text-center py-20 text-red-400">
                                        <div className="font-bold mb-2">Erreur de chargement</div>
                                        <div className="text-sm">{recordingsError}</div>
                                    </div>
                                ) : (
                                    <div className="text-center py-20 text-lvmh-gray">
                                        Aucun enregistrement trouvé
                                    </div>
                                )}

                                {/* Pagination */}
                                {recordingsTotal > 10 && (
                                    <div className="flex justify-center gap-2 mt-6">
                                        <button
                                            onClick={() => setRecordingsPage(p => Math.max(1, p - 1))}
                                            disabled={recordingsPage === 1}
                                            className="px-4 py-2 bg-white/5 rounded-lg disabled:opacity-50 hover:bg-white/10 transition-colors"
                                        >
                                            Précédent
                                        </button>
                                        <span className="px-4 py-2 text-lvmh-gray">
                                            Page {recordingsPage} / {Math.ceil(recordingsTotal / 10)}
                                        </span>
                                        <button
                                            onClick={() => setRecordingsPage(p => p + 1)}
                                            disabled={recordingsPage >= Math.ceil(recordingsTotal / 10)}
                                            className="px-4 py-2 bg-white/5 rounded-lg disabled:opacity-50 hover:bg-white/10 transition-colors"
                                        >
                                            Suivant
                                        </button>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}

                {currentTab === 'overview' && (
                    <div className="space-y-10 animate-in fade-in duration-500">
                        {/* KPI Cards */}
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                            <KPICard title="Notes Totales" value={pipelineStats?.total_processed ?? stats?.total_notes ?? 0} trend={`Aujourd'hui: ${processedToday ?? 0}`} />
                            <KPICard title="Qualité Moyenne" value={`${Math.round(avgQuality || 0)}%`} trend="Mode: Expert 🌟" gold />
                            <KPICard title="Alertes VIP" value={history?.filter(x => x?.tier === 3)?.length || 0} trend="À traiter urgent" red />
                            <KPICard title="Notes/CA/Jour" value={notesPerAdvisor} trend="Cible: 5.0 🚀" />
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
                        <h3 className="text-2xl font-display font-black gold-text mb-8">Performance Retail Mondiale</h3>
                        <div className="space-y-4">
                            {leaderboard.map((adv, i) => (
                                <div key={adv.id} className="flex items-center gap-6 glass p-6 hover:border-lvmh-gold/30 transition-all border-l-4 border-l-transparent hover:border-l-lvmh-gold">
                                    <span className="text-4xl font-black text-white/10">{i + 1}</span>
                                    <div className="flex-1">
                                        <div className="font-bold text-xl">{adv.id}</div>
                                        <div className="text-lvmh-gray text-sm">{adv.notes} interactions capturées</div>
                                    </div>
                                    <div className="text-3xl font-display font-black text-lvmh-gold">{adv.score} <span className="text-xs uppercase">points</span></div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {currentTab === 'vip' && (
                    <div className="space-y-6 animate-in slide-in-from-right duration-500">
                        <div className="flex items-center gap-2 mb-4">
                            <Star className="text-red-500 fill-red-500" size={24} />
                            <h3 className="text-2xl font-display font-black">Segment Discovery (Tier 3)</h3>
                        </div>
                        <div className="grid grid-cols-1 gap-4">
                            {(history || []).filter(x => x.tier === 3).map((r, i) => (
                                <div key={i} className="glass p-6 border-l-4 border-red-500 hover:bg-white/5 transition-all">
                                    <div className="flex justify-between items-start mb-4">
                                        <span className="text-xl font-bold">{r.ID}</span>
                                        <span className="text-xs bg-red-500/20 text-red-500 px-3 py-1 rounded-full font-bold">ALERTE MISTRAL</span>
                                    </div>
                                    <p className="text-lvmh-gray text-sm mb-4">"{r.Transcription?.substring(0, 100)}..."</p>

                                    <div className="flex flex-wrap gap-2 mb-4">
                                        {(r.tags || []).map(tag => (
                                            <span key={tag} className="text-[10px] bg-white/5 border border-white/10 px-2 py-0.5 rounded text-lvmh-gray uppercase">
                                                {tag.replace('_', ' ')}
                                            </span>
                                        ))}
                                    </div>

                                    <div className="bg-white/5 p-4 rounded-lg border border-white/5 space-y-4">
                                        <div>
                                            <div className="text-[10px] text-lvmh-gold uppercase font-bold mb-2 tracking-widest">🚀 Opportunité NBA</div>
                                            <div className="font-medium text-sm">{r.pilier_4_action_business?.next_best_action?.description || "Analyse approfondie requise"}</div>
                                        </div>

                                        {r.matched_products?.length > 0 && (
                                            <div className="pt-3 border-t border-white/5">
                                                <div className="text-[10px] text-lvmh-gray uppercase font-bold mb-2 tracking-widest">🛍️ Produits Catalogués (RAG)</div>
                                                <div className="flex gap-2 overflow-x-auto pb-1">
                                                    {r.matched_products.slice(0, 3).map((prod, pi) => (
                                                        <div key={pi} className="flex-shrink-0 bg-lvmh-black border border-white/5 p-2 rounded text-[10px]">
                                                            <div className="font-bold text-lvmh-gold">{prod.name || prod.ID}</div>
                                                            <div className="text-[9px] text-lvmh-gray">{prod.category}</div>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {currentTab === 'quality' && (
                    <div className="space-y-10 animate-in slide-in-from-right duration-500">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
                            {/* ROI CARD */}
                            <div className="glass p-8">
                                <h3 className="text-xl font-bold mb-6 flex items-center gap-2 text-green-500">💰 Performance & ROI</h3>
                                <div className="space-y-6">
                                    <div>
                                        <div className="text-xs text-lvmh-gray uppercase mb-1">Coût Total Cloud (Est.)</div>
                                        <div className="text-3xl font-display font-black">{formatCurrency(totalCost)}</div>
                                    </div>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="bg-white/5 p-4 rounded-lg">
                                            <div className="text-[10px] text-lvmh-gray uppercase">Economies</div>
                                            <div className="text-lg font-bold text-green-500">{savingsRate}</div>
                                        </div>
                                        <div className="bg-white/5 p-4 rounded-lg">
                                            <div className="text-[10px] text-lvmh-gray uppercase">Coût / Note</div>
                                            <div className="text-lg font-bold">{formatCurrency(costPerNote)}</div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* RGPD CARD */}
                            <div className="glass p-8">
                                <h3 className="text-xl font-bold mb-6 flex items-center gap-2 text-red-400">🛡️ Conformité RGPD</h3>
                                <div className="space-y-6">
                                    <div className="flex justify-between items-end">
                                        <div>
                                            <div className="text-xs text-lvmh-gray uppercase mb-1">Données Sensibles Détectées</div>
                                            <div className="text-3xl font-display font-black">{rgpdStats?.sensitive_count || 0}</div>
                                        </div>
                                        <div className="text-sm font-bold text-red-400 mb-1">{rgpdStats?.sensitive_rate || 0}% du flux</div>
                                    </div>
                                    <div className="space-y-2">
                                        {rgpdStats?.categories && Object.entries(rgpdStats.categories).map(([cat, count]) => (
                                            <div key={cat} className="flex justify-between items-center text-sm py-2 border-b border-white/5">
                                                <span className="text-lvmh-gray">{cat}</span>
                                                <span className="font-bold">{count}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* DATA CLEANING TAB */}
                {currentTab === 'datacleaning' && (
                    <div className="space-y-6 animate-in slide-in-from-right duration-500">
                        <div className="flex justify-between items-center">
                            <h3 className="text-2xl font-display font-black gold-text flex items-center gap-2">
                                <Sparkles size={24} /> Data Cleaning
                            </h3>
                        </div>

                        {/* Upload Zone */}
                        <div className="glass p-8 text-center">
                            <div className="mb-6">
                                <div className="w-16 h-16 rounded-full bg-lvmh-gold/20 flex items-center justify-center mx-auto mb-4">
                                    <Sparkles size={32} className="text-lvmh-gold" />
                                </div>
                                <h4 className="text-lg font-bold mb-2">Nettoyer un fichier CSV</h4>
                                <p className="text-sm text-lvmh-gray mb-6">
                                    Supprime les doublons, lignes vides, et normalise le texte
                                </p>
                            </div>

                            <input
                                type="file"
                                accept=".csv,.xlsx"
                                onChange={handleFileSelect}
                                className="hidden"
                                id="cleaning-file-input"
                            />
                            <label
                                htmlFor="cleaning-file-input"
                                className="inline-block px-6 py-3 bg-white/10 hover:bg-white/20 rounded-lg cursor-pointer transition-colors mb-4"
                            >
                                {cleaningFile ? cleaningFile.name : 'Sélectionner un fichier'}
                            </label>

                            {/* Column Selection */}
                            {availableColumns.length > 0 && (
                                <div className="mt-6 text-left">
                                    <label className="block text-sm text-lvmh-gray mb-2">
                                        Colonne contenant le texte à nettoyer :
                                    </label>
                                    <select
                                        value={selectedColumn}
                                        onChange={(e) => setSelectedColumn(e.target.value)}
                                        className="w-full bg-white/5 border border-white/10 rounded-lg py-3 px-4 text-white focus:ring-1 focus:ring-lvmh-gold transition-all"
                                    >
                                        <option value="">-- Choisir une colonne --</option>
                                        {availableColumns.map(col => (
                                            <option key={col} value={col}>{col}</option>
                                        ))}
                                    </select>
                                    
                                    {previewData && (
                                        <div className="mt-4 p-4 bg-white/5 rounded-lg text-left">
                                            <div className="text-xs text-lvmh-gray uppercase mb-2">
                                                {previewData.row_count} lignes • {availableColumns.length} colonnes
                                            </div>
                                            {selectedColumn && previewData.sample[0] && (
                                                <div className="text-sm">
                                                    <span className="text-lvmh-gray">Exemple:</span>
                                                    <span className="ml-2 italic">"{String(previewData.sample[0][selectedColumn]).substring(0, 60)}..."</span>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            )}

                            {cleaningFile && selectedColumn && (
                                <div className="mt-6">
                                    <button
                                        onClick={handleDataCleaning}
                                        disabled={cleaningLoading}
                                        className="px-8 py-3 bg-lvmh-gold text-black font-bold rounded-lg hover:bg-lvmh-gold/90 transition-colors disabled:opacity-50 flex items-center gap-2 mx-auto"
                                    >
                                        {cleaningLoading ? (
                                            <>
                                                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-black" />
                                                Nettoyage en cours...
                                            </>
                                        ) : (
                                            <>
                                                <Sparkles size={18} />
                                                Nettoyer avec "{selectedColumn}"
                                            </>
                                        )}
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* Error */}
                        {cleaningError && (
                            <div className="glass p-6 border-l-4 border-red-500 bg-red-500/10">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center">
                                        <Trash2 size={20} className="text-red-500" />
                                    </div>
                                    <div>
                                        <h4 className="font-bold text-lg text-red-400">Erreur de nettoyage</h4>
                                        <p className="text-sm text-red-300">{cleaningError}</p>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Results */}
                        {cleaningResult && (
                            <div className="glass p-6 animate-in fade-in duration-500">
                                <div className="flex items-center gap-3 mb-6">
                                    <div className="w-10 h-10 rounded-full bg-green-500/20 flex items-center justify-center">
                                        <Sparkles size={20} className="text-green-500" />
                                    </div>
                                    <div>
                                        <h4 className="font-bold text-lg">Nettoyage terminé !</h4>
                                        <p className="text-sm text-lvmh-gray">
                                            Réduction de {cleaningResult.report.reduction_percent}%
                                        </p>
                                    </div>
                                    <button
                                        onClick={downloadCleanedFile}
                                        className="ml-auto px-4 py-2 bg-lvmh-gold text-black font-bold rounded-lg hover:bg-lvmh-gold/90 transition-colors flex items-center gap-2"
                                    >
                                        <Download size={16} />
                                        Télécharger
                                    </button>
                                </div>

                                {/* Stats Grid */}
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                                    <div className="bg-white/5 p-4 rounded-lg text-center">
                                        <div className="text-2xl font-display font-black text-lvmh-gold">{cleaningResult.report.original_rows}</div>
                                        <div className="text-xs text-lvmh-gray uppercase">Lignes originales</div>
                                    </div>
                                    <div className="bg-white/5 p-4 rounded-lg text-center">
                                        <div className="text-2xl font-display font-black text-red-400">-{cleaningResult.report.rows_removed_total}</div>
                                        <div className="text-xs text-lvmh-gray uppercase">Lignes supprimées</div>
                                    </div>
                                    <div className="bg-white/5 p-4 rounded-lg text-center">
                                        <div className="text-2xl font-display font-black text-green-500">{cleaningResult.report.final_rows}</div>
                                        <div className="text-xs text-lvmh-gray uppercase">Lignes finales</div>
                                    </div>
                                    <div className="bg-white/5 p-4 rounded-lg text-center">
                                        <div className="text-2xl font-display font-black text-lvmh-gold">{cleaningResult.report.reduction_percent}%</div>
                                        <div className="text-xs text-lvmh-gray uppercase">Réduction</div>
                                    </div>
                                </div>

                                {/* Details */}
                                <div className="space-y-3">
                                    <h5 className="font-bold text-sm uppercase tracking-wider text-lvmh-gray mb-3">
                                        Détails des opérations
                                    </h5>
                                    {cleaningResult.report.details.map((detail, i) => (
                                        <div key={i} className="flex items-center gap-3 bg-white/5 p-3 rounded-lg">
                                            <Trash2 size={16} className="text-red-400" />
                                            <span className="text-sm">{detail}</span>
                                        </div>
                                    ))}
                                    {cleaningResult.report.rows_cleaned > 0 && (
                                        <div className="flex items-center gap-3 bg-white/5 p-3 rounded-lg">
                                            <Sparkles size={16} className="text-lvmh-gold" />
                                            <span className="text-sm">
                                                Nettoyage des espaces et normalisation du texte
                                            </span>
                                        </div>
                                    )}
                                </div>

                                {/* Column Used */}
                                <div className="mt-6 pt-6 border-t border-white/10">
                                    <div className="flex items-center gap-2 mb-3">
                                        <span className="text-sm text-lvmh-gray">Colonne utilisée pour le nettoyage:</span>
                                        <span className="text-sm font-bold text-lvmh-gold">
                                            {cleaningResult.report.text_column_used}
                                        </span>
                                    </div>
                                </div>

                                {/* Columns */}
                                <div className="mt-4">
                                    <h5 className="font-bold text-sm uppercase tracking-wider text-lvmh-gray mb-3">
                                        Colonnes ({cleaningResult.report.final_columns.length})
                                    </h5>
                                    <div className="flex flex-wrap gap-2">
                                        {cleaningResult.report.final_columns.map((col, i) => (
                                            <span 
                                                key={i} 
                                                className={`text-xs px-2 py-1 rounded ${col === cleaningResult.report.text_column_used ? 'bg-lvmh-gold text-black font-bold' : 'bg-white/10'}`}
                                            >
                                                {col}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* DEBUG PIPELINE TAB */}
                {currentTab === 'debug' && (
                    <DebugAnalyzer />
                )}

                {/* CSV RESULTS TAB - Hidden but preserved for future use */}
                {currentTab === 'csv_hidden' && (
                    <div className="space-y-6 animate-in slide-in-from-right duration-500">
                        <div className="flex justify-between items-center">
                            <h3 className="text-2xl font-display font-black gold-text flex items-center gap-2">
                                <FileText size={24} /> Résultats Batch CSV
                            </h3>
                            <span className="text-sm text-lvmh-gray">{csvTotal} résultats</span>
                        </div>

                        {/* File Selector */}
                        <div className="glass p-6">
                            <label className="text-xs text-lvmh-gray uppercase tracking-widest font-bold mb-3 block">Sélectionner un fichier</label>
                            <select
                                value={selectedCsv}
                                onChange={handleCsvSelect}
                                className="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-white focus:ring-1 focus:ring-lvmh-gold transition-all appearance-none cursor-pointer"
                            >
                                {csvFiles.map(file => (
                                    <option key={file} value={file} className="bg-lvmh-black">{file}</option>
                                ))}
                            </select>
                        </div>

                        {loadingCsv ? (
                            <div className="flex justify-center py-20">
                                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-lvmh-gold"></div>
                            </div>
                        ) : (
                            <div className="glass overflow-hidden">
                                <table className="w-full text-left">
                                    <thead className="text-lvmh-gray text-xs uppercase tracking-widest border-b border-white/10 bg-white/5">
                                        <tr>
                                            <th className="p-4">ID</th>
                                            <th className="p-4">Tags</th>
                                            <th className="p-4">Tier</th>
                                            <th className="p-4">Budget</th>
                                            <th className="p-4 text-right">Confidence</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5">
                                        {csvData.length > 0 ? csvData.map((row, i) => (
                                            <tr key={i} className="hover:bg-white/5 transition-colors">
                                                <td className="p-4 font-bold">{row.id}</td>
                                                <td className="p-4">
                                                    <div className="flex flex-wrap gap-1">
                                                        {(row.tags || []).slice(0, 3).map((tag, ti) => (
                                                            <span key={ti} className="text-[9px] bg-white/10 px-2 py-0.5 rounded text-lvmh-gray uppercase">
                                                                {tag.replace(/_/g, ' ')}
                                                            </span>
                                                        ))}
                                                        {(row.tags || []).length > 3 && (
                                                            <span className="text-[9px] text-lvmh-gray">+{row.tags.length - 3}</span>
                                                        )}
                                                    </div>
                                                </td>
                                                <td className="p-4">
                                                    <span className={`text-[10px] px-2 py-1 rounded-full font-bold ${row.tier === 1 ? 'bg-white/10 text-white' :
                                                            row.tier === 2 ? 'bg-lvmh-gold/20 text-lvmh-gold' :
                                                                'bg-red-500/20 text-red-500'
                                                        }`}>
                                                        TIER {row.tier}
                                                    </span>
                                                </td>
                                                <td className="p-4 text-sm text-lvmh-gray">{row.budget_range || 'N/A'}</td>
                                                <td className="p-4 text-right font-bold text-lvmh-gold">{Math.round(row.confidence * 100)}%</td>
                                            </tr>
                                        )) : (
                                            <tr>
                                                <td colSpan={5} className="p-10 text-center text-lvmh-gray italic">
                                                    Aucun résultat dans ce fichier
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        )}
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
