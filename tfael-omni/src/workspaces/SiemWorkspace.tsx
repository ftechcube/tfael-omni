// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — SIEM Workspace (Tailwind migration)
// 4 inner tabs: Alert Queue, Host Telemetry, SOAR Playbooks, MITRE ATT&CK
// ═══════════════════════════════════════════════════════════════════════

import { useState, useCallback } from 'react';
import type { SiemAlert } from '@/types/api';
import { useApp } from '@/context/AppContext';
import { SubTabs } from '@/components/ui/Tabs/Tabs';
import { AlertQueue } from '@/components/siem/AlertQueue/AlertQueue';
import { HostTelemetry } from '@/components/siem/HostTelemetry/HostTelemetry';
import { SoarPlaybooks } from '@/components/siem/SoarPlaybooks/SoarPlaybooks';
import { MitreMatrix } from '@/components/siem/MitreMatrix/MitreMatrix';

type SiemTab = 'alerts' | 'telemetry' | 'soar' | 'mitre';

const INNER_TABS = [
  { id: 'alerts',    label: 'Alert Queue' },
  { id: 'telemetry', label: 'Host Telemetry' },
  { id: 'soar',      label: 'SOAR Playbooks' },
  { id: 'mitre',     label: 'MITRE ATT&CK' },
];

export default function SiemWorkspace() {
  const [tab, setTab] = useState<SiemTab>('alerts');
  const [selectedAlert, setSelectedAlert] = useState<SiemAlert | null>(null);
  const { overview } = useApp();
  const alerts = overview?.siem_alerts ?? [];

  const handleSelectAlert = useCallback((alert: SiemAlert) => {
    setSelectedAlert(alert);
  }, []);

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <SubTabs
        tabs={INNER_TABS}
        active={tab}
        onChange={id => setTab(id as SiemTab)}
      />

      <div className="flex-1 overflow-auto">
        {tab === 'alerts' && (
          <AlertQueue
            alerts={alerts}
            onSelectAlert={handleSelectAlert}
          />
        )}

        {tab === 'telemetry' && (
          <HostTelemetry />
        )}

        {tab === 'soar' && (
          <SoarPlaybooks
            selectedAlert={selectedAlert}
          />
        )}

        {tab === 'mitre' && (
          <MitreMatrix
            alerts={alerts}
          />
        )}
      </div>
    </div>
  );
}
