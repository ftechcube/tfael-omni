// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Top Bar (Tailwind migration)
// Brand block + workspace tabs + status cluster (UTC, sync, user)
// ═══════════════════════════════════════════════════════════════════════

import { useApp, type WorkspaceId } from '@/context/AppContext';
import { useAuth } from '@/context/AuthContext';
import { Icon, type IconName } from '@/components/icons/Icon';
import { cn } from '@/lib/utils';

interface WorkspaceTab {
  id: WorkspaceId;
  label: string;
  icon: IconName;
  perm?: string;
}

const WORKSPACES: WorkspaceTab[] = [
  { id: 'c4isr',        label: 'C4ISR',           icon: 'satellite' },
  { id: 'osint',        label: 'OSINT Profiler',   icon: 'search' },
  { id: 'siem',         label: 'SIEM',             icon: 'shield',    perm: 'view_siem' },
  { id: 'dfir',         label: 'DFIR',             icon: 'flask' },
  { id: 'intelligence', label: 'Intel Graph',      icon: 'graph' },
  { id: 'admin',        label: 'Admin',            icon: 'settings',  perm: 'manage_users' },
];

export function TopBar() {
  const { workspace, setWorkspace, overview, utcTime } = useApp();
  const { user, role, hasPerm, logout } = useAuth();

  const unitCount = overview?.units?.length ?? 0;
  const alertCount = overview?.alerts?.length ?? 0;

  return (
    <header className="flex items-center gap-3 h-12 px-3 bg-background-panel border-b border-border-dim shrink-0 z-[100]">
      {/* ── Brand Block ─────────────────────────────────────────── */}
      <div className="flex items-center gap-2 mr-2">
        <div className="w-8 h-8 flex items-center justify-center bg-background-deep border border-border-dim rounded-sm">
          <Icon name="satellite" size={20} color="#8c9663" />
        </div>
        <div className="flex items-baseline gap-1 max-[900px]:hidden">
          <span className="font-mono text-base font-extrabold text-primary tracking-widest">TFAEL</span>
          <span className="font-mono text-2xs font-bold text-foreground-muted tracking-widest opacity-50">OMNI</span>
        </div>
      </div>

      {/* ── Workspace Tabs ──────────────────────────────────────── */}
      <nav className="flex items-center gap-0.5 flex-1 overflow-x-auto scrollbar-hide">
        {WORKSPACES.map(ws => {
          if (ws.perm && !hasPerm(ws.perm as never)) return null;
          const isActive = workspace === ws.id;
          return (
            <button
              key={ws.id}
              className={cn(
                'relative flex items-center gap-1.5 px-3 py-1.5 rounded-sm font-mono text-[11px] font-semibold uppercase tracking-wide whitespace-nowrap transition-colors',
                isActive
                  ? 'text-primary bg-background-card after:absolute after:bottom-0 after:left-2 after:right-2 after:h-0.5 after:bg-primary after:rounded-sm'
                  : 'text-foreground-muted hover:text-foreground hover:bg-background-card'
              )}
              onClick={() => setWorkspace(ws.id)}
              title={ws.label}
            >
              <Icon name={ws.icon} size={15} />
              <span className="max-[900px]:hidden">{ws.label}</span>
              {ws.id === 'siem' && alertCount > 0 && (
                <span className="bg-destructive text-white text-[9px] font-bold px-1.5 py-px rounded-lg min-w-[16px] text-center animate-pulse-red">
                  {alertCount > 99 ? '99+' : alertCount}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* ── Status Cluster ──────────────────────────────────────── */}
      <div className="flex items-center gap-2 ml-auto max-[900px]:gap-1">
        {/* UTC clock */}
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-sm bg-background-card border border-border-dim font-mono text-[11px]">
          <span className="text-foreground-muted text-2xs uppercase">UTC</span>
          <span className="text-foreground font-semibold">{utcTime}</span>
        </div>

        {/* Unit count */}
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-sm bg-background-card border border-border-dim font-mono text-[11px]">
          <span className={cn(
            'w-1.5 h-1.5 rounded-full',
            unitCount > 0 ? 'bg-accent-olive' : 'bg-secondary'
          )} />
          <span className="text-foreground-muted text-2xs uppercase">UNITS</span>
          <span className="text-foreground font-semibold">{unitCount}</span>
        </div>

        {/* User info */}
        <div className="flex items-center gap-1.5 px-2 py-1 font-mono text-[11px] text-foreground-muted max-[900px]:hidden">
          <Icon name="user" size={14} />
          <span className="text-foreground font-semibold">{user ?? '—'}</span>
          <span className="text-2xs opacity-50 uppercase">{role ?? ''}</span>
        </div>

        {/* Logout */}
        <button
          className="p-1 rounded-sm text-foreground-muted hover:text-destructive hover:bg-destructive/10 transition-colors"
          onClick={logout}
          title="Logout"
        >
          <Icon name="logout" size={16} />
        </button>
      </div>
    </header>
  );
}
