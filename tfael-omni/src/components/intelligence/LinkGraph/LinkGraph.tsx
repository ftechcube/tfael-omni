// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Intelligence Link Graph (Tailwind migration)
// D3.js v7 Force-Directed — unified cross-target link analysis
// ═══════════════════════════════════════════════════════════════════════

import { useRef, useEffect, useState, useCallback } from 'react';
import * as d3 from 'd3';
import { cn } from '@/lib/utils';
import type { GraphNode, GraphEdge } from '@/types/api';

type LayoutMode = 'force' | 'radial';

/* Node colours by type */
const NODE_COLORS: Record<string, string> = {
  person:       '#a78bfa',
  username:     '#60a5fa',
  email:        '#34d399',
  domain:       '#fbbf24',
  subdomain:    '#f59e0b',
  ip:           '#f87171',
  phone:        '#fb923c',
  platform:     '#22d3ee',
  organization: '#e879f9',
  location:     '#86efac',
  service:      '#94a3b8',
  breach:       '#ef4444',
};
const nodeColor = (t: string) => NODE_COLORS[t] ?? '#94a3b8';

const NODE_ICONS: Record<string, string> = {
  person: '👤', username: '🔑', email: '📧', domain: '🌐',
  subdomain: '🔗', ip: '🖥️', phone: '📱', platform: '✓',
  organization: '🏢', location: '📍', service: '⚙️', breach: '🔓',
};
const nodeIcon = (t: string) => NODE_ICONS[t] ?? '●';

// ── Button class helpers ─────────────────────────────────────────────

const TOOL_BTN = 'py-1 px-2.5 border border-border-dim rounded bg-transparent text-inherit font-mono text-2xs cursor-pointer transition-all hover:bg-background-card hover:border-border-accent';
const TOOL_BTN_ACTIVE = `${TOOL_BTN} !bg-accent-steel !text-black !border-accent-steel`;

interface LinkGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  loading?: boolean;
  onSelectNode?: (node: GraphNode) => void;
  onNeighborhood?: (nodeId: string) => void;
  onRebuild?: () => void;
}

export function LinkGraph({
  nodes, edges, loading, onSelectNode, onNeighborhood, onRebuild,
}: LinkGraphProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const simRef = useRef<d3.Simulation<GraphNode, GraphEdge> | null>(null);
  const [layout, setLayout] = useState<LayoutMode>('force');
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; node: GraphNode } | null>(null);

  useEffect(() => {
    const handler = () => setContextMenu(null);
    window.addEventListener('click', handler);
    return () => window.removeEventListener('click', handler);
  }, []);

  /* ── D3 render ───────────────────────────────────────────────── */
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg || !nodes.length) return;

    const width = svg.clientWidth || 800;
    const height = svg.clientHeight || 600;
    d3.select(svg).selectAll('*').remove();

    const simNodes: GraphNode[] = nodes.map(n => ({ ...n }));
    const simEdges: GraphEdge[] = edges.map(e => ({
      source: typeof e.source === 'string' ? e.source : e.source.id,
      target: typeof e.target === 'string' ? e.target : e.target.id,
      rel: e.rel ?? e.rel_type,
      last_seen: e.last_seen,
    }));

    const nodeIds = new Set(simNodes.map(n => n.id));
    const validEdges = simEdges.filter(
      e => nodeIds.has(e.source as string) && nodeIds.has(e.target as string),
    );

    const g = d3.select(svg).append('g');

    // Zoom
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.08, 5])
      .on('zoom', (event) => g.attr('transform', event.transform));
    d3.select(svg).call(zoom);

    // Arrow marker
    g.append('defs').append('marker')
      .attr('id', 'ig-arrow')
      .attr('viewBox', '0 0 10 10')
      .attr('refX', 28).attr('refY', 5)
      .attr('markerWidth', 5).attr('markerHeight', 5)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M 0 0 L 10 5 L 0 10 z')
      .attr('fill', '#555');

    // Simulation
    const sim = d3.forceSimulation<GraphNode>(simNodes)
      .force('link', d3.forceLink<GraphNode, GraphEdge>(validEdges)
        .id(d => d.id).distance(110).strength(0.35))
      .force('charge', d3.forceManyBody().strength(-260))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collide', d3.forceCollide(36));

    if (layout === 'radial') {
      sim.force('radial', d3.forceRadial(200, width / 2, height / 2));
    }
    simRef.current = sim;

    // Links
    const link = g.selectAll<SVGLineElement, GraphEdge>('.ig-link')
      .data(validEdges).join('line')
      .attr('stroke', '#333').attr('stroke-width', 1)
      .attr('marker-end', 'url(#ig-arrow)');

    // Link labels
    const linkLabel = g.selectAll<SVGTextElement, GraphEdge>('.ig-link-label')
      .data(validEdges).join('text')
      .attr('fill', '#555').attr('font-size', 7).attr('text-anchor', 'middle')
      .text(d => d.rel ?? '');

    // Node groups
    const node = g.selectAll<SVGGElement, GraphNode>('.ig-node')
      .data(simNodes).join('g')
      .attr('class', 'ig-node')
      .style('cursor', 'pointer')
      .call(d3.drag<SVGGElement, GraphNode>()
        .on('start', (event, d) => {
          if (!event.active) sim.alphaTarget(0.3).restart();
          d.fx = d.x; d.fy = d.y;
        })
        .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
        .on('end', (event, d) => {
          if (!event.active) sim.alphaTarget(0);
          d.fx = null; d.fy = null;
        }),
      );

    // Threat-score glow for high-risk nodes
    node.append('circle')
      .attr('r', d => {
        const risk = d.meta?.risk_score ?? 0;
        return risk >= 7 ? 28 : d.type === 'person' ? 22 : 16;
      })
      .attr('fill', d => nodeColor(d.type))
      .attr('stroke', d => {
        const risk = d.meta?.risk_score ?? 0;
        if (risk >= 8) return '#ef4444';
        if (risk >= 5) return '#f59e0b';
        return '#222';
      })
      .attr('stroke-width', d => (d.meta?.risk_score ?? 0) >= 7 ? 3 : 2)
      .attr('opacity', 0.9);

    // Node icons
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('font-size', d => d.type === 'person' ? 16 : 12)
      .text(d => nodeIcon(d.type));

    // Node labels
    node.append('text')
      .attr('dy', d => (d.type === 'person' ? 22 : 16) + 12)
      .attr('text-anchor', 'middle')
      .attr('fill', '#aaa').attr('font-size', 9)
      .attr('font-family', 'var(--font-mono)')
      .text(d => d.label.length > 22 ? d.label.slice(0, 22) + '…' : d.label);

    // Click → select
    node.on('click', (_event: MouseEvent, d: GraphNode) => {
      onSelectNode?.(d);
    });

    // Right-click → context menu
    node.on('contextmenu', (event: MouseEvent, d: GraphNode) => {
      event.preventDefault();
      event.stopPropagation();
      const rect = svg.getBoundingClientRect();
      setContextMenu({ x: event.clientX - rect.left, y: event.clientY - rect.top, node: d });
    });

    // Hover highlight
    node.on('mouseenter', function (_event, d) {
      link.attr('stroke', l => {
        const s = typeof l.source === 'object' ? l.source.id : l.source;
        const t = typeof l.target === 'object' ? l.target.id : l.target;
        return (s === d.id || t === d.id) ? nodeColor(d.type) : '#333';
      }).attr('stroke-width', l => {
        const s = typeof l.source === 'object' ? l.source.id : l.source;
        const t = typeof l.target === 'object' ? l.target.id : l.target;
        return (s === d.id || t === d.id) ? 2.5 : 1;
      });
    }).on('mouseleave', () => {
      link.attr('stroke', '#333').attr('stroke-width', 1);
    });

    // Tick
    sim.on('tick', () => {
      link
        .attr('x1', d => (d.source as GraphNode).x ?? 0)
        .attr('y1', d => (d.source as GraphNode).y ?? 0)
        .attr('x2', d => (d.target as GraphNode).x ?? 0)
        .attr('y2', d => (d.target as GraphNode).y ?? 0);
      linkLabel
        .attr('x', d => ((d.source as GraphNode).x! + (d.target as GraphNode).x!) / 2)
        .attr('y', d => ((d.source as GraphNode).y! + (d.target as GraphNode).y!) / 2 - 4);
      node.attr('transform', d => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    return () => { sim.stop(); };
  }, [nodes, edges, layout, onSelectNode]);

  /* ── Fit to viewport ─────────────────────────────────────────── */
  const handleFit = useCallback(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const g = d3.select(svg).select<SVGGElement>('g');
    const bbox = (g.node() as SVGGElement)?.getBBox();
    if (!bbox) return;
    const width = svg.clientWidth || 800;
    const height = svg.clientHeight || 600;
    const scale = Math.min(
      0.85 * width / (bbox.width || 1),
      0.85 * height / (bbox.height || 1),
      2,
    );
    const tx = width / 2 - (bbox.x + bbox.width / 2) * scale;
    const ty = height / 2 - (bbox.y + bbox.height / 2) * scale;
    d3.select(svg).transition().duration(600)
      .call(
        d3.zoom<SVGSVGElement, unknown>().transform as never,
        d3.zoomIdentity.translate(tx, ty).scale(scale),
      );
  }, []);

  /* ── Unique types for legend ─────────────────────────────────── */
  const nodeTypes = [...new Set(nodes.map(n => n.type))].sort();

  if (loading) {
    return (
      <div className="relative flex-1 flex flex-col overflow-hidden">
        <div className="flex items-center justify-center flex-1 font-mono text-[13px] opacity-40">
          ⏳ Loading link graph…
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex-1 flex flex-col overflow-hidden">
      <div className="flex items-center gap-2 py-2 px-3 border-b border-border-dim flex-wrap">
        <button className={TOOL_BTN} onClick={onRebuild}>🔄 Rebuild</button>
        <button className={TOOL_BTN} onClick={handleFit}>⊞ Fit</button>

        <div className="ml-auto flex gap-1">
          <button
            className={layout === 'force' ? TOOL_BTN_ACTIVE : TOOL_BTN}
            onClick={() => setLayout('force')}
          >Force</button>
          <button
            className={layout === 'radial' ? TOOL_BTN_ACTIVE : TOOL_BTN}
            onClick={() => setLayout('radial')}
          >Radial</button>
        </div>
      </div>

      <div className="flex gap-3.5 px-3 py-1.5 font-mono text-2xs opacity-50 border-b border-border-dim">
        <span className="whitespace-nowrap">Nodes: {nodes.length}</span>
        <span className="whitespace-nowrap">Edges: {edges.length}</span>
        <span className="whitespace-nowrap">Types: {nodeTypes.length}</span>
      </div>

      <div className="flex-1 relative min-h-0">
        <svg ref={svgRef} className="w-full h-full block" />

        {contextMenu && (
          <div
            className="absolute min-w-[160px] bg-background-surface border border-border-dim rounded-md shadow-[0_8px_24px_rgba(0,0,0,0.4)] z-[100] overflow-hidden"
            style={{ left: contextMenu.x, top: contextMenu.y }}
          >
            <button
              className="block w-full py-[7px] px-3 border-none bg-transparent text-inherit font-mono text-[11px] text-left cursor-pointer hover:bg-white/5"
              onClick={() => {
                onSelectNode?.(contextMenu.node);
                setContextMenu(null);
              }}
            >🔍 Detail</button>
            <button
              className="block w-full py-[7px] px-3 border-none bg-transparent text-inherit font-mono text-[11px] text-left cursor-pointer hover:bg-white/5"
              onClick={() => {
                onNeighborhood?.(contextMenu.node.id);
                setContextMenu(null);
              }}
            >🕸️ Neighborhood</button>
          </div>
        )}
      </div>

      {nodeTypes.length > 0 && (
        <div className="flex gap-2.5 flex-wrap px-3 py-1.5 border-t border-border-dim font-mono text-[9px] opacity-60">
          {nodeTypes.map(type => (
            <div key={type} className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full inline-block" style={{ background: nodeColor(type) }} />
              {type}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
