// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Card (Tailwind migration)
// Simple container with optional hover interaction
// ═══════════════════════════════════════════════════════════════════════

import type { CSSProperties, ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface CardProps {
  children: ReactNode;
  hover?: boolean;
  onClick?: () => void;
  style?: CSSProperties;
  className?: string;
}

export function Card({ children, hover, onClick, style, className }: CardProps) {
  return (
    <div
      className={cn(
        'bg-background-card border border-border-dim rounded-md p-3.5',
        hover && 'cursor-pointer transition-colors hover:bg-background-hover hover:border-border-accent',
        className,
      )}
      style={style}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      {children}
    </div>
  );
}
