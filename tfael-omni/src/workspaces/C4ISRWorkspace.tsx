// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — C4ISR Workspace (Tailwind migration)
// Tactical grid: Map ~70% | Side panels ~30%
// ═══════════════════════════════════════════════════════════════════════

import { useState, useCallback, useRef, Component, type ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { LeafletMap } from '@/components/c4isr/LeafletMap';
import { UnitPanel } from '@/components/c4isr/UnitPanel';
import { MissionControls } from '@/components/c4isr/MissionControls';
import { CctvPanel } from '@/components/c4isr/CctvPanel';
import { Icon } from '@/components/icons/Icon';
import type { CctvHeatmapEntry } from '@/types/api';

// ── Error Boundary for Map crashes ──────────────────────────────────
class MapErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean; error: string }
> {
  state = { hasError: false, error: '' };
  static getDerivedStateFromError(err: Error) {
    return { hasError: true, error: err.message };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full bg-[#1a1814] text-[#e8e0d4] gap-3 p-6">
          <div className="text-lg font-bold">⚠ Peta mengalami error</div>
          <div className="text-xs text-[#a09080] max-w-[400px] text-center">
            {this.state.error}
          </div>
          <button
            onClick={() => this.setState({ hasError: false, error: '' })}
            className="mt-2 py-2 px-5 bg-[#c8a96e] text-[#141109] border-none rounded-md font-bold cursor-pointer"
          >
            Muat Ulang Peta
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// Side-panel tab
type SideTab = 'units' | 'cctv';

export default function C4ISRWorkspace() {
  // ── State ─────────────────────────────────────────────────────────
  const [selectedUnitId, setSelectedUnitId] = useState<string | null>(null);
  const [selectedTargetId, setSelectedTargetId] = useState<string | null>(null);
  const [playbackPct, setPlaybackPct] = useState(100);
  const [sideTab, setSideTab] = useState<SideTab>('units');

  // Triangulation / CellLocate overlays for map
  const [triangulation, setTriangulation] = useState<Parameters<typeof LeafletMap>[0]['triangulation']>(null);
  const [cellLocate, setCellLocate] = useState<Parameters<typeof LeafletMap>[0]['cellLocate']>(null);

  // Map flyTo callback
  const flyToRef = useRef<((lat: number, lon: number, zoom?: number) => void) | null>(null);
  const handleMapReady = useCallback((fn: (lat: number, lon: number, zoom?: number) => void) => {
    flyToRef.current = fn;
  }, []);
  const handleFlyTo = useCallback((lat: number, lon: number, zoom?: number) => {
    flyToRef.current?.(lat, lon, zoom);
  }, []);

  // CCTV heatmap state passed to map (future expansion — already piped)
  const [, setCctvHeatmap] = useState<CctvHeatmapEntry[]>([]);
  const handleHeatmapUpdate = useCallback((entries: CctvHeatmapEntry[]) => {
    setCctvHeatmap(entries);
    // TODO: forward to LeafletMap when heatmap layer is added
  }, []);

  // ── Playback handler ──────────────────────────────────────────────
  const handlePlaybackChange = useCallback((val: number) => {
    if (val === -1) {
      // Increment signal from auto-play
      setPlaybackPct(prev => Math.min(100, prev + 2));
    } else {
      setPlaybackPct(val);
    }
  }, []);

  return (
    <div className="grid grid-cols-[1fr_320px] grid-rows-[1fr_auto] h-full overflow-hidden max-[900px]:grid-cols-1 max-[900px]:grid-rows-[55vh_1fr_auto]">
      {/* ── Map Area ───────────────────────────────── */}
      <div className="col-start-1 row-start-1 min-h-0 relative">
        <MapErrorBoundary>
          <LeafletMap
            selectedUnitId={selectedUnitId}
            onSelectUnit={setSelectedUnitId}
            onSelectTarget={setSelectedTargetId}
            triangulation={triangulation}
            cellLocate={cellLocate}
            playbackPct={playbackPct}
            onMapReady={handleMapReady}
          />
        </MapErrorBoundary>
      </div>

      {/* ── Side Panel ─────────────────────────────── */}
      <div className="col-start-2 row-start-1 flex flex-col border-l border-border-dim bg-background overflow-hidden max-[900px]:col-start-1 max-[900px]:row-start-2 max-[900px]:border-l-0 max-[900px]:border-t max-[900px]:border-border-dim">
        {/* Side-panel tabs */}
        <div className="flex border-b border-border-dim shrink-0">
          <button
            className={cn(
              'flex-1 flex items-center justify-center gap-[5px] py-2 bg-transparent border-none border-b-2 border-b-transparent text-foreground-muted font-mono text-[10px] font-bold tracking-[0.06em] cursor-pointer transition-colors hover:text-foreground',
              sideTab === 'units' && 'text-accent-steel border-b-accent-steel',
            )}
            onClick={() => setSideTab('units')}
          >
            <Icon name="radio" size={10} /> Unit & C2
          </button>
          <button
            className={cn(
              'flex-1 flex items-center justify-center gap-[5px] py-2 bg-transparent border-none border-b-2 border-b-transparent text-foreground-muted font-mono text-[10px] font-bold tracking-[0.06em] cursor-pointer transition-colors hover:text-foreground',
              sideTab === 'cctv' && 'text-accent-steel border-b-accent-steel',
            )}
            onClick={() => setSideTab('cctv')}
          >
            <Icon name="camera" size={10} /> CCTV & Visi
          </button>
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto">
          {sideTab === 'units' && (
            <UnitPanel
              selectedUnitId={selectedUnitId}
              onSelectUnit={setSelectedUnitId}
              onFlyTo={handleFlyTo}
              onTriangulation={setTriangulation}
              onCellLocate={setCellLocate}
            />
          )}
          {sideTab === 'cctv' && (
            <CctvPanel
              onHeatmapUpdate={handleHeatmapUpdate}
              onFlyTo={handleFlyTo}
            />
          )}
        </div>
      </div>

      {/* ── Bottom Controls ────────────────────────── */}
      <div className="col-span-full row-start-2 border-t border-border-dim bg-background max-[900px]:col-start-1 max-[900px]:row-start-3">
        <MissionControls
          playbackPct={playbackPct}
          onPlaybackChange={handlePlaybackChange}
          selectedUnitId={selectedUnitId}
          onFlyTo={handleFlyTo}
        />
      </div>
    </div>
  );
}
