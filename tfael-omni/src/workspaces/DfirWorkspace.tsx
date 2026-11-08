// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — DFIR Workspace (Tailwind migration)
// 3 inner tabs: Evidence Board, Chain of Custody, Forensic Analysis
// ═══════════════════════════════════════════════════════════════════════

import { useState, useCallback } from 'react';
import type { ForensicEvidence } from '@/types/api';
import { useApp } from '@/context/AppContext';
import { SubTabs } from '@/components/ui/Tabs/Tabs';
import { EvidenceBoard } from '@/components/dfir/EvidenceBoard/EvidenceBoard';
import { ChainOfCustody } from '@/components/dfir/ChainOfCustody/ChainOfCustody';
import { ForensicAnalysis } from '@/components/dfir/ForensicAnalysis/ForensicAnalysis';

type DfirTab = 'evidence' | 'chain' | 'analysis';

const INNER_TABS = [
  { id: 'evidence', label: 'Evidence Board' },
  { id: 'chain',    label: 'Chain of Custody' },
  { id: 'analysis', label: 'Forensic Analysis' },
];

export default function DfirWorkspace() {
  const [tab, setTab] = useState<DfirTab>('evidence');
  const [selectedEvidence, setSelectedEvidence] = useState<ForensicEvidence | null>(null);
  const { overview, refreshOverview } = useApp();
  const evidences = overview?.forensic_evidences ?? [];

  // Chain of custody from overview (if available) or empty
  const chain = (overview as Record<string, unknown>)?.chain_of_custody as
    import('@/types/api').ChainOfCustody[] | undefined;

  const handleSelect = useCallback((ev: ForensicEvidence) => {
    setSelectedEvidence(ev);
    setTab('analysis');
  }, []);

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <SubTabs
        tabs={INNER_TABS}
        active={tab}
        onChange={id => setTab(id as DfirTab)}
      />

      <div className="flex-1 overflow-auto">
        {tab === 'evidence' && (
          <EvidenceBoard
            evidences={evidences}
            onSelect={handleSelect}
            onRefresh={refreshOverview}
          />
        )}

        {tab === 'chain' && (
          <ChainOfCustody chain={chain} />
        )}

        {tab === 'analysis' && (
          <ForensicAnalysis evidence={selectedEvidence} />
        )}
      </div>
    </div>
  );
}
