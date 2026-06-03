'use client'

import { useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'

interface HeaderProps {
  title: string
  subtitle?: string
  lastRefresh?: Date | null
  onRefresh?: () => void
  isLoading?: boolean
}

export default function Header({ title, subtitle, lastRefresh, onRefresh, isLoading }: HeaderProps) {
  const [clock, setClock] = useState('')

  useEffect(() => {
    const update = () =>
      setClock(new Date().toLocaleTimeString('en-IN', { hour12: false }))
    update()
    const id = setInterval(update, 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <header className="h-14 flex items-center justify-between px-5 border-b border-border bg-card/70 backdrop-blur-sm sticky top-0 z-10">
      <div>
        <h1 className="text-[15px] font-semibold text-foreground leading-tight">{title}</h1>
        {subtitle && <p className="text-[11px] text-muted-foreground mt-0.5">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-2.5">
        {lastRefresh && (
          <span className="hidden sm:block text-[11px] text-muted-foreground/60 font-mono">
            {lastRefresh.toLocaleTimeString('en-IN', { hour12: false })}
          </span>
        )}

        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isLoading}
            aria-label="Refresh data"
            className="p-1.5 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground transition-colors cursor-pointer disabled:opacity-40"
          >
            <RefreshCw className={cn('w-3.5 h-3.5', isLoading && 'animate-spin')} />
          </button>
        )}

        {/* Live clock */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-muted border border-border">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse-dot" aria-hidden="true" />
          <span className="text-[11px] font-mono text-foreground tabular-nums">{clock || '--:--:--'}</span>
        </div>
      </div>
    </header>
  )
}
