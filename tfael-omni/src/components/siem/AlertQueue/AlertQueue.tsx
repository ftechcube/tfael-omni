// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — SIEM Alert Queue (Tailwind migration)
// Severity-filtered alert cards with MITRE ATT&CK tags, detail expand
// ═══════════════════════════════════════════════════════════════════════

import { useState, useCallback, useMemo } from 'react';
import type { SiemAlert } from '@/types/api';
import { simulateImpossibleTravel } from '@/api/endpoints';
import { useToast } from '@/hooks/useToast';
import { cn } from '@/lib/utils';

type SeverityFilter = 'all' | 'critical' | 'high' | 'medium' | 'low';

interface AlertQueueProps {
  alerts: SiemAlert[];
  onSelectAlert?: (alert: SiemAlert) => void;
}

const SEV_BORDER: Record<string, string> = {
  critical: 'border-l-severity-critical',
  high:     'border-l-severity-high',
  medium:   'border-l-severity-medium',
  low:      'border-l-severity-low',
};
const SEV_DOT: Record<string, string> = {
  critical: 'bg-severity-critical shadow-[0_0_6px_theme(colors.severity.critical)]',
  high:     'bg-severity-high',
  medium:   'bg-severity-medium',
  low:      'bg-severity-low',
};
const SEV_BADGE: Record<string, string> = {
  critical: 'bg-red-950 text-red-300',
  high:     'bg-orange-950 text-orange-400',
  medium:   'bg-amber-950 text-amber-300',
  low:      'bg-green-950 text-green-300',
};
const STATUS_CLS: Record<string, string> = {
  open:   'bg-red-500/15 text-red-300',
  acked:  'bg-yellow-500/15 text-yellow-300',
  closed: 'bg-green-500/15 text-green-300',
};
const STAT_COLORS: Record<string, string> = {
  critical: 'text-severity-critical',
  high:     'text-severity-high',
  medium:   'text-severity-medium',
  low:      'text-severity-low',
};

export function AlertQueue({ alerts, onSelectAlert }: AlertQueueProps) {
  const [filter, setFilter] = useState<SeverityFilter>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [simulating, setSimulating] = useState(false);
  const { toast } = useToast();

  const filtered = useMemo(() => {
    if (filter === 'all') return alerts;
    return alerts.filter(a => a.severity === filter);
  }, [alerts, filter]);

  const stats = useMemo(() => {
    const counts = { critical: 0, high: 0, medium: 0, low: 0 };
    alerts.forEach(a => { counts[a.severity]++; });
    return counts;
  }, [alerts]);

  const selected = useMemo(() =>
    filtered.find(a => a.id === selectedId) ?? null,
  [filtered, selectedId]);

  const handleSelect = useCallback((alert: SiemAlert) => {
    setSelectedId(prev => prev === alert.id ? null : alert.id);
    onSelectAlert?.(alert);
  }, [onSelectAlert]);

  const handleSimulate = useCallback(async () => {
    setSimulating(true);
    try {
      const res = await simulateImpossibleTravel();
      if (res.ok) {
        toast('Simulasi Impossible Travel dikirim', 'success');
      } else {
        toast('Gagal menjalankan simulasi', 'error');
      }
    } catch {
      toast('Gagal menjalankan simulasi', 'error');
    } finally {
      setSimulating(false);
    }
  }, [toast]);

  const fmtTime = (ts: string) => {
    try {
      return new Date(ts).toLocaleString('id-ID', {
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    } catch { return ts; }
  };

  const FILTERS: { key: SeverityFilter; label: string }[] = [
    { key: 'all', label: 'Semua' },
    { key: 'critical', label: 'Critical' },
    { key: 'high', label: 'High' },
    { key: 'medium', label: 'Medium' },
    { key: 'low', label: 'Low' },
  ];

  function KvRow({ label, children }: { label: string; children: React.ReactNode }) {
    return (
      <div className="flex gap-3 py-1 border-b border-white/[0.03] text-[11px] font-mono">
        <span className="min-w-[120px] opacity-50">{label}</span>
        <span className="flex-1 break-all">{children}</span>
      </div>
    );
  }

  return (
    <div className="p-3">
      {/* Stats bar */}
      <div className="flex gap-3 mb-3 flex-wrap">
        {(['critical', 'high', 'medium', 'low'] as const).map(sev => (
          <div key={sev} className="flex-1 min-w-[100px] px-3 py-2 bg-background-card border border-border-dim rounded-md text-center">
            <div className={cn('text-xl font-bold font-mono', STAT_COLORS[sev])}>
              {stats[sev]}
            </div>
            <div className="text-[9px] uppercase tracking-wide opacity-40 mt-0.5">{sev}</div>
          </div>
        ))}
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        {FILTERS.map(f => (
          <button
            key={f.key}
            className={cn(
              'px-2.5 py-1 border rounded font-mono text-2xs uppercase tracking-wide transition-colors',
              filter === f.key
                ? 'bg-primary border-primary text-black font-bold'
                : 'border-border-dim text-foreground-muted hover:border-primary hover:text-primary'
            )}
            onClick={() => setFilter(f.key)}
          >
            {f.label}
            {f.key !== 'all' ? ` (${stats[f.key]})` : ` (${alerts.length})`}
          </button>
        ))}
        <button
          className="ml-auto px-3 py-1 border border-secondary rounded font-mono text-2xs text-secondary hover:bg-secondary hover:text-black transition-colors disabled:opacity-50"
          onClick={handleSimulate}
          disabled={simulating}
        >
          {simulating ? '⏳' : '⚡'} Impossible Travel
        </button>
      </div>

      {/* Alert list */}
      {filtered.length === 0 ? (
        <div className="text-center py-10 px-4 opacity-30 text-[13px] font-mono">
          Tidak ada alert untuk filter ini
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {filtered.map(a => (
            <div
              key={a.id}
              className={cn(
                'flex items-start gap-2.5 px-3.5 py-2.5 bg-background-card border border-border-dim rounded-lg border-l-4 cursor-pointer transition-colors',
                SEV_BORDER[a.severity] ?? 'border-l-border-dim',
                selectedId === a.id && 'bg-primary/[0.04] border-primary'
              )}
              onClick={() => handleSelect(a)}
            >
              <div className={cn('w-2 h-2 rounded-full mt-1.5 shrink-0', SEV_DOT[a.severity])} />
              <div className="flex-1 min-w-0">
                <div className="text-[13px] font-semibold font-mono mb-0.5 flex items-center gap-1.5 flex-wrap">
                  <span>{a.title}</span>
                  <span className={cn('inline-flex px-1.5 py-px rounded-sm text-[9px] font-bold font-mono uppercase', SEV_BADGE[a.severity])}>
                    {a.severity.toUpperCase()}
                  </span>
                  {a.status && (
                    <span className={cn('inline-flex px-1.5 py-px rounded-sm text-[9px] font-semibold font-mono', STATUS_CLS[a.status?.toLowerCase()] ?? STATUS_CLS.open)}>
                      {a.status}
                    </span>
                  )}
                </div>
                <div className="text-2xs opacity-50 font-mono flex gap-2.5 flex-wrap">
                  <span>{fmtTime(a.timestamp)}</span>
                  {a.source_ip && <span>Src: {a.source_ip}</span>}
                  {a.dest_ip && <span>Dst: {a.dest_ip}</span>}
                  {a.mitre_id && (
                    <span className="inline-flex px-1.5 py-px bg-purple-500/15 border border-purple-500/30 rounded-sm text-[9px] font-bold text-purple-300 font-mono tracking-wide">
                      {a.mitre_id}{a.mitre_tactic ? ` — ${a.mitre_tactic}` : ''}
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Detail panel */}
      {selected && (
        <div className="mt-3 p-3.5 bg-background-card border border-border-dim rounded-lg">
          <div className="text-sm font-bold font-mono mb-2">Detail Alert: {selected.title}</div>
          <KvRow label="Alert ID">{selected.id}</KvRow>
          <KvRow label="Severity">
            <span className={cn('inline-flex px-1.5 py-px rounded-sm text-[9px] font-bold font-mono uppercase', SEV_BADGE[selected.severity])}>
              {selected.severity.toUpperCase()}
            </span>
          </KvRow>
          <KvRow label="Timestamp">{fmtTime(selected.timestamp)}</KvRow>
          {selected.source_ip && <KvRow label="Source IP">{selected.source_ip}</KvRow>}
          {selected.dest_ip && <KvRow label="Dest IP">{selected.dest_ip}</KvRow>}
          {selected.user_or_unit && <KvRow label="Unit / User">{selected.user_or_unit}</KvRow>}
          {selected.sigma_rule && <KvRow label="Sigma Rule">{selected.sigma_rule}</KvRow>}
          {selected.mitre_id && (
            <KvRow label="MITRE ATT&CK">
              <span className="inline-flex px-1.5 py-px bg-purple-500/15 border border-purple-500/30 rounded-sm text-[9px] font-bold text-purple-300 font-mono tracking-wide">
                {selected.mitre_id}
              </span>
              {selected.mitre_tactic && ` — ${selected.mitre_tactic}`}
            </KvRow>
          )}
          {selected.description && <KvRow label="Deskripsi">{selected.description}</KvRow>}
          {selected.distance_km != null && selected.distance_km > 0 && (
            <KvRow label="Jarak">{selected.distance_km.toLocaleString()} km</KvRow>
          )}
          {selected.velocity_kmh != null && selected.velocity_kmh > 0 && (
            <KvRow label="Kecepatan">{selected.velocity_kmh.toLocaleString()} km/jam</KvRow>
          )}
          {selected.soar_action_taken && <KvRow label="SOAR Action">{selected.soar_action_taken}</KvRow>}
          {selected.status && (
            <KvRow label="Status">
              <span className={cn('inline-flex px-1.5 py-px rounded-sm text-[9px] font-semibold font-mono', STATUS_CLS[selected.status?.toLowerCase()] ?? STATUS_CLS.open)}>
                {selected.status}
              </span>
            </KvRow>
          )}
        </div>
      )}
    </div>
  );
}
