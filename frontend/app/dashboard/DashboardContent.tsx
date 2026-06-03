'use client'

import { api } from '@/lib/api'
import { useApi } from '@/hooks/useApi'
import { useWebSocketEvents } from '@/hooks/useWebSocket'
import { formatDuration, formatHour } from '@/lib/utils'
import Header from '@/components/layout/Header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import {
  Users, UserCheck, Clock, TrendingUp,
  UsersRound, ShoppingBag, WifiOff, Radio,
} from 'lucide-react'

function MetricCard({
  label,
  value,
  sub,
  icon: Icon,
  accent = false,
  loading = false,
}: {
  label: string
  value: string | number
  sub?: string
  icon: React.ElementType
  accent?: boolean
  loading?: boolean
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle>{label}</CardTitle>
          <div className={`w-7 h-7 rounded-md flex items-center justify-center ${accent ? 'bg-primary/15' : 'bg-muted'}`}>
            <Icon className={`w-3.5 h-3.5 ${accent ? 'text-primary' : 'text-muted-foreground'}`} />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-7 w-24 mb-1" />
        ) : (
          <p className="text-2xl font-bold text-foreground tabular-nums">{value}</p>
        )}
        {sub && (
          <p className="text-[11px] text-muted-foreground mt-0.5">{sub}</p>
        )}
      </CardContent>
    </Card>
  )
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-card border border-border rounded-md px-3 py-2 text-xs shadow-lg">
      <p className="text-muted-foreground">{formatHour(Number(label))}</p>
      <p className="font-semibold text-foreground">{payload[0].value} visitors</p>
    </div>
  )
}

export default function DashboardContent() {
  const summary = useApi(() => api.getStoreSummary(), 10_000)
  const peakHours = useApi(() => api.getPeakHours(), 30_000)
  const wsEvents = useWebSocketEvents(20)

  const m = summary.data
  const loading = summary.loading

  return (
    <>
      <Header
        title="Dashboard"
        subtitle="Real-time store overview · Brigade Road, Bangalore"
        lastRefresh={summary.lastFetch}
        onRefresh={summary.refetch}
        isLoading={loading}
      />

      <div className="flex-1 p-5 space-y-5">
        {/* API offline banner */}
        {summary.error && (
          <div className="flex items-center gap-2.5 px-4 py-3 rounded-lg bg-destructive/10 border border-destructive/30 text-sm text-red-400">
            <WifiOff className="w-4 h-4 shrink-0" />
            <span>API offline — <span className="font-mono text-xs">{summary.error}</span></span>
          </div>
        )}

        {/* KPI Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          <MetricCard
            label="Visitors Today"
            value={m?.total_visitors_today ?? '—'}
            sub={`${m?.unique_visitors_today ?? '—'} unique`}
            icon={Users}
            accent
            loading={loading}
          />
          <MetricCard
            label="Current Occupancy"
            value={m?.current_occupancy ?? '—'}
            sub="in store now"
            icon={UserCheck}
            loading={loading}
          />
          <MetricCard
            label="Avg Dwell Time"
            value={m ? formatDuration(m.avg_dwell_seconds) : '—'}
            sub="per visitor"
            icon={Clock}
            loading={loading}
          />
          <MetricCard
            label="Peak Hour"
            value={m?.peak_hour != null ? formatHour(m.peak_hour) : '—'}
            sub={m?.peak_hour_count ? `${m.peak_hour_count} visitors` : undefined}
            icon={TrendingUp}
            loading={loading}
          />
          <MetricCard
            label="Re-entry Rate"
            value={m ? `${m.reentry_rate_pct.toFixed(1)}%` : '—'}
            sub="same visitor re-entered"
            icon={UsersRound}
            loading={loading}
          />
          <MetricCard
            label="Group Entries"
            value={m?.group_entry_count ?? '—'}
            sub="groups detected"
            icon={Users}
            loading={loading}
          />
          <MetricCard
            label="Conversion Rate"
            value={m ? `${m.conversion_rate_pct.toFixed(1)}%` : '—'}
            sub="visitor → purchase"
            icon={ShoppingBag}
            loading={loading}
          />
          <MetricCard
            label="Staff Count"
            value={m?.staff_count ?? '—'}
            sub="on floor"
            icon={UserCheck}
            loading={loading}
          />
        </div>

        {/* Peak Hours Chart */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-foreground font-medium text-sm">Hourly Footfall</CardTitle>
                <p className="text-[11px] text-muted-foreground mt-0.5">Visitor entries by hour</p>
              </div>
              <Badge variant="purple">Today</Badge>
            </div>
          </CardHeader>
          <CardContent>
            {peakHours.loading ? (
              <Skeleton className="h-48 w-full" />
            ) : peakHours.data?.buckets.length ? (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={peakHours.data.buckets} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                  <XAxis
                    dataKey="hour"
                    tickFormatter={formatHour}
                    tick={{ fill: 'hsl(215 20% 55%)', fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: 'hsl(215 20% 55%)', fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(139,92,246,0.08)' }} />
                  <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                    {peakHours.data.buckets.map((entry, i) => (
                      <Cell
                        key={i}
                        fill={entry.hour === m?.peak_hour ? '#8b5cf6' : 'hsl(263 70% 64% / 0.35)'}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-48 flex items-center justify-center text-muted-foreground text-sm">
                No footfall data yet
              </div>
            )}
          </CardContent>
        </Card>

        {/* Live Event Feed — WebSocket driven */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <CardTitle className="text-foreground font-medium text-sm">Live Event Feed</CardTitle>
              {wsEvents.connected ? (
                <span className="flex items-center gap-1 text-[10px] text-emerald-400">
                  <Radio className="w-3 h-3" />
                  WS
                </span>
              ) : (
                <span className="text-[10px] text-muted-foreground/50">connecting…</span>
              )}
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse-dot ml-auto" />
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {wsEvents.events.length === 0 ? (
              <div className="py-8 text-center text-sm text-muted-foreground">
                {wsEvents.connected
                  ? 'Waiting for events…'
                  : 'No events yet — run the tracker to start seeing data'}
              </div>
            ) : (
              <ul className="divide-y divide-border/50">
                {wsEvents.events.slice(0, 15).map(ev => (
                  <li key={ev.id} className="flex items-center gap-3 px-5 py-2.5 hover:bg-muted/20 transition-colors">
                    <EventTypeBadge type={ev.event_type} />
                    <span className="text-xs text-muted-foreground font-mono truncate flex-1">
                      {ev.track_id ?? 'unknown'}
                    </span>
                    <span className="text-[11px] text-muted-foreground/60 tabular-nums shrink-0">
                      {new Date(ev.timestamp).toLocaleTimeString('en-IN', { hour12: false })}
                    </span>
                    {ev.confidence != null && (
                      <span className="text-[10px] text-muted-foreground/50 shrink-0">
                        {Math.round(ev.confidence * 100)}%
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  )
}

function EventTypeBadge({ type }: { type: string }) {
  const map: Record<string, { label: string; variant: 'success' | 'destructive' | 'info' | 'warning' | 'purple' | 'outline' }> = {
    ENTRY:          { label: 'ENTRY',   variant: 'success' },
    EXIT:           { label: 'EXIT',    variant: 'destructive' },
    ZONE_ENTER:     { label: 'ZONE ↓',  variant: 'info' },
    ZONE_EXIT:      { label: 'ZONE ↑',  variant: 'outline' },
    DWELL_STARTED:  { label: 'DWELL',   variant: 'warning' },
    DWELL_ENDED:    { label: 'MOVED',   variant: 'outline' },
    GROUP_ENTRY:    { label: 'GROUP',   variant: 'purple' },
    STAFF_DETECTED: { label: 'STAFF',   variant: 'info' },
    ANOMALY:        { label: 'ANOMALY', variant: 'destructive' },
  }
  const cfg = map[type] ?? { label: type, variant: 'outline' as const }
  return <Badge variant={cfg.variant} className="font-mono shrink-0">{cfg.label}</Badge>
}
