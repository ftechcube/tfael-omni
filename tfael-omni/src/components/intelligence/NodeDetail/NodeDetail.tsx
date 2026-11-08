// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Node Detail Panel (Tailwind migration)
// Selected node properties, risk, target profile
// ═══════════════════════════════════════════════════════════════════════

import { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import type { GraphNode, TargetProfileResult } from '@/types/api';
import { graphTargetProfile, graphNeighborhood } from '@/api/endpoints';
import { useToast } from '@/hooks/useToast';

const NODE_ICONS: Record<string, string> = {
  person: '👤', username: '🔑', email: '📧', domain: '🌐',
  subdomain: '🔗', ip: '🖥️', phone: '📱', platform: '✓',
  organization: '🏢', location: '📍', service: '⚙️', breach: '🔓',
};

// ── Risk badge classes ───────────────────────────────────────────────
const RISK_CLS: Record<string, string> = {
  critical: 'bg-[rgba(239,68,68,0.2)] text-[#fca5a5]',
  high:     'bg-[rgba(245,158,11,0.2)] text-[#fbbf24]',
  medium:   'bg-[rgba(234,179,8,0.2)] text-[#fde047]',
  low:      'bg-[rgba(34,197,94,0.2)] text-[#86efac]',
};
const RISK_NONE = 'bg-[rgba(148,163,184,0.1)] text-[#94a3b8]';

const ACTION_BTN = 'py-[5px] px-3 border border-border-dim rounded bg-transparent text-inherit font-mono text-2xs cursor-pointer transition-all hover:border-accent-steel hover:bg-[rgba(34,211,238,0.05)] disabled:opacity-40 disabled:cursor-not-allowed';

interface NodeDetailProps {
  node: GraphNode | null;
  onNeighborhood?: (nodeId: string) => void;
}

export function NodeDetail({ node, onNeighborhood }: NodeDetailProps) {
  const [profile, setProfile] = useState<TargetProfileResult | null>(null);
  const [loadingProfile, setLoadingProfile] = useState(false);
  const { toast } = useToast();

  const handleProfile = useCallback(async () => {
    if (!node) return;
    setLoadingProfile(true);
    try {
      const res = await graphTargetProfile(node.id);
      if (res.ok) { setProfile(res); toast('Profile loaded', 'success'); }
      else toast('Gagal memuat profile', 'error');
    } catch { toast('Profile error', 'error'); }
    finally { setLoadingProfile(false); }
  }, [node, toast]);

  const handleNeighborhood = useCallback(async () => {
    if (!node) return;
    try {
      await graphNeighborhood(node.id);
      onNeighborhood?.(node.id);
      toast('Neighborhood loaded', 'success');
    } catch { toast('Neighborhood error', 'error'); }
  }, [node, onNeighborhood, toast]);

  if (!node) {
    return (
      <div className="p-3">
        <div className="text-center py-10 px-4 opacity-30 text-[13px] font-mono">
          Klik node pada graph untuk melihat detail
        </div>
      </div>
    );
  }

  const risk = node.meta?.risk_score;
  const riskLevel = node.meta?.risk_level;

  const riskClass = (() => {
    if (typeof riskLevel === 'string') {
      const rl = riskLevel.toLowerCase();
      if (RISK_CLS[rl]) return RISK_CLS[rl];
    }
    if (typeof risk === 'number') {
      if (risk >= 8) return RISK_CLS.critical;
      if (risk >= 5) return RISK_CLS.high;
      if (risk >= 3) return RISK_CLS.medium;
      return RISK_CLS.low;
    }
    return RISK_NONE;
  })();

  // Flatten meta + properties for KV display
  const allProps: [string, unknown][] = [];
  if (node.meta) {
    for (const [k, v] of Object.entries(node.meta)) {
      if (k !== 'risk_score' && k !== 'risk_level') allProps.push([k, v]);
    }
  }
  if (node.properties) {
    for (const [k, v] of Object.entries(node.properties)) {
      allProps.push([k, v]);
    }
  }

  const scoreColor = (val: number) => {
    if (val >= 0.7) return '#ef4444';
    if (val >= 0.4) return '#fbbf24';
    return '#22c55e';
  };

  return (
    <div className="p-3">
      {/* Header */}
      <div className="flex items-center gap-2.5 mb-3.5 pb-2.5 border-b border-border-dim">
        <span className="text-2xl">{NODE_ICONS[node.type] ?? '●'}</span>
        <div className="flex-1">
          <div className="text-base font-bold font-mono">{node.label}</div>
          <div className="text-2xs opacity-50 font-mono">{node.type}</div>
        </div>
        {(risk !== undefined || riskLevel) && (
          <span className={cn('py-0.5 px-2 rounded-[3px] text-2xs font-bold uppercase', riskClass)}>
            {riskLevel ?? `Risk ${risk}`}
          </span>
        )}
      </div>

      {/* Core info */}
      <div className="mb-3.5">
        <div className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2 font-mono font-bold">Identifiers</div>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-1.5">
          <div className="py-1.5 px-2.5 bg-background-card border border-border-dim rounded-md">
            <div className="text-[9px] uppercase tracking-[0.05em] opacity-50 font-mono mb-0.5">Node ID</div>
            <div className="text-xs font-mono break-all">{node.id}</div>
          </div>
          <div className="py-1.5 px-2.5 bg-background-card border border-border-dim rounded-md">
            <div className="text-[9px] uppercase tracking-[0.05em] opacity-50 font-mono mb-0.5">Label</div>
            <div className="text-xs font-mono break-all">{node.label}</div>
          </div>
          <div className="py-1.5 px-2.5 bg-background-card border border-border-dim rounded-md">
            <div className="text-[9px] uppercase tracking-[0.05em] opacity-50 font-mono mb-0.5">Type</div>
            <div className="text-xs font-mono break-all">{node.type}</div>
          </div>
          {risk !== undefined && (
            <div className="py-1.5 px-2.5 bg-background-card border border-border-dim rounded-md">
              <div className="text-[9px] uppercase tracking-[0.05em] opacity-50 font-mono mb-0.5">Risk Score</div>
              <div className="text-xs font-mono break-all">{risk}</div>
            </div>
          )}
        </div>
      </div>

      {/* Properties */}
      {allProps.length > 0 && (
        <div className="mb-3.5">
          <div className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2 font-mono font-bold">Properties</div>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-1.5">
            {allProps.map(([k, v]) => (
              <div key={k} className="py-1.5 px-2.5 bg-background-card border border-border-dim rounded-md">
                <div className="text-[9px] uppercase tracking-[0.05em] opacity-50 font-mono mb-0.5">{k}</div>
                <div className="text-xs font-mono break-all">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2 mb-3.5">
        <button className={ACTION_BTN} onClick={handleNeighborhood}>
          🕸️ Neighborhood
        </button>
        <button className={ACTION_BTN} onClick={handleProfile} disabled={loadingProfile}>
          {loadingProfile ? '⏳…' : '📊 Target Profile'}
        </button>
      </div>

      {/* Profile result */}
      {profile && (
        <div className="mt-2.5 p-3 bg-[#0c0a09] border border-border-dim rounded-md">
          <div className="text-[40px] font-extrabold font-mono text-center mb-1" style={{
            color: profile.profile_grade === 'A' ? '#ef4444'
              : profile.profile_grade === 'B' ? '#f59e0b'
              : profile.profile_grade === 'C' ? '#fbbf24'
              : '#22c55e',
          }}>
            {profile.profile_grade}
          </div>
          <div className="text-center font-mono text-xs opacity-60 mb-3">
            Exposure Score: {profile.profile_score.toFixed(1)} / 10
          </div>

          {/* Sub-scores */}
          {profile.scores && (
            <div className="mb-3.5">
              <div className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2 font-mono font-bold">Score Breakdown</div>
              {Object.entries(profile.scores)
                .filter(([, v]) => typeof v === 'number')
                .map(([k, v]) => (
                  <div key={k} className="flex items-center gap-2 py-1 font-mono text-[11px]">
                    <span className="min-w-[120px] capitalize text-2xs opacity-60">{k.replace(/_/g, ' ')}</span>
                    <div className="flex-1 h-2 bg-white/[0.04] rounded overflow-hidden">
                      <div
                        className="h-full rounded transition-[width] duration-500"
                        style={{
                          width: `${((v as number) / 10) * 100}%`,
                          background: scoreColor((v as number) / 10),
                        }}
                      />
                    </div>
                    <span className="min-w-[35px] text-right text-2xs opacity-50">{(v as number).toFixed(1)}</span>
                  </div>
                ))}
            </div>
          )}

          {/* Intelligence gaps */}
          {profile.intelligence_gaps.length > 0 && (
            <div className="mb-3.5">
              <div className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2 font-mono font-bold">Intelligence Gaps</div>
              <ul className="list-none m-0 p-0">
                {profile.intelligence_gaps.map((gap, i) => (
                  <li key={i} className="py-1 font-mono text-[11px] opacity-60 border-b border-white/[0.03] before:content-['⚠\_'] before:opacity-50">
                    {gap}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
