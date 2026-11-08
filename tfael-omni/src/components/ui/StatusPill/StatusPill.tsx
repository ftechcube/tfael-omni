// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Status Pill (Tailwind migration)
// Compact label + dot indicator for status values
// ═══════════════════════════════════════════════════════════════════════

import { cn } from '@/lib/utils';

type DotColor = 'green' | 'yellow' | 'blue' | 'red';

interface StatusPillProps {
  label: string;
  dot?: DotColor;
  value?: string | number;
  className?: string;
}

const DOT_CLS: Record<DotColor, string> = {
  green:  'bg-[#10b981]',
  yellow: 'bg-secondary',
  blue:   'bg-accent-steel',
  red:    'bg-destructive shadow-[0_0_6px_theme(colors.destructive.DEFAULT)] animate-pulse-red',
};

export function StatusPill({ label, dot, value, className }: StatusPillProps) {
  return (
    <div className={cn('py-1 px-2.5 rounded-sm border border-border-dim bg-background-card flex items-center gap-1.5 font-mono text-[11px]', className)}>
      {dot && <span className={cn('w-2 h-2 rounded-full shrink-0', DOT_CLS[dot])} />}
      <span className="opacity-60">{label}</span>
      {value !== undefined && <span>{value}</span>}
    </div>
  );
}
