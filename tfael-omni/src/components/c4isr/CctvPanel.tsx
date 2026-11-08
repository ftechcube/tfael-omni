// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — CCTV & Vision Panel (Tailwind migration)
// Camera live, CCTV detect, ANPR, sweep/heatmap, webcam motion tracking
// ═══════════════════════════════════════════════════════════════════════

import {
  useState, useRef, useCallback, useEffect, useMemo,
} from 'react';
import { cn } from '@/lib/utils';
import { useApp } from '@/context/AppContext';
import { Icon } from '@/components/icons/Icon';
import {
  fetchCctvList, cctvDetect, cctvSweep, anprCctv, anprImage,
  detectVision, forensicsIngest,
} from '@/api/endpoints';
import { useToast } from '@/hooks/useToast';
import type { CctvCamera, CctvDetectResult, AnprResult, CctvHeatmapEntry } from '@/types/api';

// ── Lookup objects ─────────────────────────────────────────────────
const LEVEL_COLORS: Record<string, string> = {
  lancar:  'text-[#22c55e]',
  sedang:  'text-[#f59e0b]',
  padat:   'text-[#ef4444]',
  offline: 'text-[#64748b]',
};

const RESULT_CLS: Record<string, string> = {
  error:    'border-destructive text-[#fca5a5]',
  warn:     'border-[#f59e0b] text-[#fde68a]',
  ok:       'border-[#4d6f78] text-[#cfe3e8] flex-col',
  anpr:     'border-[#a855f7] text-[#e9d5ff] flex-col',
  hitAlert: 'border-[#ef4444] text-[#fca5a5] mt-1.5 flex-col',
};

const RESULT_BASE = 'border border-border-dim rounded-md py-2 px-2.5 font-mono text-[10.5px] leading-relaxed break-all whitespace-pre-wrap text-foreground-muted flex flex-wrap items-start gap-1';

// ── Sub-tab enum ────────────────────────────────────────────────────
type SubTab = 'camera' | 'cctv';

const CCTV_LIVE_INTERVAL_MS = 6000;

// ── Component ───────────────────────────────────────────────────────

interface Props {
  onHeatmapUpdate?: (entries: CctvHeatmapEntry[]) => void;
  onFlyTo?: (lat: number, lon: number, zoom?: number) => void;
}

export function CctvPanel({ onHeatmapUpdate, onFlyTo }: Props) {
  const { refreshOverview } = useApp();
  const { toast } = useToast();

  const [subTab, setSubTab] = useState<SubTab>('camera');

  // ── Camera state ────────────────────────────────────────────────
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const prevFrameRef = useRef<Uint8ClampedArray | null>(null);
  const tickRef = useRef(0);
  const animRef = useRef<number | null>(null);
  const [webcamActive, setWebcamActive] = useState(false);
  const [cameraLog, setCameraLog] = useState(
    'Klik "Aktifkan kamera" untuk menjalankan deteksi gerakan/objek real-time, atau gunakan mode simulasi CCTV ANPR.',
  );

  // ── CCTV state ──────────────────────────────────────────────────
  const [cameras, setCameras] = useState<CctvCamera[]>([]);
  const [camerasLoaded, setCamerasLoaded] = useState(false);
  const [cctvUrl, setCctvUrl] = useState(
    'https://cctv-dishub.tangerangkab.go.id/storage/video/01jsnyfnzn18d0ca1m7p4ctvx1/01jsnyfnzn18d0ca1m7p4ctvx1.m3u8',
  );
  const [detectResult, setDetectResult] = useState<string>('');
  const [liveActive, setLiveActive] = useState(false);
  const liveTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const liveBusyRef = useRef(false);

  // ── Load camera list ────────────────────────────────────────────
  const loadCameras = useCallback(async (force = false) => {
    if (camerasLoaded && !force) return;
    try {
      const data = await fetchCctvList();
      if (data?.ok && data.cams?.length) {
        setCameras(data.cams);
        setCamerasLoaded(true);
      }
    } catch { /* ignore */ }
  }, [camerasLoaded]);

  useEffect(() => {
    if (subTab === 'cctv') loadCameras();
  }, [subTab, loadCameras]);

  // ── Webcam toggle ───────────────────────────────────────────────
  const toggleWebcam = useCallback(async () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
      if (videoRef.current) videoRef.current.srcObject = null;
      setWebcamActive(false);
      setCameraLog('Kamera dimatikan. Kembali ke mode simulasi CCTV.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 330, height: 170 },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setWebcamActive(true);
      setCameraLog('[LIVE WEBRTC ACTIVE] Kamera aktif! Mengalkulasi matriks diferensial gerakan piksel secara real-time...');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setCameraLog(`Gagal mengakses kamera (${msg}). Pastikan izin kamera browser diaktifkan.`);
    }
  }, []);

  // ── Canvas animation (motion tracking + simulation) ─────────────
  const animateCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const W = canvas.width;
    const H = canvas.height;
    tickRef.current += 1;

    const video = videoRef.current;

    // Live webcam mode — real pixel motion bounding box
    if (streamRef.current && video && video.readyState >= 2) {
      ctx.drawImage(video, 0, 0, W, H);
      const frame = ctx.getImageData(0, 0, W, H);
      const data = frame.data;
      let minX = W, minY = H, maxX = 0, maxY = 0, motionPx = 0;
      if (prevFrameRef.current && prevFrameRef.current.length === data.length) {
        const prev = prevFrameRef.current;
        for (let y = 10; y < H - 10; y += 4) {
          for (let x = 10; x < W - 10; x += 4) {
            const i = (y * W + x) * 4;
            const diff = Math.abs(data[i] - prev[i]) +
              Math.abs(data[i + 1] - prev[i + 1]) +
              Math.abs(data[i + 2] - prev[i + 2]);
            if (diff > 75) {
              motionPx++;
              if (x < minX) minX = x;
              if (y < minY) minY = y;
              if (x > maxX) maxX = x;
              if (y > maxY) maxY = y;
            }
          }
        }
      }
      prevFrameRef.current = new Uint8ClampedArray(data);

      if (motionPx > 12 && maxX > minX && maxY > minY) {
        ctx.strokeStyle = '#d9573d';
        ctx.lineWidth = 2;
        ctx.strokeRect(minX - 6, minY - 6, maxX - minX + 12, maxY - minY + 12);
        ctx.fillStyle = 'rgba(217, 87, 61, 0.9)';
        ctx.fillRect(minX - 6, Math.max(0, minY - 22), 185, 16);
        ctx.fillStyle = '#060a12';
        ctx.font = 'bold 9.5px monospace';
        ctx.fillText(`LIVE TARGET MOTION (${motionPx}px)`, minX - 2, Math.max(11, minY - 10));
      }
      ctx.fillStyle = '#10b981';
      ctx.font = 'bold 10px monospace';
      ctx.fillText('Kamera live. Pelacak gerak AI aktif.', 8, 14);
    } else {
      // Simulation fallback
      ctx.fillStyle = '#040811';
      ctx.fillRect(0, 0, W, H);
      ctx.strokeStyle = 'rgba(140, 150, 99, 0.22)';
      ctx.beginPath();
      ctx.moveTo(W * 0.35, 25);
      ctx.lineTo(15, H);
      ctx.moveTo(W * 0.65, 25);
      ctx.lineTo(W - 15, H);
      ctx.stroke();

      const vx = 75 + Math.sin(tickRef.current * 0.05) * 35;
      const vy = 55;
      ctx.strokeStyle = '#ef4444';
      ctx.lineWidth = 2;
      ctx.strokeRect(vx, vy, 115, 68);
      ctx.fillStyle = 'rgba(239, 68, 68, 0.85)';
      ctx.fillRect(vx, vy - 16, 155, 16);
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 9.5px monospace';
      ctx.fillText('CAR 0.96 | ANPR: B 1984 RFS', vx + 4, vy - 4);

      ctx.fillStyle = '#8c9663';
      ctx.font = '10px monospace';
      ctx.fillText('Simulasi CCTV. Aktifkan kamera untuk mulai.', 8, 14);
    }

    animRef.current = requestAnimationFrame(animateCanvas);
  }, []);

  // Start/stop canvas animation when camera subtab is active
  useEffect(() => {
    if (subTab === 'camera') {
      animRef.current = requestAnimationFrame(animateCanvas);
    }
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
      animRef.current = null;
    };
  }, [subTab, animateCanvas]);

  // Cleanup webcam on unmount
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
      }
      if (liveTimerRef.current) clearInterval(liveTimerRef.current);
    };
  }, []);

  // ── Capture frame to forensics ──────────────────────────────────
  const captureToForensics = useCallback(async () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dataUrl = canvas.toDataURL('image/jpeg', 0.92);
    const base64 = dataUrl.split(',')[1] || '';
    const fileName = `tangkapan_kamera_${Date.now()}.jpg`;
    try {
      const data = await forensicsIngest({
        file_name: fileName,
        content_b64: base64,
        linked_target_id: 'TGT-01',
      });
      const ev = (data as Record<string, unknown>)?.evidence as Record<string, unknown> | undefined;
      if (ev?.id) {
        await refreshOverview();
        const sha = String(ev.sha256 ?? '').slice(0, 24);
        setCameraLog(
          `Frame Kamera Disegel ke Brankas Forensik!\n` +
          `ID: ${ev.id} | SHA-256: ${sha}...\n` +
          `Buka tab REAL BINARY FORENSIC LAB untuk melihat analisis piksel ELA-nya.`,
        );
      }
    } catch {
      setCameraLog('Gagal menyegel frame ke forensik.');
    }
  }, [refreshOverview]);

  // ── Detect objects in frame ─────────────────────────────────────
  const detectObjects = useCallback(async () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    setCameraLog('Menjalankan deteksi objek pada frame...');
    const dataUrl = canvas.toDataURL('image/jpeg', 0.92);
    try {
      const { data } = await detectVision(dataUrl);
      const d = data as { ok: boolean; available?: boolean; count?: number; error?: string; detections?: Array<{ label: string; confidence: number }> };
      if (!d?.ok) {
        setCameraLog(`Deteksi gagal: ${d?.error ?? '?'}`);
      } else if (!d.available) {
        setCameraLog('Modul deteksi objek belum aktif. Hubungi admin untuk mengaktifkannya.');
      } else if (!(d.detections?.length)) {
        setCameraLog('Deteksi aktif — tidak ada objek terdeteksi pada frame.');
      } else {
        const lines = d.detections.slice(0, 8).map(
          o => ` • ${o.label} (${(o.confidence * 100).toFixed(0)}%)`,
        );
        setCameraLog(`Deteksi: ${d.count} objek terdeteksi\n${lines.join('\n')}`);
      }
    } catch (err) {
      setCameraLog(`Gagal: ${String(err)}`);
    }
  }, []);

  // ── ANPR from webcam frame ──────────────────────────────────────
  const anprFromWebcam = useCallback(async () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    setCameraLog('ANPR pada frame kamera... (beberapa detik)');
    try {
      const dataUrl = canvas.toDataURL('image/jpeg', 0.92);
      const { data } = await anprImage(dataUrl);
      if (data) setCameraLog(formatAnprResult(data));
    } catch (err) {
      setCameraLog(`Gagal: ${String(err)}`);
    }
  }, []);

  // ── CCTV detect ─────────────────────────────────────────────────
  const handleCctvDetect = useCallback(async (silent = false) => {
    const url = cctvUrl.trim();
    if (!url) {
      setDetectResult('ERR:Isi URL stream dulu.');
      return;
    }
    if (!silent) setDetectResult('LOADING:Mengambil frame & menjalankan deteksi objek...');
    try {
      const { data } = await cctvDetect(url);
      if (!data) { setDetectResult('ERR:Tidak ada respons'); return; }
      if (!data.ok) { setDetectResult(`ERR:${data.error || '?'}`); return; }
      if (!data.available) {
        setDetectResult(`WARN:Frame terambil (${data.frame_wh?.join('×')}), tapi deteksi objek belum aktif.`);
        return;
      }
      const chips = Object.entries(data.summary || {})
        .map(([k, v]) => `${k}: ${v}`)
        .join(' · ');
      let result = `OK:Deteksi: ${data.count} objek terdeteksi (frame ${data.frame_wh?.join('×')})\n${chips || 'tidak ada objek di atas ambang'}`;
      if (data.frame_b64) result += `\nIMG:${data.frame_b64}`;
      setDetectResult(result);
    } catch (err) {
      setDetectResult(`ERR:Gagal: ${String(err)}`);
    }
  }, [cctvUrl]);

  // ── CCTV live toggle ────────────────────────────────────────────
  const toggleLive = useCallback(() => {
    if (liveTimerRef.current) {
      clearInterval(liveTimerRef.current);
      liveTimerRef.current = null;
      setLiveActive(false);
      return;
    }
    setLiveActive(true);
    const tick = async () => {
      if (liveBusyRef.current) return;
      liveBusyRef.current = true;
      try { await handleCctvDetect(true); } finally { liveBusyRef.current = false; }
    };
    tick();
    liveTimerRef.current = setInterval(tick, CCTV_LIVE_INTERVAL_MS);
  }, [handleCctvDetect]);

  // ── CCTV sweep ──────────────────────────────────────────────────
  const handleSweep = useCallback(async () => {
    setDetectResult('LOADING:Memindai kepadatan semua CCTV (deteksi kendaraan per kamera)... ~15-40 detik.');
    try {
      const { data } = await cctvSweep();
      const d = data as { ok: boolean; error?: string; cached?: boolean; cams?: CctvHeatmapEntry[] };
      if (!d?.ok) { setDetectResult(`ERR:Gagal: ${d?.error || '?'}`); return; }
      const cams = d.cams ?? [];
      onHeatmapUpdate?.(cams);

      // Fly to camera spread
      const pts = cams.filter(c => c.lat != null).map(c => [c.lat!, c.lon!]);
      if (pts.length && onFlyTo) {
        const avgLat = pts.reduce((s, p) => s + p[0], 0) / pts.length;
        const avgLon = pts.reduce((s, p) => s + p[1], 0) / pts.length;
        onFlyTo(avgLat, avgLon, 12);
      }

      const lines = cams.map(c => {
        const vehicles = c.vehicles == null ? '—' : String(c.vehicles);
        return `${c.name}: ${vehicles} ${c.level}`;
      });
      setDetectResult(
        `SWEEP:Heatmap kepadatan (${cams.length} CCTV)${d.cached ? ' — cache' : ''}\n${lines.join('\n')}`,
      );
    } catch (err) {
      setDetectResult(`ERR:Gagal: ${String(err)}`);
    }
  }, [onHeatmapUpdate, onFlyTo]);

  // ── ANPR from CCTV ──────────────────────────────────────────────
  const handleAnprCctv = useCallback(async () => {
    const url = cctvUrl.trim();
    if (!url) { setDetectResult('ERR:Isi/pilih kamera dulu.'); return; }
    setDetectResult('LOADING:ANPR: ambil frame, deteksi kendaraan & baca pelat... (beberapa detik)');
    try {
      const { data } = await anprCctv(url);
      if (data) {
        setDetectResult(`ANPR:${JSON.stringify(data)}`);
        if (data.ok && data.hits?.length) {
          const cam = data.camera;
          if (cam?.lat != null && onFlyTo) onFlyTo(cam.lat, cam.lon!, 13);
          toast(`ANPR HIT: ${data.hits[0].plate} (${data.hits[0].target.code_name})`, 'warn');
          await refreshOverview();
        }
      }
    } catch (err) {
      setDetectResult(`ERR:Gagal: ${String(err)}`);
    }
  }, [cctvUrl, onFlyTo, toast, refreshOverview]);

  // ── Camera select ───────────────────────────────────────────────
  const cameraOptions = useMemo(() => (
    cameras.map(c => (
      <option key={c.stream_url} value={c.stream_url}>
        {c.name} — {c.location}
      </option>
    ))
  ), [cameras]);

  // ── Render helpers ──────────────────────────────────────────────
  const renderDetectResult = useCallback(() => {
    if (!detectResult) return null;
    const [prefix, ...rest] = detectResult.split(':');
    const body = rest.join(':');

    if (prefix === 'ERR') {
      return <div className={cn(RESULT_BASE, RESULT_CLS.error)}>{body}</div>;
    }
    if (prefix === 'WARN') {
      return <div className={cn(RESULT_BASE, RESULT_CLS.warn)}>{body}</div>;
    }
    if (prefix === 'LOADING') {
      return <div className={RESULT_BASE}><Icon name="camera" size={10} /> {body}</div>;
    }
    if (prefix === 'OK') {
      const lines = body.split('\n');
      const imgLine = lines.find(l => l.startsWith('IMG:'));
      const textLines = lines.filter(l => !l.startsWith('IMG:'));
      return (
        <>
          <div className={cn(RESULT_BASE, RESULT_CLS.ok)}>
            <Icon name="target" size={10} /> {textLines.join('\n')}
          </div>
          {imgLine && (
            <img
              src={imgLine.replace('IMG:', '')}
              alt="Frame CCTV"
              className="w-full rounded-md border border-border-dim mt-1.5"
            />
          )}
        </>
      );
    }
    if (prefix === 'SWEEP') {
      const lines = body.split('\n');
      const header = lines[0];
      const rows = lines.slice(1);
      return (
        <>
          <div className={cn(RESULT_BASE, RESULT_CLS.ok)}>
            <strong><Icon name="map" size={10} /> {header}</strong>
            <div className="text-[10px] opacity-70 mt-0.5">Titik berwarna muncul di peta.</div>
          </div>
          <div className="mt-1">
            {rows.map((row, i) => {
              const parts = row.split(': ');
              const name = parts[0];
              const detail = parts.slice(1).join(': ');
              const level = detail.includes('PADAT') ? 'padat' :
                detail.includes('SEDANG') ? 'sedang' :
                detail.includes('OFFLINE') ? 'offline' : 'lancar';
              return (
                <div key={i} className="flex justify-between border-b border-dashed border-border-dim py-0.5 font-mono text-[10px]">
                  <span>{name}</span>
                  <strong className={LEVEL_COLORS[level] ?? ''}>{detail}</strong>
                </div>
              );
            })}
          </div>
        </>
      );
    }
    if (prefix === 'ANPR') {
      try {
        const d = JSON.parse(body) as AnprResult;
        return <AnprResultDisplay data={d} />;
      } catch {
        return <div className={RESULT_BASE}>{body}</div>;
      }
    }
    return <div className={RESULT_BASE}>{detectResult}</div>;
  }, [detectResult]);

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Sub-tabs */}
      <div className="flex border-b border-border-dim px-2">
        <button
          className={cn(
            'flex-1 py-[7px] bg-transparent border-none border-b-2 border-b-transparent text-foreground-muted font-mono text-[10px] font-bold tracking-[0.05em] cursor-pointer text-center transition-colors hover:text-foreground',
            subTab === 'camera' && 'text-accent-steel border-b-accent-steel',
          )}
          onClick={() => setSubTab('camera')}
        >
          Kendali & kamera
        </button>
        <button
          className={cn(
            'flex-1 py-[7px] bg-transparent border-none border-b-2 border-b-transparent text-foreground-muted font-mono text-[10px] font-bold tracking-[0.05em] cursor-pointer text-center transition-colors hover:text-foreground',
            subTab === 'cctv' && 'text-accent-steel border-b-accent-steel',
          )}
          onClick={() => setSubTab('cctv')}
        >
          CCTV publik
        </button>
      </div>

      {/* ── Camera Tab ─────────────────────────────────── */}
      {subTab === 'camera' && (
        <div className="p-2 flex flex-col gap-1.5">
          <div className="flex justify-between items-center mb-1">
            <span className="font-bold text-accent-steel text-[11px] flex items-center gap-1">
              <Icon name="camera" size={10} /> Kamera live & deteksi gerak
            </span>
            <button
              className="flex items-center gap-1 py-0.5 px-2 bg-[#0f2e26] border border-[#22c55e] rounded-sm text-[#86efac] font-mono text-[10px] font-bold cursor-pointer transition-opacity hover:opacity-85"
              onClick={toggleWebcam}
            >
              <Icon name={webcamActive ? 'stop' : 'camera'} size={10} />
              {webcamActive ? ' Matikan kamera' : ' Aktifkan kamera'}
            </button>
          </div>

          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="hidden"
          />
          <canvas
            ref={canvasRef}
            width={330}
            height={170}
            className="w-full rounded-md border border-border-dim bg-[#040810]"
          />

          <div className="flex flex-col gap-1">
            <button
              className="w-full flex items-center gap-[5px] py-1.5 px-2.5 bg-background-card border border-border-dim rounded-sm text-foreground font-mono text-[10.5px] font-semibold cursor-pointer transition-colors hover:border-primary"
              onClick={captureToForensics}
            >
              <Icon name="camera" size={10} /> Tangkap frame & segel ke brankas forensik
            </button>
            <button
              className="w-full flex items-center gap-[5px] py-1.5 px-2.5 bg-background-card border border-border-dim rounded-sm text-foreground font-mono text-[10.5px] font-semibold cursor-pointer transition-colors hover:border-primary"
              onClick={detectObjects}
            >
              <Icon name="target" size={10} /> Deteksi objek pada frame
            </button>
            <button
              className="w-full flex items-center gap-[5px] py-1.5 px-2.5 bg-background-card border border-border-dim rounded-sm text-foreground font-mono text-[10.5px] font-semibold cursor-pointer transition-colors hover:border-primary"
              onClick={anprFromWebcam}
            >
              <Icon name="search" size={10} /> ANPR pada frame kamera
            </button>
          </div>

          <div className="border border-border-dim rounded-md py-2 px-2.5 font-mono text-[10.5px] text-foreground-muted leading-relaxed break-all whitespace-pre-wrap">
            {cameraLog.split('\n').map((line, i) => (
              <div key={i}>{line}</div>
            ))}
          </div>
        </div>
      )}

      {/* ── CCTV Tab ───────────────────────────────────── */}
      {subTab === 'cctv' && (
        <div className="p-2 flex flex-col gap-1.5">
          <div className="text-[11px] text-foreground-muted leading-normal mb-1">
            Ambil 1 frame dari CCTV lalu-lintas publik (ATCS Dishub)
            lalu deteksi objek nyata (kendaraan/orang).
          </div>

          <label className="font-mono text-[10px] text-foreground-muted mt-1">Pilih kamera (ATCS Dishub Tangerang)</label>
          <select
            className="w-full py-[5px] px-2 bg-background-card border border-border-dim rounded-sm text-foreground font-mono text-[10.5px] cursor-pointer"
            onChange={e => { if (e.target.value) setCctvUrl(e.target.value); }}
            defaultValue=""
          >
            <option value="">
              {camerasLoaded
                ? `— pilih kamera (${cameras.length}) —`
                : '— memuat daftar kamera... —'}
            </option>
            {cameraOptions}
          </select>

          <label className="font-mono text-[10px] text-foreground-muted mt-1">atau tempel URL stream CCTV (HLS .m3u8)</label>
          <input
            className="w-full py-[5px] px-2 bg-background-card border border-border-dim rounded-sm text-foreground font-mono text-[10.5px] box-border"
            value={cctvUrl}
            onChange={e => setCctvUrl(e.target.value)}
          />

          <div className="flex gap-1.5 mt-1">
            <button
              className="flex-1 flex items-center justify-center gap-[5px] py-1.5 px-2.5 bg-background-card border border-border-dim rounded-sm text-foreground font-mono text-[10.5px] font-semibold cursor-pointer transition-colors hover:border-primary"
              onClick={() => handleCctvDetect()}
            >
              <Icon name="target" size={10} /> Deteksi 1 frame
            </button>
            <button
              className={cn(
                'flex-1 py-1.5 px-2.5 bg-[#1e293b] border border-[#22c55e] rounded-sm text-[#86efac] font-mono text-[10.5px] font-bold cursor-pointer transition-colors',
                liveActive && 'bg-[#064e3b] text-white',
              )}
              onClick={toggleLive}
            >
              {liveActive ? '■ Stop live' : '● Live (auto)'}
            </button>
          </div>

          <button
            className="w-full flex items-center justify-center gap-[5px] py-1.5 px-2.5 bg-background-card border border-border-dim rounded-sm text-foreground font-mono text-[10.5px] font-semibold cursor-pointer transition-colors hover:border-primary"
            onClick={handleAnprCctv}
          >
            <Icon name="search" size={10} /> ANPR: baca pelat & cek watchlist target
          </button>
          <button
            className="w-full flex items-center justify-center gap-[5px] py-1.5 px-2.5 bg-[#1e293b] border border-[#22c55e] rounded-sm text-[#86efac] font-mono text-[10.5px] font-semibold cursor-pointer transition-colors hover:border-primary"
            onClick={handleSweep}
          >
            <Icon name="map" size={10} /> Pindai kepadatan semua CCTV jadi heatmap
          </button>

          <div className="mt-1">
            {renderDetectResult()}
          </div>
        </div>
      )}
    </div>
  );
}

// ── ANPR Result sub-component ───────────────────────────────────────
function AnprResultDisplay({ data }: { data: AnprResult }) {
  if (!data.ok) {
    return <div className={cn(RESULT_BASE, RESULT_CLS.error)}>ANPR gagal: {data.error || '?'}</div>;
  }
  const hits = data.hits ?? [];
  return (
    <>
      <div className={cn(RESULT_BASE, RESULT_CLS.anpr)}>
        <strong>
          <Icon name="search" size={10} /> ANPR: {data.vehicles} kendaraan, {data.plates_read} pelat terbaca
        </strong>{' '}
        (watchlist: {data.watchlist_size} target)
        <div className="flex flex-wrap gap-[3px] mt-1">
          {(data.plates ?? []).map((p, i) => (
            <span
              key={i}
              className={cn(
                'inline-block bg-[#2e1065] text-[#d8b4fe] border border-[#a855f7] rounded px-[7px] py-px text-[11px]',
                p.watchlist_hit && 'bg-[#7f1d1d] text-[#fecaca] border-[#ef4444]',
              )}
            >
              {p.plate}{p.watchlist_hit ? ' ⚠' : ''}
            </span>
          ))}
          {!(data.plates?.length) && <em>tak ada pelat terbaca</em>}
        </div>
      </div>
      {hits.length > 0 && (
        <div className={cn(RESULT_BASE, RESULT_CLS.hitAlert)}>
          <strong>🚨 {hits.length} HIT WATCHLIST:</strong>
          {hits.map((h, i) => (
            <div key={i}> • <strong>{h.plate}</strong> → {h.target.code_name} ({h.target.target_id})</div>
          ))}
        </div>
      )}
      {data.frame_b64 && (
        <img src={data.frame_b64} alt="Frame ANPR" className="w-full rounded-md border border-border-dim mt-1.5" />
      )}
      {data.note && <div className="text-[9.5px] text-[#64748b] mt-1">{data.note}</div>}
    </>
  );
}

// ── Format ANPR for camera log ──────────────────────────────────────
function formatAnprResult(d: AnprResult): string {
  if (!d.ok) return `ANPR gagal: ${d.error || '?'}`;
  const plates = (d.plates ?? []).map(p => `${p.plate}${p.watchlist_hit ? ' ⚠' : ''}`).join(', ');
  const hits = (d.hits ?? []).map(h => `${h.plate} → ${h.target.code_name}`).join(', ');
  let result = `ANPR: ${d.vehicles} kendaraan, ${d.plates_read} pelat terbaca\nPelat: ${plates || 'tak ada'}`;
  if (hits) result += `\n🚨 HIT WATCHLIST: ${hits}`;
  return result;
}
