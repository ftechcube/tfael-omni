// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Bot Network Graph Visualizer
// Force-directed graph of bot vs organic account clusters
// ═══════════════════════════════════════════════════════════════════════

import { useState, useEffect, useCallback, useRef } from 'react';
import { cogNetworkGraph, cogIngestGraph } from '@/api/endpoints';
import type { CogGraphData } from '@/api/endpoints';
import { Icon } from '@/components/icons/Icon';
import { cn } from '@/lib/utils';

const CLUSTER_COLORS = [
  '#ef4444', '#f97316', '#eab308', '#22c55e', '#06b6d4',
  '#3b82f6', '#8b5cf6', '#ec4899', '#64748b', '#14b8a6',
];

const LABEL_COLORS: Record<string, string> = {
  BOT_CONFIRMED: '#ef4444',
  BOT_PROBABLE: '#f97316',
  SUSPICIOUS: '#eab308',
  UNCONFIRMED: '#22d3ee',
  LOW_SIGNAL: '#22c55e',
  CHANNEL: '#3b82f6',
};

interface Props {
  jobId?: string;
}

export function NetworkGraph({ jobId }: Props) {
  const [graphData, setGraphData] = useState<CogGraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [ingestResult, setIngestResult] = useState<any>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const loadGraph = useCallback(async () => {
    setLoading(true);
    try {
      const res = await cogNetworkGraph(jobId ? { job_id: jobId } : {});
      if (res?.ok) setGraphData(res);
    } catch { /* ignore */ }
    setLoading(false);
  }, [jobId]);

  useEffect(() => { loadGraph(); }, [loadGraph]);

  const handleIngest = async () => {
    setIngesting(true);
    try {
      const res = await cogIngestGraph(jobId ? { job_id: jobId } : {});
      if (res?.ok) setIngestResult(res.ingested);
    } catch { /* ignore */ }
    setIngesting(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-foreground-muted font-mono text-xs">
        <div className="w-5 h-5 border-2 border-border-dim border-t-primary rounded-full animate-spin mr-2" />
        Membangun graf jaringan...
      </div>
    );
  }

  if (!graphData || graphData.total_nodes === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-2 text-foreground-muted font-mono text-xs">
        <Icon name="graph" size={32} />
        <span>Belum ada data jaringan. Jalankan scraping terlebih dahulu.</span>
      </div>
    );
  }

  // Simple force-directed layout (computed once for simplicity)
  const W = 700, H = 450;
  const nodePositions = computeLayout(graphData.nodes, graphData.edges, W, H);

  const hoveredDetail = hoveredNode
    ? graphData.nodes.find(n => n.id === hoveredNode)
    : null;

  return (
    <div className="flex flex-col gap-3 p-3 h-full overflow-auto">
      {/* ── Stats Bar ─────────────────────────────────── */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-4 font-mono text-xs">
          <span className="text-foreground-muted">
            Nodes: <span className="text-foreground font-bold">{graphData.total_nodes}</span>
          </span>
          <span className="text-foreground-muted">
            Edges: <span className="text-foreground font-bold">{graphData.total_edges}</span>
          </span>
          <span className="text-foreground-muted">
            Communities: <span className="text-primary font-bold">{graphData.communities}</span>
          </span>
        </div>

        <div className="flex-1" />

        <button
          className={cn(
            'flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm font-mono text-[10px] font-bold uppercase transition-colors',
            ingesting
              ? 'bg-background-deep text-foreground-muted cursor-not-allowed'
              : 'bg-primary/20 text-primary border border-primary/30 hover:bg-primary/30'
          )}
          onClick={handleIngest}
          disabled={ingesting}
        >
          <Icon name="link" size={12} />
          {ingesting ? 'Ingesting...' : 'Push ke Intel Graph'}
        </button>

        {ingestResult && (
          <span className="text-[10px] text-green-400 font-mono">
            +{ingestResult.nodes} nodes, +{ingestResult.edges} edges, +{ingestResult.alerts} alerts
          </span>
        )}
      </div>

      <div className="flex gap-3 flex-1 min-h-0">
        {/* ── Graph SVG ────────────────────────────────── */}
        <div className="flex-1 bg-background-card border border-border-dim rounded-sm overflow-hidden relative">
          <svg
            ref={svgRef}
            viewBox={`0 0 ${W} ${H}`}
            className="w-full h-full"
            style={{ minHeight: 400 }}
          >
            <rect width={W} height={H} fill="transparent" />

            {/* Edges */}
            {graphData.edges.map((e, i) => {
              const src = nodePositions.get(e.source);
              const tgt = nodePositions.get(e.target);
              if (!src || !tgt) return null;
              return (
                <line
                  key={i}
                  x1={src.x} y1={src.y}
                  x2={tgt.x} y2={tgt.y}
                  stroke="#334155"
                  strokeWidth={Math.min(2, e.weight)}
                  opacity={0.4}
                />
              );
            })}

            {/* Nodes */}
            {graphData.nodes.map(node => {
              const pos = nodePositions.get(node.id);
              if (!pos) return null;
              const r = Math.max(4, Math.min(12, node.degree * 1.5 + 3));
              const color = LABEL_COLORS[node.bot_label] || '#64748b';
              const isHovered = hoveredNode === node.id;

              return (
                <g key={node.id}
                  onMouseEnter={() => setHoveredNode(node.id)}
                  onMouseLeave={() => setHoveredNode(null)}
                  style={{ cursor: 'pointer' }}
                >
                  {isHovered && (
                    <circle cx={pos.x} cy={pos.y} r={r + 3} fill="none" stroke={color} strokeWidth={2} opacity={0.6} />
                  )}
                  <circle
                    cx={pos.x} cy={pos.y} r={r}
                    fill={color}
                    opacity={isHovered ? 1 : 0.8}
                    stroke={isHovered ? '#fff' : 'none'}
                    strokeWidth={isHovered ? 1.5 : 0}
                  />
                  {r > 6 && (
                    <text
                      x={pos.x} y={pos.y + r + 10}
                      textAnchor="middle"
                      fill="#94a3b8"
                      fontSize={8}
                      fontFamily="monospace"
                    >
                      @{node.username.slice(0, 12)}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>

          {/* Legend */}
          <div className="absolute bottom-2 left-2 bg-background-deep/80 backdrop-blur-sm rounded-sm p-2 space-y-0.5">
            {Object.entries(LABEL_COLORS).map(([label, color]) => (
              <div key={label} className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                <span className="text-[9px] font-mono text-foreground-muted">{label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* ── Hover Detail ─────────────────────────────── */}
        <div className="w-64 bg-background-card border border-border-dim rounded-sm overflow-auto flex flex-col">
          <div className="px-3 py-2 border-b border-border-dim bg-background-panel">
            <span className="font-mono text-xs font-bold uppercase tracking-wide text-foreground">
              {hoveredDetail ? `@${hoveredDetail.username}` : 'Node Detail'}
            </span>
          </div>

          {hoveredDetail ? (
            <div className="p-3 space-y-2 font-mono text-xs">
              <Row label="Bot Score" value={`${hoveredDetail.bot_score.toFixed(1)}%`} />
              <Row label="Label" value={hoveredDetail.bot_label} />
              <Row label="Cluster" value={hoveredDetail.cluster_id >= 0 ? `C${hoveredDetail.cluster_id}` : '—'} />
              <Row label="Degree" value={String(hoveredDetail.degree)} />
              <Row label="Betweenness" value={hoveredDetail.betweenness.toFixed(4)} />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center flex-1 p-3 text-foreground-muted text-xs font-mono gap-1">
              <Icon name="target" size={20} />
              <span>Hover node untuk detail</span>
            </div>
          )}

          {/* Top accounts by degree */}
          <div className="border-t border-border-dim">
            <div className="px-3 py-1.5 bg-background-panel">
              <span className="text-[10px] font-mono font-bold text-foreground-muted uppercase">Top Influencers</span>
            </div>
            <div className="max-h-48 overflow-auto">
              {graphData.nodes
                .sort((a, b) => b.degree - a.degree)
                .slice(0, 10)
                .map(n => (
                  <div
                    key={n.id}
                    className="flex items-center gap-2 px-3 py-1 border-b border-border-dim/20 hover:bg-background-panel/50"
                    onMouseEnter={() => setHoveredNode(n.id)}
                    onMouseLeave={() => setHoveredNode(null)}
                  >
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: LABEL_COLORS[n.bot_label] || '#64748b' }} />
                    <span className="flex-1 text-[10px] text-foreground truncate">@{n.username}</span>
                    <span className="text-[9px] text-foreground-muted">d:{n.degree}</span>
                  </div>
                ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-foreground-muted">{label}:</span>
      <span className="text-foreground font-bold">{value}</span>
    </div>
  );
}

/**
 * Simple deterministic layout: assign positions in a circle per cluster,
 * with some jitter. Good enough for display without a physics simulation.
 */
function computeLayout(
  nodes: CogGraphData['nodes'],
  edges: CogGraphData['edges'],
  W: number, H: number,
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();

  // Group by cluster
  const clusters = new Map<number, typeof nodes>();
  for (const n of nodes) {
    const cid = n.cluster_id >= 0 ? n.cluster_id : -1;
    if (!clusters.has(cid)) clusters.set(cid, []);
    clusters.get(cid)!.push(n);
  }

  const clusterIds = Array.from(clusters.keys());
  const cx = W / 2, cy = H / 2;
  const orbitR = Math.min(W, H) * 0.32;

  clusterIds.forEach((cid, ci) => {
    const members = clusters.get(cid)!;
    // Cluster center angle
    const cAngle = (2 * Math.PI * ci) / Math.max(clusterIds.length, 1);
    const clusterCx = cx + orbitR * Math.cos(cAngle);
    const clusterCy = cy + orbitR * Math.sin(cAngle);

    // Spread members around cluster center
    const memberR = Math.min(80, 15 + members.length * 3);
    members.forEach((m, mi) => {
      const mAngle = (2 * Math.PI * mi) / Math.max(members.length, 1);
      const jitter = (seededRandom(m.id) - 0.5) * 20;
      positions.set(m.id, {
        x: Math.max(20, Math.min(W - 20, clusterCx + memberR * Math.cos(mAngle) + jitter)),
        y: Math.max(20, Math.min(H - 20, clusterCy + memberR * Math.sin(mAngle) + jitter)),
      });
    });
  });

  return positions;
}

function seededRandom(str: string): number {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = ((h << 5) - h + str.charCodeAt(i)) | 0;
  }
  return ((h & 0x7fffffff) % 1000) / 1000;
}

