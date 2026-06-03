'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

export interface ApiState<T> {
  data: T | null
  loading: boolean
  error: string | null
  lastFetch: Date | null
  refetch: () => void
}

export function useApi<T>(
  fetcher: () => Promise<T>,
  intervalMs?: number,
): ApiState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastFetch, setLastFetch] = useState<Date | null>(null)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const fetch_ = useCallback(async () => {
    try {
      const result = await fetcherRef.current()
      setData(result)
      setError(null)
      setLastFetch(new Date())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch_()
  }, [fetch_])

  useEffect(() => {
    if (!intervalMs) return
    const id = setInterval(fetch_, intervalMs)
    return () => clearInterval(id)
  }, [intervalMs, fetch_])

  return { data, loading, error, lastFetch, refetch: fetch_ }
}
