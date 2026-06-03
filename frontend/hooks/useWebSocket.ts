'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { WS_BASE } from '@/lib/api'
import type { EventRead } from '@/types'

export interface WsState {
  events: EventRead[]
  connected: boolean
}

export function useWebSocketEvents(maxEvents = 50): WsState {
  const [events, setEvents] = useState<EventRead[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    try {
      const ws = new WebSocket(`${WS_BASE}/ws/events`)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          // Skip the connection handshake message
          if (data.type === 'connected') return
          setEvents(prev => [data as EventRead, ...prev].slice(0, maxEvents))
        } catch {
          // ignore parse errors
        }
      }

      ws.onclose = () => {
        setConnected(false)
        // Reconnect after 3s
        retryRef.current = setTimeout(connect, 3000)
      }

      ws.onerror = () => {
        ws.close()
      }
    } catch {
      // WebSocket not supported or URL invalid
      setConnected(false)
    }
  }, [maxEvents])

  useEffect(() => {
    connect()
    return () => {
      if (retryRef.current) clearTimeout(retryRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { events, connected }
}
