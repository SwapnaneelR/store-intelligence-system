'use client'

import { api } from '@/lib/api'
import { useApi } from '@/hooks/useApi'
import Header from '@/components/layout/Header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { WifiOff, TrendingDown } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LabelList,
} from 'recharts'
import type { FunnelStage } from '@/types'

const STAGE_COLORS = ['#8b5cf6', '#7c3aed', '#6d28d9', '#5b21b6', '#4c1d95']

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null
  const d = payload[0].payload as FunnelStage
  return (
    <div className="bg-card border border-border rounded-md px-3 py-2.5 text-xs shadow-lg min-w-[140px]">
      <p className="font-medium text-foreground mb-1">{d.stage}</p>
      <p className="text-muted-foreground">Visitors: <span className="text-foreground font-mono">{d.count.toLocaleString()}</span></p>
      <p className="text-muted-foreground">Conversion: <span className="text-green-400 font-mono">{d.conversion_rate.toFixed(1)}%</span></p>
      {d.drop_off > 0 && (
        <p className="text-muted-foreground">Drop-off: <span className="text-red-400 font-mono">{d.drop_off.toLocaleString()}</span></p>
      )}
    </div>
  )
}

export default function FunnelContent() {
  const { data, loading, error, lastFetch, refetch } = useApi(
    () => api.getFunnel(),
    30_000,
  )

  const stages: FunnelStage[] = data?.stages ?? []
  const first = stages[0]
  const last = stages[stages.length - 1]
  const overallConversion = first && last && first.count > 0
    ? ((last.count / first.count) * 100).toFixed(1)
    : '0.0'

  return (
    <>
      <Header
        title="Funnel"
        subtitle="Customer journey funnel · last 24 hours"
        lastRefresh={lastFetch}
        onRefresh={refetch}
        isLoading={loading}
      />

      <div className="flex-1 p-5 space-y-5">
        {error && (
          <div className="flex items-center gap-2.5 px-4 py-3 rounded-lg bg-destructive/10 border border-destructive/30 text-sm text-red-400">
            <WifiOff className="w-4 h-4 shrink-0" />
            <span>API offline — {error}</span>
          </div>
        )}

        {/* Summary stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card>
            <CardContent className="pt-4">
              <p className="text-[11px] text-muted-foreground mb-1">Overall Conversion</p>
              {loading ? <Skeleton className="h-7 w-16" /> : (
                <p className="text-2xl font-bold text-green-400 tabular-nums">{overallConversion}%</p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <p className="text-[11px] text-muted-foreground mb-1">Total Entered</p>
              {loading ? <Skeleton className="h-7 w-20" /> : (
                <p className="text-2xl font-bold text-foreground tabular-nums">
                  {first?.count.toLocaleString() ?? '—'}
                </p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <p className="text-[11px] text-muted-foreground mb-1">Exited Store</p>
              {loading ? <Skeleton className="h-7 w-20" /> : (
                <p className="text-2xl font-bold text-foreground tabular-nums">
                  {last?.count.toLocaleString() ?? '—'}
                </p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <p className="text-[11px] text-muted-foreground mb-1">Total Drop-off</p>
              {loading ? <Skeleton className="h-7 w-20" /> : (
                <p className="text-2xl font-bold text-red-400 tabular-nums">
                  {stages.reduce((s, st) => s + st.drop_off, 0).toLocaleString()}
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-5 gap-5">
          {/* Funnel bar chart */}
          <Card className="xl:col-span-3">
            <CardHeader>
              <CardTitle className="text-foreground font-medium text-sm">Journey Funnel</CardTitle>
              <p className="text-[11px] text-muted-foreground">Visitor count at each stage</p>
            </CardHeader>
            <CardContent>
              {loading ? (
                <Skeleton className="h-60 w-full" />
              ) : stages.length === 0 ? (
                <div className="h-60 flex items-center justify-center text-muted-foreground text-sm">
                  No funnel data — need ENTRY + EXIT events in the DB
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart
                    data={stages}
                    layout="vertical"
                    margin={{ top: 4, right: 40, left: 8, bottom: 4 }}
                  >
                    <XAxis type="number" tick={{ fill: 'hsl(215 20% 55%)', fontSize: 10 }} axisLine={false} tickLine={false} />
                    <YAxis
                      type="category"
                      dataKey="stage"
                      tick={{ fill: 'hsl(215 20% 55%)', fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                      width={90}
                    />
                    <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(139,92,246,0.06)' }} />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                      {stages.map((_, i) => (
                        <Cell key={i} fill={STAGE_COLORS[i % STAGE_COLORS.length]} />
                      ))}
                      <LabelList
                        dataKey="count"
                        position="right"
                        style={{ fill: 'hsl(215 20% 65%)', fontSize: 11, fontFamily: 'monospace' }}
                        formatter={(v: number) => v.toLocaleString()}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          {/* Stage breakdown */}
          <Card className="xl:col-span-2">
            <CardHeader>
              <CardTitle className="text-foreground font-medium text-sm">Stage Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5">
              {loading ? (
                Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-14 w-full" />)
              ) : stages.length === 0 ? (
                <p className="text-muted-foreground text-sm text-center py-4">No data</p>
              ) : (
                stages.map((stage, i) => (
                  <div
                    key={stage.stage}
                    className="flex items-center justify-between px-3 py-2.5 rounded-md border border-border hover:bg-muted/20 transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className="w-2.5 h-2.5 rounded-full shrink-0"
                        style={{ backgroundColor: STAGE_COLORS[i % STAGE_COLORS.length] }}
                      />
                      <span className="text-sm text-foreground">{stage.stage}</span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="font-mono text-sm font-semibold text-foreground tabular-nums">
                        {stage.count.toLocaleString()}
                      </span>
                      <Badge
                        variant={stage.conversion_rate >= 70 ? 'success' : stage.conversion_rate >= 40 ? 'warning' : 'destructive'}
                        className="text-[10px] font-mono"
                      >
                        {stage.conversion_rate.toFixed(1)}%
                      </Badge>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>

        {/* Drop-off analysis */}
        {stages.length > 1 && (
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <TrendingDown className="w-4 h-4 text-red-400" />
                <CardTitle className="text-foreground font-medium text-sm">Drop-off Analysis</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                {stages.slice(1).map((stage, i) => {
                  const prev = stages[i]
                  const dropPct = prev.count > 0
                    ? ((prev.count - stage.count) / prev.count * 100).toFixed(1)
                    : '0.0'
                  return (
                    <div key={stage.stage} className="p-3 rounded-md border border-border bg-muted/20">
                      <p className="text-[11px] text-muted-foreground mb-1.5">
                        {prev.stage} → {stage.stage}
                      </p>
                      <p className="text-lg font-bold font-mono text-red-400 tabular-nums">−{dropPct}%</p>
                      <p className="text-[11px] text-muted-foreground font-mono mt-0.5 tabular-nums">
                        {stage.drop_off.toLocaleString()} lost
                      </p>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </>
  )
}
