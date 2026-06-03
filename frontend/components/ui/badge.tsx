import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default:
          'border-transparent bg-primary text-primary-foreground',
        secondary:
          'border-transparent bg-secondary text-secondary-foreground',
        destructive:
          'border-transparent bg-destructive/20 text-red-400 border-red-800/40',
        outline:
          'text-foreground border-border',
        success:
          'border-transparent bg-green-900/40 text-green-400 border-green-800/40',
        warning:
          'border-transparent bg-yellow-900/40 text-yellow-400 border-yellow-800/40',
        info:
          'border-transparent bg-blue-900/40 text-blue-400 border-blue-800/40',
        purple:
          'border-transparent bg-purple-900/40 text-purple-400 border-purple-800/40',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
