// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Mission Controls (Tailwind migration)
// Playback slider, GPX import, route HUD
// ═══════════════════════════════════════════════════════════════════════

import { useState, useRef, useCallback, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { useApp } from '@/context/AppContext';
import { Icon } from '@/components/icons/Icon';
import { importGpx, clearRoutes } from '@/api/endpoints';
import { useToast } from '@/hooks/useToast';
import type { Unit, ActiveRoute } from '@/types/api';

// ── Haversine distance ──────────────────────────────────────────────

function metersBetween(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371000;
  const toR = Math.PI / 180;
  const dLat = (lat2 - lat1) * toR;
  const dLon = (lon2 - lon1) * toR;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * toR) * Math.cos(lat2 * toR) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function routeNav(lat: number, lon: number, route: ActiveRoute) {
  const pts = route.points;
  if (!pts || pts.length < 2) return null;
  const R = 6371000;
  const toR = Math.PI / 180;
  const refLat = lat * toR;
  const X = (pl: number, po: number): [number, number] => [
    (po - lon) * toR * R * Math.cos(refLat),
    (pl - lat) * toR * R,
  ];
  let best = { d: Infinity, seg: 0, t: 0 };
  for (let i = 0; i < pts.length - 1; i++) {
    const a = X(pts[i][0], pts[i][1]);
    const b = X(pts[i + 1][0], pts[i + 1][1]);
    const abx = b[0] - a[0];
    const aby = b[1] - a[1];
    const ab2 = abx * abx + aby * aby || 1e-9;
    let t = -(a[0] * abx + a[1] * aby) / ab2;
    t = Math.max(0, Math.min(1, t));
    const d = Math.hypot(a[0] + t * abx, a[1] + t * aby);
    if (d < best.d) best = { d, seg: i, t };
  }
  let rem = metersBetween(pts[best.seg][0], pts[best.seg][1], pts[best.seg + 1][0], pts[best.seg + 1][1]) * (1 - best.t);
  for (let i = best.seg + 1; i < pts.length - 1; i++) {
    rem += metersBetween(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]);
  }
  return { crossM: Math.round(best.d), remainingKm: +(rem / 1000).toFixed(2), offRoute: best.d > 30 };
}

// ── Component ────────────────────────────────────────────────────────

interface Props {
  playbackPct: number;
  onPlaybackChange: (pct: number) => void;
  selectedUnitId: string | null;
  onFlyTo?: (lat: number, lon: number, zoom?: number) => void;
}

export function MissionControls({
  playbackPct,
  onPlaybackChange,
  selectedUnitId,
  onFlyTo,
}: Props) {
  const { overview, refreshOverview } = useApp();
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [playing, setPlaying] = useState(false);

  const route = overview?.active_route ?? null;
  const units = overview?.units ?? [];
  const selectedUnit = units.find(u => u.unit_id === selectedUnitId) ?? null;

  // Playback label
  const playbackLabel = playbackPct >= 100
    ? 'LIVE (T-00:00)'
    : `HISTORI (T-${Math.round((100 - playbackPct) * 0.45)} Menit Lalu)`;

  // ── Playback toggle ───────────────────────────────────────────────
  const togglePlayback = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
      setPlaying(false);
      return;
    }
    onPlaybackChange(0);
    setPlaying(true);
    timerRef.current = setInterval(() => {
      onPlaybackChange(-1); // signal to increment
    }, 350);
  }, [onPlaybackChange]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  // Auto-stop at 100%
  useEffect(() => {
    if (playbackPct >= 100 && timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
      setPlaying(false);
    }
  }, [playbackPct]);

  // ── GPX Import ────────────────────────────────────────────────────
  const handleGpxImport = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (fileInputRef.current) fileInputRef.current.value = '';
    if (!file) return;
    try {
      const gpx = await file.text();
      const name = file.name.replace(/\.gpx$/i, '');
      const { data } = await importGpx(gpx, name);
      const d = data as { ok: boolean; name?: string; num_points?: number; total_km?: number };
      if (d?.ok) {
        await refreshOverview();
        toast(`Rute "${d.name}" dimuat: ${d.num_points} titik · ${d.total_km} km`);
      } else {
        toast('Gagal impor GPX', 'error');
      }
    } catch {
      toast('Gagal membaca berkas GPX.', 'error');
    }
  }, [refreshOverview, toast]);

  const handleClearRoute = useCallback(async () => {
    const { data } = await clearRoutes();
    if (data?.ok) {
      await refreshOverview();
      toast('Rute dihapus dari peta.');
    }
  }, [refreshOverview, toast]);

  // Route navigation
  const routeNavInfo = selectedUnit && route
    ? routeNav(selectedUnit.lat, selectedUnit.lon, route)
    : null;

  return (
    <div className="flex flex-col gap-2.5 p-2">
      {/* ── Playback ──────────────────────────── */}
      <div className="bg-background-card border border-border-dim rounded-md p-2.5">
        <div className="font-mono text-[10px] font-extrabold tracking-[0.12em] text-foreground-muted mb-2 flex items-center gap-[5px]">
          <Icon name="play" size={10} /> MISSION PLAYBACK
        </div>
        <div className="flex items-center gap-2">
          <button
            className="flex items-center gap-[5px] py-[5px] px-2.5 bg-[#1e293b] border border-[#6f93a0] rounded-sm text-[#a7c6cf] font-mono text-[10px] font-bold cursor-pointer whitespace-nowrap transition-opacity hover:opacity-85"
            onClick={togglePlayback}
          >
            <Icon name={playing ? 'pause' : 'play'} size={12} />
            {playing ? 'Hentikan' : 'Putar ulang'}
          </button>
          <input
            type="range"
            min={0}
            max={100}
            value={playbackPct}
            onChange={e => onPlaybackChange(parseInt(e.target.value))}
            className="tactical-slider flex-1 h-1"
          />
        </div>
        <div className="font-mono text-[10px] text-foreground-muted mt-1 tracking-[0.04em]">{playbackLabel}</div>
      </div>

      {/* ── GPX Route ─────────────────────────── */}
      <div className="bg-background-card border border-border-dim rounded-md p-2.5">
        <div className="font-mono text-[10px] font-extrabold tracking-[0.12em] text-foreground-muted mb-2 flex items-center gap-[5px]">
          <Icon name="route" size={10} /> RUTE GPX
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".gpx"
          className="hidden"
          onChange={handleGpxImport}
        />
        <div className="flex gap-1.5 mb-1.5">
          <button
            className="flex items-center gap-[5px] py-[5px] px-2.5 bg-[#0f2e26] border border-[#22c55e] rounded-sm text-[#86efac] font-mono text-[10px] font-bold cursor-pointer transition-opacity hover:opacity-85"
            onClick={() => fileInputRef.current?.click()}
          >
            <Icon name="upload" size={10} /> Impor GPX
          </button>
          {route && (
            <button
              className="flex items-center gap-[5px] py-[5px] px-2.5 bg-[#7f1d1d] border border-destructive rounded-sm text-[#fca5a5] font-mono text-[10px] font-bold cursor-pointer transition-opacity hover:opacity-85"
              onClick={handleClearRoute}
            >
              <Icon name="x" size={10} /> Hapus
            </button>
          )}
        </div>
        {route && (
          <div className={cn('font-mono text-[10.5px] leading-normal', routeNavInfo?.offRoute ? 'text-[#f59e0b]' : 'text-[#00e5a8]')}>
            ▸ {route.name} · {route.total_km} km
            {routeNavInfo && selectedUnit && (
              <> · {selectedUnit.unit_id}: {routeNavInfo.offRoute ? '⚠ keluar jalur ' : ''}{routeNavInfo.crossM} m dari jalur, sisa {routeNavInfo.remainingKm} km</>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
