// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Chain of Custody (Tailwind migration)
// Blockchain-style hash chain verification timeline
// ═══════════════════════════════════════════════════════════════════════

import { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import type { ChainOfCustody as ChainEntry } from '@/types/api';
import { forensicsVerifyChain } from '@/api/endpoints';
import { useToast } from '@/hooks/useToast';

interface ChainOfCustodyProps {
  chain?: ChainEntry[];
}

export function ChainOfCustody({ chain = [] }: ChainOfCustodyProps) {
  const [verifying, setVerifying] = useState(false);
  const [verifyOk, setVerifyOk] = useState<boolean | null>(null);
  const [verifyMsg, setVerifyMsg] = useState('');
  const { toast } = useToast();

  const handleVerify = useCallback(async () => {
    setVerifying(true);
    try {
      const res = await forensicsVerifyChain();
      const intact = (res as Record<string, unknown>).vault_intact ?? res.ok;
      if (intact) {
        setVerifyOk(true);
        setVerifyMsg(`Chain of Custody VALID — ${(res as Record<string, unknown>).total_blocks ?? ''} blok terverifikasi`);
        toast('Chain terverifikasi', 'success');
      } else {
        setVerifyOk(false);
        setVerifyMsg((res as Record<string, unknown>).error as string ?? 'Chain INVALID — hash mismatch terdeteksi');
        toast('Chain INVALID', 'error');
      }
    } catch {
      setVerifyOk(false);
      setVerifyMsg('Gagal memverifikasi chain');
      toast('Gagal memverifikasi chain', 'error');
    } finally {
      setVerifying(false);
    }
  }, [toast]);

  const fmtTime = (ts: string) => {
    try {
      return new Date(ts).toLocaleString('id-ID', {
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    } catch { return ts; }
  };

  return (
    <div className="p-3">
      <div className="flex items-center gap-2 mb-3">
        <button
          className="py-[5px] px-3 border border-[#10b981] rounded bg-transparent text-[#10b981] font-mono text-[11px] cursor-pointer transition-all hover:bg-[#10b981] hover:text-black disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={handleVerify}
          disabled={verifying}
        >
          {verifying ? '⏳ Memverifikasi…' : '🔗 Verifikasi Chain'}
        </button>
      </div>

      {/* Verification result */}
      {verifyOk !== null && (
        <div
          className={cn(
            'py-2.5 px-3.5 rounded-lg font-mono text-xs mb-3',
            verifyOk
              ? 'bg-[rgba(34,197,94,0.1)] border border-[rgba(34,197,94,0.3)] text-[#86efac]'
              : 'bg-[rgba(239,68,68,0.1)] border border-[rgba(239,68,68,0.3)] text-[#fca5a5]',
          )}
        >
          {verifyOk ? '✅' : '❌'} {verifyMsg}
        </div>
      )}

      {/* Chain timeline */}
      {chain.length === 0 ? (
        <div className="text-center py-10 px-4 opacity-30 text-[13px] font-mono">
          Belum ada chain of custody. Ingest evidence untuk memulai.
        </div>
      ) : (
        <div className="relative pl-6 before:content-[''] before:absolute before:left-[10px] before:top-0 before:bottom-0 before:w-0.5 before:bg-border-dim">
          {chain.map((entry, i) => (
            <div
              key={`${entry.hash}-${i}`}
              className="relative p-2.5 px-3.5 bg-background-card border border-border-dim rounded-lg mb-2.5 transition-colors hover:border-border-accent"
            >
              <div
                className={cn(
                  'absolute -left-[19px] top-3.5 w-2.5 h-2.5 rounded-full border-2 border-background-deep bg-accent-steel',
                  verifyOk === true && 'bg-[#22c55e]',
                  verifyOk === false && 'bg-[#ef4444] shadow-[0_0_6px_#ef4444]',
                )}
              />
              <div className="text-[13px] font-bold font-mono mb-1 uppercase">{entry.action}</div>
              <div className="text-2xs opacity-50 font-mono mb-1.5">
                {fmtTime(entry.timestamp)} · {entry.actor}
              </div>
              <div className="text-[9px] font-mono opacity-30 break-all">
                <span className="inline-block min-w-[60px] opacity-60">Hash:</span> {entry.hash}
              </div>
              <div className="text-[9px] font-mono opacity-30 break-all">
                <span className="inline-block min-w-[60px] opacity-60">Prev:</span> {entry.prev_hash || '(genesis)'}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
