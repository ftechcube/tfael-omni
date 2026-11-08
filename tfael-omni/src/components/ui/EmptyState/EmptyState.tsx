// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Empty State (Tailwind migration)
// Centered placeholder for empty data areas
// ═══════════════════════════════════════════════════════════════════════

import type { ReactNode } from 'react';

interface EmptyStateProps {
  icon?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 px-5 text-center min-h-[200px]">
      {icon && <div className="text-[32px] opacity-30">{icon}</div>}
      <div className="font-mono text-[13px] font-bold text-foreground-muted uppercase tracking-wide">{title}</div>
      {description && <div className="text-xs text-foreground-muted opacity-60 max-w-[320px]">{description}</div>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
