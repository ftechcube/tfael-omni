// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Graph Statistics (Tailwind migration)
// Summary cards + type distribution bars
// ═══════════════════════════════════════════════════════════════════════

import { useState, useEffect } from 'react';
import type { GraphStatsResponse } from '@/types/api';
import { fetchGraphStats } from '@/api/endpoints';

const TYPE_COLORS: Record<string, string> = {
  person: '#a78bfa', username: '#60a5fa', email: '#34d399',
  domain: '#fbbf24', ip: '#f87171', phone: '#fb923c',
  platform: '#22d3ee', organization: '#e879f9', location: '#86efac',
  service: '#94a3b8', breach: '#ef4444',
};

/** Normalize API response — handle both old format (node_types object)
    and new format (top_types array + total_targets). */
function normalizeStats(raw: GraphStatsResponse) {
  // Derive top_types from node_types dict if not present
  const topTypes: Array<{ type: string; count: number }> =
    raw.top_types ??
    Object.entries(raw.node_types ?? {})
      .map(([type, count]) => ({ type, count }))
      .sort((a, b) => b.count - a.count);

  // Derive total_targets from node_types.person if not present
  const totalTargets: number =
    raw.total_targets ?? raw.node_types?.person ?? 0;

  return { ...raw, top_types: topTypes, total_targets: totalTargets };
}

export function GraphStats() {
  const [stats, setStats] = useState<ReturnType<typeof normalizeStats> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        const res = await fetchGraphStats();
        if (!cancel && res.ok) setStats(normalizeStats(res));
      } catch (e) { console.error('GraphStats fetch error', e); }
      if (!cancel) setLoading(false);
    })();
    return () => { cancel = true; };
  }, []);

  if (loading) return <div className="p-3"><div className="text-center py-10 px-4 opacity-40 text-[13px] font-mono">⏳ Loading stats…</div></div>;
  if (!stats) return <div className="p-3"><div className="text-center py-10 px-4 opacity-40 text-[13px] font-mono">Tidak ada data statistik graph</div></div>;

  const topTypes = stats.top_types ?? [];
  const maxCount = Math.max(1, ...topTypes.map(t => t.count));

  return (
    <div className="p-3">
      <div className="grid grid-cols-[repeat(auto-fill,minmax(130px,1fr))] gap-2 mb-3.5">
        <div className="p-3 px-3.5 bg-background-card border border-border-dim rounded-lg text-center">
          <div className="text-[28px] font-extrabold font-mono leading-none text-[#22d3ee]">{stats.total_nodes}</div>
          <div className="text-[9px] uppercase tracking-[0.06em] opacity-50 font-mono mt-1">Total Nodes</div>
        </div>
        <div className="p-3 px-3.5 bg-background-card border border-border-dim rounded-lg text-center">
          <div className="text-[28px] font-extrabold font-mono leading-none text-[#a78bfa]">{stats.total_edges}</div>
          <div className="text-[9px] uppercase tracking-[0.06em] opacity-50 font-mono mt-1">Total Edges</div>
        </div>
        <div className="p-3 px-3.5 bg-background-card border border-border-dim rounded-lg text-center">
          <div className="text-[28px] font-extrabold font-mono leading-none text-[#fbbf24]">{stats.total_targets}</div>
          <div className="text-[9px] uppercase tracking-[0.06em] opacity-50 font-mono mt-1">Targets</div>
        </div>
        <div className="p-3 px-3.5 bg-background-card border border-border-dim rounded-lg text-center">
          <div className="text-[28px] font-extrabold font-mono leading-none text-[#34d399]">{topTypes.length}</div>
          <div className="text-[9px] uppercase tracking-[0.06em] opacity-50 font-mono mt-1">Node Types</div>
        </div>
      </div>

      {topTypes.length > 0 && (
        <div className="mb-3.5">
          <div className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2 font-mono font-bold">
            Node Type Distribution
          </div>
          {topTypes.map(({ type, count }) => (
            <div key={type} className="flex items-center gap-2 py-[5px] font-mono text-xs">
              <span className="min-w-[100px] capitalize">{type}</span>
              <div className="flex-1 h-2.5 bg-white/[0.04] rounded-[5px] overflow-hidden">
                <div
                  className="h-full rounded-[5px] transition-[width] duration-500"
                  style={{
                    width: `${(count / maxCount) * 100}%`,
                    background: TYPE_COLORS[type] ?? '#94a3b8',
                  }}
                />
              </div>
              <span className="min-w-[40px] text-right opacity-50 text-2xs">{count}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
