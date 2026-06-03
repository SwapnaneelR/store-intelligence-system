'use client'

import { useState } from 'react'
import { api } from '@/lib/api'
import { useApi } from '@/hooks/useApi'
import Header from '@/components/layout/Header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { AlertTriangle, CheckCircle, WifiOff } from 'lucide-react'
import type { AnomalyRead } from '@/types'

const SEVERITY_VARIANT: Record<string, 'destructive' | 'warning' | 'info' | 'outline'> = {
  CRITICAL: 'destructive',
  HIGH: 'destructive',
  MEDIUM: 'warning',
  LOW: 'info',
}

const TYPE_LABELS: Record<string, string> = {
  CROWD_SURGE: 'Crowd Surge',
  LONG_STAY: 'Long Stay',
  EXCESS_REENTRY: 'Excess Re-entry',
  CAMERA_FAILURE: 'Camera Failure',
  LOITERING: 'Loitering',
  ABANDONED_OBJECT: 'Abandoned Object',
  TAILGATE: 'Tailgate',
}

function SeverityDot({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    CRITICAL: 'bg-red-500',
    HIGH: 'bg-orange-500',
    MEDIUM: 'bg-yellow-500',
    LOW: 'bg-blue-500',
  }
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full shrink-0 ${colors[severity] ?? 'bg-muted'}`}
      aria-hidden="true"
    />
  )
}

export default function AnomaliesContent() {
  const [resolving, setResolving] = useState<string | null>(null)
  const { data, loading, error, lastFetch, refetch } = useApi(
    () => api.getAnomalies({ resolved: 'false', limit: '100' }),
    10_000,
  )

  const items: AnomalyRead[] = data?.items ?? []
  const bySeverity = {
    CRITICAL: items.filter(a => a.severity === 'CRITICAL').length,
    HIGH: items.filter(a => a.severity === 'HIGH').length,
    MEDIUM: items.filter(a => a.severity === 'MEDIUM').length,
    LOW: items.filter(a => a.severity === 'LOW').length,
  }

  async function handleResolve(id: string) {
    setResolving(id)
    try {
      await api.resolveAnomaly(id, 'dashboard-user')
      refetch()
    } catch {
      // silently fail
    } finally {
      setResolving(null)
    }
  }

  return (
    <>
      <Header
        title="Anomalies"
        subtitle="Unresolved store anomalies · auto-refreshes every 10s"
        lastRefresh={lastFetch}
        onRefresh={refetch}
        isLoading={loading}
      />

      <div className="flex-1 p-5 space-y-4">
        {error && (
          <div className="flex items-center gap-2.5 px-4 py-3 rounded-lg bg-destructive/10 border border-destructive/30 text-sm text-red-400">
            <WifiOff className="w-4 h-4 shrink-0" />
            <span>API offline — {error}</span>
          </div>
        )}

        {/* Severity summary cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { key: 'CRITICAL', label: 'Critical', color: 'text-red-400', bg: 'bg-red-900/20 border-red-800/30' },
            { key: 'HIGH',     label: 'High',     color: 'text-orange-400', bg: 'bg-orange-900/20 border-orange-800/30' },
            { key: 'MEDIUM',   label: 'Medium',   color: 'text-yellow-400', bg: 'bg-yellow-900/20 border-yellow-800/30' },
            { key: 'LOW',      label: 'Low',      color: 'text-blue-400', bg: 'bg-blue-900/20 border-blue-800/30' },
          ].map(({ key, label, color, bg }) => (
            <div key={key} className={`flex items-center gap-3 px-4 py-3 rounded-lg border ${bg}`}>
              <AlertTriangle className={`w-4 h-4 shrink-0 ${color}`} />
              <div>
                {loading ? (
                  <Skeleton className="h-5 w-8 mb-0.5" />
                ) : (
                  <p className={`text-xl font-bold tabular-nums ${color}`}>{bySeverity[key as keyof typeof bySeverity]}</p>
                )}
                <p className="text-[11px] text-muted-foreground">{label}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Anomaly table */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-foreground font-medium text-sm">Open Anomalies</CardTitle>
              {items.length > 0 && (
                <Badge variant="destructive">{items.length} unresolved</Badge>
              )}
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="p-4 space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Severity</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Detected</TableHead>
                    <TableHead>Track</TableHead>
                    <TableHead>Notes</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-12">
                        <div className="flex flex-col items-center gap-2 text-muted-foreground">
                          <CheckCircle className="w-8 h-8 text-green-500/50" />
                          <p className="text-sm">No open anomalies</p>
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : (
                    items.map(a => (
                      <TableRow key={a.id}>
                        <TableCell>
                          <div className="flex items-center gap-1.5">
                            <SeverityDot severity={a.severity} />
                            <Badge variant={SEVERITY_VARIANT[a.severity] ?? 'outline'} className="text-[10px]">
                              {a.severity}
                            </Badge>
                          </div>
                        </TableCell>
                        <TableCell className="text-sm text-foreground font-medium">
                          {TYPE_LABELS[a.anomaly_type] ?? a.anomaly_type}
                        </TableCell>
                        <TableCell className="font-mono text-[11px] text-muted-foreground whitespace-nowrap">
                          {new Date(a.detected_at).toLocaleString('en-IN', { hour12: false, hour: '2-digit', minute: '2-digit' })}
                        </TableCell>
                        <TableCell className="font-mono text-[11px] text-muted-foreground max-w-[80px] truncate">
                          {a.event_id ?? '—'}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground max-w-[160px] truncate">
                          {a.notes ?? '—'}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleResolve(a.id)}
                            disabled={resolving === a.id}
                            className="h-7 text-xs"
                          >
                            {resolving === a.id ? 'Resolving…' : 'Resolve'}
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  )
}
