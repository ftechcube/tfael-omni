// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Cognitive Domain / BotRadar Workspace
// 4 inner tabs: Scrape Panel, BotRadar, Network Graph, Narrative Tracker
// ═══════════════════════════════════════════════════════════════════════

import { useState, useCallback } from 'react';
import { SubTabs } from '@/components/ui/Tabs/Tabs';
import { ScrapePanel } from '@/components/cognitive/ScrapePanel';
import { BotRadar } from '@/components/cognitive/BotRadar';
import { NetworkGraph } from '@/components/cognitive/NetworkGraph';
import { NarrativeTracker } from '@/components/cognitive/NarrativeTracker';

type CogTab = 'scrape' | 'botradar' | 'network' | 'narrative';

const INNER_TABS = [
  { id: 'scrape',    label: 'Scrape & Pipeline' },
  { id: 'botradar',  label: 'BotRadar' },
  { id: 'network',   label: 'Network Graph' },
  { id: 'narrative',  label: 'Narrative Intel' },
];

export default function CognitiveWorkspace() {
  const [tab, setTab] = useState<CogTab>('scrape');
  const [activeJobId, setActiveJobId] = useState<string | undefined>();

  const handleJobComplete = useCallback((jobId: string) => {
    setActiveJobId(jobId);
  }, []);

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <SubTabs
        tabs={INNER_TABS}
        active={tab}
        onChange={id => setTab(id as CogTab)}
      />

      <div className="flex-1 overflow-auto">
        {tab === 'scrape' && (
          <ScrapePanel onJobComplete={handleJobComplete} />
        )}

        {tab === 'botradar' && (
          <BotRadar jobId={activeJobId} />
        )}

        {tab === 'network' && (
          <NetworkGraph jobId={activeJobId} />
        )}

        {tab === 'narrative' && (
          <NarrativeTracker jobId={activeJobId} />
        )}
      </div>
    </div>
  );
}

