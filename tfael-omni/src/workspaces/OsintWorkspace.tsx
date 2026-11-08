// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — OSINT Profiler Workspace
// 4 inner tabs: Riwayat Scan, Scanner, Knowledge Graph, Dossier
// ═══════════════════════════════════════════════════════════════════════

import { useState, useCallback, useRef } from 'react';
import type { OsintSearchResult, OsintSearchType, ScanHistoryEntry, KGNode, KGEdge } from '@/types/api';
import {
  osintSearch, osintUsername, osintEmail, osintDomain,
  osintIp, osintPhone, osintGraph,
} from '@/api/endpoints';
import { HISTORY_KEY, HISTORY_MAX } from '@/components/osint/helpers';
import { useToast } from '@/hooks/useToast';

import { SubTabs } from '@/components/ui/Tabs/Tabs';
import { Panel } from '@/components/ui/Panel/Panel';
import { SearchBar } from '@/components/osint/SearchBar/SearchBar';
import { ResultsPanel } from '@/components/osint/ResultsPanel/ResultsPanel';
import { ScanHistory } from '@/components/osint/ScanHistory/ScanHistory';
import { KnowledgeGraph } from '@/components/osint/KnowledgeGraph/KnowledgeGraph';
import { EmailHeader } from '@/components/osint/EmailHeader/EmailHeader';
import { MetadataExtractor } from '@/components/osint/MetadataExtractor/MetadataExtractor';
import { TargetDossier } from '@/components/osint/TargetDossier/TargetDossier';

type OsintTab = 'history' | 'scanner' | 'graph' | 'dossier';

const INNER_TABS = [
  { id: 'history',  label: 'Riwayat Scan' },
  { id: 'scanner',  label: 'Scanner' },
  { id: 'graph',    label: 'Knowledge Graph' },
  { id: 'dossier',  label: 'Dossier & Pelacakan' },
];

// ── localStorage helpers ───────────────────────────────────────────────

function loadHistory(): ScanHistoryEntry[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as ScanHistoryEntry[];
  } catch {
    return [];
  }
}

function saveHistory(entries: ScanHistoryEntry[]) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(entries.slice(0, HISTORY_MAX)));
  } catch { /* quota exceeded — silently ignore */ }
}

// ════════════════════════════════════════════════════════════════════════

export default function OsintWorkspace() {
  const [tab, setTab] = useState<OsintTab>('scanner');
  const [loading, setLoading] = useState(false);
  const [scanResult, setScanResult] = useState<OsintSearchResult | null>(null);
  const [history, setHistory] = useState<ScanHistoryEntry[]>(loadHistory);

  // Knowledge graph state
  const [kgNodes, setKgNodes] = useState<KGNode[]>([]);
  const [kgEdges, setKgEdges] = useState<KGEdge[]>([]);

  const { toast } = useToast();

  // ── Scan ──────────────────────────────────────────────────────────────

  const handleSearch = useCallback(async (query: string, type: OsintSearchType = 'name') => {
    setLoading(true);
    try {
      let res: OsintSearchResult;
      switch (type) {
        case 'username': res = await osintUsername(query); break;
        case 'email':    res = await osintEmail(query);    break;
        case 'domain':   res = await osintDomain(query);   break;
        case 'ip':       res = await osintIp(query);       break;
        case 'phone':    res = await osintPhone(query);    break;
        default:         res = await osintSearch(query);   break;
      }
      setScanResult(res);

      // Save to history
      const entry: ScanHistoryEntry = {
        ts: new Date().toISOString(),
        type: res.type ?? 'name',
        query,
        ok: res.ok,
        data: res,
      };
      const updated = [entry, ...history].slice(0, HISTORY_MAX);
      setHistory(updated);
      saveHistory(updated);

      if (!res.ok) {
        toast((res as Record<string, unknown>).error as string ?? 'Scan gagal', 'error');
      }
    } catch {
      toast('Gagal menjalankan scan', 'error');
    } finally {
      setLoading(false);
    }
  }, [history, toast]);

  // ── Build Knowledge Graph ────────────────────────────────────────────

  const handleBuildGraph = useCallback(async () => {
    if (!scanResult) return;
    try {
      const res = await osintGraph(scanResult);
      if (res.ok && res.nodes && res.edges) {
        // Merge new nodes/edges with existing
        const existingIds = new Set(kgNodes.map(n => n.id));
        const newNodes = res.nodes.filter(n => !existingIds.has(n.id));
        const allNodes = [...kgNodes, ...newNodes];
        const allEdges = [...kgEdges, ...res.edges];
        setKgNodes(allNodes);
        setKgEdges(allEdges);
        setTab('graph');
        toast(`Graph: ${allNodes.length} node, ${allEdges.length} edge`, 'success');
      } else {
        toast('Gagal membangun graph', 'error');
      }
    } catch {
      toast('Gagal membangun graph', 'error');
    }
  }, [scanResult, kgNodes, kgEdges, toast]);

  // ── Expand node in graph (scan & merge) ──────────────────────────────

  const handleExpandNode = useCallback(async (nodeId: string) => {
    const node = kgNodes.find(n => n.id === nodeId);
    if (!node) return;
    try {
      const res = await osintSearch(node.label);
      if (res.ok) {
        const graphRes = await osintGraph(res);
        if (graphRes.ok && graphRes.nodes && graphRes.edges) {
          const existingIds = new Set(kgNodes.map(n => n.id));
          const newNodes = graphRes.nodes.filter(n => !existingIds.has(n.id));
          setKgNodes(prev => [...prev, ...newNodes]);
          setKgEdges(prev => [...prev, ...graphRes.edges!]);
          toast(`+${newNodes.length} node dari expand "${node.label}"`, 'success');
        }
      }
    } catch {
      toast('Gagal expand node', 'error');
    }
  }, [kgNodes, toast]);

  // ── Save to Dossier ──────────────────────────────────────────────────

  const handleSaveToDossier = useCallback(() => {
    setTab('dossier');
  }, []);

  // ── Scan username from results (candidates click) ────────────────────

  const handleScanUsername = useCallback((username: string) => {
    handleSearch(username);
  }, [handleSearch]);

  // ── Export PDF ────────────────────────────────────────────────────────

  const handleExport = useCallback(() => {
    if (!scanResult) return;
    // Open a printable window
    const w = window.open('', '_blank');
    if (!w) return;
    w.document.write(`
      <html><head><title>TFAEL OSINT Report</title>
      <style>body{font-family:monospace;background:#fff;color:#000;padding:24px}
      pre{white-space:pre-wrap;font-size:11px}</style>
      </head><body>
      <h1>TFAEL OSINT — ${scanResult.type?.toUpperCase()} Report</h1>
      <p>Query: <strong>${scanResult.query}</strong></p>
      <p>Timestamp: ${new Date().toISOString()}</p>
      <hr>
      <pre>${JSON.stringify(scanResult, null, 2)}</pre>
      <script>window.print();</script>
      </body></html>
    `);
    w.document.close();
  }, [scanResult]);

  // ── History management ───────────────────────────────────────────────

  const handleClearHistory = useCallback(() => {
    setHistory([]);
    saveHistory([]);
    toast('Riwayat dihapus', 'success');
  }, [toast]);

  const handleLoadScan = useCallback((entry: ScanHistoryEntry) => {
    setScanResult(entry.data);
    setTab('scanner');
  }, []);

  // ── Graph data for dossier ───────────────────────────────────────────

  const graphData = kgNodes.length > 0 ? { nodes: kgNodes, edges: kgEdges } : null;

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Inner tabs */}
      <SubTabs
        tabs={INNER_TABS}
        active={tab}
        onChange={id => setTab(id as OsintTab)}
      />

      {/* Tab content */}
      <div className="flex-1 overflow-auto">
        {/* ── Riwayat Scan ────────────────────────────────────────── */}
        {tab === 'history' && (
          <ScanHistory
            history={history}
            onClear={handleClearHistory}
            onLoadScan={handleLoadScan}
          />
        )}

        {/* ── Scanner ─────────────────────────────────────────────── */}
        {tab === 'scanner' && (
          <>
            <SearchBar
              onSearch={handleSearch}
              onExport={handleExport}
              loading={loading}
              hasResult={!!scanResult}
            />

            {scanResult && (
              <div className="px-3.5 pb-3.5">
                <ResultsPanel
                  data={scanResult}
                  onBuildGraph={handleBuildGraph}
                  onSaveToDossier={handleSaveToDossier}
                  onScanUsername={handleScanUsername}
                />
              </div>
            )}

            {/* Sub-tools: Email Header + Metadata Extractor */}
            <div className="px-3.5 pb-3.5 flex gap-3 flex-wrap">
              <Panel title="Email Header Analyzer" icon="📧" className="flex-1 min-w-[300px]">
                <EmailHeader />
              </Panel>
              <Panel title="Metadata Extractor" icon="📎" className="flex-1 min-w-[300px]">
                <MetadataExtractor />
              </Panel>
            </div>
          </>
        )}

        {/* ── Knowledge Graph ─────────────────────────────────────── */}
        {tab === 'graph' && (
          <div className="h-[calc(100vh-160px)] p-3.5">
            <KnowledgeGraph
              nodes={kgNodes}
              edges={kgEdges}
              onExpandNode={handleExpandNode}
            />
          </div>
        )}

        {/* ── Dossier & Pelacakan ─────────────────────────────────── */}
        {tab === 'dossier' && (
          <TargetDossier
            scanResult={scanResult}
            graphData={graphData}
          />
        )}
      </div>
    </div>
  );
}
