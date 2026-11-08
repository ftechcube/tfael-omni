// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — OSINT Scan History (Tailwind migration)
// Two-column layout: history list + preview panel
// ═══════════════════════════════════════════════════════════════════════

import { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import type { ScanHistoryEntry } from '@/types/api';
import { TYPE_ICONS } from '../helpers';
import { ResultsPanel } from '../ResultsPanel/ResultsPanel';

interface ScanHistoryProps {
  history: ScanHistoryEntry[];
  onClear: () => void;
  onLoadScan?: (entry: ScanHistoryEntry) => void;
}

export function ScanHistory({ history, onClear, onLoadScan }: ScanHistoryProps) {
  const [selected, setSelected] = useState<number | null>(null);

  const handleSelect = useCallback((idx: number) => {
    setSelected(idx === selected ? null : idx);
  }, [selected]);

  const handleLoad = useCallback((entry: ScanHistoryEntry) => {
    onLoadScan?.(entry);
  }, [onLoadScan]);

  const selectedEntry = selected != null ? history[selected] : null;

  return (
    <div className="flex gap-3 h-full min-h-[300px]">
      {/* Left column: history list */}
      <div className="w-[260px] min-w-[200px] flex flex-col border-r border-border-dim">
        <div className="flex items-center justify-between py-2 px-2.5 border-b border-border-dim">
          <span className="text-[11px] font-bold font-mono uppercase opacity-50">
            Riwayat ({history.length})
          </span>
          {history.length > 0 && (
            <button
              className="text-[10px] py-0.5 px-2 bg-transparent border border-border-dim rounded-[3px] text-destructive font-mono cursor-pointer hover:opacity-70"
              onClick={onClear}
            >
              Hapus
            </button>
          )}
        </div>
        <div className="flex-1 overflow-y-auto">
          {history.length === 0 && (
            <div className="p-4 opacity-30 text-xs text-center">
              Belum ada scan
            </div>
          )}
          {history.map((entry, i) => (
            <div
              key={`${entry.ts}-${i}`}
              className={cn(
                'flex items-center gap-1.5 py-2 px-2.5 cursor-pointer border-b border-white/[0.03] transition-colors text-xs hover:bg-background-hover',
                i === selected && 'bg-background-hover',
              )}
              onClick={() => handleSelect(i)}
              onDoubleClick={() => handleLoad(entry)}
            >
              <span className="text-sm shrink-0">{TYPE_ICONS[entry.type] ?? '❓'}</span>
              <div className="flex-1 min-w-0">
                <div className="font-semibold whitespace-nowrap overflow-hidden text-ellipsis">
                  {entry.query}
                </div>
                <div className="text-[10px] opacity-40 mt-px">
                  {entry.type.toUpperCase()} · {new Date(entry.ts).toLocaleString('id-ID')}
                </div>
              </div>
              <div
                className={cn('w-1.5 h-1.5 rounded-full shrink-0', entry.ok ? 'bg-[#22c55e]' : 'bg-[#ef4444]')}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Right column: preview */}
      <div className="flex-1 overflow-y-auto p-2">
        {selectedEntry ? (
          <ResultsPanel data={selectedEntry.data} />
        ) : (
          <div className="flex items-center justify-center h-full opacity-30 text-[13px] font-mono">
            Pilih scan untuk preview
          </div>
        )}
      </div>
    </div>
  );
}
