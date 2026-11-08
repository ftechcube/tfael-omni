// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — MITRE ATT&CK Matrix (Tailwind migration)
// Visual tactic/technique grid with alert-hit highlighting
// ═══════════════════════════════════════════════════════════════════════

import { useMemo } from 'react';
import type { SiemAlert } from '@/types/api';
import { cn } from '@/lib/utils';

// ── MITRE ATT&CK Enterprise subset ───────────────────────────────────

interface Technique {
  id: string;
  name: string;
}

interface Tactic {
  id: string;
  name: string;
  techniques: Technique[];
}

const MITRE_TACTICS: Tactic[] = [
  {
    id: 'TA0001',
    name: 'Initial Access',
    techniques: [
      { id: 'T1566', name: 'Phishing' },
      { id: 'T1190', name: 'Exploit Public-Facing App' },
      { id: 'T1133', name: 'External Remote Services' },
      { id: 'T1078', name: 'Valid Accounts' },
      { id: 'T1199', name: 'Trusted Relationship' },
    ],
  },
  {
    id: 'TA0002',
    name: 'Execution',
    techniques: [
      { id: 'T1059', name: 'Command & Scripting' },
      { id: 'T1204', name: 'User Execution' },
      { id: 'T1203', name: 'Exploitation for Client Exec' },
      { id: 'T1053', name: 'Scheduled Task/Job' },
    ],
  },
  {
    id: 'TA0003',
    name: 'Persistence',
    techniques: [
      { id: 'T1547', name: 'Boot/Logon Autostart' },
      { id: 'T1136', name: 'Create Account' },
      { id: 'T1098', name: 'Account Manipulation' },
      { id: 'T1543', name: 'Create/Modify System Process' },
    ],
  },
  {
    id: 'TA0004',
    name: 'Privilege Escalation',
    techniques: [
      { id: 'T1548', name: 'Abuse Elevation Control' },
      { id: 'T1068', name: 'Exploitation for Priv Esc' },
      { id: 'T1055', name: 'Process Injection' },
    ],
  },
  {
    id: 'TA0005',
    name: 'Defense Evasion',
    techniques: [
      { id: 'T1070', name: 'Indicator Removal' },
      { id: 'T1036', name: 'Masquerading' },
      { id: 'T1027', name: 'Obfuscated Files/Info' },
      { id: 'T1562', name: 'Impair Defenses' },
    ],
  },
  {
    id: 'TA0006',
    name: 'Credential Access',
    techniques: [
      { id: 'T1110', name: 'Brute Force' },
      { id: 'T1003', name: 'OS Credential Dumping' },
      { id: 'T1558', name: 'Steal/Forge Kerberos Tix' },
      { id: 'T1539', name: 'Steal Web Session Cookie' },
    ],
  },
  {
    id: 'TA0007',
    name: 'Discovery',
    techniques: [
      { id: 'T1046', name: 'Network Service Discovery' },
      { id: 'T1082', name: 'System Info Discovery' },
      { id: 'T1087', name: 'Account Discovery' },
    ],
  },
  {
    id: 'TA0008',
    name: 'Lateral Movement',
    techniques: [
      { id: 'T1021', name: 'Remote Services' },
      { id: 'T1210', name: 'Exploitation of Remote Svc' },
      { id: 'T1080', name: 'Taint Shared Content' },
    ],
  },
  {
    id: 'TA0009',
    name: 'Collection',
    techniques: [
      { id: 'T1005', name: 'Data from Local System' },
      { id: 'T1114', name: 'Email Collection' },
      { id: 'T1056', name: 'Input Capture' },
    ],
  },
  {
    id: 'TA0011',
    name: 'Command & Control',
    techniques: [
      { id: 'T1071', name: 'Application Layer Protocol' },
      { id: 'T1572', name: 'Protocol Tunneling' },
      { id: 'T1105', name: 'Ingress Tool Transfer' },
      { id: 'T1090', name: 'Proxy' },
    ],
  },
  {
    id: 'TA0010',
    name: 'Exfiltration',
    techniques: [
      { id: 'T1048', name: 'Exfiltration Over Alt Protocol' },
      { id: 'T1041', name: 'Exfiltration Over C2 Channel' },
      { id: 'T1567', name: 'Exfil Over Web Service' },
    ],
  },
  {
    id: 'TA0040',
    name: 'Impact',
    techniques: [
      { id: 'T1486', name: 'Data Encrypted for Impact' },
      { id: 'T1490', name: 'Inhibit System Recovery' },
      { id: 'T1489', name: 'Service Stop' },
    ],
  },
];

// ── Component ─────────────────────────────────────────────────────────

interface MitreMatrixProps {
  alerts: SiemAlert[];
}

export function MitreMatrix({ alerts }: MitreMatrixProps) {
  // Build hit map from alert MITRE IDs
  const hitMap = useMemo(() => {
    const map = new Map<string, number>();
    alerts.forEach(a => {
      if (a.mitre_id) {
        // Match both T1234 and sub-techniques T1234.001
        const base = a.mitre_id.split('.')[0];
        map.set(base, (map.get(base) ?? 0) + 1);
      }
    });
    return map;
  }, [alerts]);

  const totalHits = useMemo(() => {
    let sum = 0;
    hitMap.forEach(v => { sum += v; });
    return sum;
  }, [hitMap]);

  const coveredTactics = useMemo(() => {
    return MITRE_TACTICS.filter(tactic =>
      tactic.techniques.some(tech => hitMap.has(tech.id))
    ).length;
  }, [hitMap]);

  return (
    <div className="p-3">
      {/* Legend */}
      <div className="flex items-center gap-3 mb-3 text-2xs font-mono opacity-60">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-sm inline-block bg-red-500" />
          Alert terdeteksi
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-sm inline-block bg-white/[0.08]" />
          Tidak ada alert
        </span>
        <span className="ml-auto">
          MITRE ATT&CK Enterprise v14
        </span>
      </div>

      {/* Matrix grid */}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(160px,1fr))] gap-2">
        {MITRE_TACTICS.map(tactic => (
          <div key={tactic.id} className="bg-background-card border border-border-dim rounded-lg overflow-hidden">
            <div className="px-2.5 py-2 bg-purple-500/[0.08] border-b border-border-dim text-[11px] font-bold font-mono text-purple-400 uppercase tracking-wide">
              {tactic.name}
            </div>
            <div className="p-1.5 flex flex-col gap-0.5">
              {tactic.techniques.map(tech => {
                const hits = hitMap.get(tech.id) ?? 0;
                const hasHit = hits > 0;
                return (
                  <div
                    key={tech.id}
                    className={cn(
                      'flex items-center gap-1.5 px-2 py-1 rounded text-2xs font-mono cursor-pointer transition-colors',
                      hasHit
                        ? 'bg-red-500/[0.08] border-l-2 border-l-red-500 hover:bg-red-500/[0.14]'
                        : 'hover:bg-white/[0.06]'
                    )}
                    title={`${tech.id}: ${tech.name}${hasHit ? ` (${hits} alert)` : ''}`}
                  >
                    <span className={cn(
                      'w-1.5 h-1.5 rounded-full shrink-0',
                      hasHit ? 'bg-red-500 shadow-[0_0_4px_#ef4444]' : 'bg-white/[0.08]'
                    )} />
                    <span className="opacity-50 min-w-[50px]">{tech.id}</span>
                    <span className="flex-1">{tech.name}</span>
                    {hasHit && (
                      <span className="px-1.5 py-px rounded-sm text-[9px] font-bold bg-red-500/20 text-red-300">
                        {hits}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Summary */}
      <div className="mt-3 px-3 py-2 bg-background-card border border-border-dim rounded-md text-2xs font-mono opacity-50 flex gap-4 flex-wrap">
        <span>Tactics: {MITRE_TACTICS.length}</span>
        <span>Techniques mapped: {MITRE_TACTICS.reduce((sum, t) => sum + t.techniques.length, 0)}</span>
        <span>Alert hits: {totalHits}</span>
        <span>Tactic coverage: {coveredTactics}/{MITRE_TACTICS.length}</span>
      </div>
    </div>
  );
}
