// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Audit Log (Tailwind migration)
// Filterable audit trail with hash-chain verification
// ═══════════════════════════════════════════════════════════════════════

import { useState, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import type { AuditEntry } from '@/types/api';
import { adminAuditLog, adminVerifyAuditChain } from '@/api/endpoints';
import { useToast } from '@/hooks/useToast';

// ── Category badge classes ───────────────────────────────────────────
const CAT_CLS: Record<string, string> = {
  auth:       'bg-[rgba(34,211,238,0.15)] text-[#67e8f9]',
  admin:      'bg-[rgba(239,68,68,0.15)] text-[#fca5a5]',
  scan:       'bg-[rgba(167,139,250,0.15)] text-[#c4b5fd]',
  forensics:  'bg-[rgba(34,197,94,0.15)] text-[#86efac]',
};
const CAT_DEFAULT = 'bg-[rgba(148,163,184,0.1)] text-[#94a3b8]';

const FILTER_INPUT = 'py-[5px] px-2.5 bg-background-card border border-border-dim rounded font-mono text-[11px] text-inherit min-w-[120px] focus:outline-none focus:border-accent-steel';

export function AuditLog() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Filters
  const [filterCat, setFilterCat] = useState('');
  const [filterActor, setFilterActor] = useState('');
  const [filterResult, setFilterResult] = useState('');

  // Chain verification
  const [verifyOk, setVerifyOk] = useState<boolean | null>(null);

  const { toast } = useToast();

  const loadLog = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { limit: 200 };
      if (filterCat) params.category = filterCat;
      if (filterActor) params.actor = filterActor;
      if (filterResult) params.result = filterResult;
      const res = await adminAuditLog(params);
      if (res.ok) {
        // Backend returns `rows` with `audit_id`; normalize to `entries` with `id`
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const raw = (res as any).rows ?? res.entries ?? [];
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        setEntries(raw.map((e: any) => ({
          id:        e.audit_id ?? e.id ?? '',
          timestamp: e.timestamp ?? '',
          actor:     e.actor ?? '',
          action:    e.action ?? '',
          category:  (e.category ?? '').toLowerCase(),
          result:    (e.result ?? '').toLowerCase() === 'sukses' ? 'success' : 'fail',
          detail:    e.detail || e.target_ref || undefined,
        })));
      }
    } catch { /* swallow */ }
    setLoading(false);
  }, [filterCat, filterActor, filterResult]);

  useEffect(() => { loadLog(); }, [loadLog]);

  const handleVerify = useCallback(async () => {
    try {
      const res = await adminVerifyAuditChain();
      if (res.ok) {
        setVerifyOk(true);
        toast('Audit chain VALID', 'success');
      } else {
        setVerifyOk(false);
        toast('Audit chain INVALID', 'error');
      }
    } catch {
      setVerifyOk(false);
      toast('Gagal verifikasi audit chain', 'error');
    }
  }, [toast]);

  const fmtTime = (ts: string) => {
    try {
      return new Date(ts).toLocaleString('id-ID', {
        day: '2-digit', month: 'short',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    } catch { return ts; }
  };

  return (
    <div className="p-3">
      {/* Filters */}
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <input
          className={FILTER_INPUT}
          placeholder="Filter actor…"
          value={filterActor}
          onChange={e => setFilterActor(e.target.value)}
        />
        <select className={cn(FILTER_INPUT, 'cursor-pointer')} value={filterCat} onChange={e => setFilterCat(e.target.value)}>
          <option value="">All categories</option>
          <option value="auth">Auth</option>
          <option value="admin">Admin</option>
          <option value="scan">Scan</option>
          <option value="forensics">Forensics</option>
        </select>
        <select className={cn(FILTER_INPUT, 'cursor-pointer')} value={filterResult} onChange={e => setFilterResult(e.target.value)}>
          <option value="">All results</option>
          <option value="success">Success</option>
          <option value="fail">Fail</option>
        </select>
        <button
          className="py-[5px] px-3 border border-[#10b981] rounded bg-transparent text-[#10b981] font-mono text-[11px] cursor-pointer ml-auto hover:bg-[#10b981] hover:text-black"
          onClick={handleVerify}
        >
          🔗 Verify Chain
        </button>
      </div>

      {/* Chain verification result */}
      {verifyOk !== null && (
        <div className={cn(
          'py-2 px-3.5 rounded-md font-mono text-[11px] mb-2.5',
          verifyOk
            ? 'bg-[rgba(34,197,94,0.1)] border border-[rgba(34,197,94,0.3)] text-[#86efac]'
            : 'bg-[rgba(239,68,68,0.1)] border border-[rgba(239,68,68,0.3)] text-[#fca5a5]',
        )}>
          {verifyOk ? '✅ Audit chain terverifikasi — semua hash valid' : '❌ Audit chain INVALID — hash mismatch terdeteksi'}
        </div>
      )}

      {/* Log entries */}
      {loading ? (
        <div className="text-center py-10 px-4 opacity-40 text-[13px] font-mono">⏳ Loading audit log…</div>
      ) : entries.length === 0 ? (
        <div className="text-center py-10 px-4 opacity-30 text-[13px] font-mono">Tidak ada entri audit</div>
      ) : (
        <div className="flex flex-col gap-1.5">
          {entries.map(e => (
            <div
              key={e.id}
              className={cn('grid grid-cols-[140px_80px_1fr_80px_60px] gap-2 items-center py-[7px] px-2.5 bg-background-card border border-border-dim rounded-md font-mono text-[11px] transition-colors hover:border-border-accent', e.detail ? 'cursor-pointer' : 'cursor-default')}
              onClick={() => setExpandedId(prev => prev === e.id ? null : e.id)}
            >
              <span className="text-2xs opacity-50 whitespace-nowrap">{fmtTime(e.timestamp)}</span>
              <span className="font-bold text-accent-steel text-2xs truncate">{e.actor}</span>
              <span className="truncate">{e.action}</span>
              <span className={cn('py-0.5 px-1.5 rounded-[3px] text-[9px] font-bold uppercase text-center', CAT_CLS[e.category] ?? CAT_DEFAULT)}>
                {e.category}
              </span>
              <span className={cn(
                'text-[9px] font-bold uppercase text-center',
                e.result === 'success' ? 'text-[#22c55e]' : 'text-[#ef4444]',
              )}>
                {e.result}
              </span>

              {expandedId === e.id && e.detail && (
                <div className="col-span-full py-1.5 px-2.5 bg-[#0c0a09] rounded text-2xs opacity-60 whitespace-pre-wrap break-all mt-1">
                  {e.detail}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
