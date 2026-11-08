// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — OSINT Knowledge Graph (Tailwind migration)
// D3.js v7 Force-Directed — Palantir / i2-style interactive link analysis
// ═══════════════════════════════════════════════════════════════════════

import { useRef, useEffect, useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import * as d3 from 'd3';
import type { KGNode, KGEdge } from '@/types/api';
import { kgColor, kgIcon, KG_COLORS } from '../helpers';

type LayoutMode = 'force' | 'radial';

interface KnowledgeGraphProps {
  nodes: KGNode[];
  edges: KGEdge[];
  onExpandNode?: (nodeId: string) => void;
}

export function KnowledgeGraph({ nodes, edges, onExpandNode }: KnowledgeGraphProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const simRef = useRef<d3.Simulation<KGNode, KGEdge> | null>(null);
  const [layout, setLayout] = useState<LayoutMode>('force');
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; node: KGNode } | null>(null);

  // Close context menu on click outside
  useEffect(() => {
    const handler = () => setContextMenu(null);
    window.addEventListener('click', handler);
    return () => window.removeEventListener('click', handler);
  }, []);

  // Main D3 render
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg || !nodes.length) return;

    const width = svg.clientWidth || 800;
    const height = svg.clientHeight || 600;

    // Clear previous
    d3.select(svg).selectAll('*').remove();

    // Clone data for D3 mutation
    const simNodes: KGNode[] = nodes.map(n => ({ ...n }));
    const simEdges: KGEdge[] = edges.map(e => ({
      source: typeof e.source === 'string' ? e.source : e.source.id,
      target: typeof e.target === 'string' ? e.target : e.target.id,
      rel: e.rel,
      label: e.label,
    }));

    // Filter edges to only those with valid nodes
    const nodeIds = new Set(simNodes.map(n => n.id));
    const validEdges = simEdges.filter(
      e => nodeIds.has(e.source as string) && nodeIds.has(e.target as string)
    );

    // Container group for zoom/pan
    const g = d3.select(svg)
      .append('g');

    // Zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });
    d3.select(svg).call(zoom);

    // Arrow marker
    g.append('defs').append('marker')
      .attr('id', 'kg-arrow')
      .attr('viewBox', '0 0 10 10')
      .attr('refX', 30)
      .attr('refY', 5)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M 0 0 L 10 5 L 0 10 z')
      .attr('fill', '#555');

    // Force simulation
    const sim = d3.forceSimulation<KGNode>(simNodes)
      .force('link', d3.forceLink<KGNode, KGEdge>(validEdges)
        .id(d => d.id)
        .distance(120)
        .strength(0.4))
      .force('charge', d3.forceManyBody().strength(-280))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collide', d3.forceCollide(40));

    if (layout === 'radial') {
      sim.force('radial', d3.forceRadial(180, width / 2, height / 2));
    }

    simRef.current = sim;

    // Links
    const link = g.selectAll<SVGLineElement, KGEdge>('.kg-link')
      .data(validEdges)
      .join('line')
      .attr('class', 'kg-link')
      .attr('stroke', '#333')
      .attr('stroke-width', 1)
      .attr('marker-end', 'url(#kg-arrow)');

    // Link labels
    const linkLabel = g.selectAll<SVGTextElement, KGEdge>('.kg-link-label')
      .data(validEdges)
      .join('text')
      .attr('class', 'kg-link-label')
      .attr('fill', '#555')
      .attr('font-size', 8)
      .attr('text-anchor', 'middle')
      .text(d => d.label ?? d.rel ?? '');

    // Node groups
    const node = g.selectAll<SVGGElement, KGNode>('.kg-node')
      .data(simNodes)
      .join('g')
      .attr('class', 'kg-node')
      .style('cursor', 'pointer')
      .call(d3.drag<SVGGElement, KGNode>()
        .on('start', (event, d) => {
          if (!event.active) sim.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event, d) => {
          if (!event.active) sim.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        })
      );

    // Node circles
    node.append('circle')
      .attr('r', d => d.type === 'person' ? 22 : 16)
      .attr('fill', d => kgColor(d.type))
      .attr('stroke', '#222')
      .attr('stroke-width', 2)
      .attr('opacity', 0.9);

    // Node icons (emoji)
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('font-size', d => d.type === 'person' ? 16 : 12)
      .text(d => kgIcon(d.type));

    // Node labels
    node.append('text')
      .attr('dy', d => (d.type === 'person' ? 22 : 16) + 12)
      .attr('text-anchor', 'middle')
      .attr('fill', '#aaa')
      .attr('font-size', 10)
      .attr('font-family', 'var(--font-mono)')
      .text(d => d.label.length > 20 ? d.label.slice(0, 20) + '…' : d.label);

    // Right-click context menu
    node.on('contextmenu', (event: MouseEvent, d: KGNode) => {
      event.preventDefault();
      event.stopPropagation();
      const rect = svg.getBoundingClientRect();
      setContextMenu({
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
        node: d,
      });
    });

    // Hover highlight
    node.on('mouseenter', function (_event, d) {
      d3.select(this).select('circle')
        .transition().duration(150)
        .attr('stroke', '#fff')
        .attr('stroke-width', 3);
      // Dim non-connected
      const connectedIds = new Set<string>();
      connectedIds.add(d.id);
      validEdges.forEach(e => {
        const src = typeof e.source === 'string' ? e.source : (e.source as KGNode).id;
        const tgt = typeof e.target === 'string' ? e.target : (e.target as KGNode).id;
        if (src === d.id) connectedIds.add(tgt);
        if (tgt === d.id) connectedIds.add(src);
      });
      node.attr('opacity', n => connectedIds.has(n.id) ? 1 : 0.2);
      link.attr('opacity', e => {
        const src = typeof e.source === 'string' ? e.source : (e.source as KGNode).id;
        const tgt = typeof e.target === 'string' ? e.target : (e.target as KGNode).id;
        return src === d.id || tgt === d.id ? 1 : 0.1;
      });
    });
    node.on('mouseleave', function () {
      d3.select(this).select('circle')
        .transition().duration(150)
        .attr('stroke', '#222')
        .attr('stroke-width', 2);
      node.attr('opacity', 1);
      link.attr('opacity', 1);
    });

    // Tick
    sim.on('tick', () => {
      link
        .attr('x1', d => (d.source as KGNode).x ?? 0)
        .attr('y1', d => (d.source as KGNode).y ?? 0)
        .attr('x2', d => (d.target as KGNode).x ?? 0)
        .attr('y2', d => (d.target as KGNode).y ?? 0);

      linkLabel
        .attr('x', d => (((d.source as KGNode).x ?? 0) + ((d.target as KGNode).x ?? 0)) / 2)
        .attr('y', d => (((d.source as KGNode).y ?? 0) + ((d.target as KGNode).y ?? 0)) / 2);

      node.attr('transform', d => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    // Initial zoom to fit
    setTimeout(() => {
      d3.select(svg).call(zoom.transform, d3.zoomIdentity);
    }, 500);

    return () => {
      sim.stop();
    };
  }, [nodes, edges, layout]);

  const handleLayoutToggle = useCallback(() => {
    setLayout(l => l === 'force' ? 'radial' : 'force');
  }, []);

  const handleResetZoom = useCallback(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const zoom = d3.zoom<SVGSVGElement, unknown>();
    d3.select(svg).transition().duration(500).call(zoom.transform, d3.zoomIdentity);
  }, []);

  const handleContextAction = useCallback((action: string) => {
    if (!contextMenu) return;
    if (action === 'expand' && onExpandNode) {
      onExpandNode(contextMenu.node.id);
    } else if (action === 'url' && contextMenu.node.data?.url) {
      window.open(contextMenu.node.data.url, '_blank');
    }
    setContextMenu(null);
  }, [contextMenu, onExpandNode]);

  // Empty state
  if (!nodes.length) {
    return (
      <div className="flex flex-col items-center justify-center w-full h-full min-h-[400px] opacity-30 text-[13px] font-mono gap-2">
        <div className="text-[32px]">🕸</div>
        <div>Lakukan scan, lalu klik "Build Graph"</div>
      </div>
    );
  }

  // Collect unique types for legend
  const types = [...new Set(nodes.map(n => n.type))];

  return (
    <div className="relative w-full h-full min-h-[400px] bg-[#0a0a0a] rounded-lg overflow-hidden">
      {/* Legend */}
      <div className="absolute top-2 left-2 flex flex-wrap gap-1.5 z-10">
        {types.map(t => (
          <div key={t} className="flex items-center gap-1 text-[9px] font-mono opacity-60">
            <div className="w-2 h-2 rounded-full" style={{ background: kgColor(t) }} />
            {t}
          </div>
        ))}
      </div>

      {/* Controls */}
      <div className="absolute top-2 right-2 flex flex-col gap-1 z-10">
        <button
          className={cn(
            'py-1 px-2.5 bg-black/70 border border-border-dim rounded text-foreground font-mono text-[10px] cursor-pointer whitespace-nowrap transition-all hover:border-accent-steel hover:text-accent-steel',
            layout === 'force' && 'border-[#10b981] text-[#10b981]',
          )}
          onClick={handleLayoutToggle}
        >
          {layout === 'force' ? '⚡ Force' : '🎯 Radial'}
        </button>
        <button
          className="py-1 px-2.5 bg-black/70 border border-border-dim rounded text-foreground font-mono text-[10px] cursor-pointer whitespace-nowrap transition-all hover:border-accent-steel hover:text-accent-steel"
          onClick={handleResetZoom}
        >
          🔄 Reset
        </button>
      </div>

      {/* Stats */}
      <div className="absolute bottom-2 left-2 text-[10px] font-mono text-foreground-muted opacity-60 z-10">
        {nodes.length} nodes · {edges.length} edges
      </div>

      {/* SVG canvas */}
      <svg ref={svgRef} className="w-full h-full cursor-grab active:cursor-grabbing" />

      {/* Context menu */}
      {contextMenu && (
        <div
          className="absolute bg-[#1c1917] border border-border-dim rounded-md py-1 min-w-[140px] z-20 shadow-[0_4px_16px_rgba(0,0,0,0.4)]"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          <button
            className="block w-full py-1.5 px-3 bg-transparent border-none text-foreground text-[11px] font-mono text-left cursor-pointer hover:bg-background-hover"
            onClick={() => handleContextAction('expand')}
          >
            🔍 Scan & Expand
          </button>
          {contextMenu.node.data?.url && (
            <button
              className="block w-full py-1.5 px-3 bg-transparent border-none text-foreground text-[11px] font-mono text-left cursor-pointer hover:bg-background-hover"
              onClick={() => handleContextAction('url')}
            >
              🔗 Buka URL
            </button>
          )}
        </div>
      )}
    </div>
  );
}
