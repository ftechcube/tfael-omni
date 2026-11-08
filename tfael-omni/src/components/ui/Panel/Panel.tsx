// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Panel (Tailwind migration)
// Section container with optional header, icon, and actions
// ═══════════════════════════════════════════════════════════════════════

import type { ReactNode, CSSProperties } from 'react';
import { cn } from '@/lib/utils';

interface PanelProps {
  title?: string;
  icon?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  noPad?: boolean;
  className?: string;
  style?: CSSProperties;
}

export function Panel({ title, icon, actions, children, noPad, className = '', style }: PanelProps) {
  return (
    <div className={cn('bg-background-panel border border-border-dim rounded-lg flex flex-col overflow-hidden', className)} style={style}>
      {title && (
        <div className="flex items-center gap-2 py-2.5 px-3.5 border-b border-border-dim bg-background-surface text-xs font-bold text-accent-steel font-mono uppercase tracking-wide shrink-0">
          {icon && <span className="text-sm opacity-80">{icon}</span>}
          <span className="flex-1">{title}</span>
          {actions && <div className="flex gap-1 items-center">{actions}</div>}
        </div>
      )}
      <div className={cn('flex-1 overflow-y-auto', noPad ? 'p-0' : 'py-2.5 px-3.5')}>
        {children}
      </div>
    </div>
  );
}
