import type {
  AnomalyRead,
  CursorPage,
  EventRead,
  FunnelResponse,
  PeakHoursResponse,
  StoreMetricsSummary,
  ZonePopularity,
} from '@/types'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1'

export const WS_BASE = typeof window !== 'undefined'
  ? BASE.replace(/^http/, 'ws').replace('/api/v1', '')
  : 'ws://localhost:8000'

async function get<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${BASE}${path}`)
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v))
  }
  const res = await fetch(url.toString(), {
    next: { revalidate: 0 },
    signal: AbortSignal.timeout(8000),
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`)
  return res.json() as Promise<T>
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(8000),
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`)
  return res.json() as Promise<T>
}

export const api = {
  getStoreSummary: () =>
    get<StoreMetricsSummary>('/store-metrics/summary'),

  getPeakHours: (date?: string) =>
    get<PeakHoursResponse>('/store-metrics/peak-hours', date ? { date } : undefined),

  getZones: () =>
    get<ZonePopularity[]>('/store-metrics/zones'),

  getEvents: (params?: Record<string, string>) =>
    get<CursorPage<EventRead>>('/events', { limit: '50', ...params }),

  getAnomalies: (params?: Record<string, string>) =>
    get<CursorPage<AnomalyRead>>('/anomalies', { resolved: 'false', limit: '50', ...params }),

  getFunnel: () =>
    get<FunnelResponse>('/funnel'),

  resolveAnomaly: (id: string, resolvedBy: string, notes?: string) =>
    patch<AnomalyRead>(`/anomalies/${id}/resolve`, { resolved_by: resolvedBy, notes }),

  healthCheck: () =>
    fetch(`${BASE.replace('/api/v1', '')}/health`, { signal: AbortSignal.timeout(3000) })
      .then(r => r.ok)
      .catch(() => false),
}
