interface LiveBadgeProps {
  interval?: number
}

export default function LiveBadge({ interval = 5 }: LiveBadgeProps) {
  return (
    <div
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[11px] font-semibold tracking-wide select-none"
      aria-label={`Live data, refreshes every ${interval} seconds`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" aria-hidden="true" />
      LIVE · {interval}s
    </div>
  )
}
