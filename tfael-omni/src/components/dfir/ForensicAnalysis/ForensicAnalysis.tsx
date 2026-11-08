// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Forensic Analysis Detail (Tailwind migration)
// YARA matches, ELA, SQLite tables, PCAP summary for selected evidence
// ═══════════════════════════════════════════════════════════════════════

import { cn } from '@/lib/utils';
import type { ForensicEvidence } from '@/types/api';

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

interface ForensicAnalysisProps {
  evidence: ForensicEvidence | null;
}

export function ForensicAnalysis({ evidence }: ForensicAnalysisProps) {
  if (!evidence) {
    return (
      <div className="p-3">
        <div className="text-center py-10 px-4 opacity-30 text-[13px] font-mono">
          Pilih evidence dari Evidence Board untuk melihat analisis
        </div>
      </div>
    );
  }

  const { analysis } = evidence;
  const yaraMatches = analysis?.yara ?? [];
  const sqliteTables = analysis?.sqlite_tables ?? [];
  const hasEla = !!analysis?.ela;
  const hasPcap = !!analysis?.pcap_summary;

  return (
    <div className="p-3">
      {/* Header */}
      <div className="flex items-center gap-2.5 mb-3.5 pb-2.5 border-b border-border-dim">
        <span className="text-2xl">🔬</span>
        <div className="flex-1">
          <div className="text-base font-bold font-mono">{evidence.filename}</div>
          <div className="text-2xs opacity-50 font-mono">
            {evidence.type} · {formatSize(evidence.size)} · {evidence.ingested_at}
          </div>
        </div>
      </div>

      {/* File info */}
      <div className="mb-3.5">
        <div className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2 font-mono font-bold">
          File Information
        </div>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-2">
          {[
            ['Filename', evidence.filename],
            ['Type', evidence.type],
            ['Size', formatSize(evidence.size)],
            ['SHA-256', evidence.sha256],
            ['Ingested At', evidence.ingested_at],
          ].map(([label, value]) => (
            <div key={label} className="py-2 px-2.5 bg-background-card border border-border-dim rounded-md">
              <div className="text-[9px] uppercase tracking-[0.05em] opacity-50 font-mono mb-0.5">{label}</div>
              <div className="text-xs font-mono break-all">{value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* YARA Matches */}
      {yaraMatches.length > 0 && (
        <div className="mb-3.5">
          <div className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2 font-mono font-bold">
            YARA Matches ({yaraMatches.length})
          </div>
          <div className="flex flex-col gap-1.5">
            {yaraMatches.map((match, i) => (
              <div
                key={`${match.rule}-${i}`}
                className="py-2.5 px-3 bg-[rgba(239,68,68,0.05)] border border-[rgba(239,68,68,0.15)] rounded-md border-l-[3px] border-l-[#ef4444]"
              >
                <div className="text-[13px] font-bold font-mono text-[#fca5a5] mb-1">
                  {match.rule}
                  {match.severity && (
                    <span
                      className={cn(
                        'ml-2 text-2xs py-px px-1.5 rounded-[3px] text-white',
                        match.severity === 'CRITICAL' ? 'bg-[#ef4444]' :
                        match.severity === 'HIGH' ? 'bg-[#f97316]' :
                        match.severity === 'INFO' ? 'bg-[#3b82f6]' : 'bg-[#eab308]',
                      )}
                    >
                      {match.severity}
                    </span>
                  )}
                </div>
                {match.desc && (
                  <div className="text-2xs opacity-50 font-mono flex gap-2.5 flex-wrap mb-1">
                    <span>{match.desc}</span>
                  </div>
                )}
                {match.meta && Object.keys(match.meta).length > 0 && (
                  <div className="text-2xs opacity-50 font-mono flex gap-2.5 flex-wrap mb-1">
                    {Object.entries(match.meta).map(([k, v]) => (
                      <span key={k}>{k}: {v}</span>
                    ))}
                  </div>
                )}
                {match.strings && match.strings.length > 0 && (
                  <div className="text-2xs font-mono opacity-60">
                    {match.strings.map((str, j) => (
                      <div key={j} className="py-0.5 border-b border-white/[0.03]">
                        <span className="inline-block min-w-[70px] text-secondary">
                          0x{str.offset.toString(16)}
                        </span>
                        {str.identifier}: {str.data}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ELA Analysis */}
      {hasEla && (
        <div className="mb-3.5">
          <div className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2 font-mono font-bold">
            Error Level Analysis (ELA)
          </div>
          <div className="p-3.5 bg-background-card border border-border-dim rounded-lg text-center">
            {typeof analysis!.ela === 'number' ? (
              <div className="flex items-center gap-3">
                <div className="w-[200px] h-3 rounded-md bg-background-deep overflow-hidden">
                  <div
                    className={cn(
                      'h-full rounded-md',
                      (analysis!.ela as number) > 0.7 ? 'bg-[#ef4444]' :
                      (analysis!.ela as number) > 0.4 ? 'bg-[#f97316]' : 'bg-[#22c55e]',
                    )}
                    style={{ width: `${Math.min((analysis!.ela as number) * 100, 100)}%` }}
                  />
                </div>
                <span className="font-mono text-[13px]">
                  {((analysis!.ela as number) * 100).toFixed(1)}% anomaly
                </span>
                <span
                  className={cn(
                    'text-2xs py-px px-1.5 rounded-[3px] text-white',
                    (analysis!.ela as number) > 0.7 ? 'bg-[#ef4444]' :
                    (analysis!.ela as number) > 0.4 ? 'bg-[#f97316]' : 'bg-[#22c55e]',
                  )}
                >
                  {(analysis!.ela as number) > 0.7 ? 'HIGH ANOMALY' :
                   (analysis!.ela as number) > 0.4 ? 'MODERATE' : 'LOW'}
                </span>
              </div>
            ) : typeof analysis!.ela === 'string' ? (
              <img
                src={`data:image/png;base64,${analysis!.ela}`}
                alt="ELA Result"
                className="max-w-full rounded-md"
              />
            ) : (
              <div className="text-[11px] opacity-50 font-mono mt-1.5">
                ELA data tersedia — format: {typeof analysis!.ela}
              </div>
            )}
            <div className="text-[11px] opacity-50 font-mono mt-2">
              Skor anomali tinggi mengindikasikan kemungkinan manipulasi
            </div>
          </div>
        </div>
      )}

      {/* SQLite Tables */}
      {sqliteTables.length > 0 && (
        <div className="mb-3.5">
          <div className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2 font-mono font-bold">
            SQLite Tables ({sqliteTables.length})
          </div>
          <div className="flex gap-1.5 flex-wrap">
            {sqliteTables.map(table => (
              <span
                key={table}
                className="py-[3px] px-2 bg-[rgba(59,130,246,0.1)] border border-[rgba(59,130,246,0.2)] rounded text-2xs font-mono text-[#93c5fd]"
              >
                {table}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* PCAP Summary */}
      {hasPcap && (
        <div className="mb-3.5">
          <div className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2 font-mono font-bold">
            PCAP Summary
          </div>
          <div className="p-2.5 bg-[#0c0a09] border border-border-dim rounded-md font-mono text-2xs whitespace-pre-wrap max-h-[300px] overflow-y-auto opacity-60 break-all">
            {JSON.stringify(analysis!.pcap_summary, null, 2)}
          </div>
        </div>
      )}

      {/* No analysis available */}
      {!hasEla && yaraMatches.length === 0 && sqliteTables.length === 0 && !hasPcap && (
        <div className="mb-3.5">
          <div className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2 font-mono font-bold">
            Analysis
          </div>
          <div className="text-center py-10 px-4 opacity-30 text-[13px] font-mono">
            Tidak ada hasil analisis untuk evidence ini
          </div>
        </div>
      )}
    </div>
  );
}
