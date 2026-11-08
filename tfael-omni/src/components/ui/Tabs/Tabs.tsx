import { cn } from '@/lib/utils';

/* ── Primary Tabs (workspace-level) ─────────────────────────────────── */
interface Tab {
  id: string;
  label: string;
  icon?: string;
  badge?: number | string;
}

interface TabsProps {
  tabs: Tab[];
  active: string;
  onChange: (id: string) => void;
  className?: string;
}

export function Tabs({ tabs, active, onChange, className }: TabsProps) {
  return (
    <div className={cn('flex gap-0.5 bg-background-deep p-0.5 rounded-sm', className)}>
      {tabs.map(t => (
        <button
          key={t.id}
          className={cn(
            'flex items-center gap-1.5 px-3.5 py-1.5 rounded-sm font-mono text-[11px] font-semibold uppercase tracking-wide whitespace-nowrap transition-colors',
            t.id === active
              ? 'bg-background-card text-primary shadow-[inset_0_-2px_0_theme(colors.primary.DEFAULT)]'
              : 'text-foreground-muted hover:bg-background-card hover:text-foreground'
          )}
          onClick={() => onChange(t.id)}
        >
          {t.icon && <span className="text-sm opacity-70">{t.icon}</span>}
          <span>{t.label}</span>
          {t.badge !== undefined && (
            <span className="bg-destructive text-white text-[9px] font-bold px-1.5 py-px rounded-lg min-w-[16px] text-center">
              {t.badge}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

/* ── Sub-tabs (within a workspace) ──────────────────────────────────── */
interface SubTabsProps {
  tabs: Tab[];
  active: string;
  onChange: (id: string) => void;
  className?: string;
}

export function SubTabs({ tabs, active, onChange, className }: SubTabsProps) {
  return (
    <div className={cn('flex border-b border-border-dim px-1', className)}>
      {tabs.map(t => (
        <button
          key={t.id}
          className={cn(
            'border-b-2 px-3.5 py-2 font-mono text-[11px] font-semibold transition-colors',
            t.id === active
              ? 'text-primary border-primary'
              : 'text-foreground-muted border-transparent hover:text-foreground'
          )}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
