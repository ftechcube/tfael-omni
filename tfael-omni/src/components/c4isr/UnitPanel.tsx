// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Unit Panel (Tailwind migration)
// Unit list + selected unit inspector with C2 controls
// ═══════════════════════════════════════════════════════════════════════

import { useState, useCallback } from 'react';
import { useApp } from '@/context/AppContext';
import { Icon } from '@/components/icons/Icon';
import {
  forcePing, triangulate, cellLocate, geoConvert,
} from '@/api/endpoints';
import type {
  Unit, ForcePingResult, TriangulationResult, CellLocateResult,
} from '@/types/api';
import { cn } from '@/lib/utils';

// ── Tailwind lookup objects ─────────────────────────────────────────

const TAG_COLORS: Record<string, string> = {
  GREEN:  'bg-[#064e3b] text-[#6ee7b7]',
  YELLOW: 'bg-[#78350f] text-[#fde68a]',
  BLUE:   'bg-[#1e3a5f] text-[#a7c6cf]',
  RED:    'bg-[#7f1d1d] text-[#fca5a5]',
};

const C2_BTN: Record<string, string> = {
  amber:   'bg-[#78350f] border-[#f59e0b] text-[#fde68a]',
  crimson: 'bg-[#7f1d1d] border-destructive text-[#fca5a5]',
  blue:    'bg-[#1e293b] border-[#6f93a0] text-[#a7c6cf]',
  green:   'bg-[#0f2e26] border-[#22c55e] text-[#86efac]',
};

const CRYPTO_BOX: Record<string, string> = {
  crimson: 'border-destructive text-[#fca5a5]',
  green:   'border-[#22c55e] text-[#86efac]',
  amber:   'border-[#f59e0b] text-[#fde68a]',
  blue:    'border-[#6f93a0] text-[#cfe3e8]',
};

// ── Helpers ──────────────────────────────────────────────────────────

const CHANNEL_LABELS: Record<string, string> = {
  GPS_NORMAL: 'NORMAL',
  BTS_FALLBACK: 'BTS ONLY',
  SOS_EMERGENCY: 'SOS',
  OFFLINE: 'OFFLINE',
};

function humanChannel(ch: string): string {
  return CHANNEL_LABELS[ch] || ch;
}

function timeAgo(iso?: string): string {
  if (!iso) return '—';
  const t = Date.parse(iso);
  if (isNaN(t)) return '—';
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 45) return 'baru saja';
  if (s < 3600) return Math.floor(s / 60) + ' menit lalu';
  if (s < 86400) return Math.floor(s / 3600) + ' jam lalu';
  return Math.floor(s / 86400) + ' hari lalu';
}

// ── Component ────────────────────────────────────────────────────────

interface Props {
  selectedUnitId: string | null;
  onSelectUnit: (id: string) => void;
  onFlyTo?: (lat: number, lon: number, zoom?: number) => void;
  onTriangulation?: (result: TriangulationResult | null) => void;
  onCellLocate?: (result: CellLocateResult | null) => void;
}

export function UnitPanel({ selectedUnitId, onSelectUnit, onFlyTo, onTriangulation, onCellLocate }: Props) {
  const { overview, refreshOverview } = useApp();
  const units = overview?.units ?? [];

  const [pingResult, setPingResult] = useState<ForcePingResult | null>(null);
  const [triResult, setTriResult] = useState<TriangulationResult | null>(null);
  const [cellResult, setCellResult] = useState<CellLocateResult | null>(null);
  const [unitMgrs, setUnitMgrs] = useState<string>('menghitung…');
  const [busy, setBusy] = useState('');

  const selectedUnit = units.find(u => u.unit_id === selectedUnitId) ?? units[0] ?? null;

  // Load MGRS for selected unit
  const loadMgrs = useCallback(async (u: Unit) => {
    setUnitMgrs('menghitung…');
    try {
      const { data } = await geoConvert(u.lat, u.lon);
      setUnitMgrs(data?.ok ? (data as Record<string, string>).mgrs ?? '—' : '—');
    } catch {
      setUnitMgrs('—');
    }
  }, []);

  const handleSelect = useCallback((id: string) => {
    onSelectUnit(id);
    setPingResult(null);
    setTriResult(null);
    setCellResult(null);
    const u = units.find(x => x.unit_id === id);
    if (u) {
      loadMgrs(u);
      onFlyTo?.(u.lat, u.lon, 14);
    }
  }, [units, onSelectUnit, onFlyTo, loadMgrs]);

  // ── C2 Actions ────────────────────────────────────────────────────
  const handleForcePing = useCallback(async (spoofAttack: boolean) => {
    if (!selectedUnit) return;
    setBusy(spoofAttack ? 'spoof' : 'ping');
    try {
      const { data } = await forcePing(selectedUnit.unit_id, spoofAttack);
      setPingResult(data as ForcePingResult);
      await refreshOverview();
    } catch {
      setPingResult(null);
    }
    setBusy('');
  }, [selectedUnit, refreshOverview]);

  const handleTriangulate = useCallback(async () => {
    if (!selectedUnit) return;
    setBusy('tri');
    try {
      const { data } = await triangulate(selectedUnit.unit_id);
      const d = data as TriangulationResult;
      setTriResult(d);
      onTriangulation?.(d ?? null);
      if (d?.ok) {
        onFlyTo?.(d.lat!, d.lon!, 13);
      }
    } catch {
      setTriResult(null);
      onTriangulation?.(null);
    }
    setBusy('');
  }, [selectedUnit, onFlyTo, onTriangulation]);

  const handleCellLocate = useCallback(async () => {
    if (!selectedUnit) return;
    if (!selectedUnit.lac || !selectedUnit.cid || !selectedUnit.mcc) {
      setCellResult({
        ok: false,
        error: 'Unit belum punya data sel serving.',
        detail: 'Nyalakan seluler di HP agar aplikasi mengirim serving cell asli.',
      });
      return;
    }
    setBusy('cell');
    setCellResult({ ok: false, pending: true } as CellLocateResult);
    try {
      const { data } = await cellLocate({
        radio: 'lte',
        mcc: selectedUnit.mcc,
        mnc: selectedUnit.mnc,
        cells: [{ lac: selectedUnit.lac, cid: selectedUnit.cid, signal: selectedUnit.signal_dbm || undefined }],
        attach_unit_id: selectedUnit.unit_id,
      });
      const r = data as CellLocateResult;
      setCellResult(r);
      onCellLocate?.(r ?? null);
      if (r?.ok) {
        await refreshOverview();
        onFlyTo?.(r.lat!, r.lon!, 14);
      }
    } catch {
      setCellResult({ ok: false, error: 'Server tidak merespons.' });
      onCellLocate?.(null);
    }
    setBusy('');
  }, [selectedUnit, refreshOverview, onFlyTo, onCellLocate]);

  // ── Render ────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-2 h-full overflow-y-auto">
      {/* ── Unit List ─────────────────────────────── */}
      <div className="p-2">
        <div className="font-mono text-[10px] font-extrabold tracking-[0.12em] text-foreground-muted mb-1.5 flex items-center gap-[5px]">
          <Icon name="radio" size={12} /> UNIT LAPANGAN
        </div>
        {units.length === 0 ? (
          <div className="text-center py-5 px-2.5 text-foreground-muted text-xs">
            Belum ada unit lapangan terhubung.
            <span className="block mt-1.5 text-[11px] opacity-60">Hubungkan GPS Mac atau perangkat lapangan untuk mulai melacak.</span>
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            {units.map(u => (
              <button
                key={u.unit_id}
                className={cn(
                  'block w-full bg-background-card border border-border-dim rounded-sm py-2 px-2.5 cursor-pointer text-left font-sans text-xs text-foreground transition-colors hover:border-primary hover:bg-background-hover',
                  u.unit_id === selectedUnitId && 'border-accent-steel bg-[rgba(111,147,160,0.08)]'
                )}
                onClick={() => handleSelect(u.unit_id)}
              >
                <div className="flex justify-between items-center mb-[3px] font-bold text-xs">
                  <span>{u.unit_id} <small className="text-foreground-muted font-normal">({u.callsign})</small></span>
                  <span className={cn('inline-block px-[7px] py-px rounded font-mono text-[9px] font-extrabold tracking-[0.05em]', TAG_COLORS[u.status_color] ?? '')}>
                    {humanChannel(u.channel)}
                  </span>
                </div>
                <div className="text-[11.5px] mb-1 text-[#cbd5e1]">{u.name}</div>
                <div className="font-mono text-[10px] text-foreground-muted leading-relaxed">
                  <Icon name="pin" size={10} /> {u.lat.toFixed(4)}, {u.lon.toFixed(4)} | <Icon name="battery" size={10} /> {u.battery_pct}% | <Icon name="signal" size={10} /> {u.signal_dbm} dBm
                  <br /><Icon name="clock" size={10} /> Terlihat {timeAgo(u.last_seen)}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── Unit Inspector ─────────────────────────── */}
      {selectedUnit && (
        <div className="bg-background-card border border-border-dim rounded-md p-2.5 mx-2 mb-2 max-md:mx-1 max-md:mb-1 max-md:p-2">
          <div className="flex justify-between items-center mb-1.5">
            <span className="font-extrabold text-[13px]">{selectedUnit.unit_id} // {selectedUnit.role}</span>
            <span className={cn('inline-block px-[7px] py-px rounded font-mono text-[9px] font-extrabold tracking-[0.05em]', TAG_COLORS[selectedUnit.status_color] ?? '')}>
              {humanChannel(selectedUnit.channel)}
            </span>
          </div>

          <div className="font-mono text-[10.5px] text-foreground-muted leading-[1.7] mb-2">
            • Koordinat: <strong>{selectedUnit.lat.toFixed(5)}, {selectedUnit.lon.toFixed(5)}</strong> (Alt: {selectedUnit.alt_m}m)<br />
            • MGRS: <strong className="text-[#6ee7b7] font-mono">{unitMgrs}</strong><br />
            • Kecepatan: {selectedUnit.speed_kmh} km/jam | Baterai: {selectedUnit.battery_pct}%<br />
            • Menara BTS: MCC {selectedUnit.mcc} / MNC {selectedUnit.mnc} / LAC {selectedUnit.lac} / CID {selectedUnit.cid}<br />
            • Estimasi Radius Presisi: ±{selectedUnit.bts_radius_m} meter
          </div>

          {/* C2 Buttons */}
          <div className="flex flex-col gap-1 mb-2">
            <button
              className={cn('w-full flex items-center gap-1.5 py-[7px] px-2.5 border rounded-sm font-mono text-[10.5px] font-bold cursor-pointer transition-opacity disabled:opacity-50 disabled:cursor-not-allowed', C2_BTN.amber)}
              disabled={busy !== ''}
              onClick={() => handleForcePing(false)}
            >
              <Icon name="zap" size={12} />
              {busy === 'ping' ? 'Mengirim…' : 'Kirim ping GPS sekarang (SMS terenkripsi)'}
            </button>
            <button
              className={cn('w-full flex items-center gap-1.5 py-[7px] px-2.5 border rounded-sm font-mono text-[10.5px] font-bold cursor-pointer transition-opacity disabled:opacity-50 disabled:cursor-not-allowed', C2_BTN.crimson)}
              disabled={busy !== ''}
              onClick={() => handleForcePing(true)}
            >
              <Icon name="shield" size={12} />
              {busy === 'spoof' ? 'Menguji…' : 'Uji keamanan: tolak SMS spoofing'}
            </button>
            <button
              className={cn('w-full flex items-center gap-1.5 py-[7px] px-2.5 border rounded-sm font-mono text-[10.5px] font-bold cursor-pointer transition-opacity disabled:opacity-50 disabled:cursor-not-allowed', C2_BTN.blue)}
              disabled={busy !== ''}
              onClick={handleTriangulate}
            >
              <Icon name="triangulate" size={12} />
              {busy === 'tri' ? 'Menghitung…' : `Triangulasi Cell-ID offline (${(overview?.bts_tower_count ?? 0).toLocaleString('id')} menara)`}
            </button>
            <button
              className={cn('w-full flex items-center gap-1.5 py-[7px] px-2.5 border rounded-sm font-mono text-[10.5px] font-bold cursor-pointer transition-opacity disabled:opacity-50 disabled:cursor-not-allowed', C2_BTN.green)}
              disabled={busy !== ''}
              onClick={handleCellLocate}
            >
              <Icon name="satellite" size={12} />
              {busy === 'cell' ? 'Menghubungi…' : 'Geolokasi sel NYATA (Unwired Labs)'}
            </button>
          </div>

          {/* Ping Result */}
          {pingResult && <PingResultBox result={pingResult} />}
          {/* Triangulation Result */}
          {triResult && <TriangulationResultBox result={triResult} />}
          {/* Cell Locate Result */}
          {cellResult && <CellLocateResultBox result={cellResult} />}
        </div>
      )}
    </div>
  );
}

// ── Sub-components for result boxes ──────────────────────────────────

function PingResultBox({ result: r }: { result: ForcePingResult }) {
  if (r.spoof_blocked) {
    return (
      <div className={cn('border rounded-md py-2 px-2.5 mt-1.5 font-mono text-[10.5px] leading-relaxed break-all', CRYPTO_BOX.crimson)}>
        <strong><Icon name="shield" size={12} /> ANTI-SPOOFING: PERINTAH PALSU DITOLAK 100%!</strong><br />
        Status: {r.verify_status}<br />
        PDU Port: {r.command_packet?.udh_port} | Nonce: {r.command_packet?.nonce_hex}<br />
        Tag Diterima: {r.verification_meta?.received_hmac}<br />
        Tag Seharusnya: {r.verification_meta?.expected_hmac}<br />
        <Icon name="alert" size={12} /> <em>Alert SIEM {r.siem_alert_triggered} otomatis diterbitkan!</em>
      </div>
    );
  }

  if (!r.ok) return null;

  const sim = r.simulated;
  return (
    <div className={cn('border rounded-md py-2 px-2.5 mt-1.5 font-mono text-[10.5px] leading-relaxed break-all', sim ? CRYPTO_BOX.amber : CRYPTO_BOX.green)}>
      <strong><Icon name="check" size={12} /> C2 PING: Kripto terverifikasi ({r.crypto_processing_ms} ms)</strong>{' '}
      {sim ? (
        <span className="inline-block bg-[#78350f] text-[#fde68a] px-1.5 py-px rounded text-[10px]"><Icon name="alert" size={10} /> SIMULASI</span>
      ) : (
        <span className="inline-block bg-[#064e3b] text-[#6ee7b7] px-1.5 py-px rounded text-[10px]">● Fix terkunci</span>
      )}<br />
      <strong>• Sumber fix:</strong> {r.fix_source}<br />
      <strong>[1] TX SMS Binary Port 8901:</strong> {r.command_packet?.packet_hex}<br />
      <strong>• HMAC-SHA256 (96-bit):</strong> {r.command_packet?.hmac_tag_hex}<br />
      <strong>[2] RX Balasan AES-128-GCM ({r.encrypted_reply?.wire_size_bytes}B):</strong><br />
      <strong>• Ciphertext:</strong> {r.encrypted_reply?.ciphertext_hex?.slice(0, 32)}…<br />
      <strong>• GCM Tag:</strong> {r.encrypted_reply?.auth_tag_hex}<br />
      <strong>• Koordinat:</strong> {r.position?.lat}, {r.position?.lon}
      {sim && (
        <div className="opacity-80 text-[11px] mt-1">
          Kripto HMAC/AES asli, tetapi posisi bukan dari perangkat nyata.
        </div>
      )}
    </div>
  );
}

function TriangulationResultBox({ result: r }: { result: TriangulationResult }) {
  if (!r.ok) {
    return (
      <div className={cn('border rounded-md py-2 px-2.5 mt-1.5 font-mono text-[10.5px] leading-relaxed break-all', CRYPTO_BOX.crimson)}>
        <strong><Icon name="triangulate" size={12} /> TRIANGULASI GAGAL:</strong> {r.error}
      </div>
    );
  }

  const realMode = r.mode === 'REAL_OBSERVED_CELLS';
  if (!realMode) {
    return (
      <div className={cn('border rounded-md py-2 px-2.5 mt-1.5 font-mono text-[10.5px] leading-relaxed break-all', CRYPTO_BOX.blue)}>
        <strong><Icon name="triangulate" size={12} /> TRIANGULASI CELL-ID</strong>{' '}
        <span className="inline-block bg-[#1e3a5f] text-[#a7c6cf] px-1.5 py-px rounded text-[10px]">menunggu sel nyata</span><br />
        <span className="opacity-80 text-[11px]">
          Unit ini belum melaporkan sel seluler yang benar-benar terdengar.
          Jalankan aplikasi agent (ATAK) di HP dengan seluler aktif.
        </span>
      </div>
    );
  }

  const errTxt = r.error_vs_truth_m != null
    ? `${r.error_vs_truth_m} m ${r.within_accuracy ? '✓ (di dalam radius)' : '⚠ (di luar radius)'}`
    : 'N/A';

  return (
    <div className={cn('border rounded-md py-2 px-2.5 mt-1.5 font-mono text-[10.5px] leading-relaxed break-all', CRYPTO_BOX.blue)}>
      <strong><Icon name="triangulate" size={12} /> ESTIMASI POSISI MULTILATERASI CELL-ID</strong>{' '}
      <span className="inline-block bg-[#064e3b] text-[#6ee7b7] px-1.5 py-px rounded text-[10px]">● Sel &amp; RSSI terukur</span><br />
      <strong>• Metode:</strong> {r.method}<br />
      <strong>• Menara dipakai:</strong> {r.num_towers} BTS<br />
      <strong>• Posisi estimasi:</strong> {r.lat}, {r.lon}<br />
      <strong>• Radius akurasi (95%):</strong> ±{r.accuracy_m} m
      {r.residual_rms_m != null && ` | Residu RMS: ${r.residual_rms_m} m`}<br />
      {r.error_vs_truth_m != null && (
        <><strong>• Galat vs GPS asli:</strong> {errTxt}<br /></>
      )}
      <strong>• Model radio:</strong> ref {r.model?.ref_rssi_dbm} dBm @1m, path-loss n={r.model?.path_loss_exp}<br />
      <span className="opacity-60 text-[10px]">Data posisi menara: © OpenCellID</span><br />
      {r.towers?.map((t, i) => (
        <span key={i} className="opacity-85 text-[10px]">
          &nbsp;&nbsp;• {t.tower_id} ({t.operator}): RSSI {t.rssi_dbm} dBm → d̂ {t.est_distance_m} m<br />
        </span>
      ))}
    </div>
  );
}

function CellLocateResultBox({ result: r }: { result: CellLocateResult }) {
  if (r.pending) {
    return (
      <div className={cn('border rounded-md py-2 px-2.5 mt-1.5 font-mono text-[10.5px] leading-relaxed break-all', CRYPTO_BOX.blue)}>
        <Icon name="satellite" size={12} /> Menghubungi Unwired Labs…
      </div>
    );
  }
  if (!r.ok) {
    return (
      <div className={cn('border rounded-md py-2 px-2.5 mt-1.5 font-mono text-[10.5px] leading-relaxed break-all', CRYPTO_BOX.crimson)}>
        <strong><Icon name="satellite" size={12} /> GEOLOKASI SEL GAGAL:</strong> {r.error}
        {r.detail && <><br /><span className="text-foreground-muted font-normal">{r.detail}</span></>}
      </div>
    );
  }
  return (
    <div className={cn('border rounded-md py-2 px-2.5 mt-1.5 font-mono text-[10.5px] leading-relaxed break-all', CRYPTO_BOX.green)}>
      <strong><Icon name="satellite" size={12} /> GEOLOKASI SEL NYATA (Unwired Labs)</strong><br />
      <strong>• Penyedia:</strong> {r.provider ?? 'UnwiredLabs'}{r.cached ? ' (cache)' : ''}<br />
      <strong>• Posisi:</strong> {r.lat}, {r.lon}<br />
      <strong>• Akurasi:</strong> ±{r.accuracy_m} m<br />
      <strong>• Sel dipakai:</strong> {r.num_cells} ({r.radio})<br />
      {r.balance_remaining != null && (
        <><strong>• Sisa kuota:</strong> {r.balance_remaining}<br /></>
      )}
      {r.attached_unit_id && (
        <><strong>• Dipasang ke unit:</strong> {r.attached_unit_id}<br /></>
      )}
      <span className="opacity-60 text-[10px]">Data menara: Unwired Labs / © OpenCellID</span>
    </div>
  );
}
