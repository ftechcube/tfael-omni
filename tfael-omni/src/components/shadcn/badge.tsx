import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default:
          'border-transparent bg-primary text-primary-foreground',
        secondary:
          'border-transparent bg-secondary text-secondary-foreground',
        destructive:
          'border-transparent bg-destructive text-destructive-foreground',
        outline:
          'border-border text-foreground',
        // Tactical severity badges
        critical:
          'border-transparent bg-severity-critical/20 text-severity-critical',
        high:
          'border-transparent bg-severity-high/20 text-severity-high',
        medium:
          'border-transparent bg-severity-medium/20 text-severity-medium',
        low:
          'border-transparent bg-severity-low/20 text-severity-low',
        info:
          'border-transparent bg-severity-info/20 text-severity-info',
        // Domain badges
        olive:
          'border-transparent bg-accent-olive/15 text-accent-olive',
        amber:
          'border-transparent bg-accent-amber/15 text-accent-amber',
        purple:
          'border-transparent bg-accent-purple/15 text-accent-purple',
        steel:
          'border-transparent bg-accent-steel/15 text-accent-steel',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
