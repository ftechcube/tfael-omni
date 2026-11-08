// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Host Telemetry (Tailwind migration)
// CPU / memory / disk / network gauge cards per host
// ═══════════════════════════════════════════════════════════════════════

import { useState, useCallback, useEffect } from 'react';
import type { HostTelemetry as HostData } from '@/types/api';
import { hostGeoip } from '@/api/endpoints';
import { useToast } from '@/hooks/useToast';
import { cn } from '@/lib/utils';

function gaugeColor(pct: number): string {
  if (pct >= 90) return '#ef4444';
  if (pct >= 70) return '#f97316';
  if (pct >= 50) return '#eab308';
  return '#22c55e';
}

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

interface HostCardProps {
  host: HostData;
}

function HostCard({ host }: HostCardProps) {
  const gauges = [
    { label: 'CPU', value: host.cpu_pct },
    { label: 'MEM', value: host.mem_pct },
    { label: 'DISK', value: host.disk_pct },
  ];

  return (
    <div className="p-3.5 bg-background-card border border-border-dim rounded-lg transition-colors hover:border-primary/50">
      <div className="flex justify-between items-center mb-2.5">
        <span className="text-sm font-bold font-mono">{host.hostname}</span>
        <span className="px-2 py-0.5 bg-primary/10 border border-primary/20 rounded-sm text-[9px] font-mono text-primary">
          {host.os}
        </span>
      </div>

      <div className="flex flex-col gap-2">
        {gauges.map(g => (
          <div key={g.label} className="flex items-center gap-2">
            <span className="min-w-[36px] text-2xs font-mono opacity-60 uppercase">
              {g.label}
            </span>
            <div className="flex-1 h-2 bg-white/[0.06] rounded overflow-hidden">
              <div
                className="h-full rounded transition-[width] duration-[600ms] ease-out"
                style={{
                  width: `${Math.min(g.value, 100)}%`,
                  background: gaugeColor(g.value),
                }}
              />
            </div>
            <span
              className="min-w-[40px] text-right text-[11px] font-bold font-mono"
              style={{ color: gaugeColor(g.value) }}
            >
              {g.value.toFixed(1)}%
            </span>
          </div>
        ))}
      </div>

      <div className="flex gap-2.5 mt-2.5 text-2xs font-mono opacity-50 flex-wrap">
        <span>Uptime: {formatUptime(host.uptime)}</span>
        <span>Koneksi: {host.net_conns}</span>
        <span>Proses: {host.processes}</span>
      </div>

      {host.geo && (
        <div className="mt-1.5 inline-flex items-center gap-1 px-2 py-0.5 bg-green-500/10 border border-green-500/20 rounded text-2xs font-mono text-green-300">
          📍 {host.geo.city}, {host.geo.country}
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────

interface HostTelemetryProps {
  hosts?: HostData[];
}

export function HostTelemetry({ hosts: propHosts }: HostTelemetryProps) {
  const [localHost, setLocalHost] = useState<HostData | null>(null);
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  const fetchLocalHost = useCallback(async () => {
    setLoading(true);
    try {
      const res = await hostGeoip();
      // Build host card even when GeoIP is unreachable (air-gap mode)
      // Use public IP from GeoIP when available, otherwise LAN IP or localhost
      const ip = (res as Record<string, unknown>).ip as string
                  || (res as Record<string, unknown>).lan_ip as string
                  || 'localhost';
      // Simulated host metrics for demo (real deployment uses SNMP/agent)
      const rng = () => Math.random();
      const host: HostData = {
        hostname: ip,
        os: navigator.platform || 'Unknown',
        uptime: Math.floor(rng() * 604800) + 3600,
        cpu_pct: Math.round((15 + rng() * 45) * 10) / 10,
        mem_pct: Math.round((35 + rng() * 40) * 10) / 10,
        disk_pct: Math.round((20 + rng() * 55) * 10) / 10,
        net_conns: Math.floor(rng() * 120) + 8,
        processes: Math.floor(rng() * 200) + 60,
        geo: res.ok && res.lat && res.lon ? {
          city: res.city ?? 'Unknown',
          country: 'ID',
          lat: res.lat,
          lon: res.lon,
        } : undefined,
      };
      setLocalHost(host);
    } catch {
      toast('Gagal mengambil data host', 'error');
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    if (!propHosts || propHosts.length === 0) {
      fetchLocalHost();
    }
  }, [propHosts, fetchLocalHost]);

  const allHosts = propHosts && propHosts.length > 0
    ? propHosts
    : localHost ? [localHost] : [];

  return (
    <div className="p-3">
      <div className="flex items-center gap-2 mb-3">
        <button
          className="px-3 py-1 border border-border-dim rounded font-mono text-[11px] text-foreground-muted transition-colors hover:border-primary hover:text-primary"
          onClick={fetchLocalHost}
        >
          🔄 Refresh Telemetry
        </button>
      </div>

      {loading && (
        <div className="text-center py-6 text-xs opacity-50 font-mono">
          ⏳ Memuat data host…
        </div>
      )}

      {!loading && allHosts.length === 0 ? (
        <div className="text-center py-10 px-4 opacity-30 text-[13px] font-mono">
          Tidak ada data telemetry. Pastikan endpoint host-geoip aktif.
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-2.5">
          {allHosts.map((h, i) => (
            <HostCard key={h.hostname + i} host={h} />
          ))}
        </div>
      )}
    </div>
  );
}
