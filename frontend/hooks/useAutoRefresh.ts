'use client'

import { useEffect, useRef } from 'react'

export function useAutoRefresh(callback: () => void, intervalMs = 5000): void {
  const savedCallback = useRef(callback)

  useEffect(() => {
    savedCallback.current = callback
  }, [callback])

  useEffect(() => {
    const id = setInterval(() => savedCallback.current(), intervalMs)
    return () => clearInterval(id)
  }, [intervalMs])
}
