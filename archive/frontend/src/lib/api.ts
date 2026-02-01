/**
 * LVMH Voice-to-Tag API Client
 * Robust fetch wrapper with error handling, timeout, and cancellation.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ============== Error Classes ==============

export class APIError extends Error {
    constructor(
        public status: number,
        message: string,
        public details?: unknown
    ) {
        super(message)
        this.name = 'APIError'
    }
}

// ============== Types ==============

export interface ExtractionTags {
    brand?: string
    product_category?: string
    product_type?: string
    vip_status?: string
    budget_range?: string
    occasion?: string
    preferences: string[]
}

export interface RoutingInfo {
    tier: number
    confidence: number
    reason?: string
}

export interface RGPDInfo {
    contains_sensitive: boolean
    categories_detected: string[]
    anonymized_text?: string
}

export interface ExtractionResult {
    id: string
    tags: string[]
    extraction: ExtractionTags
    routing: RoutingInfo
    rgpd: RGPDInfo
    processing_time_ms: number
    cache_hit: boolean
    model_used?: string
}

export interface TierStats {
    tier: number
    count: number
    percentage: number
    avg_processing_time_ms: number
}

export interface OverviewStats {
    total_notes: number
    total_tags: number
    avg_confidence: number
    avg_processing_time_ms: number
    tier_distribution: TierStats[]
    top_tags: Record<string, number>
    cache_hit_rate: number
}

export interface RGPDStats {
    total_notes: number
    sensitive_count: number
    sensitive_rate: number
    categories: Record<string, number>
    false_positive_rate: number
    false_negative_rate: number
}

export interface CostStats {
    total_cost: number
    cost_by_tier: Record<string, number>
    projection_annual: number
    roi_metrics: Record<string, unknown>
}

export interface PaginatedResults {
    items: ExtractionResult[]
    total: number
    page: number
    page_size: number
    total_pages: number
}

export interface BatchTask {
    task_id: string
    status: 'pending' | 'processing' | 'complete' | 'error'
    progress: number
    total: number
    results: ExtractionResult[]
    error?: string
}

// ============== Fetch Wrapper ==============

async function fetchAPI<T>(
    endpoint: string,
    options?: RequestInit
): Promise<T> {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 30000) // 30s timeout

    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            ...options,
            signal: controller.signal,
            headers: {
                'Content-Type': 'application/json',
                ...options?.headers,
            },
        })

        clearTimeout(timeoutId)

        if (!response.ok) {
            const error = await response.json().catch(() => ({}))
            throw new APIError(
                response.status,
                error.detail || error.message || `HTTP ${response.status}`,
                error
            )
        }

        return response.json()
    } catch (error) {
        clearTimeout(timeoutId)

        if (error instanceof APIError) throw error

        if (error instanceof Error && error.name === 'AbortError') {
            throw new APIError(408, 'Request timeout')
        }

        throw new APIError(500, 'Network error', error)
    }
}

// ============== API Methods ==============

export const api = {
    // Health check
    async health() {
        return fetchAPI<{ status: string; version: string }>('/health')
    },

    // Single note analysis
    async analyzeNote(text: string, language: 'FR' | 'EN' | 'IT' = 'FR') {
        return fetchAPI<ExtractionResult>('/api/analyze', {
            method: 'POST',
            body: JSON.stringify({ text, language }),
        })
    },

    // Start batch processing
    async startBatch(file: File) {
        const formData = new FormData()
        formData.append('file', file)

        const response = await fetch(`${API_BASE_URL}/api/batch`, {
            method: 'POST',
            body: formData,
        })

        if (!response.ok) {
            throw new APIError(response.status, await response.text())
        }

        return response.json() as Promise<{ task_id: string; total: number }>
    },

    // Get batch status (polling)
    async getBatchStatus(taskId: string) {
        return fetchAPI<BatchTask>(`/api/batch/${taskId}`)
    },

    // Subscribe to batch progress (SSE)
    subscribeToBatch(
        taskId: string,
        onProgress: (task: BatchTask) => void,
        onComplete: (task: BatchTask) => void,
        onError: (error: Error) => void
    ) {
        const eventSource = new EventSource(
            `${API_BASE_URL}/api/batch/${taskId}/stream`
        )

        eventSource.onmessage = (event) => {
            const task: BatchTask = JSON.parse(event.data)

            if (task.status === 'complete') {
                onComplete(task)
                eventSource.close()
            } else if (task.status === 'error') {
                onError(new Error(task.error || 'Batch processing failed'))
                eventSource.close()
            } else {
                onProgress(task)
            }
        }

        eventSource.onerror = () => {
            onError(new Error('Connection lost'))
            eventSource.close()
        }

        return () => eventSource.close()
    },

    // Results (paginated)
    async getResults(page = 1, pageSize = 20, filters?: {
        tier?: number
        search?: string
        sensitive_only?: boolean
    }) {
        const params = new URLSearchParams({
            page: page.toString(),
            page_size: pageSize.toString(),
        })

        if (filters?.tier) params.set('tier', filters.tier.toString())
        if (filters?.search) params.set('search', filters.search)
        if (filters?.sensitive_only) params.set('sensitive_only', 'true')

        return fetchAPI<PaginatedResults>(`/api/results?${params}`)
    },

    // Get single result detail
    async getResultDetail(noteId: string) {
        return fetchAPI<Record<string, unknown>>(`/api/results/${noteId}`)
    },

    // Stats endpoints
    async getOverviewStats() {
        return fetchAPI<OverviewStats>('/api/stats/overview')
    },

    async getRGPDStats() {
        return fetchAPI<RGPDStats>('/api/stats/rgpd')
    },

    async getCostStats() {
        return fetchAPI<CostStats>('/api/stats/cost')
    },
}

export default api
