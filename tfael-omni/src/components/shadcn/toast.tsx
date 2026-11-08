import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

// ═══════════════════════════════════════════════════════════════════════
// Toast — Tailwind-styled replacement for existing ToastContainer.
// Integrates with the existing useToast hook.
// ═══════════════════════════════════════════════════════════════════════

const toastVariants = cva(
  'flex items-center gap-2 rounded-md border px-4 py-3 text-sm shadow-lg animate-slide-up',
  {
    variants: {
      variant: {
        default: 'border-border bg-background-panel text-foreground',
        success: 'border-accent-olive/30 bg-accent-olive/10 text-accent-olive',
        error: 'border-destructive/30 bg-destructive/10 text-destructive',
        warning: 'border-secondary/30 bg-secondary/10 text-secondary',
        info: 'border-accent-steel/30 bg-accent-steel/10 text-accent-steel',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
)

export interface ToastProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof toastVariants> {
  onDismiss?: () => void
}

function Toast({ className, variant, onDismiss, children, ...props }: ToastProps) {
  return (
    <div className={cn(toastVariants({ variant }), className)} {...props}>
      <span className="flex-1">{children}</span>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="ml-2 shrink-0 text-foreground-muted hover:text-foreground transition-colors"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M1 1l10 10M11 1L1 11" />
          </svg>
        </button>
      )}
    </div>
  )
}

export { Toast, toastVariants }
