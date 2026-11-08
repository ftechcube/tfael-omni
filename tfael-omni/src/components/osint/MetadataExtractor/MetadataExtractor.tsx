// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Metadata Extractor (Tailwind migration)
// Upload file → extract EXIF/GPS/tags via API
// ═══════════════════════════════════════════════════════════════════════

import { useState, useCallback, useRef } from 'react';
import { cn } from '@/lib/utils';
import type { OsintMetadataResult } from '@/types/api';
import { osintMetadata } from '@/api/endpoints';
import { useToast } from '@/hooks/useToast';

export function MetadataExtractor() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OsintMetadataResult | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const { toast } = useToast();

  const processFile = useCallback(async (f: File) => {
    setFile(f);
    setLoading(true);
    setResult(null);
    try {
      const buf = await f.arrayBuffer();
      const b64 = btoa(
        new Uint8Array(buf).reduce((data, byte) => data + String.fromCharCode(byte), '')
      );
      const res = await osintMetadata(b64, f.name);
      setResult(res);
      if (!res.ok) toast(res.error ?? 'Gagal mengekstrak metadata', 'error');
    } catch {
      toast('Gagal mengekstrak metadata', 'error');
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) processFile(f);
  }, [processFile]);

  const handleClick = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) processFile(f);
  }, [processFile]);

  return (
    <div className="p-3">
      <input
        ref={inputRef}
        type="file"
        onChange={handleFileInput}
        className="hidden"
      />
      <div
        className={cn(
          'border-2 border-dashed border-border-dim rounded-lg py-8 px-4 text-center cursor-pointer transition-all mb-3 font-mono text-xs text-foreground-muted',
          'hover:border-accent-steel hover:text-accent-steel',
          dragging && 'border-accent-steel text-accent-steel',
        )}
        onClick={handleClick}
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <div className="text-2xl mb-2">📎</div>
        <div>{loading ? '⏳ Mengekstrak…' : 'Klik atau drag file ke sini'}</div>
        <div className="text-[10px] opacity-40 mt-1">
          Gambar, PDF, dokumen — ekstrak EXIF, GPS, metadata
        </div>
        {file && <div className="mt-2 text-[11px] text-[#10b981]">{file.name}</div>}
      </div>

      {result?.ok && (
        <div className="mt-3.5">
          {result.format && (
            <>
              <h4 className="text-[11px] uppercase tracking-[0.07em] opacity-50 mt-3 mb-1.5 font-mono">
                FORMAT
              </h4>
              <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-2.5 mb-3.5">
                <div className="mb-1">
                  <div className="opacity-60 text-[10px] font-mono">Format</div>
                  <div className="text-xs font-mono">{result.format}</div>
                </div>
              </div>
            </>
          )}

          {/* GPS data */}
          {result.gps && (
            <>
              <h4 className="text-[11px] uppercase tracking-[0.07em] opacity-50 mt-3 mb-1.5 font-mono">
                GPS DATA
              </h4>
              <div className="py-2.5 px-3.5 bg-[#0f2a1a] border border-[#166534] rounded-lg mb-2.5">
                <div className="text-sm font-bold text-[#4ade80] font-mono mb-1">
                  📍 {result.gps.lat.toFixed(6)}, {result.gps.lon.toFixed(6)}
                </div>
                {result.gps.alt_m != null && (
                  <div className="text-[11px] opacity-60">Alt: {result.gps.alt_m}m</div>
                )}
                {result.gps.date && (
                  <div className="text-[11px] opacity-60">Date: {result.gps.date}</div>
                )}
                <a
                  href={`https://www.google.com/maps?q=${result.gps.lat},${result.gps.lon}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block py-1 px-3 bg-[#14532d] text-white rounded text-[11px] no-underline mt-1.5 hover:opacity-85"
                >
                  Buka di Google Maps
                </a>
              </div>
            </>
          )}

          {/* Tags */}
          {result.tags && Object.keys(result.tags).length > 0 && (
            <>
              <h4 className="text-[11px] uppercase tracking-[0.07em] opacity-50 mt-3 mb-1.5 font-mono">
                METADATA TAGS
              </h4>
              <div className="mt-2">
                {Object.entries(result.tags).map(([k, v]) => (
                  <div key={k} className="flex gap-2 py-[3px] border-b border-white/[0.03] text-[11px]">
                    <span className="min-w-[140px] opacity-50 font-mono">{k}</span>
                    <span className="flex-1 font-mono break-all">{String(v)}</span>
                  </div>
                ))}
              </div>
            </>
          )}

          {result.note && (
            <div className="mt-2 py-1.5 px-2.5 bg-[#1c1917] border border-[#44403c] rounded text-[11px] text-[#a8a29e]">
              {result.note}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
