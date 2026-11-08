// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Intelligence Graph Workspace (Tailwind migration)
// 4 inner tabs: Link Graph, Statistics, Analysis Tools, Node Detail
// ═══════════════════════════════════════════════════════════════════════

import { useState, useEffect, useCallback } from 'react';
import type { GraphNode, GraphEdge } from '@/types/api';
import { fetchLinkGraph, graphRebuild } from '@/api/endpoints';
import { useToast } from '@/hooks/useToast';
import { SubTabs } from '@/components/ui/Tabs/Tabs';
import { LinkGraph } from '@/components/intelligence/LinkGraph/LinkGraph';
import { GraphStats } from '@/components/intelligence/GraphStats/GraphStats';
import { GraphAnalysis } from '@/components/intelligence/GraphAnalysis/GraphAnalysis';
import { NodeDetail } from '@/components/intelligence/NodeDetail/NodeDetail';

type IntelTab = 'graph' | 'stats' | 'analysis' | 'detail';

const INNER_TABS = [
  { id: 'graph',    label: 'Link Graph' },
  { id: 'stats',    label: 'Statistics' },
  { id: 'analysis', label: 'Analysis Tools' },
  { id: 'detail',   label: 'Node Detail' },
];

export default function IntelligenceWorkspace() {
  const [tab, setTab] = useState<IntelTab>('graph');
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const { toast } = useToast();

  const loadGraph = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchLinkGraph();
      if (res.ok) {
        setNodes(res.nodes ?? []);
        setEdges(res.edges ?? []);
      }
    } catch { /* swallow */ }
    setLoading(false);
  }, []);

  useEffect(() => { loadGraph(); }, [loadGraph]);

  const handleSelectNode = useCallback((node: GraphNode) => {
    setSelectedNode(node);
    setTab('detail');
  }, []);

  const handleRebuild = useCallback(async () => {
    try {
      const res = await graphRebuild();
      if (res.ok) {
        toast('Graph rebuild dimulai', 'success');
        await loadGraph();
      } else {
        toast('Gagal rebuild graph', 'error');
      }
    } catch { toast('Rebuild error', 'error'); }
  }, [loadGraph, toast]);

  const handleNeighborhood = useCallback((_nodeId: string) => {
    // Neighborhood data already fetched via API and graph is refreshed
    loadGraph();
  }, [loadGraph]);

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <SubTabs
        tabs={INNER_TABS}
        active={tab}
        onChange={id => setTab(id as IntelTab)}
      />

      <div className="flex-1 overflow-auto flex flex-col">
        {tab === 'graph' && (
          <LinkGraph
            nodes={nodes}
            edges={edges}
            loading={loading}
            onSelectNode={handleSelectNode}
            onNeighborhood={handleNeighborhood}
            onRebuild={handleRebuild}
          />
        )}

        {tab === 'stats' && <GraphStats />}

        {tab === 'analysis' && <GraphAnalysis />}

        {tab === 'detail' && (
          <NodeDetail
            node={selectedNode}
            onNeighborhood={handleNeighborhood}
          />
        )}
      </div>
    </div>
  );
}
