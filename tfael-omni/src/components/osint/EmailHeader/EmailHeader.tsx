// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Email Header Analyzer (Tailwind migration)
// Parse raw email headers for SPF/DKIM/DMARC, routing hops, IP origins
// ═══════════════════════════════════════════════════════════════════════

import { useState, useCallback } from 'react';
import type { OsintEmailHeaderResult } from '@/types/api';
import { osintEmailHeader } from '@/api/endpoints';
import { useToast } from '@/hooks/useToast';

const AUTH_CLS: Record<string, string> = {
  pass: 'text-[#22c55e]',
  fail: 'text-[#ef4444]',
  none: 'text-[#6b7280]',
};

export function EmailHeader() {
  const [raw, setRaw] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OsintEmailHeaderResult | null>(null);
  const { toast } = useToast();

  const handleAnalyze = useCallback(async () => {
    const text = raw.trim();
    if (!text) return;
    setLoading(true);
    try {
      const res = await osintEmailHeader(text);
      setResult(res);
      if (!res.ok) toast(res.error ?? 'Analisis gagal', 'error');
    } catch {
      toast('Gagal menganalisis header', 'error');
    } finally {
      setLoading(false);
    }
  }, [raw, toast]);

  const authColor = (val?: string) => {
    if (!val) return AUTH_CLS.none;
    const lower = val.toLowerCase();
    if (lower.includes('pass')) return AUTH_CLS.pass;
    if (lower.includes('fail') || lower.includes('none')) return AUTH_CLS.fail;
    return AUTH_CLS.none;
  };

  return (
    <div className="p-3">
      <textarea
        className="w-full min-h-[120px] bg-background-card border border-border-dim rounded-md py-2.5 px-3 text-foreground font-mono text-[11px] resize-y mb-2 focus:outline-none focus:border-accent-steel"
        value={raw}
        onChange={e => setRaw(e.target.value)}
        placeholder="Paste raw email header di sini…"
        disabled={loading}
      />
      <button
        className="py-1.5 px-4 bg-[#10b981] text-black border-none rounded font-mono text-[11px] font-bold cursor-pointer mb-3.5 hover:opacity-85 disabled:opacity-50 disabled:cursor-not-allowed"
        onClick={handleAnalyze}
        disabled={loading || !raw.trim()}
      >
        {loading ? '⏳ Analyzing…' : '📧 Analyze Header'}
      </button>

      {result?.ok && (
        <div className="mt-3">
          {/* Basic info */}
          {result.from && (
            <div className="flex gap-2 py-1 border-b border-white/[0.04] text-xs">
              <span className="w-20 opacity-50 font-mono shrink-0">From</span>
              <span className="flex-1 font-mono">{result.from}</span>
            </div>
          )}
          {result.to && (
            <div className="flex gap-2 py-1 border-b border-white/[0.04] text-xs">
              <span className="w-20 opacity-50 font-mono shrink-0">To</span>
              <span className="flex-1 font-mono">{result.to}</span>
            </div>
          )}
          {result.subject && (
            <div className="flex gap-2 py-1 border-b border-white/[0.04] text-xs">
              <span className="w-20 opacity-50 font-mono shrink-0">Subject</span>
              <span className="flex-1 font-mono">{result.subject}</span>
            </div>
          )}
          {result.date && (
            <div className="flex gap-2 py-1 border-b border-white/[0.04] text-xs">
              <span className="w-20 opacity-50 font-mono shrink-0">Date</span>
              <span className="flex-1 font-mono">{result.date}</span>
            </div>
          )}

          {/* Auth checks */}
          <h4 className="text-[11px] uppercase tracking-[0.07em] opacity-50 mt-3 mb-1.5 font-mono">
            EMAIL AUTHENTICATION
          </h4>
          <div className="grid grid-cols-3 gap-2 my-2.5">
            <div className="p-1.5 bg-background-card rounded text-center">
              <div className="text-[10px] opacity-50 mb-0.5">SPF</div>
              <div className={`text-xs font-bold ${authColor(result.spf)}`}>
                {result.spf ?? '—'}
              </div>
            </div>
            <div className="p-1.5 bg-background-card rounded text-center">
              <div className="text-[10px] opacity-50 mb-0.5">DKIM</div>
              <div className={`text-xs font-bold ${authColor(result.dkim)}`}>
                {result.dkim ?? '—'}
              </div>
            </div>
            <div className="p-1.5 bg-background-card rounded text-center">
              <div className="text-[10px] opacity-50 mb-0.5">DMARC</div>
              <div className={`text-xs font-bold ${authColor(result.dmarc)}`}>
                {result.dmarc ?? '—'}
              </div>
            </div>
          </div>

          {/* Hops */}
          {result.hops && result.hops.length > 0 && (
            <>
              <h4 className="text-[11px] uppercase tracking-[0.07em] opacity-50 mt-3 mb-1.5 font-mono">
                ROUTING HOPS ({result.hop_count ?? result.hops.length})
              </h4>
              {result.hops.map((hop, i) => (
                <div key={i} className="flex gap-2 py-1 px-1.5 border-b border-white/[0.04] font-mono text-[10px]">
                  <span className="opacity-40 min-w-[20px]">{hop.hop}</span>
                  <span className="text-accent-steel flex-1">{hop.from ?? '—'}</span>
                  <span className="opacity-50">→</span>
                  <span className="flex-1">{hop.by ?? '—'}</span>
                  {hop.ips && <span className="opacity-50">[{hop.ips.join(', ')}]</span>}
                </div>
              ))}
            </>
          )}

          {/* IP origins */}
          {result.ip_details && result.ip_details.length > 0 && (
            <>
              <h4 className="text-[11px] uppercase tracking-[0.07em] opacity-50 mt-3 mb-1.5 font-mono">
                IP ORIGINS
              </h4>
              {result.ip_details.map((ip, i) => (
                <div key={i} className="p-1.5 bg-background-card rounded text-[11px] mb-1.5">
                  <div className="text-[#f59e0b] font-mono mb-0.5">{ip.ip}</div>
                  <div className="opacity-70">
                    {[ip.city, ip.country].filter(Boolean).join(', ')}
                    {ip.isp && ` · ${ip.isp}`}
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}
