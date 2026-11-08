import * as React from 'react'
import { cn } from '@/lib/utils'

// ═══════════════════════════════════════════════════════════════════════
// ScrollArea — lightweight scrollable container with tactical scrollbar.
// No Radix dependency — uses native CSS scrollbar styling.
// ═══════════════════════════════════════════════════════════════════════

interface ScrollAreaProps extends React.HTMLAttributes<HTMLDivElement> {
  orientation?: 'vertical' | 'horizontal' | 'both'
}

const ScrollArea = React.forwardRef<HTMLDivElement, ScrollAreaProps>(
  ({ className, orientation = 'vertical', children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'relative',
        orientation === 'vertical' && 'overflow-y-auto overflow-x-hidden',
        orientation === 'horizontal' && 'overflow-x-auto overflow-y-hidden',
        orientation === 'both' && 'overflow-auto',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
)
ScrollArea.displayName = 'ScrollArea'

export { ScrollArea }
