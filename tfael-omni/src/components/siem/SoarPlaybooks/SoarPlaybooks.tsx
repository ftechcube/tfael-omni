// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — SOAR Playbooks (Tailwind migration)
// Predefined response actions: block IP, isolate host, snapshot, etc.
// ═══════════════════════════════════════════════════════════════════════

import { useState, useCallback } from 'react';
import type { SiemAlert } from '@/types/api';
import { runSoarPlaybook } from '@/api/endpoints';
import { useToast } from '@/hooks/useToast';
import { cn } from '@/lib/utils';

interface Playbook {
  id: string;
  name: string;
  icon: string;
  description: string;
  action: string;
  paramLabel?: string;
  paramPlaceholder?: string;
}

const PLAYBOOKS: Playbook[] = [
  {
    id: 'block-ip',
    name: 'Block IP',
    icon: '🚫',
    description: 'Tambah IP ke firewall blacklist dan log ke SIEM',
    action: 'block_ip',
    paramLabel: 'IP Address',
    paramPlaceholder: '192.168.1.100',
  },
  {
    id: 'isolate-host',
    name: 'Isolate Host',
    icon: '🔒',
    description: 'Isolasi host dari jaringan, pertahankan akses forensik',
    action: 'isolate_host',
    paramLabel: 'Hostname',
    paramPlaceholder: 'workstation-07',
  },
  {
    id: 'snapshot',
    name: 'Snapshot & Preserve',
    icon: '📸',
    description: 'Ambil snapshot memory dan disk untuk forensik',
    action: 'snapshot',
    paramLabel: 'Target ID',
    paramPlaceholder: 'target-id atau hostname',
  },
  {
    id: 'kill-process',
    name: 'Kill Process',
    icon: '💀',
    description: 'Terminasi proses berbahaya pada endpoint',
    action: 'kill_process',
    paramLabel: 'PID / Process Name',
    paramPlaceholder: '1234 atau malware.exe',
  },
  {
    id: 'revoke-token',
    name: 'Revoke Access Token',
    icon: '🔑',
    description: 'Revoke semua token aktif untuk user terkompromi',
    action: 'revoke_token',
    paramLabel: 'Username',
    paramPlaceholder: 'user@domain.com',
  },
  {
    id: 'notify',
    name: 'Notify SOC Team',
    icon: '📢',
    description: 'Kirim notifikasi eskalasi ke SOC / CISO',
    action: 'notify_soc',
    paramLabel: 'Pesan',
    paramPlaceholder: 'Alert eskalasi: brute force terdeteksi',
  },
];

interface SoarPlaybooksProps {
  selectedAlert?: SiemAlert | null;
}

export function SoarPlaybooks({ selectedAlert }: SoarPlaybooksProps) {
  const [selectedPb, setSelectedPb] = useState<string | null>(null);
  const [paramValue, setParamValue] = useState('');
  const [executing, setExecuting] = useState(false);
  const [resultLog, setResultLog] = useState<string | null>(null);
  const [resultError, setResultError] = useState(false);
  const { toast } = useToast();

  const playbook = PLAYBOOKS.find(p => p.id === selectedPb);

  const handleSelect = useCallback((pb: Playbook) => {
    setSelectedPb(pb.id);
    setResultLog(null);
    setResultError(false);
    // Pre-fill param from selected alert
    if (selectedAlert) {
      if (pb.action === 'block_ip' && selectedAlert.source_ip) {
        setParamValue(selectedAlert.source_ip);
      } else if (pb.action === 'isolate_host') {
        setParamValue('');
      } else {
        setParamValue('');
      }
    } else {
      setParamValue('');
    }
  }, [selectedAlert]);

  const handleExecute = useCallback(async () => {
    if (!playbook || !selectedAlert) return;
    setExecuting(true);
    setResultLog(null);
    setResultError(false);
    try {
      const res = await runSoarPlaybook({
        action: playbook.action,
        alert_id: selectedAlert.id,
        params: paramValue ? { value: paramValue } : undefined,
      });
      if (res.ok) {
        const log = [
          `[SOAR] Playbook: ${playbook.name}`,
          `[SOAR] Action: ${playbook.action}`,
          `[SOAR] Alert: ${selectedAlert.id} — ${selectedAlert.title}`,
          paramValue ? `[SOAR] Param: ${paramValue}` : null,
          `[SOAR] Status: SUCCESS`,
          `[SOAR] Timestamp: ${new Date().toISOString()}`,
        ].filter(Boolean).join('\n');
        setResultLog(log);
        toast(`Playbook "${playbook.name}" berhasil dijalankan`, 'success');
      } else {
        setResultLog(`[SOAR] ERROR: ${(res as Record<string, unknown>).error ?? 'Unknown error'}`);
        setResultError(true);
        toast('Playbook gagal dijalankan', 'error');
      }
    } catch {
      setResultLog('[SOAR] ERROR: Network / server error');
      setResultError(true);
      toast('Gagal menjalankan playbook', 'error');
    } finally {
      setExecuting(false);
    }
  }, [playbook, selectedAlert, paramValue, toast]);

  return (
    <div className="p-3">
      {/* Playbook grid */}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-2.5 mb-3.5">
        {PLAYBOOKS.map(pb => (
          <div
            key={pb.id}
            className={cn(
              'p-3.5 bg-background-card border border-border-dim rounded-lg cursor-pointer transition-colors hover:border-primary/50',
              selectedPb === pb.id && 'border-primary bg-primary/[0.04]'
            )}
            onClick={() => handleSelect(pb)}
          >
            <div className="text-2xl mb-2">{pb.icon}</div>
            <div className="text-[13px] font-bold font-mono mb-1">{pb.name}</div>
            <div className="text-[11px] opacity-50 font-mono leading-relaxed">{pb.description}</div>
            <span className="inline-flex mt-1.5 px-1.5 py-0.5 rounded-sm text-[9px] font-semibold font-mono bg-primary/10 text-primary">
              {pb.action}
            </span>
          </div>
        ))}
      </div>

      {/* Execute panel */}
      {playbook && (
        <div className="p-3.5 bg-background-card border border-border-dim rounded-lg">
          <div className="text-[13px] font-bold font-mono mb-2.5">
            {playbook.icon} Jalankan: {playbook.name}
          </div>

          {!selectedAlert && (
            <div className="text-center py-6 opacity-30 text-xs font-mono">
              Pilih alert dari tab Alert Queue terlebih dahulu
            </div>
          )}

          {selectedAlert && (
            <>
              <div className="mb-2.5">
                <label className="block text-2xs font-mono uppercase tracking-wide opacity-60 mb-1">
                  Alert Target
                </label>
                <input
                  className="w-full px-2.5 py-1.5 bg-background-card border border-border-dim rounded font-mono text-xs text-foreground outline-none focus:border-primary"
                  value={`${selectedAlert.id} — ${selectedAlert.title}`}
                  readOnly
                />
              </div>

              {playbook.paramLabel && (
                <div className="mb-2.5">
                  <label className="block text-2xs font-mono uppercase tracking-wide opacity-60 mb-1">
                    {playbook.paramLabel}
                  </label>
                  <input
                    className="w-full px-2.5 py-1.5 bg-background-card border border-border-dim rounded font-mono text-xs text-foreground outline-none focus:border-primary"
                    value={paramValue}
                    onChange={e => setParamValue(e.target.value)}
                    placeholder={playbook.paramPlaceholder}
                  />
                </div>
              )}

              <button
                className="px-4 py-2 bg-green-600 border border-green-600 rounded font-mono text-xs font-bold text-black cursor-pointer transition-opacity hover:opacity-85 disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={handleExecute}
                disabled={executing}
              >
                {executing ? '⏳ Menjalankan…' : `▶ Jalankan ${playbook.name}`}
              </button>
            </>
          )}

          {resultLog && (
            <div className={cn(
              'mt-3 p-2.5 px-3.5 bg-[#0c0a09] border border-border-dim rounded-md font-mono text-[11px] whitespace-pre-wrap max-h-[200px] overflow-y-auto',
              resultError ? 'text-red-300' : 'text-green-300'
            )}>
              {resultLog}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
