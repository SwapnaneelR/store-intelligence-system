export interface StoreMetricsSummary {
  as_of: string
  total_visitors_today: number
  current_occupancy: number
  unique_visitors_today: number
  avg_dwell_seconds: number
  peak_hour: number | null
  peak_hour_count: number
  reentry_rate_pct: number
  group_entry_count: number
  staff_count: number
  conversion_rate_pct: number
  total_transactions: number
  total_gmv: number
}

export interface EventRead {
  id: string
  event_type: string
  timestamp: string
  camera_id: string | null
  track_id: string | null
  session_id: string | null
  zone_id: string | null
  group_id: string | null
  person_class: string | null
  confidence: number | null
}

export interface AnomalyRead {
  id: string
  event_id: string | null
  anomaly_type: string
  severity: string
  resolved: boolean
  resolved_at: string | null
  resolved_by: string | null
  notes: string | null
  detected_at: string
}

export interface FunnelStage {
  stage: string
  count: number
  drop_off: number
  conversion_rate: number
}

export interface FunnelResponse {
  from_ts: string
  to_ts: string
  stages: FunnelStage[]
}

export interface ZonePopularity {
  zone_id: string
  zone_name: string | null
  visit_count: number
  avg_dwell_seconds: number
}

export interface HourBucket {
  hour: number
  count: number
}

export interface PeakHoursResponse {
  date: string
  buckets: HourBucket[]
}

export interface CursorPage<T> {
  items: T[]
  next_cursor: string | null
  total: number | null
}
