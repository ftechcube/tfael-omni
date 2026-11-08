// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Leaflet GIS Map (Tailwind migration)
// Full tactical map with 10+ layer types: geofences, BTS, units, targets,
// annotations, SIEM arcs, forensic pins, GPX routes, triangulation
// ═══════════════════════════════════════════════════════════════════════

import { useEffect, useRef, useCallback, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useApp } from '@/context/AppContext';
import { geoConvert } from '@/api/endpoints';
import { cn } from '@/lib/utils';

interface TileConfig {
  url: string;
  attr: string;
  subdomains: string;
  dark?: boolean;
}

const TILE_URLS: Record<string, TileConfig> = {
  dark: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attr: '&copy; OpenStreetMap (mode taktis gelap)',
    subdomains: 'abc',
    dark: true,
  },
  satellite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attr: '&copy; Esri World Imagery',
    subdomains: 'abc',
  },
  osm: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attr: '&copy; OpenStreetMap Contributors',
    subdomains: 'abc',
  },
};

const UNIT_COLORS: Record<string, string> = {
  GREEN: '#10b981',
  YELLOW: '#f59e0b',
  BLUE: '#6f93a0',
  RED: '#ef4444',
};

interface CoordHud {
  mgrs: string;
  utm: string;
  dms: string;
  decimal: string;
}

interface LeafletMapProps {
  selectedUnitId: string | null;
  onSelectUnit: (id: string) => void;
  onSelectTarget: (id: string) => void;
  triangulation?: {
    ok: boolean;
    mode: string;
    lat: number;
    lon: number;
    accuracy_m: number;
    method: string;
    num_towers: number;
    error_vs_truth_m?: number;
    ground_truth?: { lat: number; lon: number };
    towers?: Array<{ tower_id: string; lat: number; lon: number; rssi_dbm: number; est_distance_m: number }>;
  } | null;
  cellLocate?: {
    ok: boolean;
    lat: number;
    lon: number;
    accuracy_m: number;
    source: string;
  } | null;
  playbackPct?: number;
  onMapReady?: (flyTo: (lat: number, lon: number, zoom?: number) => void) => void;
}

export function LeafletMap({
  selectedUnitId,
  onSelectUnit,
  onSelectTarget,
  triangulation,
  cellLocate,
  playbackPct = 100,
  onMapReady,
}: LeafletMapProps) {
  const { overview } = useApp();
  const mapRef = useRef<L.Map | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const tileRef = useRef<L.TileLayer | null>(null);
  const overlayRef = useRef<L.LayerGroup | null>(null);
  const targetLayerRef = useRef<L.LayerGroup | null>(null);
  const unitLayerRef = useRef<L.LayerGroup | null>(null);
  const unitMarkersRef = useRef<Record<string, { marker: L.Marker }>>({});
  const targetCacheRef = useRef<Record<string, { marker: L.Marker; circle?: L.Circle }>>({});

  const [tileStyle, setTileStyle] = useState('dark');
  const [coordHud, setCoordHud] = useState<CoordHud | null>(null);

  // ── Initialize map ──────────────────────────────────────────────
  useEffect(() => {
    if (mapRef.current || !containerRef.current) return;

    const map = L.map(containerRef.current, {
      center: [-6.1754, 106.835],
      zoom: 12,
      zoomControl: true,
    });

    if (map.attributionControl) map.attributionControl.setPrefix(false);
    overlayRef.current = L.layerGroup().addTo(map);
    targetLayerRef.current = L.layerGroup().addTo(map);
    unitLayerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    // Coordinate HUD on mouse move (throttled)
    let hudLast = 0;
    let hudTimeout: ReturnType<typeof setTimeout>;
    const updateHud = async (lat: number, lon: number) => {
      try {
        const { data } = await geoConvert(lat, lon);
        if (data.ok) {
          setCoordHud({ mgrs: data.mgrs, utm: data.utm, dms: data.dms, decimal: data.decimal });
        }
      } catch { /* silent */ }
    };
    map.on('mousemove', (ev: L.LeafletMouseEvent) => {
      const now = Date.now();
      if (now - hudLast > 250) {
        hudLast = now;
        updateHud(ev.latlng.lat, ev.latlng.lng);
      } else {
        clearTimeout(hudTimeout);
        hudTimeout = setTimeout(() => updateHud(ev.latlng.lat, ev.latlng.lng), 200);
      }
    });

    setTimeout(() => map.invalidateSize(), 120);

    // Expose flyTo callback to parent
    onMapReady?.((lat, lon, zoom) => {
      map.flyTo([lat, lon], zoom ?? 13, { duration: 0.8 });
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // ── Tile layer management ───────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (tileRef.current) map.removeLayer(tileRef.current);

    const cfg = TILE_URLS[tileStyle] || TILE_URLS.dark;
    const tilePane = map.getPane('tilePane');
    if (tilePane) tilePane.classList.toggle('tactical-dark', !!cfg.dark);

    const tile = L.tileLayer(cfg.url, {
      maxZoom: 19,
      attribution: cfg.attr,
      subdomains: cfg.subdomains,
      crossOrigin: true,
    });

    let tileErrs = 0;
    tile.on('tileerror', () => {
      tileErrs++;
      if (tileErrs === 6 && tileStyle !== 'osm') {
        setTileStyle('osm');
      }
    });

    tile.addTo(map);
    tileRef.current = tile;
  }, [tileStyle]);

  // ── Animate marker smoothly ─────────────────────────────────────
  const animateMarkerTo = useCallback((marker: L.Marker, toLat: number, toLon: number, ms: number) => {
    const from = marker.getLatLng();
    const dLat = toLat - from.lat;
    const dLon = toLon - from.lng;
    const dist = Math.sqrt(dLat * dLat + dLon * dLon);
    if (dist < 0.0000001 || dist > 0.05) {
      marker.setLatLng([toLat, toLon]);
      return;
    }
    const start = performance.now();
    function step(now: number) {
      const t = Math.min(1, (now - start) / ms);
      const e = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
      marker.setLatLng([from.lat + dLat * e, from.lng + dLon * e]);
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }, []);

  // ── Render all map layers ───────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    const overlay = overlayRef.current;
    const targetLayer = targetLayerRef.current;
    const unitLayer = unitLayerRef.current;
    if (!map || !overlay || !targetLayer || !unitLayer || !overview) return;

    try {
    overlay.clearLayers();

    // ── GPX Route ─────────────────────────────────────────────
    const route = overview.active_route;
    if (route && Array.isArray(route.points) && route.points.length > 1) {
      const latlngs = route.points.map((p: number[]) => [p[0], p[1]] as L.LatLngTuple);
      overlay.addLayer(L.polyline(latlngs, { color: '#0b1f14', weight: 7, opacity: 0.7 }));
      overlay.addLayer(L.polyline(latlngs, { color: '#00e5a8', weight: 3, opacity: 0.95 }));
      overlay.addLayer(L.circleMarker(latlngs[0], { radius: 6, color: '#fff', fillColor: '#16a34a', fillOpacity: 1, weight: 2 }));
      overlay.addLayer(L.circleMarker(latlngs[latlngs.length - 1], { radius: 6, color: '#fff', fillColor: '#dc2626', fillOpacity: 1, weight: 2 }));
    }

    // ── Geofences ─────────────────────────────────────────────
    (overview.geofences || []).forEach((g: any) => {
      overlay.addLayer(
        L.polygon(g.polygon, {
          color: g.color, weight: 2, dashArray: '6, 4',
          fillColor: g.color, fillOpacity: 0.14,
        }).bindPopup(`<strong>${g.zone_name}</strong><br/>Tipe: ${g.zone_type}`)
      );
    });

    // ── BTS Towers ────────────────────────────────────────────
    (overview.bts_towers || []).forEach((b: any) => {
      overlay.addLayer(
        L.circle([b.lat, b.lon], {
          radius: b.radius_m, color: '#f59e0b', weight: 1.2,
          dashArray: '4, 4', fillColor: '#f59e0b', fillOpacity: 0.07,
        }).bindPopup(`<strong>${b.tower_id} (${b.operator})</strong><br/>${b.area_name}<br/>MCC:${b.mcc} MNC:${b.mnc}`)
      );
    });

    // ── SIEM Impossible Travel Arcs ───────────────────────────
    (overview.siem_alerts || [])
      .filter((a: any) => a.status === 'OPEN' && a.velocity_kmh > 0)
      .forEach((a: any) => {
        overlay.addLayer(
          L.polyline([[a.phys_lat, a.phys_lon], [a.cyber_lat, a.cyber_lon]], {
            color: '#ef4444', weight: 2.5, dashArray: '6, 6',
          }).bindPopup(`<strong>IMPOSSIBLE TRAVEL (${a.mitre_id})</strong><br/>Unit: ${a.user_or_unit}`)
        );
      });

    // ── Forensic Evidence GPS Pins ────────────────────────────
    (overview.forensic_evidences || []).forEach((ev: any) => {
      if (ev.exif?.GPSLatitude && ev.exif?.GPSLongitude) {
        const icon = L.divIcon({
          className: 'tactical-pin',
          html: `<div style="background:#9d82b4;width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;border:2px solid #fff;font-size:11px">🧪</div>`,
          iconSize: [22, 22],
        });
        overlay.addLayer(
          L.marker([ev.exif.GPSLatitude, ev.exif.GPSLongitude], { icon })
            .bindPopup(`<strong>Bukti: ${ev.evidence_id}</strong><br/>${ev.file_name}`)
        );
      }
    });

    // ── Target Markers (diff-based) ───────────────────────────
    const cache = targetCacheRef.current;
    const seenIds = new Set<string>();

    (overview.targets || []).forEach((t: any) => {
      seenIds.add(t.target_id);
      // Skip targets with missing or invalid coordinates
      if (t.lat == null || t.lon == null || !isFinite(t.lat) || !isFinite(t.lon)) return;
      const locSrc = (t.loc_source || 'manual').toLowerCase();
      const isGeoIp = locSrc.startsWith('geoip');
      const isGps = locSrc === 'gps_osint';
      const isHw = locSrc.startsWith('hardware gps');

      let bg = '#6b7280';
      if (isHw) bg = '#ef4444';
      else if (isGps) bg = '#22c55e';
      else if (isGeoIp) bg = '#f59e0b';

      const icon = L.divIcon({
        className: 'tactical-pin',
        html: `<div style="background:${bg};width:24px;height:24px;border-radius:${isHw ? '4px' : '50%'};display:flex;align-items:center;justify-content:center;border:2px solid #fff;opacity:${isGeoIp ? 0.85 : 1}"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="7.5"/><circle cx="12" cy="12" r="3.5"/><path d="M12 1.5v3M12 19.5v3M1.5 12h3M19.5 12h3"/></svg></div>`,
        iconSize: [24, 24],
      });

      const popup = `<strong>${t.target_id}: ${t.code_name}</strong><br/>Risiko: ${t.risk_score}/100 (${t.risk_level})`;

      const existing = cache[t.target_id];
      if (existing) {
        existing.marker.setIcon(icon);
        existing.marker.setPopupContent(popup);
        const ll = existing.marker.getLatLng();
        if (Math.abs(ll.lat - t.lat) > 0.00001 || Math.abs(ll.lng - t.lon) > 0.00001) {
          existing.marker.setLatLng([t.lat, t.lon]);
          if (existing.circle) existing.circle.setLatLng([t.lat, t.lon]);
        }
      } else {
        const m = L.marker([t.lat, t.lon], { icon }).bindPopup(popup, { maxWidth: 260 });
        m.on('click', () => onSelectTarget(t.target_id));
        targetLayer.addLayer(m);
        const entry: { marker: L.Marker; circle?: L.Circle } = { marker: m };
        if (isGeoIp) {
          const circle = L.circle([t.lat, t.lon], {
            radius: 15000, color: '#f59e0b', weight: 1, fillColor: '#f59e0b', fillOpacity: 0.06, dashArray: '6 4',
          });
          targetLayer.addLayer(circle);
          entry.circle = circle;
        }
        cache[t.target_id] = entry;
      }
    });

    // Prune removed targets
    for (const id of Object.keys(cache)) {
      if (!seenIds.has(id)) {
        targetLayer.removeLayer(cache[id].marker);
        if (cache[id].circle) targetLayer.removeLayer(cache[id].circle);
        delete cache[id];
      }
    }

    // ── Unit Markers (persistent, animated) ───────────────────
    const unitMarkers = unitMarkersRef.current;
    const presentIds = new Set<string>();

    (overview.units || []).forEach((u: any) => {
      presentIds.add(u.unit_id);
      const col = UNIT_COLORS[u.status_color] || '#10b981';
      const trail = u.trail || [];
      let curLat = u.lat, curLon = u.lon;

      // Normalize trail: backend may return [{lat,lon,ts},...] or [[lat,lon],...]
      const normTrail: [number, number][] = trail
        .map((p: any) => {
          if (Array.isArray(p) && p.length >= 2 && p[0] != null && p[1] != null && isFinite(p[0]) && isFinite(p[1])) return [p[0], p[1]] as [number, number];
          if (p && typeof p === 'object' && p.lat != null && p.lon != null && isFinite(p.lat) && isFinite(p.lon)) return [p.lat, p.lon] as [number, number];
          return null;
        })
        .filter((p: any): p is [number, number] => p !== null);

      if (playbackPct < 100 && normTrail.length > 0) {
        const idx = Math.min(normTrail.length - 1, Math.floor((playbackPct / 100) * normTrail.length));
        curLat = normTrail[idx][0];
        curLon = normTrail[idx][1];
      }

      // Trail polyline
      if (normTrail.length > 1 && curLat != null && curLon != null) {
        overlay.addLayer(L.polyline([...normTrail, [curLat, curLon]], { color: col, weight: 3, opacity: 0.85 }));
      }

      // Skip unit if coordinates are invalid
      if (curLat == null || curLon == null || !isFinite(curLat) || !isFinite(curLon)) return;

      // BTS radius circle
      if (u.status_color === 'YELLOW' && u.bts_radius_m > 40) {
        overlay.addLayer(L.circle([curLat, curLon], {
          radius: u.bts_radius_m, color: '#f59e0b', fillColor: '#f59e0b', fillOpacity: 0.18,
        }));
      }

      const isSelected = u.unit_id === selectedUnitId;
      const sz = isSelected ? 28 : 22;
      const icon = L.divIcon({
        className: 'tactical-pin',
        html: `<div style="background:${col};width:${sz}px;height:${sz}px;border-radius:50%;display:flex;align-items:center;justify-content:center;border:${isSelected ? '3px solid #fff' : '2px solid #141109'};box-shadow:0 0 0 1px rgba(0,0,0,.35)${isSelected ? ',0 0 8px ' + col : ''};font-weight:800;font-size:9px;color:#141109;">${u.unit_id.slice(0, 3)}</div>`,
        iconSize: [sz, sz],
      });

      const popup = `<strong>${u.unit_id} (${u.callsign})</strong><br/>${u.name}<br/>Baterai: ${u.battery_pct}% | Sinyal: ${u.signal_dbm} dBm`;

      const existing = unitMarkers[u.unit_id];
      if (existing) {
        existing.marker.setIcon(icon);
        existing.marker.setPopupContent(popup);
        if (playbackPct >= 100) animateMarkerTo(existing.marker, curLat, curLon, 900);
        else existing.marker.setLatLng([curLat, curLon]);
      } else {
        const m = L.marker([curLat, curLon], { icon }).bindPopup(popup);
        m.on('click', () => onSelectUnit(u.unit_id));
        unitLayer.addLayer(m);
        unitMarkers[u.unit_id] = { marker: m };
      }
    });

    // Prune removed units
    Object.keys(unitMarkers).forEach(id => {
      if (!presentIds.has(id)) {
        unitLayer.removeLayer(unitMarkers[id].marker);
        delete unitMarkers[id];
      }
    });

    // ── Annotations (ATAK-style shared markers) ───────────────
    (overview.annotations || []).forEach((an: any) => {
      if (an.lat == null || an.lon == null) return;
      const color = an.color || '#f2a93b';
      if (an.kind === 'circle' && an.radius_m > 0) {
        overlay.addLayer(
          L.circle([an.lat, an.lon], { radius: an.radius_m, color, weight: 2, fillColor: color, fillOpacity: 0.12 })
        );
      } else {
        const icon = L.divIcon({
          className: 'tactical-pin',
          html: `<div style="background:${color};width:14px;height:14px;border-radius:3px;border:2px solid #141109"></div>`,
          iconSize: [14, 14],
        });
        overlay.addLayer(L.marker([an.lat, an.lon], { icon }).bindPopup(an.label || 'Marker'));
      }
    });

    // ── Triangulation overlay ─────────────────────────────────
    if (triangulation?.ok && triangulation.mode === 'REAL_OBSERVED_CELLS') {
      const tri = triangulation;
      (tri.towers || []).forEach(t => {
        overlay.addLayer(L.polyline([[t.lat, t.lon], [tri.lat, tri.lon]], { color: '#6f93a0', weight: 1, opacity: 0.5, dashArray: '3, 5' }));
        overlay.addLayer(L.circle([t.lat, t.lon], { radius: t.est_distance_m, color: '#6f93a0', weight: 0.8, opacity: 0.35, fill: false, dashArray: '2, 6' }));
      });
      overlay.addLayer(L.circle([tri.lat, tri.lon], { radius: tri.accuracy_m, color: '#6f93a0', weight: 1.5, fillColor: '#6f93a0', fillOpacity: 0.12 }));
      const triIcon = L.divIcon({
        className: 'tactical-pin',
        html: `<div style="width:18px;height:18px;background:#6f93a0;border:2px solid #fff;transform:rotate(45deg);box-shadow:0 0 10px #6f93a0"></div>`,
        iconSize: [18, 18],
      });
      overlay.addLayer(L.marker([tri.lat, tri.lon], { icon: triIcon }).bindPopup(`<strong>Estimasi Cell-ID</strong><br/>Akurasi: ±${tri.accuracy_m}m`));
    }

    // ── Cell Locate overlay ───────────────────────────────────
    if (cellLocate?.ok) {
      overlay.addLayer(L.circle([cellLocate.lat, cellLocate.lon], {
        radius: cellLocate.accuracy_m || 500, color: '#22c55e', weight: 1.5,
        fillColor: '#22c55e', fillOpacity: 0.1,
      }));
      const clIcon = L.divIcon({
        className: 'tactical-pin',
        html: `<div style="width:16px;height:16px;background:#22c55e;border-radius:50%;border:2px solid #fff;box-shadow:0 0 8px #22c55e"></div>`,
        iconSize: [16, 16],
      });
      overlay.addLayer(L.marker([cellLocate.lat, cellLocate.lon], { icon: clIcon }).bindPopup(`<strong>Cell Locate</strong><br/>±${cellLocate.accuracy_m}m`));
    }

    } catch (err) {
      console.error('[LeafletMap] Render error caught:', err);
    }
  }, [overview, selectedUnitId, triangulation, cellLocate, playbackPct, animateMarkerTo, onSelectUnit, onSelectTarget]);

  // ── Invalidate map size when container resizes ──────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const timer = setTimeout(() => map.invalidateSize(), 100);
    return () => clearTimeout(timer);
  });

  return (
    <div className="absolute inset-0">
      {/* Map container */}
      <div ref={containerRef} className="w-full h-full bg-background-deep" />

      {/* Tile style selector */}
      <div className="absolute top-2.5 right-2.5 z-[500] flex gap-0.5 bg-background-panel border border-border-dim rounded-sm p-0.5">
        {Object.keys(TILE_URLS).map(key => (
          <button
            key={key}
            className={cn(
              'px-2 py-1 bg-transparent border-none font-mono text-[9px] font-bold text-foreground-muted cursor-pointer rounded-sm tracking-[0.05em] transition-colors hover:bg-background-card hover:text-foreground',
              key === tileStyle && 'bg-background-card text-accent-steel'
            )}
            onClick={() => setTileStyle(key)}
          >
            {key === 'dark' ? 'TAKTIS' : key === 'satellite' ? 'SATELIT' : 'OSM'}
          </button>
        ))}
      </div>

      {/* Coordinate HUD */}
      {coordHud && (
        <div className="absolute bottom-2 left-2 z-[500] flex gap-3 bg-[rgba(20,17,9,0.88)] border border-border-dim rounded-sm px-2.5 py-1 font-mono text-[10px] text-foreground-muted max-md:flex-col max-md:gap-0.5">
          <span>MGRS: {coordHud.mgrs}</span>
          <span>UTM: {coordHud.utm}</span>
          <span>DMS: {coordHud.dms}</span>
          <span>DEC: {coordHud.decimal}</span>
        </div>
      )}
    </div>
  );
}
