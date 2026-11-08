// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Graph Analysis Tools (Tailwind migration)
// Centrality, communities, shortest path, threat scores, attack paths
// ═══════════════════════════════════════════════════════════════════════

import { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import type {
  CentralityResult, CommunityResult, ShortestPathResult,
  ThreatScoreResult, AttackPathResult,
} from '@/types/api';
import {
  graphCentrality, graphCommunities, graphShortestPath,
  graphThreatScores, graphAttackPaths,
} from '@/api/endpoints';
import { useToast } from '@/hooks/useToast';

type ToolId = 'centrality' | 'communities' | 'shortest_path' | 'threat_scores' | 'attack_paths';

interface ToolDef {
  id: ToolId;
  icon: string;
  name: string;
  desc: string;
}

const TOOLS: ToolDef[] = [
  { id: 'centrality',    icon: '🎯', name: 'Centrality',    desc: 'Find most connected/influential nodes' },
  { id: 'communities',   icon: '🏘️', name: 'Communities',   desc: 'Detect clusters of related entities' },
  { id: 'shortest_path', icon: '🛤️', name: 'Shortest Path', desc: 'Find shortest link between two nodes' },
  { id: 'threat_scores', icon: '⚠️', name: 'Threat Scores', desc: 'Calculate risk scores for all nodes' },
  { id: 'attack_paths',  icon: '💀', name: 'Attack Paths',  desc: 'Discover potential attack vectors' },
];

// ── Tier badge classes ───────────────────────────────────────────────
const TIER_CLS: Record<string, string> = {
  CRITICAL: 'bg-[rgba(239,68,68,0.2)] text-[#fca5a5]',
  HIGH:     'bg-[rgba(245,158,11,0.2)] text-[#fbbf24]',
  MEDIUM:   'bg-[rgba(234,179,8,0.2)] text-[#fde047]',
};
const TIER_DEFAULT = 'bg-[rgba(34,197,94,0.2)] text-[#86efac]';

// ── Shared class strings ─────────────────────────────────────────────
const TOOL_CARD_BASE = 'p-3 bg-background-card border border-border-dim rounded-lg cursor-pointer transition-all text-center hover:border-border-accent';
const TOOL_CARD_ACTIVE = `${TOOL_CARD_BASE} !border-accent-steel !bg-[rgba(34,211,238,0.05)]`;
const INPUT_CLS = 'flex-1 py-[5px] px-2.5 bg-background-deep border border-border-dim rounded font-mono text-xs text-inherit focus:outline-none focus:border-accent-steel';

// ── Helper: extract display label from node (string or {id,type,label}) ──
function nodeLabel(n: unknown): string {
  if (typeof n === 'string') return n;
  if (n && typeof n === 'object') {
    const obj = n as Record<string, unknown>;
    return String(obj.label ?? obj.id ?? '');
  }
  return String(n);
}
function nodeKey(n: unknown, i: number): string {
  return typeof n === 'string' ? n : (n as any)?.id ?? String(i);
}

export function GraphAnalysis() {
  const [activeTool, setActiveTool] = useState<ToolId | null>(null);
  const [running, setRunning] = useState(false);
  const { toast } = useToast();

  // Inputs
  const [topN, setTopN] = useState('20');
  const [nodeA, setNodeA] = useState('');
  const [nodeB, setNodeB] = useState('');
  const [targetId, setTargetId] = useState('');

  // Results
  const [centralityResult, setCentralityResult] = useState<CentralityResult | null>(null);
  const [communityResult, setCommunityResult] = useState<CommunityResult | null>(null);
  const [pathResult, setPathResult] = useState<ShortestPathResult | null>(null);
  const [threatResult, setThreatResult] = useState<ThreatScoreResult | null>(null);
  const [attackResult, setAttackResult] = useState<AttackPathResult | null>(null);

  const runTool = useCallback(async () => {
    if (!activeTool) return;
    setRunning(true);
    try {
      switch (activeTool) {
        case 'centrality': {
          const res = await graphCentrality(parseInt(topN) || 20);
          if (res.ok) { setCentralityResult(res); toast('Centrality computed', 'success'); }
          else toast('Gagal menghitung centrality', 'error');
          break;
        }
        case 'communities': {
          const res = await graphCommunities();
          if (res.ok) { setCommunityResult(res); toast(`${res.total_communities} communities detected`, 'success'); }
          else toast('Gagal mendeteksi communities', 'error');
          break;
        }
        case 'shortest_path': {
          if (!nodeA.trim() || !nodeB.trim()) { toast('Masukkan kedua Node ID', 'error'); break; }
          const res = await graphShortestPath(nodeA.trim(), nodeB.trim());
          if (res.ok) { setPathResult(res); toast(res.found ? `Path ditemukan: ${res.hops} hops` : 'No path found', res.found ? 'success' : 'info'); }
          else toast('Gagal mencari path', 'error');
          break;
        }
        case 'threat_scores': {
          const res = await graphThreatScores(parseInt(topN) || 30);
          if (res.ok) { setThreatResult(res); toast(`${res.total_scored} nodes scored`, 'success'); }
          else toast('Gagal menghitung threat scores', 'error');
          break;
        }
        case 'attack_paths': {
          if (!targetId.trim()) { toast('Masukkan Target ID', 'error'); break; }
          const res = await graphAttackPaths(targetId.trim());
          if (res.ok) { setAttackResult(res); toast(`${res.paths.length} attack paths found`, 'success'); }
          else toast('Gagal mencari attack paths', 'error');
          break;
        }
      }
    } catch {
      toast('Analysis error', 'error');
    } finally {
      setRunning(false);
    }
  }, [activeTool, topN, nodeA, nodeB, targetId, toast]);

  return (
    <div className="p-3">
      {/* Tool selection */}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-2 mb-3.5">
        {TOOLS.map(t => (
          <div
            key={t.id}
            className={activeTool === t.id ? TOOL_CARD_ACTIVE : TOOL_CARD_BASE}
            onClick={() => setActiveTool(t.id)}
          >
            <div className="text-2xl mb-1">{t.icon}</div>
            <div className="text-[13px] font-bold font-mono">{t.name}</div>
            <div className="text-2xs opacity-50 font-mono mt-0.5">{t.desc}</div>
          </div>
        ))}
      </div>

      {/* Execution panel */}
      {activeTool && (
        <div className="mt-2.5 p-3.5 bg-background-card border border-border-dim rounded-lg">
          <div className="text-[13px] font-bold font-mono mb-2.5">
            {TOOLS.find(t => t.id === activeTool)?.icon}{' '}
            {TOOLS.find(t => t.id === activeTool)?.name}
          </div>

          {/* Centrality inputs */}
          {activeTool === 'centrality' && (
            <div className="flex items-center gap-2 mb-2 font-mono text-xs">
              <span className="min-w-[80px] text-2xs uppercase opacity-50">Top N</span>
              <input className={INPUT_CLS} type="number" value={topN} onChange={e => setTopN(e.target.value)} />
            </div>
          )}

          {/* Shortest path inputs */}
          {activeTool === 'shortest_path' && (
            <>
              <div className="flex items-center gap-2 mb-2 font-mono text-xs">
                <span className="min-w-[80px] text-2xs uppercase opacity-50">Node A</span>
                <input className={INPUT_CLS} value={nodeA} onChange={e => setNodeA(e.target.value)} placeholder="Node ID asal" />
              </div>
              <div className="flex items-center gap-2 mb-2 font-mono text-xs">
                <span className="min-w-[80px] text-2xs uppercase opacity-50">Node B</span>
                <input className={INPUT_CLS} value={nodeB} onChange={e => setNodeB(e.target.value)} placeholder="Node ID tujuan" />
              </div>
            </>
          )}

          {/* Threat scores input */}
          {activeTool === 'threat_scores' && (
            <div className="flex items-center gap-2 mb-2 font-mono text-xs">
              <span className="min-w-[80px] text-2xs uppercase opacity-50">Top N</span>
              <input className={INPUT_CLS} type="number" value={topN} onChange={e => setTopN(e.target.value)} />
            </div>
          )}

          {/* Attack paths input */}
          {activeTool === 'attack_paths' && (
            <div className="flex items-center gap-2 mb-2 font-mono text-xs">
              <span className="min-w-[80px] text-2xs uppercase opacity-50">Target ID</span>
              <input className={INPUT_CLS} value={targetId} onChange={e => setTargetId(e.target.value)} placeholder="Target node ID" />
            </div>
          )}

          <button
            className="py-1.5 px-4 border border-[#10b981] rounded bg-transparent text-[#10b981] font-mono text-[11px] cursor-pointer transition-all hover:bg-[#10b981] hover:text-black disabled:opacity-30 disabled:cursor-not-allowed"
            onClick={runTool}
            disabled={running}
          >
            {running ? '⏳ Analyzing…' : '▶ Run Analysis'}
          </button>
        </div>
      )}

      {/* ── Results ───────────────────────────────────────────────── */}

      {/* Centrality */}
      {activeTool === 'centrality' && centralityResult && (
        <div className="mt-2.5 p-3 bg-[#0c0a09] border border-border-dim rounded-md max-h-[400px] overflow-y-auto">
          <div className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2 font-mono font-bold">Centrality Ranking</div>
          <ul className="list-none m-0 p-0">
            {centralityResult.top.map((item, i) => (
              <li key={item.id} className="flex items-center gap-2 py-1 font-mono text-[11px] border-b border-white/[0.03]">
                <span className="min-w-[28px] text-center opacity-40 text-2xs">{i + 1}</span>
                <span className="flex-1 break-all">{item.id}</span>
                <span className="text-accent-steel min-w-[60px] text-right">{item.centrality.toFixed(4)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Communities */}
      {activeTool === 'communities' && communityResult && (
        <div className="mt-2.5 p-3 bg-[#0c0a09] border border-border-dim rounded-md max-h-[400px] overflow-y-auto">
          <div className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2 font-mono font-bold">
            {communityResult.total_communities} Communities Detected
          </div>
          <div className="flex flex-col gap-1.5">
            {communityResult.communities.map((c, i) => (
              <div key={i} className="py-1.5 px-2.5 bg-[rgba(167,139,250,0.05)] border border-[rgba(167,139,250,0.15)] rounded-md font-mono text-[11px]">
                <div className="font-bold text-[#c4b5fd] mb-0.5">Community #{i + 1} ({c.members.length} members)</div>
                <div className="text-2xs opacity-50 break-all">{c.members.map(m => nodeLabel(m)).join(', ')}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Shortest path */}
      {activeTool === 'shortest_path' && pathResult && (
        <div className="mt-2.5 p-3 bg-[#0c0a09] border border-border-dim rounded-md max-h-[400px] overflow-y-auto">
          <div className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2 font-mono font-bold">Shortest Path Result</div>
          {pathResult.found ? (
            <div>
              <div className="text-xl font-bold font-mono text-accent-steel mb-2">{pathResult.hops} hops</div>
              <div className="flex items-center gap-1 flex-wrap font-mono text-xs">
                {pathResult.path.map((node, i) => (
                  <span key={nodeKey(node, i)}>
                    <span className="py-[3px] px-2 bg-[rgba(34,211,238,0.1)] border border-[rgba(34,211,238,0.2)] rounded text-2xs">{nodeLabel(node)}</span>
                    {i < pathResult.path.length - 1 && <span className="opacity-30 mx-0.5"> → </span>}
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-center py-6 opacity-30 text-[13px] font-mono">No path found between the two nodes</div>
          )}
        </div>
      )}

      {/* Threat scores */}
      {activeTool === 'threat_scores' && threatResult && (
        <div className="mt-2.5 p-3 bg-[#0c0a09] border border-border-dim rounded-md max-h-[400px] overflow-y-auto">
          <div className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2 font-mono font-bold">
            {threatResult.total_scored} Nodes Scored
          </div>
          {threatResult.scored.map((item: any) => (
            <div key={item.id ?? item.node_id} className="flex items-center gap-2 py-1.5 border-b border-white/[0.03] font-mono text-[11px]">
              <span className={cn('py-0.5 px-1.5 rounded-[3px] text-[9px] font-bold uppercase min-w-[65px] text-center', TIER_CLS[item.tier] ?? TIER_DEFAULT)}>
                {item.tier}
              </span>
              <span className="flex-1 break-all">{item.label ?? item.id ?? item.node_id}</span>
              <span className="text-secondary min-w-[50px] text-right">{(item.threat_score ?? item.score ?? 0).toFixed(2)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Attack paths */}
      {activeTool === 'attack_paths' && attackResult && (
        <div className="mt-2.5 p-3 bg-[#0c0a09] border border-border-dim rounded-md max-h-[400px] overflow-y-auto">
          <div className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2 font-mono font-bold">
            {attackResult.paths.length} Attack Paths — Risk: {attackResult.assessment.risk_level}
          </div>
          {attackResult.paths.map((p, i) => (
            <div key={i} className="py-2 px-2.5 bg-[rgba(239,68,68,0.05)] border border-[rgba(239,68,68,0.15)] rounded-md mb-1.5">
              {p.vector && <div className="text-[11px] font-bold font-mono text-[#fca5a5] mb-1">{p.vector}</div>}
              <div className="text-2xs font-mono text-secondary mb-1">Weakness: {p.weakness_score.toFixed(2)}</div>
              <div className="flex items-center gap-1 flex-wrap font-mono text-xs">
                {p.path.map((node: any, j: number) => (
                  <span key={nodeKey(node, j)}>
                    <span className="py-[3px] px-2 bg-[rgba(34,211,238,0.1)] border border-[rgba(34,211,238,0.2)] rounded text-2xs">{nodeLabel(node)}</span>
                    {j < p.path.length - 1 && <span className="opacity-30 mx-0.5"> → </span>}
                  </span>
                ))}
              </div>
            </div>
          ))}
          {attackResult.pivot_points.length > 0 && (
            <>
              <div className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2 mt-2.5 font-mono font-bold">Pivot Points</div>
              {attackResult.pivot_points.map(pp => (
                <div key={(pp as any).id ?? pp.node_id} className="flex items-center gap-2 py-1 font-mono text-[11px] border-b border-white/[0.03]">
                  <span className="flex-1 break-all">{(pp as any).label ?? (pp as any).id ?? pp.node_id}</span>
                  <span className="text-accent-steel min-w-[60px] text-right">freq: {pp.frequency}</span>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}
