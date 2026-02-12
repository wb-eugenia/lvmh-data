import React, { lazy, Suspense, useState, useEffect } from 'react'
import { ArrowLeft, LayoutDashboard, Trophy, Users, Star, Download, Search, FileText, Mic, Play, Pause, Tag, ShoppingBag, Zap, Sparkles, Trash2, Terminal, AlertTriangle, Clock3, Filter, BriefcaseBusiness, Activity, RefreshCcw, BellRing, Building2, UserRound, Wifi, WifiOff, LogOut, X } from 'lucide-react'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'
import { apiFetch, normalizeAnalysisResult, wsUrl } from '../lib/api'
import { useAuth } from '../context/AuthContext'

const DebugAnalyzer = lazy(() => import('./DebugAnalyzer'))

export default function ManagerView({ onBack }) {
    const { logout } = useAuth()
    const [currentTab, setCurrentTab] = useState('overview')
    const [stats, setStats] = useState({ total_notes: 0, avg_quality: 0, tier_distribution: { 1: 0, 2: 0, 3: 0 } })
    const [dashboardMetrics, setDashboardMetrics] = useState(null)
    const [dashboardSummary, setDashboardSummary] = useState(null)
    const [segmentsData, setSegmentsData] = useState(null)
    const [segmentsLoading, setSegmentsLoading] = useState(false)
    const [segmentsError, setSegmentsError] = useState(null)
    const [leaderboard, setLeaderboard] = useState([])
    const [history, setHistory] = useState([])
    const [overviewRecordings, setOverviewRecordings] = useState([])
    const [rgpdStats, setRgpdStats] = useState(null)
    const [costStats, setCostStats] = useState(null)
    const [overviewWindow, setOverviewWindow] = useState('7d')
    const [overviewPriority, setOverviewPriority] = useState('all')
    const [overviewAdvisor, setOverviewAdvisor] = useState('all')
    const [liveAlerts, setLiveAlerts] = useState([])
    const [pipelineSocketState, setPipelineSocketState] = useState('connecting')
    const [drilldownAdvisor, setDrilldownAdvisor] = useState('all')
    const [drilldownStore, setDrilldownStore] = useState('all')
    const [focusMetric, setFocusMetric] = useState('volume')
    const [opportunityActions, setOpportunityActions] = useState({})
    const [opportunityStatusFilter, setOpportunityStatusFilter] = useState('all')
    const [opportunitySearch, setOpportunitySearch] = useState('')
    const [opportunitySort, setOpportunitySort] = useState('priority')
    const [opportunityLimit, setOpportunityLimit] = useState(10)
    const [selectedOpportunityId, setSelectedOpportunityId] = useState(null)
    const [selectedOpportunityIds, setSelectedOpportunityIds] = useState([])
    const [bulkActionSubmitting, setBulkActionSubmitting] = useState(false)
    const [actionsLoading, setActionsLoading] = useState(false)
    const [actionsError, setActionsError] = useState(null)
    const [actionSubmittingId, setActionSubmittingId] = useState(null)
    const [exportingManager, setExportingManager] = useState(null)
    const [exportError, setExportError] = useState(null)

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

    const formatPreviewValue = (value) => {
        if (value === null || value === undefined) return null

        if (Array.isArray(value)) {
            const normalized = value
                .map((item) => formatPreviewValue(item))
                .filter(Boolean)
                .slice(0, 4)
            return normalized.length ? normalized.join(', ') : null
        }

        if (typeof value === 'object') {
            if (typeof value.description === 'string' && value.description.trim()) return value.description.trim()
            if (typeof value.label === 'string' && value.label.trim()) return value.label.trim()

            const compact = Object.entries(value)
                .filter(([, nested]) => ['string', 'number', 'boolean'].includes(typeof nested))
                .slice(0, 3)
                .map(([nestedKey, nestedValue]) => `${nestedKey}: ${nestedValue}`)
                .join(' | ')
            return compact || null
        }

        const normalizedText = String(value).trim()
        return normalizedText || null
    }

    const buildPillarEntries = (pillar) => {
        if (!pillar || typeof pillar !== 'object') return []
        return Object.entries(pillar)
            .map(([key, value]) => ({
                key: key.replace(/_/g, ' '),
                value: formatPreviewValue(value)
            }))
            .filter((entry) => entry.value)
            .slice(0, 8)
    }

    const formatFileTimestamp = () => {
        return new Date().toISOString().replace(/[:.]/g, '-')
    }

    const escapeCsvCell = (value) => {
        if (value === null || value === undefined) return ''
        const text = String(value).replace(/\r?\n/g, ' ').trim()
        if (/[\",;]/.test(text)) {
            return `"${text.replace(/\"/g, '""')}"`
        }
        return text
    }

    const escapeHtml = (value) => {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/\"/g, '&quot;')
            .replace(/'/g, '&#39;')
    }

    const downloadTextFile = (content, filename, mimeType) => {
        const blob = new Blob([content], { type: mimeType })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = filename
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        URL.revokeObjectURL(url)
    }

    const normalizeRecording = (recording) => {
        if (!recording || typeof recording !== 'object') return null
        const normalized = normalizeAnalysisResult({
            ...recording,
            routing: recording.routing || {
                tier: recording.tier,
                confidence: recording.confidence
            },
            tags: recording.tags,
            rgpd: recording.rgpd,
            meta_analysis: recording.meta_analysis,
            pilier_1_univers_produit: recording.pilier_1_univers_produit,
            pilier_2_profil_client: recording.pilier_2_profil_client,
            pilier_3_hospitalite_care: recording.pilier_3_hospitalite_care,
            pilier_4_action_business: recording.pilier_4_action_business
        })

        return {
            ...recording,
            ...normalized,
            tier: normalized.routing.tier,
            confidence: normalized.routing.confidence
        }
    }

    const normalizeRecordingsList = (items) => (
        Array.isArray(items)
            ? items.map(normalizeRecording).filter(Boolean)
            : []
    )

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

    const extractBudgetValue = (value) => {
        if (typeof value === 'number' && Number.isFinite(value)) return value
        if (!value) return null

        const text = String(value).toLowerCase()
        const matches = [...text.matchAll(/(\d+(?:[.,]\d+)?)\s*(k|m)?/g)]
        if (!matches.length) return null

        const parsedValues = matches.map((match) => {
            const numeric = Number(String(match[1]).replace(',', '.'))
            if (!Number.isFinite(numeric)) return null
            if (match[2] === 'm') return numeric * 1000000
            if (match[2] === 'k') return numeric * 1000
            return numeric
        }).filter((n) => Number.isFinite(n))

        if (!parsedValues.length) return null
        return Math.max(...parsedValues)
    }

    const normalizeUrgency = (value) => {
        const text = String(value || '').toLowerCase()
        if (!text) return { level: 1, label: 'Low' }
        if (
            text.includes('urgent')
            || text.includes('high')
            || text.includes('immediat')
            || text.includes('crit')
            || text.includes('hot')
        ) {
            return { level: 3, label: 'High' }
        }
        if (
            text.includes('medium')
            || text.includes('modere')
            || text.includes('normal')
            || text.includes('moyen')
        ) {
            return { level: 2, label: 'Medium' }
        }
        return { level: 1, label: 'Low' }
    }

    const WINDOW_DAYS_MAP = {
        today: 1,
        '7d': 7,
        '30d': 30
    }

    const windowDays = WINDOW_DAYS_MAP[overviewWindow] || null

    const toTimestampMs = (value) => {
        if (!value) return null
        const ts = new Date(value).getTime()
        return Number.isNaN(ts) ? null : ts
    }

    const computeWindowKpis = (records) => {
        const safeRecords = Array.isArray(records) ? records : []
        const total = safeRecords.length
        if (total === 0) {
            return {
                total: 0,
                vipShare: 0,
                urgentCount: 0,
                avgConfidencePct: 0,
                tier3Count: 0
            }
        }

        const vipCount = safeRecords.filter((recording) => recording?.client?.vic_status && recording.client.vic_status !== 'Standard').length
        const urgentCount = safeRecords.filter((recording) => {
            const p4 = recording?.pilier_4_action_business || {}
            const urgency = normalizeUrgency(p4?.urgency || p4?.priority || p4?.lead_temperature)
            return urgency.level === 3
        }).length
        const confidenceAvg = safeRecords.reduce((sum, recording) => sum + Number(recording?.confidence || 0), 0) / total
        const tier3Count = safeRecords.filter((recording) => Number(recording?.tier || 1) === 3).length

        return {
            total,
            vipShare: (vipCount / total) * 100,
            urgentCount,
            avgConfidencePct: confidenceAvg * 100,
            tier3Count
        }
    }

    const formatDeltaLabel = (current, previous, precision = 0) => {
        if (previous === null || previous === undefined) return 'Delta N/A'
        const delta = current - previous
        if (Math.abs(delta) < 0.0001) return 'Stable vs periode precedente'

        const sign = delta > 0 ? '+' : '-'
        const absolute = Math.abs(delta).toFixed(precision)
        if (Math.abs(previous) < 0.0001) {
            return `${sign}${absolute} vs periode precedente`
        }
        const pct = Math.abs((delta / previous) * 100).toFixed(1)
        return `${sign}${absolute} (${sign}${pct}%) vs periode precedente`
    }

    const isWithinWindow = (timestamp, windowKey) => {
        if (!timestamp) return windowKey === 'all'
        if (windowKey === 'all') return true
        const date = new Date(timestamp)
        if (Number.isNaN(date.getTime())) return false

        const now = Date.now()
        const diffDays = (now - date.getTime()) / (1000 * 60 * 60 * 24)
        if (windowKey === 'today') return diffDays <= 1
        if (windowKey === '7d') return diffDays <= 7
        if (windowKey === '30d') return diffDays <= 30
        return true
    }

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

    const buildLiveAlert = (payload) => {
        const step = normalizePipelineStep(payload?.step)
        if (!step) return null

        const tier = payload?.tier ? `T${payload.tier}` : null
        const advisorId = payload?.user_id ? `Advisor ${payload.user_id}` : null
        const segments = [advisorId, tier].filter(Boolean)
        const context = segments.length ? ` (${segments.join(' | ')})` : ''

        if (step === 'failed') {
            return {
                severity: 'critical',
                title: `Echec pipeline${context}`,
                message: payload?.error || 'Erreur de traitement detectee.',
                timestamp: new Date().toISOString()
            }
        }
        if (step === 'routing' && Number(payload?.tier || 0) === 3) {
            return {
                severity: 'warning',
                title: `Escalade Tier 3${context}`,
                message: `Note complexe detectee${payload?.score ? `, score ${payload.score}` : ''}.`,
                timestamp: new Date().toISOString()
            }
        }
        if (step === 'cleaning' && payload?.contains_sensitive) {
            return {
                severity: 'warning',
                title: `Signal RGPD${context}`,
                message: 'Donnees sensibles detectees durant le pre-traitement.',
                timestamp: new Date().toISOString()
            }
        }
        if (step === 'done') {
            return {
                severity: 'info',
                title: `Pipeline complete${context}`,
                message: payload?.quality_score ? `Qualite ${formatPercent(payload.quality_score)}` : 'Traitement termine.',
                timestamp: new Date().toISOString()
            }
        }

        return {
            severity: 'info',
            title: `Pipeline ${step}${context}`,
            message: payload?.status || 'Evenement temps reel recu.',
            timestamp: new Date().toISOString()
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

    useEffect(() => {
        if (overviewAdvisor !== 'all') {
            setDrilldownAdvisor(overviewAdvisor)
        }
    }, [overviewAdvisor])

    useEffect(() => {
        const socketUrl = wsUrl('/ws/pipeline')
        let ws
        let reconnectTimer
        let isActive = true

        const connect = () => {
            if (!isActive) return
            setPipelineSocketState('connecting')
            ws = new WebSocket(socketUrl)

            ws.onopen = () => {
                if (!isActive) return
                setPipelineSocketState('connected')
            }

            ws.onmessage = (event) => {
                if (!isActive) return

                try {
                    const payload = JSON.parse(event.data || '{}')
                    if (payload?.type === 'leaderboard') {
                        setLeaderboard(payload.data || [])
                        return
                    }

                    if (!payload?.step) return
                    const liveAlert = buildLiveAlert(payload)
                    if (!liveAlert) return

                    setLiveAlerts((previous) => [liveAlert, ...previous].slice(0, 30))
                } catch (error) {
                    console.error('Manager WS parse error:', error)
                }
            }

            ws.onerror = () => {
                if (!isActive) return
                setPipelineSocketState('disconnected')
            }

            ws.onclose = () => {
                if (!isActive) return
                setPipelineSocketState('disconnected')
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
            
            const res = await apiFetch('/api/data-cleaning/preview', {
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
            
            const res = await apiFetch('/api/data-cleaning', {
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
            const res = await apiFetch(`/api/recordings?${params}`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                }
            })
            console.log('Response status:', res.status)
            
            if (res.ok) {
                const data = await res.json()
                console.log('Recordings data:', data)
                setRecordings(normalizeRecordingsList(data.recordings))
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
            const res = await apiFetch('/api/batch-results')
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
            const res = await apiFetch(`/api/batch-results?file=${encodeURIComponent(filename)}`)
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
            const sRes = await apiFetch('/api/stats/overview')
            if (sRes.ok) {
                setStats(await sRes.json())
            }

            const lRes = await apiFetch('/api/leaderboard')
            if (lRes.ok) {
                setLeaderboard(await lRes.json())
            }

            const hRes = await apiFetch('/api/search?q=')
            if (hRes.ok) {
                const hData = await hRes.json()
                setHistory(hData.results || [])
            }

            const token = localStorage.getItem('token')
            const ovRes = await apiFetch('/api/recordings?page=1&limit=100', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            })
            if (ovRes.ok) {
                const ovData = await ovRes.json()
                setOverviewRecordings(normalizeRecordingsList(ovData.recordings))
            }

            const rRes = await apiFetch('/api/stats/rgpd')
            if (rRes.ok) {
                setRgpdStats(await rRes.json())
            }

            const cRes = await apiFetch('/api/stats/cost')
            if (cRes.ok) {
                setCostStats(await cRes.json())
            }

            const dRes = await apiFetch('/api/dashboard/metrics')
            if (dRes.ok) {
                setDashboardMetrics(await dRes.json())
            }

            const dsRes = await apiFetch('/api/dashboard/metrics/summary')
            if (dsRes.ok) {
                setDashboardSummary(await dsRes.json())
            }
        } catch (e) { console.error(e) }
    }

    const loadSegments = async () => {
        setSegmentsLoading(true)
        setSegmentsError(null)
        try {
            const params = new URLSearchParams()
            params.set('window', overviewWindow)
            params.set('n_clusters', '5')
            params.set('limit', '1500')
            if (overviewAdvisor && overviewAdvisor !== 'all') {
                params.set('advisor', overviewAdvisor)
            }

            const res = await apiFetch(`/api/dashboard/segments?${params.toString()}`)
            if (!res.ok) {
                const body = await res.text()
                throw new Error(body || `Erreur segments (${res.status})`)
            }
            setSegmentsData(await res.json())
        } catch (error) {
            setSegmentsError(error.message || 'Erreur chargement segments')
            setSegmentsData(null)
        } finally {
            setSegmentsLoading(false)
        }
    }

    const loadOpportunityActions = async (noteIdsCsv) => {
        if (!noteIdsCsv) {
            setOpportunityActions({})
            setActionsError(null)
            return
        }

        setActionsLoading(true)
        setActionsError(null)
        try {
            const params = new URLSearchParams()
            params.set('note_ids', noteIdsCsv)
            params.set('limit', '500')
            const res = await apiFetch(`/api/dashboard/opportunities/actions?${params.toString()}`)
            if (!res.ok) {
                const body = await res.text()
                throw new Error(body || `Erreur chargement actions (${res.status})`)
            }
            const payload = await res.json()
            const nextMap = (payload?.actions || []).reduce((acc, action) => {
                if (action?.note_id) {
                    acc[action.note_id] = action
                }
                return acc
            }, {})
            setOpportunityActions(nextMap)
        } catch (error) {
            setActionsError(error.message || 'Erreur chargement actions')
        } finally {
            setActionsLoading(false)
        }
    }

    const buildOpportunityActionPayload = (actionType, currentActionState = null) => {
        if (actionType === 'call') {
            return { action_type: 'call', status: 'planned' }
        }
        if (actionType === 'schedule') {
            return { action_type: 'schedule', status: 'planned' }
        }
        if (actionType === 'done') {
            return {
                action_type: currentActionState?.action_type || currentActionState?.actionType || 'other',
                status: 'done'
            }
        }
        return { action_type: 'other', status: 'planned' }
    }

    const upsertOpportunityAction = async (noteId, actionType, currentActionState = null) => {
        const payload = buildOpportunityActionPayload(actionType, currentActionState)
        const res = await apiFetch('/api/dashboard/opportunities/actions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                note_id: noteId,
                action_type: payload.action_type,
                status: payload.status
            })
        })
        if (!res.ok) {
            const body = await res.text()
            throw new Error(body || `Erreur action (${res.status})`)
        }
        const parsed = await res.json()
        return parsed?.action || null
    }

    const handleOpportunityAction = async (opportunity, actionType) => {
        if (!opportunity?.id) return

        const currentActionState = opportunityActions[opportunity.id] || null
        setActionSubmittingId(opportunity.id)
        setActionsError(null)
        try {
            const savedAction = await upsertOpportunityAction(opportunity.id, actionType, currentActionState)
            if (savedAction?.note_id) {
                setOpportunityActions((previous) => ({
                    ...previous,
                    [savedAction.note_id]: savedAction
                }))
            }
        } catch (error) {
            setActionsError(error.message || 'Erreur sauvegarde action')
        } finally {
            setActionSubmittingId(null)
        }
    }

    const handleBulkOpportunityAction = async (actionType) => {
        const noteIds = Array.from(
            new Set(
                (selectedOpportunityIds || [])
                    .map((id) => Number(id))
                    .filter((id) => Number.isFinite(id))
            )
        )
        if (!noteIds.length) return

        setBulkActionSubmitting(true)
        setActionsError(null)
        try {
            const results = await Promise.allSettled(
                noteIds.map((noteId) => {
                    const currentActionState = opportunityActions[noteId] || null
                    return upsertOpportunityAction(noteId, actionType, currentActionState)
                })
            )

            const savedActions = []
            let failureCount = 0
            results.forEach((result) => {
                if (result.status === 'fulfilled') {
                    if (result.value?.note_id) savedActions.push(result.value)
                } else {
                    failureCount += 1
                }
            })

            if (savedActions.length) {
                setOpportunityActions((previous) => {
                    const next = { ...previous }
                    savedActions.forEach((action) => {
                        if (action?.note_id) next[action.note_id] = action
                    })
                    return next
                })
            }

            if (failureCount > 0) {
                setActionsError(`${failureCount} action(s) n'ont pas ete sauvegardees.`)
            } else {
                setSelectedOpportunityIds([])
            }
        } catch (error) {
            setActionsError(error.message || 'Erreur sauvegarde actions bulk')
        } finally {
            setBulkActionSubmitting(false)
        }
    }

    const getOpportunityActionLabel = (state) => {
        if (!state) return 'Aucune action'
        const status = String(state.status || '').toLowerCase()
        const actionType = String(state.action_type || state.actionType || '').toLowerCase()
        if (status === 'done') return 'Action finalisee'
        if (actionType === 'call') return 'Appel planifie'
        if (actionType === 'schedule') return 'Rappel planifie'
        if (status === 'planned') return 'Action planifiee'
        return 'Action en cours'
    }

    const pipelineStats = dashboardMetrics?.pipeline_stats || {}
    const qualityStats = dashboardMetrics?.quality_metrics || {}
    const mergedCostStats = dashboardMetrics?.cost_stats || costStats
    const tierDistribution = normalizeTierDistribution(pipelineStats?.tier_distribution || stats?.tier_distribution)
    const avgQuality = qualityStats?.accuracy_rate ?? stats?.avg_quality ?? 0
    const totalCost = mergedCostStats?.total_cost_eur ?? mergedCostStats?.total_cost ?? 0
    const costPerNote = mergedCostStats?.cost_per_note ?? mergedCostStats?.roi_metrics?.cost_per_note ?? 0
    const savingsRate = mergedCostStats?.roi_metrics?.savings || '-'
    const totalProcessed = pipelineStats?.total_processed ?? stats?.total_notes ?? 0
    const healthScore = Math.round(dashboardSummary?.health_score || 0)
    const healthStatus = dashboardSummary?.health_status || 'healthy'
    const alerts = dashboardSummary?.alerts || dashboardMetrics?.alerts || []
    const alertToneClass = healthStatus === 'healthy'
        ? 'border-green-500/30 bg-green-500/10 text-green-400'
        : healthStatus === 'warning'
            ? 'border-lvmh-gold/30 bg-lvmh-gold/10 text-lvmh-gold'
            : 'border-red-500/30 bg-red-500/10 text-red-400'

    const overviewAdvisorOptions = Array.from(
        new Set(
            (overviewRecordings || [])
                .map((recording) => recording?.advisor?.name)
                .filter(Boolean)
        )
    ).sort((a, b) => a.localeCompare(b))

    const overviewScopedRecordings = (overviewRecordings || []).filter((recording) => {
        if (!isWithinWindow(recording?.timestamp, overviewWindow)) return false
        if (overviewAdvisor !== 'all' && recording?.advisor?.name !== overviewAdvisor) return false
        return true
    })

    const previousWindowScopedRecordings = (() => {
        if (!windowDays) return []
        const nowMs = Date.now()
        const currentStartMs = nowMs - (windowDays * 24 * 60 * 60 * 1000)
        const previousStartMs = currentStartMs - (windowDays * 24 * 60 * 60 * 1000)

        return (overviewRecordings || []).filter((recording) => {
            if (overviewAdvisor !== 'all' && recording?.advisor?.name !== overviewAdvisor) return false
            const timestampMs = toTimestampMs(recording?.timestamp)
            if (!timestampMs) return false
            return timestampMs >= previousStartMs && timestampMs < currentStartMs
        })
    })()

    const currentWindowKpis = computeWindowKpis(overviewScopedRecordings)
    const previousWindowKpis = windowDays ? computeWindowKpis(previousWindowScopedRecordings) : null
    const scopedNoteIdsCsv = overviewScopedRecordings
        .map((recording) => recording?.id)
        .filter((id) => Number.isFinite(Number(id)))
        .join(',')

    const scopedTierDistribution = overviewScopedRecordings.reduce((acc, recording) => {
        const tier = Number(recording?.tier || 1)
        if (tier === 1 || tier === 2 || tier === 3) acc[tier] += 1
        return acc
    }, { 1: 0, 2: 0, 3: 0 })
    const hasScopedDistribution = (scopedTierDistribution[1] + scopedTierDistribution[2] + scopedTierDistribution[3]) > 0
    const chartSource = hasScopedDistribution ? scopedTierDistribution : tierDistribution

    const chartData = [
        { name: 'Tier 1', value: chartSource?.[1] || 0, color: '#888888' },
        { name: 'Tier 2', value: chartSource?.[2] || 0, color: '#D4AF37' },
        { name: 'Tier 3', value: chartSource?.[3] || 0, color: '#FF5252' }
    ]

    const opportunitiesBase = overviewScopedRecordings.map((recording) => {
        const p4 = recording?.pilier_4_action_business || {}
        const urgency = normalizeUrgency(p4?.urgency || p4?.priority || p4?.lead_temperature)
        const budgetValue = extractBudgetValue(p4?.budget_specific ?? p4?.budget_potential)
        const nextAction = p4?.next_best_action?.description
            || recording?.next_best_action?.description
            || 'Relance conseiller recommandee.'
        const isVip = Boolean(recording?.client?.vic_status && recording.client.vic_status !== 'Standard')
        const tierScore = recording?.tier === 3 ? 30 : recording?.tier === 2 ? 18 : 8
        const urgencyScore = urgency.level * 15
        const vipScore = isVip ? 25 : 0
        const budgetScore = budgetValue ? Math.min(35, budgetValue / 2000) : 0
        const confidenceScore = Math.round(Number(recording?.confidence || 0) * 12)

        return {
            id: recording?.id,
            clientName: recording?.client?.name || 'Client inconnu',
            advisorName: recording?.advisor?.name || 'Inconnu',
            advisorStore: recording?.advisor?.store || 'N/A',
            vipLabel: recording?.client?.vic_status || 'Standard',
            isVip,
            tier: recording?.tier || 1,
            urgencyLevel: urgency.level,
            urgencyLabel: urgency.label,
            nextAction,
            budgetValue,
            budgetLabel: budgetValue ? formatCurrency(budgetValue) : (p4?.budget_potential || '-'),
            priorityScore: Math.round(tierScore + urgencyScore + vipScore + budgetScore + confidenceScore),
            tagsCount: (recording?.tags || []).length,
            confidence: formatPercent(recording?.confidence || 0),
            timestamp: recording?.timestamp,
            timestampMs: toTimestampMs(recording?.timestamp) || 0
        }
    }).filter((item) => item.nextAction || item.tier >= 2)

    const resolveOpportunityAction = (opportunityId) => {
        const state = opportunityActions?.[opportunityId]
        if (!state || typeof state !== 'object') return null

        const normalizedStatus = String(state.status || '').trim().toLowerCase()
        const normalizedActionType = String(state.action_type || state.actionType || '').trim().toLowerCase()
        return {
            ...state,
            status: normalizedStatus,
            action_type: normalizedActionType
        }
    }

    const normalizedOpportunitySearch = opportunitySearch.trim().toLowerCase()

    const filteredOpportunities = opportunitiesBase.filter((item) => {
        if (overviewPriority === 'urgent' && item.urgencyLevel !== 3) return false
        if (overviewPriority === 'vip' && !item.isVip) return false
        if (overviewPriority === 'tier3' && item.tier !== 3) return false

        const actionState = resolveOpportunityAction(item.id)
        if (opportunityStatusFilter === 'open' && actionState && actionState.status !== 'open') return false
        if (opportunityStatusFilter === 'planned' && actionState?.status !== 'planned') return false
        if (opportunityStatusFilter === 'done' && actionState?.status !== 'done') return false

        if (normalizedOpportunitySearch) {
            const searchable = `${item.clientName} ${item.advisorName} ${item.nextAction} ${item.vipLabel} ${item.budgetLabel}`.toLowerCase()
            if (!searchable.includes(normalizedOpportunitySearch)) return false
        }
        return true
    })
    const filteredOpportunityIdsKey = filteredOpportunities
        .map((item) => Number(item?.id))
        .filter((id) => Number.isFinite(id))
        .join(',')

    const sortedOpportunities = [...filteredOpportunities].sort((a, b) => {
        if (opportunitySort === 'recent') return (b.timestampMs || 0) - (a.timestampMs || 0)
        if (opportunitySort === 'budget') return (b.budgetValue || 0) - (a.budgetValue || 0)
        if (opportunitySort === 'urgency') {
            if (b.urgencyLevel !== a.urgencyLevel) return b.urgencyLevel - a.urgencyLevel
            return b.priorityScore - a.priorityScore
        }
        return b.priorityScore - a.priorityScore
    })
    const safeOpportunityLimit = Number(opportunityLimit) > 0 ? Number(opportunityLimit) : 10
    const topOpportunities = sortedOpportunities.slice(0, safeOpportunityLimit)
    const visibleOpportunityIds = topOpportunities
        .map((item) => Number(item?.id))
        .filter((id) => Number.isFinite(id))
    const visibleOpportunityIdSet = new Set(visibleOpportunityIds)
    const selectedOpportunityIdSet = new Set(
        (selectedOpportunityIds || [])
            .map((id) => Number(id))
            .filter((id) => Number.isFinite(id))
    )
    const selectedOpportunitiesCount = selectedOpportunityIdSet.size
    const selectedVisibleCount = visibleOpportunityIds.filter((id) => selectedOpportunityIdSet.has(id)).length
    const allVisibleOpportunitiesSelected = visibleOpportunityIds.length > 0 && selectedVisibleCount === visibleOpportunityIds.length

    const toggleOpportunitySelection = (opportunityId) => {
        const normalizedId = Number(opportunityId)
        if (!Number.isFinite(normalizedId)) return
        setSelectedOpportunityIds((previous) => {
            if (previous.includes(normalizedId)) {
                return previous.filter((id) => id !== normalizedId)
            }
            return [...previous, normalizedId]
        })
    }

    const toggleSelectVisibleOpportunities = () => {
        setSelectedOpportunityIds((previous) => {
            const previousSet = new Set(
                previous
                    .map((id) => Number(id))
                    .filter((id) => Number.isFinite(id))
            )
            if (allVisibleOpportunitiesSelected) {
                return previous.filter((id) => !visibleOpportunityIdSet.has(Number(id)))
            }
            visibleOpportunityIds.forEach((id) => previousSet.add(id))
            return Array.from(previousSet)
        })
    }

    const vipCountScoped = overviewScopedRecordings.filter((recording) => recording?.client?.vic_status && recording.client.vic_status !== 'Standard').length
    const opportunityBudgetTotal = topOpportunities.reduce((sum, item) => sum + (item.budgetValue || 0), 0)
    const urgentActionsCount = filteredOpportunities.filter((item) => item.urgencyLevel === 3).length

    const topAdvisorScore = leaderboard?.[0]?.score || 0
    const tier3Alerts = filteredOpportunities.filter((item) => item.tier === 3).length || (history?.filter((item) => item?.tier === 3)?.length || 0)
    const volumeDeltaLabel = formatDeltaLabel(
        currentWindowKpis.total,
        previousWindowKpis ? previousWindowKpis.total : null,
        0
    )
    const confidenceDeltaLabel = formatDeltaLabel(
        currentWindowKpis.avgConfidencePct,
        previousWindowKpis ? previousWindowKpis.avgConfidencePct : null,
        1
    )
    const vipDeltaLabel = formatDeltaLabel(
        currentWindowKpis.vipShare,
        previousWindowKpis ? previousWindowKpis.vipShare : null,
        1
    )
    const urgentDeltaLabel = formatDeltaLabel(
        currentWindowKpis.urgentCount,
        previousWindowKpis ? previousWindowKpis.urgentCount : null,
        0
    )

    const opportunityActionStats = filteredOpportunities.reduce((acc, item) => {
        const actionState = resolveOpportunityAction(item.id)
        const status = String(actionState?.status || '').toLowerCase()
        const actionType = String(actionState?.action_type || actionState?.actionType || '').toLowerCase()

        if (status === 'done') {
            acc.done += 1
        } else {
            acc.open += 1
            if (actionType === 'call') acc.call += 1
            if (actionType === 'schedule') acc.schedule += 1
        }
        return acc
    }, { open: 0, done: 0, call: 0, schedule: 0 })
    const opportunityActionsOpen = opportunityActionStats.open
    const opportunityActionsDone = opportunityActionStats.done
    const opportunityCallPlanned = opportunityActionStats.call
    const opportunitySchedulePlanned = opportunityActionStats.schedule

    const selectedOpportunityRecord = selectedOpportunityId
        ? (overviewScopedRecordings.find((recording) => Number(recording?.id) === Number(selectedOpportunityId))
            || overviewRecordings.find((recording) => Number(recording?.id) === Number(selectedOpportunityId))
            || null)
        : null
    const selectedOpportunityActionState = selectedOpportunityRecord
        ? resolveOpportunityAction(selectedOpportunityRecord.id)
        : null
    const selectedOpportunityActionLabel = getOpportunityActionLabel(selectedOpportunityActionState)
    const selectedOpportunityP4 = selectedOpportunityRecord?.pilier_4_action_business || {}
    const selectedOpportunityUrgency = normalizeUrgency(
        selectedOpportunityP4?.urgency
        || selectedOpportunityP4?.priority
        || selectedOpportunityP4?.lead_temperature
    )
    const selectedOpportunityBudget = extractBudgetValue(
        selectedOpportunityP4?.budget_specific ?? selectedOpportunityP4?.budget_potential
    )
    const selectedOpportunityPillars = [
        { title: 'Pilier 1 - Produit', entries: buildPillarEntries(selectedOpportunityRecord?.pilier_1_univers_produit) },
        { title: 'Pilier 2 - Client', entries: buildPillarEntries(selectedOpportunityRecord?.pilier_2_profil_client) },
        { title: 'Pilier 3 - Hospitalite', entries: buildPillarEntries(selectedOpportunityRecord?.pilier_3_hospitalite_care) },
        { title: 'Pilier 4 - Action', entries: buildPillarEntries(selectedOpportunityRecord?.pilier_4_action_business) }
    ]
    const selectedOpportunityTags = Array.isArray(selectedOpportunityRecord?.tags) ? selectedOpportunityRecord.tags : []
    const selectedOpportunityProducts = Array.isArray(selectedOpportunityRecord?.matched_products) ? selectedOpportunityRecord.matched_products : []
    const selectedOpportunityNba = selectedOpportunityP4?.next_best_action || selectedOpportunityRecord?.next_best_action || null
    const selectedOpportunityChurn = Number(selectedOpportunityP4?.churn_risk || 0)
    const selectedOpportunityClv = extractBudgetValue(selectedOpportunityP4?.clv_estimate)
    const selectedOpportunityPredictionSource = selectedOpportunityP4?.prediction_source || null
    const segmentRows = Array.isArray(segmentsData?.segments) ? segmentsData.segments : []

    useEffect(() => {
        if (currentTab === 'overview') return
        if (selectedOpportunityId !== null) {
            setSelectedOpportunityId(null)
        }
    }, [currentTab, selectedOpportunityId])

    useEffect(() => {
        if (!selectedOpportunityRecord) return

        const previousOverflow = document.body.style.overflow
        const handleKeyDown = (event) => {
            if (event.key === 'Escape') {
                setSelectedOpportunityId(null)
            }
        }

        document.body.style.overflow = 'hidden'
        window.addEventListener('keydown', handleKeyDown)
        return () => {
            document.body.style.overflow = previousOverflow
            window.removeEventListener('keydown', handleKeyDown)
        }
    }, [selectedOpportunityRecord])

    useEffect(() => {
        if (currentTab !== 'overview') return
        loadOpportunityActions(scopedNoteIdsCsv)
    }, [currentTab, scopedNoteIdsCsv])

    useEffect(() => {
        if (currentTab !== 'overview') return
        loadSegments()
    }, [currentTab, overviewWindow, overviewAdvisor])

    useEffect(() => {
        if (currentTab !== 'overview') {
            if (selectedOpportunityIds.length > 0) setSelectedOpportunityIds([])
            return
        }

        const availableIdSet = new Set(
            filteredOpportunityIdsKey
                .split(',')
                .map((id) => Number(id))
                .filter((id) => Number.isFinite(id))
        )
        setSelectedOpportunityIds((previous) => {
            if (!previous.length) return previous
            const next = previous.filter((id) => availableIdSet.has(Number(id)))
            if (next.length === previous.length && next.every((id, index) => id === previous[index])) {
                return previous
            }
            return next
        })
    }, [currentTab, filteredOpportunityIdsKey, selectedOpportunityIds.length])

    const storeOptions = Array.from(
        new Set(
            overviewScopedRecordings
                .map((recording) => recording?.advisor?.store)
                .filter(Boolean)
        )
    ).sort((a, b) => a.localeCompare(b))

    const advisorDrilldownRows = Array.from(
        overviewScopedRecordings.reduce((acc, recording) => {
            const advisorName = recording?.advisor?.name || 'Inconnu'
            const advisorStore = recording?.advisor?.store || 'N/A'
            const key = `${advisorName}::${advisorStore}`
            const urgency = normalizeUrgency(
                recording?.pilier_4_action_business?.urgency
                || recording?.pilier_4_action_business?.priority
                || recording?.pilier_4_action_business?.lead_temperature
            )
            const budget = extractBudgetValue(
                recording?.pilier_4_action_business?.budget_specific
                ?? recording?.pilier_4_action_business?.budget_potential
            ) || 0
            const confidence = Number(recording?.confidence || 0)
            const isVip = Boolean(recording?.client?.vic_status && recording.client.vic_status !== 'Standard')

            if (!acc.has(key)) {
                acc.set(key, {
                    advisorName,
                    advisorStore,
                    notes: 0,
                    tier3: 0,
                    urgent: 0,
                    vip: 0,
                    confidenceTotal: 0,
                    budgetTotal: 0,
                    latestTimestamp: recording?.timestamp || null
                })
            }

            const row = acc.get(key)
            row.notes += 1
            if (Number(recording?.tier || 1) === 3) row.tier3 += 1
            if (urgency.level === 3) row.urgent += 1
            if (isVip) row.vip += 1
            row.confidenceTotal += confidence
            row.budgetTotal += budget
            if (recording?.timestamp && (!row.latestTimestamp || new Date(recording.timestamp) > new Date(row.latestTimestamp))) {
                row.latestTimestamp = recording.timestamp
            }
            return acc
        }, new Map()).values()
    ).map((row) => ({
        ...row,
        avgConfidence: row.notes > 0 ? (row.confidenceTotal / row.notes) : 0,
        priorityIndex: Math.round((row.tier3 * 18) + (row.urgent * 15) + (row.vip * 8) + (row.notes * 2))
    })).sort((a, b) => b.priorityIndex - a.priorityIndex)

    const filteredDrilldownRows = advisorDrilldownRows.filter((row) => {
        if (drilldownStore !== 'all' && row.advisorStore !== drilldownStore) return false
        if (drilldownAdvisor !== 'all' && row.advisorName !== drilldownAdvisor) return false
        return true
    })

    const selectedDrilldownRow = filteredDrilldownRows[0] || null
    const selectedAdvisorLabel = selectedDrilldownRow?.advisorName || '-'

    const selectedAdvisorRecentNotes = selectedDrilldownRow
        ? overviewScopedRecordings
            .filter((recording) =>
                (recording?.advisor?.name || 'Inconnu') === selectedDrilldownRow.advisorName
                && (recording?.advisor?.store || 'N/A') === selectedDrilldownRow.advisorStore
            )
            .sort((a, b) => new Date(b?.timestamp || 0).getTime() - new Date(a?.timestamp || 0).getTime())
            .slice(0, 5)
        : []

    const liveAlertsCritical = liveAlerts.filter((item) => item.severity === 'critical').length
    const liveAlertsWarning = liveAlerts.filter((item) => item.severity === 'warning').length
    const liveAlertsInfo = liveAlerts.filter((item) => item.severity === 'info').length

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

    const managerFilterSummary = `window=${overviewWindow} | priority=${overviewPriority} | advisor=${overviewAdvisor} | action=${opportunityStatusFilter} | search=${opportunitySearch || '-'} | sort=${opportunitySort} | limit=${safeOpportunityLimit}`

    const buildOpportunityExportRows = () => {
        return topOpportunities.map((opportunity, index) => {
            const actionState = resolveOpportunityAction(opportunity.id)
            return {
                row_index: index + 1,
                note_id: opportunity.id,
                client_name: opportunity.clientName,
                advisor_name: opportunity.advisorName,
                advisor_store: opportunity.advisorStore,
                vip_label: opportunity.vipLabel,
                tier: opportunity.tier,
                urgency: opportunity.urgencyLabel,
                priority_score: opportunity.priorityScore,
                budget_value: opportunity.budgetValue || '',
                budget_label: opportunity.budgetLabel,
                confidence: opportunity.confidence,
                next_action: opportunity.nextAction,
                action_status: actionState?.status || 'open',
                action_type: actionState?.action_type || actionState?.actionType || '',
                action_label: getOpportunityActionLabel(actionState),
                action_updated_at: actionState?.updated_at || '',
                note_timestamp: opportunity.timestamp || '',
                filter_window: overviewWindow,
                filter_priority: overviewPriority,
                filter_advisor: overviewAdvisor,
                filter_action_status: opportunityStatusFilter,
                filter_search: opportunitySearch || '',
                filter_sort: opportunitySort,
                filter_limit: safeOpportunityLimit
            }
        })
    }

    const resolveFilenameFromDisposition = (contentDisposition, fallbackName) => {
        if (!contentDisposition) return fallbackName
        const utfMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)
        if (utfMatch?.[1]) {
            try {
                return decodeURIComponent(utfMatch[1].trim())
            } catch {
                return utfMatch[1].trim()
            }
        }
        const basicMatch = contentDisposition.match(/filename="?([^\";]+)"?/i)
        if (basicMatch?.[1]) return basicMatch[1].trim()
        return fallbackName
    }

    const handleExportManagerCsv = async () => {
        if (currentTab !== 'overview') {
            setExportError("L'export manager est disponible uniquement dans l'overview.")
            return
        }

        if (!topOpportunities.length) {
            setExportError("Aucune opportunite a exporter avec les filtres actifs.")
            return
        }

        setExportingManager('csv')
        setExportError(null)
        try {
            const params = new URLSearchParams()
            params.set('format', 'csv')
            params.set('window', overviewWindow)
            params.set('priority', overviewPriority)
            params.set('action_status', opportunityStatusFilter)
            params.set('sort', opportunitySort)
            params.set('limit', String(safeOpportunityLimit))

            if (overviewAdvisor && overviewAdvisor !== 'all') {
                params.set('advisor', overviewAdvisor)
            }
            if (opportunitySearch?.trim()) {
                params.set('search', opportunitySearch.trim())
            }
            if (selectedOpportunityIds.length > 0) {
                params.set('note_ids', selectedOpportunityIds.join(','))
            }

            const response = await apiFetch(`/api/dashboard/opportunities/export?${params.toString()}`)
            if (!response.ok) {
                const body = await response.text()
                throw new Error(body || `Erreur export manager (${response.status})`)
            }

            const blob = await response.blob()
            const fallbackName = `manager_opportunities_${formatFileTimestamp()}.csv`
            const filename = resolveFilenameFromDisposition(
                response.headers.get('content-disposition'),
                fallbackName
            )
            const url = URL.createObjectURL(blob)
            const link = document.createElement('a')
            link.href = url
            link.download = filename
            document.body.appendChild(link)
            link.click()
            document.body.removeChild(link)
            URL.revokeObjectURL(url)
        } catch (error) {
            setExportError(error.message || "Erreur lors de l'export CSV manager.")
        } finally {
            setExportingManager(null)
        }
    }

    const handleExportManagerPdf = () => {
        if (currentTab !== 'overview') {
            setExportError("L'export manager est disponible uniquement dans l'overview.")
            return
        }

        const rows = buildOpportunityExportRows()
        if (!rows.length) {
            setExportError("Aucune opportunite a exporter avec les filtres actifs.")
            return
        }

        setExportingManager('pdf')
        setExportError(null)
        try {
            const printWindow = window.open('', '_blank', 'noopener,noreferrer,width=1300,height=900')
            if (!printWindow) {
                throw new Error('Impossible douvrir la fenetre dimpression.')
            }

            const tableRows = rows.map((row) => `
                <tr>
                    <td>${escapeHtml(row.row_index)}</td>
                    <td>${escapeHtml(row.client_name)}</td>
                    <td>${escapeHtml(row.advisor_name)}</td>
                    <td>${escapeHtml(row.vip_label)}</td>
                    <td>${escapeHtml(row.tier)}</td>
                    <td>${escapeHtml(row.urgency)}</td>
                    <td>${escapeHtml(row.priority_score)}</td>
                    <td>${escapeHtml(row.budget_label)}</td>
                    <td>${escapeHtml(row.action_label)}</td>
                    <td>${escapeHtml(row.next_action)}</td>
                </tr>
            `).join('')

            const html = `
                <!doctype html>
                <html>
                <head>
                    <meta charset="utf-8" />
                    <title>Manager Opportunities Export</title>
                    <style>
                        body { font-family: Arial, sans-serif; margin: 24px; color: #111; }
                        h1 { margin: 0 0 6px; font-size: 20px; }
                        .meta { color: #444; font-size: 12px; margin-bottom: 14px; }
                        .filters { color: #444; font-size: 11px; margin-bottom: 14px; }
                        table { width: 100%; border-collapse: collapse; font-size: 11px; }
                        th, td { border: 1px solid #ddd; padding: 6px; text-align: left; vertical-align: top; }
                        th { background: #f6f6f6; }
                    </style>
                </head>
                <body>
                    <h1>LVMH Manager Opportunity Export</h1>
                    <div class="meta">Generated: ${escapeHtml(new Date().toLocaleString('fr-FR'))} | Scope: ${escapeHtml(rows.length)} rows</div>
                    <div class="filters">Filters: ${escapeHtml(managerFilterSummary)}</div>
                    <table>
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>Client</th>
                                <th>Advisor</th>
                                <th>VIP</th>
                                <th>Tier</th>
                                <th>Urgency</th>
                                <th>Priority</th>
                                <th>Budget</th>
                                <th>Action</th>
                                <th>Next Best Action</th>
                            </tr>
                        </thead>
                        <tbody>${tableRows}</tbody>
                    </table>
                </body>
                </html>
            `

            printWindow.document.open()
            printWindow.document.write(html)
            printWindow.document.close()
            printWindow.focus()
            setTimeout(() => {
                try {
                    printWindow.print()
                } finally {
                    printWindow.onafterprint = () => printWindow.close()
                }
            }, 250)
        } catch (error) {
            setExportError(error.message || "Erreur lors de l'export PDF manager.")
        } finally {
            setExportingManager(null)
        }
    }

    const handleLogout = () => {
        logout()
        if (onBack) onBack()
        else window.location.assign('/login')
    }

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
                        <div className={`w-2 h-2 rounded-full ${pipelineSocketState === 'connected' ? 'bg-green-500 animate-pulse' : pipelineSocketState === 'connecting' ? 'bg-lvmh-gold animate-pulse' : 'bg-red-500'}`}></div>
                        {pipelineSocketState === 'connected' ? 'Serveur Live' : pipelineSocketState === 'connecting' ? 'Connexion WS...' : 'WS deconnecte'}
                    </div>
                    <button
                        onClick={handleLogout}
                        className="mt-4 w-full flex items-center gap-3 px-4 py-3 rounded-xl text-red-400 hover:bg-red-500/10 transition-colors"
                    >
                        <LogOut size={18} />
                        <span className="text-sm font-semibold">Deconnexion</span>
                    </button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 overflow-y-auto p-10">
                <div className="flex flex-wrap justify-between items-start gap-4 mb-10">
                    <div>
                        <h2 className="text-3xl font-display font-black mb-1">Boutique Paris Rivoli</h2>
                        <p className="text-lvmh-gray">Pilotage de la performance Client Advisor</p>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                        <div className="flex flex-wrap items-center justify-end gap-2">
                            <button
                                onClick={handleExportManagerCsv}
                                disabled={currentTab !== 'overview' || Boolean(exportingManager)}
                                className="glass flex items-center gap-2 px-4 py-2 hover:bg-white/10 transition-colors uppercase text-[11px] font-bold tracking-widest disabled:opacity-40"
                            >
                                <Download size={14} />
                                {exportingManager === 'csv' ? 'Export CSV...' : 'Export CSV'}
                            </button>
                            <button
                                onClick={handleExportManagerPdf}
                                disabled={currentTab !== 'overview' || Boolean(exportingManager)}
                                className="glass flex items-center gap-2 px-4 py-2 hover:bg-white/10 transition-colors uppercase text-[11px] font-bold tracking-widest disabled:opacity-40"
                            >
                                <FileText size={14} />
                                {exportingManager === 'pdf' ? 'Export PDF...' : 'Export PDF'}
                            </button>
                        </div>
                        <div className="text-[10px] text-lvmh-gray text-right">
                            {currentTab === 'overview'
                                ? `Scope export: ${topOpportunities.length}/${filteredOpportunities.length} priorites visibles | ${managerFilterSummary}`
                                : "Export disponible dans l'overview manager"}
                        </div>
                        {exportError && (
                            <div className="text-[10px] text-red-300 border border-red-500/30 bg-red-500/10 rounded px-2 py-1 max-w-[640px] text-right">
                                {exportError}
                            </div>
                        )}
                    </div>
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
                    <div className="space-y-8 animate-in fade-in duration-500">
                        <div className="glass p-6 border border-white/10">
                            <div className="flex flex-wrap items-start justify-between gap-4">
                                <div>
                                    <div className="text-[10px] uppercase tracking-[0.24em] text-lvmh-gray mb-2">Executive cockpit</div>
                                    <h3 className="text-2xl font-display font-black gold-text">Manager Command Center</h3>
                                    <p className="text-sm text-lvmh-gray mt-1">Pilotage commercial, qualite IA et priorites CRM en un seul ecran.</p>
                                </div>
                                <div className="flex flex-wrap items-center gap-2">
                                    <span className={`text-[11px] px-3 py-2 rounded-full border font-bold ${alertToneClass}`}>
                                        Health {healthScore}/100
                                    </span>
                                    <span className="text-[11px] px-3 py-2 rounded-full border border-white/10 bg-white/5 text-lvmh-gray">
                                        {alerts.length} alertes
                                    </span>
                                    <button
                                        onClick={fetchData}
                                        className="inline-flex items-center gap-2 text-[11px] uppercase tracking-widest px-3 py-2 rounded-full border border-white/10 hover:border-lvmh-gold/40 hover:text-lvmh-gold transition-colors"
                                    >
                                        <RefreshCcw size={12} /> Refresh
                                    </button>
                                </div>
                            </div>

                            {alerts.length > 0 && (
                                <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
                                    {alerts.slice(0, 3).map((alert, index) => (
                                        <div key={`${alert}-${index}`} className="rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-200 flex items-start gap-2">
                                            <AlertTriangle size={14} className="text-red-400 mt-0.5" />
                                            <span>{alert}</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        <div className="glass p-4 flex flex-wrap items-center gap-3">
                            <div className="inline-flex items-center gap-2 text-xs uppercase tracking-widest text-lvmh-gray mr-2">
                                <Filter size={13} /> Filtres
                            </div>

                            <select
                                value={overviewWindow}
                                onChange={(e) => setOverviewWindow(e.target.value)}
                                className="bg-white/5 border border-white/10 rounded-lg py-2 px-3 text-sm text-white focus:ring-1 focus:ring-lvmh-gold"
                            >
                                <option value="today">Aujourd hui</option>
                                <option value="7d">7 jours</option>
                                <option value="30d">30 jours</option>
                                <option value="all">Tout</option>
                            </select>

                            <select
                                value={overviewPriority}
                                onChange={(e) => setOverviewPriority(e.target.value)}
                                className="bg-white/5 border border-white/10 rounded-lg py-2 px-3 text-sm text-white focus:ring-1 focus:ring-lvmh-gold"
                            >
                                <option value="all">Toutes priorites</option>
                                <option value="urgent">Urgent</option>
                                <option value="vip">VIC / VIP</option>
                                <option value="tier3">Tier 3</option>
                            </select>

                            <select
                                value={overviewAdvisor}
                                onChange={(e) => setOverviewAdvisor(e.target.value)}
                                className="bg-white/5 border border-white/10 rounded-lg py-2 px-3 text-sm text-white focus:ring-1 focus:ring-lvmh-gold"
                            >
                                <option value="all">Tous advisors</option>
                                {overviewAdvisorOptions.map((advisorName) => (
                                    <option key={advisorName} value={advisorName}>{advisorName}</option>
                                ))}
                            </select>

                            <select
                                value={opportunityStatusFilter}
                                onChange={(e) => setOpportunityStatusFilter(e.target.value)}
                                className="bg-white/5 border border-white/10 rounded-lg py-2 px-3 text-sm text-white focus:ring-1 focus:ring-lvmh-gold"
                            >
                                <option value="all">Actions: toutes</option>
                                <option value="open">Actions: ouvertes</option>
                                <option value="planned">Actions: planifiees</option>
                                <option value="done">Actions: finalisees</option>
                            </select>

                            <div className="relative min-w-[220px]">
                                <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-lvmh-gray pointer-events-none" />
                                <input
                                    type="text"
                                    value={opportunitySearch}
                                    onChange={(e) => setOpportunitySearch(e.target.value)}
                                    placeholder="Recherche opportunites..."
                                    className="w-full bg-white/5 border border-white/10 rounded-lg py-2 pl-9 pr-3 text-sm text-white placeholder:text-lvmh-gray focus:ring-1 focus:ring-lvmh-gold"
                                />
                            </div>

                            <select
                                value={opportunitySort}
                                onChange={(e) => setOpportunitySort(e.target.value)}
                                className="bg-white/5 border border-white/10 rounded-lg py-2 px-3 text-sm text-white focus:ring-1 focus:ring-lvmh-gold"
                            >
                                <option value="priority">Tri: priorite</option>
                                <option value="urgency">Tri: urgence</option>
                                <option value="budget">Tri: budget</option>
                                <option value="recent">Tri: recence</option>
                            </select>

                            <select
                                value={String(opportunityLimit)}
                                onChange={(e) => setOpportunityLimit(Number(e.target.value))}
                                className="bg-white/5 border border-white/10 rounded-lg py-2 px-3 text-sm text-white focus:ring-1 focus:ring-lvmh-gold"
                            >
                                <option value="10">Top 10</option>
                                <option value="20">Top 20</option>
                                <option value="50">Top 50</option>
                            </select>

                            <div className="ml-auto text-xs text-lvmh-gray">
                                Scope: {overviewScopedRecordings.length} notes
                                {windowDays ? ` | Periode precedente: ${previousWindowScopedRecordings.length}` : ''}
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                            <KPICard
                                title="Volume traite"
                                value={currentWindowKpis.total}
                                trend={volumeDeltaLabel}
                                subtitle={`Fenetre active: ${overviewWindow} | Global: ${totalProcessed}`}
                            />
                            <KPICard
                                title="Confiance moyenne"
                                value={`${Math.round(currentWindowKpis.avgConfidencePct || 0)}%`}
                                trend={confidenceDeltaLabel}
                                subtitle={`Qualite IA globale: ${Math.round(avgQuality || 0)}%`}
                                gold
                            />
                            <KPICard
                                title="Part VIC"
                                value={`${Math.round(currentWindowKpis.vipShare)}%`}
                                trend={vipDeltaLabel}
                                subtitle={`${vipCountScoped} clients VIC dans la fenetre`}
                            />
                            <KPICard
                                title="Actions urgentes"
                                value={currentWindowKpis.urgentCount}
                                trend={urgentDeltaLabel}
                                subtitle={`Tier 3 detectes: ${tier3Alerts} | Potentiel: ${formatCurrency(opportunityBudgetTotal)}`}
                                red={urgentActionsCount > 0}
                                trendTone={currentWindowKpis.urgentCount > (previousWindowKpis?.urgentCount || 0) ? 'negative' : 'positive'}
                            />
                        </div>

                        <div className="glass p-6">
                            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                                <h3 className="text-lg font-bold flex items-center gap-2">
                                    <Users size={18} className="text-lvmh-gold" /> Segments comportementaux (notes)
                                </h3>
                                <span className="text-xs text-lvmh-gray">
                                    {segmentsLoading ? 'Calcul en cours...' : `${segmentsData?.total_notes || 0} notes | ${segmentRows.length} segments`}
                                </span>
                            </div>
                            {segmentsError && (
                                <div className="mb-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                                    {segmentsError}
                                </div>
                            )}
                            <div className="overflow-x-auto">
                                <table className="w-full text-left">
                                    <thead className="text-lvmh-gray text-[11px] uppercase tracking-widest border-b border-white/10">
                                        <tr>
                                            <th className="pb-3">Segment</th>
                                            <th className="pb-3 text-right">Notes</th>
                                            <th className="pb-3 text-right">Budget moyen</th>
                                            <th className="pb-3 text-right">Tier 3</th>
                                            <th className="pb-3 text-right">VIP</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5">
                                        {segmentRows.slice(0, 5).map((segment) => (
                                            <tr key={`segment-${segment.segment_id}`} className="hover:bg-white/5 transition-colors">
                                                <td className="py-3 text-sm font-semibold">{segment.segment_label}</td>
                                                <td className="py-3 text-sm text-right text-white">{segment.count}</td>
                                                <td className="py-3 text-sm text-right text-lvmh-gold">{formatCurrency(segment.avg_budget || 0)}</td>
                                                <td className="py-3 text-sm text-right text-red-300">{Math.round(segment.tier3_share_pct || 0)}%</td>
                                                <td className="py-3 text-sm text-right text-lvmh-gray">{Math.round(segment.vip_share_pct || 0)}%</td>
                                            </tr>
                                        ))}
                                        {!segmentsLoading && segmentRows.length === 0 && (
                                            <tr>
                                                <td colSpan={5} className="py-6 text-sm text-lvmh-gray text-center">
                                                    Aucun segment disponible pour cette fenetre.
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 xl:grid-cols-[0.95fr_1.05fr] gap-6">
                            <div className="glass p-6">
                                <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                                    <h3 className="text-lg font-bold flex items-center gap-2">
                                        <BellRing size={18} className="text-lvmh-gold" /> Alert Center Live
                                    </h3>
                                    <div className="flex items-center gap-2">
                                        <span className={`text-[10px] px-2 py-1 rounded-full border inline-flex items-center gap-1 ${pipelineSocketState === 'connected' ? 'border-green-500/40 text-green-400 bg-green-500/10' : pipelineSocketState === 'connecting' ? 'border-lvmh-gold/40 text-lvmh-gold bg-lvmh-gold/10' : 'border-red-500/40 text-red-400 bg-red-500/10'}`}>
                                            {pipelineSocketState === 'connected' ? <Wifi size={11} /> : <WifiOff size={11} />}
                                            {pipelineSocketState === 'connected' ? 'WS LIVE' : pipelineSocketState === 'connecting' ? 'WS CONNECT' : 'WS OFF'}
                                        </span>
                                        <button
                                            onClick={() => setLiveAlerts([])}
                                            className="text-[10px] uppercase tracking-widest px-2 py-1 rounded-full border border-white/10 hover:border-white/30 transition-colors"
                                        >
                                            Clear
                                        </button>
                                    </div>
                                </div>

                                <div className="grid grid-cols-3 gap-2 mb-4">
                                    <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-2 text-center">
                                        <div className="text-[10px] uppercase tracking-widest text-red-300">Critical</div>
                                        <div className="font-bold text-red-300">{liveAlertsCritical}</div>
                                    </div>
                                    <div className="bg-lvmh-gold/10 border border-lvmh-gold/20 rounded-lg p-2 text-center">
                                        <div className="text-[10px] uppercase tracking-widest text-lvmh-gold">Warning</div>
                                        <div className="font-bold text-lvmh-gold">{liveAlertsWarning}</div>
                                    </div>
                                    <div className="bg-white/5 border border-white/10 rounded-lg p-2 text-center">
                                        <div className="text-[10px] uppercase tracking-widest text-lvmh-gray">Info</div>
                                        <div className="font-bold text-white">{liveAlertsInfo}</div>
                                    </div>
                                </div>

                                <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
                                    {liveAlerts.length > 0 ? liveAlerts.slice(0, 10).map((item, index) => (
                                        <div
                                            key={`${item.timestamp}-${index}`}
                                            className={`rounded-lg p-3 border ${item.severity === 'critical' ? 'border-red-500/30 bg-red-500/10' : item.severity === 'warning' ? 'border-lvmh-gold/30 bg-lvmh-gold/10' : 'border-white/10 bg-white/[0.03]'}`}
                                        >
                                            <div className="flex items-center justify-between gap-2">
                                                <div className={`text-xs font-semibold ${item.severity === 'critical' ? 'text-red-300' : item.severity === 'warning' ? 'text-lvmh-gold' : 'text-white'}`}>
                                                    {item.title}
                                                </div>
                                                <div className="text-[10px] text-lvmh-gray">{formatDateTime(item.timestamp)}</div>
                                            </div>
                                            <div className="text-xs text-lvmh-gray mt-1">{item.message}</div>
                                        </div>
                                    )) : (
                                        <div className="rounded-lg border border-white/10 bg-white/[0.02] p-4 text-sm text-lvmh-gray">
                                            Aucun evenement live pour le moment.
                                        </div>
                                    )}
                                </div>
                            </div>

                            <div className="glass p-6">
                                <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                                    <h3 className="text-lg font-bold flex items-center gap-2">
                                        <UserRound size={18} className="text-lvmh-gold" /> Drill-down Advisor
                                    </h3>
                                    <span className="text-xs text-lvmh-gray">{filteredDrilldownRows.length} profils</span>
                                </div>

                                <div className="flex flex-wrap gap-2 mb-4">
                                    <select
                                        value={drilldownStore}
                                        onChange={(e) => setDrilldownStore(e.target.value)}
                                        className="bg-white/5 border border-white/10 rounded-lg py-2 px-3 text-sm text-white focus:ring-1 focus:ring-lvmh-gold"
                                    >
                                        <option value="all">Tous stores</option>
                                        {storeOptions.map((store) => (
                                            <option key={store} value={store}>{store}</option>
                                        ))}
                                    </select>
                                    <select
                                        value={drilldownAdvisor}
                                        onChange={(e) => setDrilldownAdvisor(e.target.value)}
                                        className="bg-white/5 border border-white/10 rounded-lg py-2 px-3 text-sm text-white focus:ring-1 focus:ring-lvmh-gold"
                                    >
                                        <option value="all">Tous advisors</option>
                                        {overviewAdvisorOptions.map((advisorName) => (
                                            <option key={advisorName} value={advisorName}>{advisorName}</option>
                                        ))}
                                    </select>
                                    <button
                                        onClick={() => setFocusMetric((prev) => prev === 'volume' ? 'priority' : 'volume')}
                                        className="text-[10px] uppercase tracking-widest px-3 py-2 rounded-lg border border-white/10 hover:border-lvmh-gold/40 hover:text-lvmh-gold transition-colors"
                                    >
                                        Focus: {focusMetric}
                                    </button>
                                </div>

                                <div className="overflow-x-auto">
                                    <table className="w-full text-left">
                                        <thead className="text-lvmh-gray text-[11px] uppercase tracking-widest border-b border-white/10">
                                            <tr>
                                                <th className="pb-3">Advisor</th>
                                                <th className="pb-3">Store</th>
                                                <th className="pb-3 text-right">Urgent</th>
                                                <th className="pb-3 text-right">{focusMetric === 'priority' ? 'Priority' : 'Notes'}</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-white/5">
                                            {filteredDrilldownRows.slice(0, 8).map((row, index) => (
                                                <tr
                                                    key={`${row.advisorName}-${row.advisorStore}-${index}`}
                                                    className="hover:bg-white/5 cursor-pointer transition-colors"
                                                    onClick={() => {
                                                        setDrilldownAdvisor(row.advisorName)
                                                        setDrilldownStore(row.advisorStore)
                                                        setOverviewAdvisor(row.advisorName)
                                                    }}
                                                >
                                                    <td className="py-3 font-semibold">{row.advisorName}</td>
                                                    <td className="py-3 text-sm text-lvmh-gray">{row.advisorStore}</td>
                                                    <td className="py-3 text-right text-sm text-red-300">{row.urgent}</td>
                                                    <td className="py-3 text-right font-black text-lvmh-gold">{focusMetric === 'priority' ? row.priorityIndex : row.notes}</td>
                                                </tr>
                                            ))}
                                            {filteredDrilldownRows.length === 0 && (
                                                <tr>
                                                    <td colSpan={4} className="py-6 text-sm text-lvmh-gray text-center">Aucune donnee pour ce drill-down</td>
                                                </tr>
                                            )}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 xl:grid-cols-[1.05fr_0.95fr] gap-6">
                            <div className="glass p-6">
                                <div className="flex items-center justify-between mb-4">
                                    <h3 className="text-lg font-bold flex items-center gap-2">
                                        <Trophy size={18} className="text-lvmh-gold" /> Advisor Pulse
                                    </h3>
                                    <span className="text-xs text-lvmh-gray">Top score: {topAdvisorScore} pts</span>
                                </div>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-left">
                                        <thead className="text-lvmh-gray text-[11px] uppercase tracking-widest border-b border-white/10">
                                            <tr>
                                                <th className="pb-3">Advisor</th>
                                                <th className="pb-3">Notes</th>
                                                <th className="pb-3 text-right">Score</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-white/5">
                                            {(leaderboard || []).slice(0, 8).map((advisor, index) => (
                                                <tr key={`${advisor.id}-${index}`} className="hover:bg-white/5 transition-colors">
                                                    <td className="py-3 font-semibold">{advisor.id}</td>
                                                    <td className="py-3 text-sm text-lvmh-gray">{advisor.notes} notes</td>
                                                    <td className="py-3 text-right font-black text-lvmh-gold">{advisor.score} pts</td>
                                                </tr>
                                            ))}
                                            {(!leaderboard || leaderboard.length === 0) && (
                                                <tr>
                                                    <td colSpan={3} className="py-6 text-sm text-lvmh-gray text-center">Aucune donnee advisor disponible</td>
                                                </tr>
                                            )}
                                        </tbody>
                                    </table>
                                </div>
                            </div>

                            <div className="glass p-6">
                                <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                                    <Activity size={18} className="text-lvmh-gold" /> Tier Mix
                                </h3>
                                <div className="h-[260px]">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <PieChart>
                                            <Pie
                                                data={chartData}
                                                innerRadius={70}
                                                outerRadius={105}
                                                paddingAngle={4}
                                                dataKey="value"
                                            >
                                                {chartData.map((entry, index) => (
                                                    <Cell key={`tier-cell-${index}`} fill={entry.color} />
                                                ))}
                                            </Pie>
                                            <Tooltip contentStyle={{ backgroundColor: '#1A1A1A', border: '1px solid #333', borderRadius: '8px' }} />
                                            <Legend />
                                        </PieChart>
                                    </ResponsiveContainer>
                                </div>
                                <div className="mt-4 grid grid-cols-3 gap-3 text-center">
                                    <div className="bg-white/5 border border-white/5 rounded-lg p-3">
                                        <div className="text-[10px] uppercase tracking-widest text-lvmh-gray">T1</div>
                                        <div className="font-bold">{chartData[0]?.value || 0}</div>
                                    </div>
                                    <div className="bg-white/5 border border-white/5 rounded-lg p-3">
                                        <div className="text-[10px] uppercase tracking-widest text-lvmh-gray">T2</div>
                                        <div className="font-bold text-lvmh-gold">{chartData[1]?.value || 0}</div>
                                    </div>
                                    <div className="bg-white/5 border border-white/5 rounded-lg p-3">
                                        <div className="text-[10px] uppercase tracking-widest text-lvmh-gray">T3</div>
                                        <div className="font-bold text-red-400">{chartData[2]?.value || 0}</div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 xl:grid-cols-[1.1fr_0.9fr] gap-6">
                            <div className="glass p-6">
                                <div className="flex items-center justify-between gap-3 mb-4">
                                    <h3 className="text-lg font-bold flex items-center gap-2">
                                        <Building2 size={18} className="text-lvmh-gold" /> Focus Advisor
                                    </h3>
                                    <span className="text-xs text-lvmh-gray">{selectedAdvisorLabel}</span>
                                </div>

                                {selectedDrilldownRow ? (
                                    <>
                                        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                                            <div className="bg-white/5 border border-white/10 rounded-lg p-3">
                                                <div className="text-[10px] uppercase tracking-widest text-lvmh-gray">Store</div>
                                                <div className="font-semibold mt-1">{selectedDrilldownRow.advisorStore}</div>
                                            </div>
                                            <div className="bg-white/5 border border-white/10 rounded-lg p-3">
                                                <div className="text-[10px] uppercase tracking-widest text-lvmh-gray">Notes</div>
                                                <div className="font-semibold mt-1">{selectedDrilldownRow.notes}</div>
                                            </div>
                                            <div className="bg-white/5 border border-white/10 rounded-lg p-3">
                                                <div className="text-[10px] uppercase tracking-widest text-lvmh-gray">Tier 3</div>
                                                <div className="font-semibold mt-1 text-red-300">{selectedDrilldownRow.tier3}</div>
                                            </div>
                                            <div className="bg-white/5 border border-white/10 rounded-lg p-3">
                                                <div className="text-[10px] uppercase tracking-widest text-lvmh-gray">Urgent</div>
                                                <div className="font-semibold mt-1 text-red-300">{selectedDrilldownRow.urgent}</div>
                                            </div>
                                            <div className="bg-white/5 border border-white/10 rounded-lg p-3">
                                                <div className="text-[10px] uppercase tracking-widest text-lvmh-gray">Conf. moy.</div>
                                                <div className="font-semibold mt-1">{formatPercent(selectedDrilldownRow.avgConfidence)}</div>
                                            </div>
                                        </div>

                                        <div className="mt-4 text-xs text-lvmh-gray">
                                            Potentiel budget cumule: <span className="text-lvmh-gold font-bold">{formatCurrency(selectedDrilldownRow.budgetTotal)}</span>
                                        </div>
                                    </>
                                ) : (
                                    <div className="text-sm text-lvmh-gray border border-white/10 rounded-lg p-4 bg-white/[0.02]">
                                        Selectionnez un advisor dans le drill-down pour afficher son detail.
                                    </div>
                                )}
                            </div>

                            <div className="glass p-6">
                                <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                                    <Clock3 size={18} className="text-lvmh-gold" /> Dernieres notes du focus
                                </h3>
                                {selectedAdvisorRecentNotes.length > 0 ? (
                                    <div className="space-y-3 max-h-[320px] overflow-y-auto pr-1">
                                        {selectedAdvisorRecentNotes.map((note) => (
                                            <button
                                                key={`focus-note-${note.id}`}
                                                onClick={() => {
                                                    setCurrentTab('recordings')
                                                    setRecordingsSearch(note?.client?.name || '')
                                                    setRecordingsPage(1)
                                                    setSelectedRecording(null)
                                                }}
                                                className="w-full text-left border border-white/10 rounded-lg p-3 bg-white/[0.03] hover:bg-white/[0.06] transition-colors"
                                            >
                                                <div className="flex items-center justify-between gap-2">
                                                    <div className="text-sm font-semibold">{note?.client?.name || 'Client inconnu'}</div>
                                                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/10 text-lvmh-gray">T{note?.tier || 1}</span>
                                                </div>
                                                <div className="text-xs text-lvmh-gray mt-1">{formatDateTime(note?.timestamp)}</div>
                                                <div className="text-xs text-lvmh-gray mt-2 line-clamp-2">{note?.transcription || '-'}</div>
                                            </button>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="text-sm text-lvmh-gray border border-white/10 rounded-lg p-4 bg-white/[0.02]">
                                        Aucune note recente disponible pour ce focus.
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="glass p-6">
                            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                                <h3 className="text-lg font-bold flex items-center gap-2">
                                    <BriefcaseBusiness size={18} className="text-lvmh-gold" /> Opportunity Board
                                </h3>
                                <div className="flex flex-wrap items-center gap-2 text-xs">
                                    <span className="text-lvmh-gray">
                                        {topOpportunities.length}/{filteredOpportunities.length} priorites visibles
                                    </span>
                                    <span className={`px-2 py-1 rounded-full border ${selectedOpportunitiesCount > 0 ? 'border-lvmh-gold/40 bg-lvmh-gold/10 text-lvmh-gold' : 'border-white/10 bg-white/5 text-lvmh-gray'}`}>
                                        Selection: {selectedOpportunitiesCount}
                                    </span>
                                    <button
                                        onClick={() => setOpportunityStatusFilter('open')}
                                        className={`px-2 py-1 rounded-full border transition-colors ${opportunityStatusFilter === 'open'
                                            ? 'border-lvmh-gold/40 bg-lvmh-gold/10 text-lvmh-gold'
                                            : 'border-white/10 bg-white/5 text-lvmh-gray hover:border-white/30'
                                            }`}
                                    >
                                        Queue: {opportunityActionsOpen}
                                    </button>
                                    <button
                                        onClick={() => setOpportunityStatusFilter('planned')}
                                        className={`px-2 py-1 rounded-full border transition-colors ${opportunityStatusFilter === 'planned'
                                            ? 'border-lvmh-gold/40 bg-lvmh-gold/10 text-lvmh-gold'
                                            : 'border-white/10 bg-white/5 text-lvmh-gray hover:border-white/30'
                                            }`}
                                    >
                                        Calls: {opportunityCallPlanned}
                                    </button>
                                    <span className="px-2 py-1 rounded-full border border-white/10 bg-white/5 text-lvmh-gray">
                                        Rappels: {opportunitySchedulePlanned}
                                    </span>
                                    <button
                                        onClick={() => setOpportunityStatusFilter('done')}
                                        className={`px-2 py-1 rounded-full border transition-colors ${opportunityStatusFilter === 'done'
                                            ? 'border-green-500/40 bg-green-500/15 text-green-300'
                                            : 'border-green-500/30 bg-green-500/10 text-green-300 hover:border-green-400/50'
                                            }`}
                                    >
                                        Done: {opportunityActionsDone}
                                    </button>
                                    <button
                                        onClick={() => setOpportunityStatusFilter('all')}
                                        className={`px-2 py-1 rounded-full border transition-colors ${opportunityStatusFilter === 'all'
                                            ? 'border-white/40 bg-white/10 text-white'
                                            : 'border-white/10 bg-white/5 text-lvmh-gray hover:border-white/30'
                                            }`}
                                    >
                                        Reset
                                    </button>
                                    <button
                                        onClick={toggleSelectVisibleOpportunities}
                                        className="px-2 py-1 rounded-full border border-white/20 bg-white/5 text-lvmh-gray hover:border-white/35 hover:text-white transition-colors"
                                    >
                                        {allVisibleOpportunitiesSelected ? 'Deselectionner visibles' : 'Selectionner visibles'}
                                    </button>
                                    <button
                                        onClick={() => setSelectedOpportunityIds([])}
                                        disabled={selectedOpportunitiesCount === 0}
                                        className="px-2 py-1 rounded-full border border-white/10 bg-white/5 text-lvmh-gray hover:border-white/30 transition-colors disabled:opacity-40"
                                    >
                                        Vider
                                    </button>
                                    <button
                                        onClick={() => handleBulkOpportunityAction('call')}
                                        disabled={selectedOpportunitiesCount === 0 || bulkActionSubmitting}
                                        className="px-2 py-1 rounded-full border border-white/20 bg-white/5 text-white hover:border-green-500/40 hover:text-green-300 transition-colors disabled:opacity-40"
                                    >
                                        Bulk appeler
                                    </button>
                                    <button
                                        onClick={() => handleBulkOpportunityAction('schedule')}
                                        disabled={selectedOpportunitiesCount === 0 || bulkActionSubmitting}
                                        className="px-2 py-1 rounded-full border border-white/20 bg-white/5 text-white hover:border-lvmh-gold/40 hover:text-lvmh-gold transition-colors disabled:opacity-40"
                                    >
                                        Bulk planifier
                                    </button>
                                    <button
                                        onClick={() => handleBulkOpportunityAction('done')}
                                        disabled={selectedOpportunitiesCount === 0 || bulkActionSubmitting}
                                        className="px-2 py-1 rounded-full border border-green-500/30 bg-green-500/10 text-green-300 hover:border-green-400/50 transition-colors disabled:opacity-40"
                                    >
                                        Bulk fait
                                    </button>
                                </div>
                            </div>

                            {actionsError && (
                                <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-200 mb-3">
                                    {actionsError}
                                </div>
                            )}
                            {actionsLoading && (
                                <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3 text-xs text-lvmh-gray mb-3">
                                    Synchronisation des actions manager...
                                </div>
                            )}
                            {bulkActionSubmitting && (
                                <div className="rounded-lg border border-lvmh-gold/30 bg-lvmh-gold/10 p-3 text-xs text-lvmh-gold mb-3">
                                    Application des actions bulk en cours...
                                </div>
                            )}

                            {topOpportunities.length > 0 ? (
                                <div className="space-y-3">
                                    {topOpportunities.map((opportunity) => {
                                        const actionState = resolveOpportunityAction(opportunity.id)
                                        const actionLabel = getOpportunityActionLabel(actionState)
                                        const isSelected = selectedOpportunityIdSet.has(Number(opportunity.id))
                                        return (
                                        <div key={opportunity.id} className="border border-white/10 rounded-xl p-4 bg-white/[0.03] hover:bg-white/[0.06] transition-colors">
                                            <div className="flex flex-wrap items-start justify-between gap-3">
                                                <div>
                                                    <div className="flex flex-wrap items-center gap-2">
                                                        <label className="inline-flex items-center gap-2 text-[10px] uppercase tracking-widest text-lvmh-gray mr-1 cursor-pointer">
                                                            <input
                                                                type="checkbox"
                                                                checked={isSelected}
                                                                onChange={() => toggleOpportunitySelection(opportunity.id)}
                                                                className="h-3.5 w-3.5 rounded border-white/20 bg-transparent text-lvmh-gold focus:ring-lvmh-gold"
                                                            />
                                                            Sel
                                                        </label>
                                                        <span className="font-semibold text-white">{opportunity.clientName}</span>
                                                        <span className={`text-[10px] px-2 py-0.5 rounded-full border ${opportunity.urgencyLevel === 3 ? 'border-red-500/40 bg-red-500/15 text-red-300' : opportunity.urgencyLevel === 2 ? 'border-lvmh-gold/40 bg-lvmh-gold/10 text-lvmh-gold' : 'border-white/15 bg-white/5 text-lvmh-gray'}`}>
                                                            {opportunity.urgencyLabel}
                                                        </span>
                                                        <span className={`text-[10px] px-2 py-0.5 rounded-full ${opportunity.isVip ? 'bg-lvmh-gold/20 text-lvmh-gold' : 'bg-white/10 text-lvmh-gray'}`}>
                                                            {opportunity.vipLabel}
                                                        </span>
                                                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/10 text-lvmh-gray">T{opportunity.tier}</span>
                                                    </div>

                                                    <p className="text-sm text-lvmh-gray mt-2 max-w-3xl">{opportunity.nextAction}</p>

                                                    <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-lvmh-gray">
                                                        <span className="inline-flex items-center gap-1"><Clock3 size={12} /> {formatDateTime(opportunity.timestamp)}</span>
                                                        <span>Advisor: {opportunity.advisorName}</span>
                                                        <span>Budget: {opportunity.budgetLabel}</span>
                                                        <span>Confiance: {opportunity.confidence}</span>
                                                        <span>Priorite: {opportunity.priorityScore}</span>
                                                    </div>
                                                </div>

                                                <div className="flex flex-col items-end gap-2">
                                                    <span className={`text-[10px] px-2 py-1 rounded-full border ${actionState?.status === 'done' ? 'border-green-500/30 bg-green-500/10 text-green-300' : actionState?.status === 'planned' ? 'border-lvmh-gold/30 bg-lvmh-gold/10 text-lvmh-gold' : actionState ? 'border-white/30 bg-white/10 text-white' : 'border-white/10 bg-white/5 text-lvmh-gray'}`}>
                                                        {actionLabel}
                                                    </span>
                                                    {actionState?.updated_at && (
                                                        <span className="text-[10px] text-lvmh-gray">
                                                            Maj: {formatDateTime(actionState.updated_at)}
                                                        </span>
                                                    )}
                                                    <div className="flex flex-wrap justify-end items-center gap-2">
                                                        <button
                                                            onClick={() => setSelectedOpportunityId(opportunity.id)}
                                                            className="text-[10px] uppercase tracking-widest px-3 py-2 rounded-lg border border-white/20 text-white hover:border-lvmh-gold/40 hover:text-lvmh-gold transition-colors"
                                                        >
                                                            Details
                                                        </button>
                                                        <button
                                                            onClick={() => {
                                                                setCurrentTab('recordings')
                                                                setRecordingsSearch(opportunity.clientName)
                                                                setRecordingsPage(1)
                                                                setSelectedRecording(null)
                                                            }}
                                                            className="text-[10px] uppercase tracking-widest px-3 py-2 rounded-lg border border-lvmh-gold/40 text-lvmh-gold hover:bg-lvmh-gold/10 transition-colors"
                                                        >
                                                            Ouvrir
                                                        </button>
                                                        <button
                                                            onClick={() => setOverviewAdvisor(opportunity.advisorName)}
                                                            className="text-[10px] uppercase tracking-widest px-3 py-2 rounded-lg border border-white/10 text-white hover:border-white/30 transition-colors"
                                                        >
                                                            Assigner
                                                        </button>
                                                        <button
                                                            onClick={() => handleOpportunityAction(opportunity, 'call')}
                                                            disabled={actionSubmittingId === opportunity.id || bulkActionSubmitting}
                                                            className="text-[10px] uppercase tracking-widest px-3 py-2 rounded-lg border border-white/10 text-white hover:border-green-500/40 hover:text-green-300 transition-colors disabled:opacity-50"
                                                        >
                                                            Appeler
                                                        </button>
                                                        <button
                                                            onClick={() => handleOpportunityAction(opportunity, 'schedule')}
                                                            disabled={actionSubmittingId === opportunity.id || bulkActionSubmitting}
                                                            className="text-[10px] uppercase tracking-widest px-3 py-2 rounded-lg border border-white/10 text-white hover:border-lvmh-gold/40 hover:text-lvmh-gold transition-colors disabled:opacity-50"
                                                        >
                                                            Planifier
                                                        </button>
                                                        <button
                                                            onClick={() => handleOpportunityAction(opportunity, 'done')}
                                                            disabled={actionSubmittingId === opportunity.id || bulkActionSubmitting}
                                                            className="text-[10px] uppercase tracking-widest px-3 py-2 rounded-lg border border-green-500/40 text-green-300 hover:bg-green-500/10 transition-colors disabled:opacity-50"
                                                        >
                                                            Fait
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    )})}
                                </div>
                            ) : (
                                <div className="text-sm text-lvmh-gray border border-white/10 rounded-xl p-5 bg-white/[0.02]">
                                    Aucune opportunite pour les filtres actifs. Elargissez la fenetre, retirez un filtre action, ou videz la recherche.
                                </div>
                            )}
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
                    <Suspense fallback={<div className="glass p-6 text-sm text-lvmh-gray">Chargement module debug...</div>}>
                        <DebugAnalyzer />
                    </Suspense>
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

                {currentTab === 'overview' && selectedOpportunityRecord && (
                    <div
                        className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm p-4 md:p-8"
                        onClick={() => setSelectedOpportunityId(null)}
                    >
                        <div
                            className="mx-auto h-full max-w-6xl rounded-2xl border border-white/10 bg-lvmh-black shadow-2xl flex flex-col overflow-hidden"
                            onClick={(event) => event.stopPropagation()}
                        >
                            <div className="flex items-start justify-between gap-4 p-5 border-b border-white/10 bg-white/[0.02]">
                                <div>
                                    <div className="text-[10px] uppercase tracking-[0.24em] text-lvmh-gray mb-2">Opportunity Detail</div>
                                    <h4 className="text-2xl font-display font-black text-white">
                                        {selectedOpportunityRecord?.client?.name || 'Client inconnu'}
                                    </h4>
                                    <div className="mt-3 flex flex-wrap items-center gap-2 text-[10px]">
                                        <span className={`px-2 py-1 rounded-full border ${selectedOpportunityUrgency.level === 3 ? 'border-red-500/40 bg-red-500/15 text-red-300' : selectedOpportunityUrgency.level === 2 ? 'border-lvmh-gold/40 bg-lvmh-gold/10 text-lvmh-gold' : 'border-white/20 bg-white/10 text-lvmh-gray'}`}>
                                            Urgence: {selectedOpportunityUrgency.label}
                                        </span>
                                        <span className={`px-2 py-1 rounded-full ${selectedOpportunityRecord?.client?.vic_status && selectedOpportunityRecord.client.vic_status !== 'Standard' ? 'bg-lvmh-gold/20 text-lvmh-gold' : 'bg-white/10 text-lvmh-gray'}`}>
                                            {selectedOpportunityRecord?.client?.vic_status || 'Standard'}
                                        </span>
                                        <span className="px-2 py-1 rounded-full bg-white/10 text-lvmh-gray">
                                            Tier {selectedOpportunityRecord?.tier || 1}
                                        </span>
                                        <span className={`px-2 py-1 rounded-full border ${selectedOpportunityActionState?.status === 'done' ? 'border-green-500/40 bg-green-500/15 text-green-300' : selectedOpportunityActionState?.status === 'planned' ? 'border-lvmh-gold/40 bg-lvmh-gold/10 text-lvmh-gold' : 'border-white/20 bg-white/10 text-lvmh-gray'}`}>
                                            {selectedOpportunityActionLabel}
                                        </span>
                                    </div>
                                </div>
                                <button
                                    onClick={() => setSelectedOpportunityId(null)}
                                    className="h-10 w-10 rounded-lg border border-white/10 bg-white/5 text-lvmh-gray hover:text-white hover:border-white/30 transition-colors inline-flex items-center justify-center"
                                >
                                    <X size={16} />
                                </button>
                            </div>

                            <div className="flex-1 overflow-y-auto p-5 md:p-6 space-y-5">
                                <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_0.8fr] gap-5">
                                    <div className="space-y-5">
                                        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
                                            <div className="text-[10px] uppercase tracking-[0.18em] text-lvmh-gray mb-2">Next Best Action</div>
                                            <p className="text-sm text-white leading-relaxed">
                                                {selectedOpportunityNba?.description || selectedOpportunityP4?.next_step || 'Relance manager recommandee pour qualification commerciale.'}
                                            </p>
                                            {Array.isArray(selectedOpportunityNba?.target_products) && selectedOpportunityNba.target_products.length > 0 && (
                                                <div className="mt-4 flex flex-wrap gap-2">
                                                    {selectedOpportunityNba.target_products.slice(0, 8).map((product, index) => (
                                                        <span key={`nba-target-${index}`} className="text-[10px] px-2 py-1 rounded-full border border-lvmh-gold/30 bg-lvmh-gold/10 text-lvmh-gold">
                                                            {product}
                                                        </span>
                                                    ))}
                                                </div>
                                            )}
                                        </div>

                                        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
                                            <div className="text-[10px] uppercase tracking-[0.18em] text-lvmh-gray mb-2">Transcription</div>
                                            <p className="text-sm text-lvmh-gray leading-relaxed">
                                                {selectedOpportunityRecord?.transcription || 'Aucune transcription disponible.'}
                                            </p>
                                        </div>
                                    </div>

                                    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
                                        <div className="text-[10px] uppercase tracking-[0.18em] text-lvmh-gray mb-3">Contexte operationnel</div>
                                        <div className="space-y-2 text-sm">
                                            <div className="flex items-center justify-between gap-3">
                                                <span className="text-lvmh-gray">Advisor</span>
                                                <span className="text-white font-medium">{selectedOpportunityRecord?.advisor?.name || 'Inconnu'}</span>
                                            </div>
                                            <div className="flex items-center justify-between gap-3">
                                                <span className="text-lvmh-gray">Store</span>
                                                <span className="text-white font-medium">{selectedOpportunityRecord?.advisor?.store || 'N/A'}</span>
                                            </div>
                                            <div className="flex items-center justify-between gap-3">
                                                <span className="text-lvmh-gray">Date</span>
                                                <span className="text-white font-medium">{formatDateTime(selectedOpportunityRecord?.timestamp)}</span>
                                            </div>
                                            <div className="flex items-center justify-between gap-3">
                                                <span className="text-lvmh-gray">Confiance</span>
                                                <span className="text-white font-medium">{formatPercent(selectedOpportunityRecord?.confidence || 0)}</span>
                                            </div>
                                            <div className="flex items-center justify-between gap-3">
                                                <span className="text-lvmh-gray">Budget potentiel</span>
                                                <span className="text-lvmh-gold font-medium">
                                                    {selectedOpportunityBudget ? formatCurrency(selectedOpportunityBudget) : (selectedOpportunityP4?.budget_potential || '-')}
                                                </span>
                                            </div>
                                            <div className="flex items-center justify-between gap-3">
                                                <span className="text-lvmh-gray">Risque churn</span>
                                                <span className={`${selectedOpportunityChurn >= 0.7 ? 'text-red-300' : selectedOpportunityChurn >= 0.4 ? 'text-lvmh-gold' : 'text-white'} font-medium`}>
                                                    {selectedOpportunityP4?.churn_level ? `${selectedOpportunityP4.churn_level.toUpperCase()} (${Math.round(selectedOpportunityChurn * 100)}%)` : '-'}
                                                </span>
                                            </div>
                                            <div className="flex items-center justify-between gap-3">
                                                <span className="text-lvmh-gray">CLV estimé</span>
                                                <span className="text-white font-medium">
                                                    {selectedOpportunityClv ? `${formatCurrency(selectedOpportunityClv)} (${selectedOpportunityP4?.clv_tier || 'n/a'})` : '-'}
                                                </span>
                                            </div>
                                            <div className="flex items-center justify-between gap-3">
                                                <span className="text-lvmh-gray">Source prediction</span>
                                                <span className="text-lvmh-gray font-medium">{selectedOpportunityPredictionSource || '-'}</span>
                                            </div>
                                        </div>

                                        <div className="mt-5 pt-4 border-t border-white/10">
                                            <div className="text-[10px] uppercase tracking-[0.18em] text-lvmh-gray mb-3">Quick actions manager</div>
                                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                                <button
                                                    onClick={() => handleOpportunityAction({ id: selectedOpportunityRecord.id }, 'call')}
                                                    disabled={actionSubmittingId === selectedOpportunityRecord.id || bulkActionSubmitting}
                                                    className="text-[10px] uppercase tracking-widest px-3 py-2 rounded-lg border border-white/20 text-white hover:border-green-500/40 hover:text-green-300 transition-colors disabled:opacity-50"
                                                >
                                                    Appeler
                                                </button>
                                                <button
                                                    onClick={() => handleOpportunityAction({ id: selectedOpportunityRecord.id }, 'schedule')}
                                                    disabled={actionSubmittingId === selectedOpportunityRecord.id || bulkActionSubmitting}
                                                    className="text-[10px] uppercase tracking-widest px-3 py-2 rounded-lg border border-white/20 text-white hover:border-lvmh-gold/40 hover:text-lvmh-gold transition-colors disabled:opacity-50"
                                                >
                                                    Planifier
                                                </button>
                                                <button
                                                    onClick={() => handleOpportunityAction({ id: selectedOpportunityRecord.id }, 'done')}
                                                    disabled={actionSubmittingId === selectedOpportunityRecord.id || bulkActionSubmitting}
                                                    className="text-[10px] uppercase tracking-widest px-3 py-2 rounded-lg border border-green-500/40 text-green-300 hover:bg-green-500/10 transition-colors disabled:opacity-50"
                                                >
                                                    Marquer fait
                                                </button>
                                                <button
                                                    onClick={() => {
                                                        setCurrentTab('recordings')
                                                        setRecordingsSearch(selectedOpportunityRecord?.client?.name || '')
                                                        setRecordingsPage(1)
                                                        setSelectedRecording(null)
                                                        setSelectedOpportunityId(null)
                                                    }}
                                                    className="text-[10px] uppercase tracking-widest px-3 py-2 rounded-lg border border-lvmh-gold/40 text-lvmh-gold hover:bg-lvmh-gold/10 transition-colors"
                                                >
                                                    Ouvrir fiche
                                                </button>
                                            </div>
                                            {selectedOpportunityActionState?.updated_at && (
                                                <div className="mt-3 text-[10px] text-lvmh-gray">
                                                    Derniere mise a jour action: {formatDateTime(selectedOpportunityActionState.updated_at)}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    {selectedOpportunityPillars.map((pillar) => (
                                        <div key={pillar.title} className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                                            <div className="text-[10px] uppercase tracking-[0.18em] text-lvmh-gray mb-3">{pillar.title}</div>
                                            {pillar.entries.length > 0 ? (
                                                <div className="space-y-2">
                                                    {pillar.entries.map((entry, index) => (
                                                        <div key={`${pillar.title}-${entry.key}-${index}`} className="rounded-lg border border-white/10 bg-white/[0.02] p-2">
                                                            <div className="text-[10px] uppercase tracking-wide text-lvmh-gray">{entry.key}</div>
                                                            <div className="text-xs text-white mt-1">{entry.value}</div>
                                                        </div>
                                                    ))}
                                                </div>
                                            ) : (
                                                <div className="text-xs text-lvmh-gray">Aucune information extraite.</div>
                                            )}
                                        </div>
                                    ))}
                                </div>

                                <div className="grid grid-cols-1 xl:grid-cols-[0.8fr_1.2fr] gap-4">
                                    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                                        <div className="text-[10px] uppercase tracking-[0.18em] text-lvmh-gray mb-3">Tags</div>
                                        {selectedOpportunityTags.length > 0 ? (
                                            <div className="flex flex-wrap gap-2">
                                                {selectedOpportunityTags.slice(0, 20).map((tag, index) => (
                                                    <span key={`detail-tag-${index}`} className="text-[10px] px-2 py-1 rounded-full border border-white/15 bg-white/5 text-lvmh-gray uppercase">
                                                        {String(tag).replace(/_/g, ' ')}
                                                    </span>
                                                ))}
                                            </div>
                                        ) : (
                                            <div className="text-xs text-lvmh-gray">Aucun tag detecte.</div>
                                        )}
                                    </div>

                                    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                                        <div className="text-[10px] uppercase tracking-[0.18em] text-lvmh-gray mb-3">Produits RAG</div>
                                        {selectedOpportunityProducts.length > 0 ? (
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                                {selectedOpportunityProducts.slice(0, 6).map((product, index) => {
                                                    const productName = product?.name || product?.ID || product?.sku || `Produit ${index + 1}`
                                                    const productMeta = [product?.category, product?.brand].filter(Boolean).join(' • ')
                                                    const scoreRaw = product?.score ?? product?.similarity ?? product?.match_score
                                                    const scoreValue = Number(scoreRaw)
                                                    return (
                                                        <div key={`detail-product-${index}`} className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
                                                            <div className="text-sm font-semibold text-white">{productName}</div>
                                                            <div className="text-xs text-lvmh-gray mt-1">{productMeta || 'Categorie non renseignee'}</div>
                                                            {!Number.isNaN(scoreValue) && Number.isFinite(scoreValue) && (
                                                                <div className="text-[10px] text-lvmh-gold mt-2">Match: {Math.round(scoreValue * 100)}%</div>
                                                            )}
                                                        </div>
                                                    )
                                                })}
                                            </div>
                                        ) : (
                                            <div className="text-xs text-lvmh-gray">Aucun produit rapproche sur cette opportunite.</div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}

function KPICard({ title, value, trend, subtitle = null, gold = false, red = false, trendTone = 'auto' }) {
    const trendText = trend || '-'
    const hasPositiveSignal = /\+|up|hausse|above|au-dessus|cible atteinte/i.test(String(trendText))
    const trendClass = trendTone === 'positive'
        ? 'text-green-500'
        : trendTone === 'negative'
            ? 'text-red-400'
            : hasPositiveSignal
                ? 'text-green-500'
                : 'text-lvmh-gray'
    return (
        <div className="glass p-6 relative overflow-hidden group hover:scale-[1.02] transition-transform">
            {gold && <div className="absolute top-0 right-0 w-32 h-32 bg-lvmh-gold/5 rounded-full -mr-16 -mt-16 blur-3xl group-hover:bg-lvmh-gold/10 transition-colors"></div>}
            <div className="text-lvmh-gray text-xs uppercase tracking-widest font-bold mb-4">{title}</div>
            <div className={`text-4xl font-black mb-2 ${gold ? 'gold-text' : (red ? 'text-red-500' : 'text-white')}`}>{value}</div>
            <div className={`text-[10px] font-bold ${trendClass}`}>{trendText}</div>
            {subtitle && (
                <div className="text-[10px] text-lvmh-gray mt-2 uppercase tracking-wide">{subtitle}</div>
            )}
        </div>
    )
}



