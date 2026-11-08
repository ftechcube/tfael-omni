// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Button (Tailwind migration)
// Tactical styled button with variant and size support
// ═══════════════════════════════════════════════════════════════════════

import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

type Variant = 'default' | 'primary' | 'danger' | 'amber' | 'ghost';
type Size = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const VARIANT_CLS: Record<Variant, string> = {
  default: 'bg-background-card hover:bg-background-hover hover:border-border-accent',
  primary: 'bg-[rgba(140,150,99,0.18)] border-accent-steel text-accent-steel hover:bg-[rgba(140,150,99,0.28)]',
  danger:  'bg-[rgba(217,87,61,0.12)] border-destructive text-destructive hover:bg-[rgba(217,87,61,0.22)]',
  amber:   'bg-[rgba(242,169,59,0.12)] border-secondary text-secondary hover:bg-[rgba(242,169,59,0.22)]',
  ghost:   'bg-transparent border-transparent hover:bg-background-card hover:border-border-dim',
};

const SIZE_CLS: Record<Size, string> = {
  sm: 'text-2xs py-[3px] px-2',
  md: 'text-xs py-[7px] px-3.5',
  lg: 'text-sm py-2.5 px-5',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'default', size = 'md', className, children, ...rest }, ref) => (
    <button
      ref={ref}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border border-border-dim font-semibold font-sans cursor-pointer transition-all whitespace-nowrap leading-snug active:scale-[0.97] disabled:opacity-45 disabled:cursor-not-allowed',
        SIZE_CLS[size],
        VARIANT_CLS[variant],
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  )
);

Button.displayName = 'Button';
