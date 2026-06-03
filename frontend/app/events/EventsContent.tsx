'use client'

import { useState } from 'react'
import { api } from '@/lib/api'
import { useApi } from '@/hooks/useApi'
import Header from '@/components/layout/Header'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { WifiOff } from 'lucide-react'
import type { EventRead } from '@/types'

const EVENT_TYPES = ['ALL', 'ENTRY', 'EXIT', 'ZONE_ENTER', 'ZONE_EXIT', 'DWELL_STARTED', 'DWELL_ENDED', 'GROUP_ENTRY', 'STAFF_DETECTED', 'ANOMALY']
const PERSON_CLASSES = ['ALL', 'customer', 'staff', 'unknown']

const EVENT_VARIANT: Record<string, 'success' | 'destructive' | 'info' | 'warning' | 'purple' | 'outline'> = {
  ENTRY: 'success',
  EXIT: 'destructive',
  ZONE_ENTER: 'info',
  ZONE_EXIT: 'outline',
  DWELL_STARTED: 'warning',
  DWELL_ENDED: 'outline',
  GROUP_ENTRY: 'purple',
  STAFF_DETECTED: 'info',
  ANOMALY: 'destructive',
}

const CLASS_VARIANT: Record<string, 'success' | 'info' | 'outline'> = {
  customer: 'success',
  staff: 'info',
  unknown: 'outline',
}

export default function EventsContent() {
  const [eventType, setEventType] = useState('ALL')
  const [personClass, setPersonClass] = useState('ALL')

  const params: Record<string, string> = { limit: '100' }
  if (eventType !== 'ALL') params.event_type = eventType
  if (personClass !== 'ALL') params.person_class = personClass

  const { data, loading, error, lastFetch, refetch } = useApi(
    () => api.getEvents(params),
    5_000,
  )

  const items: EventRead[] = data?.items ?? []

  return (
    <>
      <Header
        title="Events"
        subtitle="Store events · auto-refreshes every 5s"
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

        {/* Filters */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <label className="text-xs text-muted-foreground whitespace-nowrap">Event type</label>
            <Select value={eventType} onChange={e => setEventType(e.target.value)} className="w-44">
              {EVENT_TYPES.map(t => (
                <option key={t} value={t}>{t === 'ALL' ? 'All types' : t}</option>
              ))}
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-muted-foreground whitespace-nowrap">Person</label>
            <Select value={personClass} onChange={e => setPersonClass(e.target.value)} className="w-36">
              {PERSON_CLASSES.map(c => (
                <option key={c} value={c}>{c === 'ALL' ? 'All' : c}</option>
              ))}
            </Select>
          </div>
          <span className="text-[11px] text-muted-foreground ml-auto tabular-nums">
            {loading ? 'Loading…' : `${items.length} events`}
          </span>
        </div>

        <Card>
          <CardContent className="p-0">
            {loading ? (
              <div className="p-4 space-y-2">
                {Array.from({ length: 8 }).map((_, i) => (
                  <Skeleton key={i} className="h-9 w-full" />
                ))}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Timestamp</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Track ID</TableHead>
                    <TableHead>Camera</TableHead>
                    <TableHead>Zone</TableHead>
                    <TableHead>Person</TableHead>
                    <TableHead className="text-right">Confidence</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-12 text-muted-foreground text-sm">
                        No events found — run tracker or seed demo data
                      </TableCell>
                    </TableRow>
                  ) : (
                    items.map(ev => (
                      <TableRow key={ev.id}>
                        <TableCell className="font-mono text-[11px] text-muted-foreground whitespace-nowrap">
                          {new Date(ev.timestamp).toLocaleTimeString('en-IN', { hour12: false })}
                        </TableCell>
                        <TableCell>
                          <Badge variant={EVENT_VARIANT[ev.event_type] ?? 'outline'} className="font-mono text-[10px]">
                            {ev.event_type}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-mono text-[11px] text-muted-foreground max-w-[110px] truncate">
                          {ev.track_id ?? '—'}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">{ev.camera_id ?? '—'}</TableCell>
                        <TableCell className="text-xs text-muted-foreground max-w-[100px] truncate">{ev.zone_id ?? '—'}</TableCell>
                        <TableCell>
                          {ev.person_class ? (
                            <Badge variant={CLASS_VARIANT[ev.person_class] ?? 'outline'} className="text-[10px]">
                              {ev.person_class}
                            </Badge>
                          ) : <span className="text-muted-foreground text-xs">—</span>}
                        </TableCell>
                        <TableCell className="text-right font-mono text-[11px] text-muted-foreground">
                          {ev.confidence != null ? `${Math.round(ev.confidence * 100)}%` : '—'}
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
