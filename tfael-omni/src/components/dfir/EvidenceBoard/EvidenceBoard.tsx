// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Evidence Board (Tailwind migration)
// Grid of forensic evidence items with ingest upload
// ═══════════════════════════════════════════════════════════════════════

import { useState, useCallback, useRef } from 'react';
import { cn } from '@/lib/utils';
import type { ForensicEvidence } from '@/types/api';
import { forensicsIngest } from '@/api/endpoints';
import { useToast } from '@/hooks/useToast';

// ── Type badge lookup ─────────────────────────────────────────────────

const TYPE_CLS: Record<string, string> = {
  image:  'bg-[#312e81] text-[#a5b4fc]',
  sqlite: 'bg-[#1e3a5f] text-[#93c5fd]',
  pcap:   'bg-[#365314] text-[#bef264]',
};
const TYPE_DEFAULT = 'bg-[#1c1917] text-[#a8a29e]';

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

function typeIcon(type?: string): string {
  switch ((type ?? '').toLowerCase()) {
    case 'image': return '🖼';
    case 'sqlite': return '🗄';
    case 'pcap': return '📡';
    case 'pdf': return '📄';
    case 'binary': return '⚙';
    default: return '📎';
  }
}

function typeClass(type?: string): string {
  return TYPE_CLS[(type ?? '').toLowerCase()] ?? TYPE_DEFAULT;
}

interface EvidenceBoardProps {
  evidences: ForensicEvidence[];
  onSelect?: (evidence: ForensicEvidence) => void;
  onRefresh?: () => void;
}

export function EvidenceBoard({ evidences, onSelect, onRefresh }: EvidenceBoardProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const { toast } = useToast();

  const handleSelect = useCallback((ev: ForensicEvidence) => {
    setSelectedId(prev => prev === ev.id ? null : ev.id);
    onSelect?.(ev);
  }, [onSelect]);

  const handleIngest = useCallback(async (file: File) => {
    setUploading(true);
    try {
      const buf = await file.arrayBuffer();
      const b64 = btoa(
        new Uint8Array(buf).reduce((data, byte) => data + String.fromCharCode(byte), '')
      );
      const res = await forensicsIngest({
        filename: file.name,
        data_b64: b64,
        type: file.type || 'application/octet-stream',
      });
      if (res.ok) {
        toast(`Evidence "${file.name}" berhasil diingest`, 'success');
        onRefresh?.();
      } else {
        toast('Gagal mengingest evidence', 'error');
      }
    } catch {
      toast('Gagal mengingest evidence', 'error');
    } finally {
      setUploading(false);
    }
  }, [toast, onRefresh]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleIngest(f);
  }, [handleIngest]);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleIngest(f);
  }, [handleIngest]);

  const fmtDate = (ts: string) => {
    try {
      return new Date(ts).toLocaleString('id-ID', {
        day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
      });
    } catch { return ts; }
  };

  return (
    <div className="p-3">
      {/* Upload zone */}
      <input
        ref={inputRef}
        type="file"
        onChange={handleFileInput}
        className="hidden"
      />
      <div
        className={cn(
          'border-2 border-dashed border-border-dim rounded-lg py-8 px-4 text-center cursor-pointer transition-all mb-3.5 font-mono text-xs text-foreground-muted',
          'hover:border-accent-steel hover:text-accent-steel',
          dragging && 'border-accent-steel text-accent-steel',
        )}
        onClick={() => inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <div className="text-2xl mb-2">📦</div>
        <div>{uploading ? '⏳ Mengingest…' : 'Klik atau drag file untuk ingest'}</div>
        <div className="text-2xs opacity-40 mt-1">
          Image, SQLite, PCAP, PDF, binary — analisis forensik otomatis
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-2 mb-3">
        <button
          className="py-[5px] px-3 border border-border-dim rounded bg-transparent text-foreground-muted font-mono text-[11px] cursor-pointer transition-all hover:border-accent-steel hover:text-accent-steel"
          onClick={onRefresh}
        >
          🔄 Refresh
        </button>
      </div>

      {/* Evidence grid */}
      {evidences.length === 0 ? (
        <div className="text-center py-10 px-4 opacity-30 text-[13px] font-mono">
          Belum ada evidence. Upload file untuk memulai analisis forensik.
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-2.5">
          {evidences.map(ev => {
            const hasYara = ev.analysis?.yara && ev.analysis.yara.length > 0;
            const hasEla = !!ev.analysis?.ela;
            const hasSqlite = ev.analysis?.sqlite_tables && ev.analysis.sqlite_tables.length > 0;
            const hasPcap = !!ev.analysis?.pcap_summary;
            return (
              <div
                key={ev.id}
                className={cn(
                  'p-3 bg-background-card border border-border-dim rounded-lg cursor-pointer transition-all hover:border-border-accent',
                  selectedId === ev.id && 'border-accent-steel bg-[rgba(111,147,160,0.04)]',
                )}
                onClick={() => handleSelect(ev)}
              >
                <div className="flex justify-between items-start mb-1.5">
                  <span className="text-xl">{typeIcon(ev.type)}</span>
                  <span className={`py-0.5 px-2 rounded-[3px] text-[9px] font-bold font-mono uppercase ${typeClass(ev.type)}`}>
                    {ev.type}
                  </span>
                </div>
                <div className="text-[13px] font-bold font-mono mb-1 break-all">{ev.filename}</div>
                <div className="text-[9px] font-mono opacity-35 break-all mb-1">SHA256: {ev.sha256}</div>
                <div className="text-2xs opacity-50 font-mono flex gap-2.5 flex-wrap">
                  <span>{formatSize(ev.size)}</span>
                  <span>{fmtDate(ev.ingested_at)}</span>
                </div>
                <div className="flex gap-1 mt-1.5 flex-wrap">
                  {hasEla && <span className="py-0.5 px-1.5 rounded-[3px] text-[9px] font-semibold font-mono bg-[rgba(111,147,160,0.1)] text-accent-steel">ELA</span>}
                  {hasYara && <span className="py-0.5 px-1.5 rounded-[3px] text-[9px] font-semibold font-mono bg-[rgba(239,68,68,0.15)] text-[#fca5a5]">YARA: {ev.analysis!.yara!.length}</span>}
                  {hasSqlite && <span className="py-0.5 px-1.5 rounded-[3px] text-[9px] font-semibold font-mono bg-[rgba(111,147,160,0.1)] text-accent-steel">SQLite: {ev.analysis!.sqlite_tables!.length} tbl</span>}
                  {hasPcap && <span className="py-0.5 px-1.5 rounded-[3px] text-[9px] font-semibold font-mono bg-[rgba(111,147,160,0.1)] text-accent-steel">PCAP</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="mt-2 text-2xs opacity-40 font-mono">{evidences.length} evidence terdaftar</div>
    </div>
  );
}
