// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — OSINT Results Panel (Tailwind migration)
// Renders scan results with type-specific sub-renderers
// ═══════════════════════════════════════════════════════════════════════

import type {
  OsintSearchResult, OsintPlatform, OsintGeo,
  OsintReputation, OsintGitHub, OsintWayback,
  OsintBreach, OsintWhois, OsintHttpProbe,
} from '@/types/api';
import { TYPE_ICONS } from '../helpers';

// ── Lookup tables ─────────────────────────────────────────────────────

const BANNER_CLS: Record<string, string> = {
  warn:    'bg-[#451a03] border border-[#92400e] text-[#fcd34d]',
  info:    'bg-[#1c1917] border border-[#44403c] text-[#a8a29e]',
  danger:  'bg-[#1a0a0a] border border-[#7f1d1d]',
  success: 'bg-[#052e16] border border-[#166534]',
};

const WB_STATUS: Record<string, string> = {
  ok:    'py-px px-1.5 rounded-[3px] bg-[#14532d] text-[11px]',
  redir: 'py-px px-1.5 rounded-[3px] bg-[#1e3a5f] text-[11px]',
  err:   'py-px px-1.5 rounded-[3px] bg-[#7c2d12] text-[11px]',
};

// ── Helpers ────────────────────────────────────────────────────────────

function Badge({ label, bg }: { label: string; bg: string }) {
  return (
    <span
      className="inline-block py-0.5 px-2 rounded font-mono text-[11px] m-0.5 whitespace-nowrap"
      style={{ background: bg }}
    >
      {label}
    </span>
  );
}

function SectionTitle({ children }: { children: string }) {
  return (
    <h4 className="text-[11px] uppercase tracking-[0.07em] opacity-50 mb-1.5 font-mono">
      {children}
    </h4>
  );
}

function KVGrid({ items }: { items: Array<{ label: string; value?: string | number | null }> }) {
  const valid = items.filter(i => i.value != null && i.value !== '');
  if (!valid.length) return null;
  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-2.5 mb-3.5">
      {valid.map(i => (
        <div key={i.label} className="mb-1.5">
          <div className="opacity-60 text-[11px] font-mono">{i.label}</div>
          <div className="text-[13px] font-mono">{String(i.value)}</div>
        </div>
      ))}
    </div>
  );
}

function Banner({ type, children }: { type: 'warn' | 'info' | 'danger' | 'success'; children: React.ReactNode }) {
  return (
    <div className={`py-2 px-3 rounded-md text-[11px] leading-normal mb-2.5 ${BANNER_CLS[type] ?? BANNER_CLS.info}`}>
      {children}
    </div>
  );
}

// ── Platform Grid ──────────────────────────────────────────────────────

function PlatformGrid({ platforms, verified }: { platforms: OsintPlatform[]; verified: boolean }) {
  if (!platforms?.length) return null;
  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-2">
      {platforms.map(p => (
        <a
          key={p.url}
          href={p.url}
          target="_blank"
          rel="noopener noreferrer"
          className={`flex items-center gap-2 py-2 px-3 bg-background-card rounded-lg border no-underline text-inherit transition-colors hover:bg-background-hover ${
            verified ? 'border-[#11ff66]' : 'border-[#ca8a04]'
          }`}
        >
          <div>
            <div className="font-semibold text-[13px]">{p.platform}</div>
            <div className="text-[10px] opacity-50 overflow-hidden text-ellipsis whitespace-nowrap max-w-[160px]">
              {p.url}
            </div>
          </div>
        </a>
      ))}
    </div>
  );
}

// ── GitHub ──────────────────────────────────────────────────────────────

function GitHubSection({ gh }: { gh: OsintGitHub }) {
  if (!gh?.ok) return null;
  const p = gh.profile;
  return (
    <div className="mb-3.5">
      <SectionTitle>GITHUB</SectionTitle>
      <div className="flex gap-4 items-start flex-wrap mb-3.5">
        {p?.avatar_url && <img src={p.avatar_url} alt="" className="w-16 h-16 rounded-full border-2 border-[#1e3a5f]" />}
        <div className="flex-1 min-w-[180px]">
          {p?.name && <div className="font-bold text-base">{p.name}</div>}
          {p?.bio && <div className="text-xs opacity-70 mt-1">{p.bio}</div>}
          <div className="flex gap-3 mt-2 text-xs">
            {p?.followers != null && <span>👥 {p.followers}</span>}
            {p?.public_repos != null && <span>📦 {p.public_repos}</span>}
            {p?.location && <span>📍 {p.location}</span>}
          </div>
          {p?.html_url && (
            <a href={p.html_url} target="_blank" rel="noopener noreferrer" className="text-[11px] text-[#60a5fa] mt-1.5 inline-block">
              {p.html_url}
            </a>
          )}
        </div>
      </div>

      {gh.emails && gh.emails.length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>COMMIT EMAILS</SectionTitle>
          {gh.emails.map(e => (
            <Badge key={e} label={e} bg="#14532d" />
          ))}
        </div>
      )}

      {gh.repos && gh.repos.length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>REPOSITORI ({gh.repos.length})</SectionTitle>
          {gh.repos.map(r => (
            <div key={r.url} className="py-1.5 border-b border-white/[0.05]">
              <a href={r.url} target="_blank" rel="noopener noreferrer" className="text-[#60a5fa] text-[13px] font-semibold no-underline">
                {r.name}
              </a>
              {r.stars != null && <span className="text-[11px] opacity-50 ml-2">⭐ {r.stars}</span>}
              {r.description && <div className="text-[11px] opacity-50 mt-0.5">{r.description}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Wayback ────────────────────────────────────────────────────────────

function WaybackSection({ wb }: { wb: OsintWayback }) {
  if (!wb?.ok) return null;

  const wbStatusCls = (status?: string) => {
    if (!status) return WB_STATUS.err;
    if (status.startsWith('2')) return WB_STATUS.ok;
    if (status.startsWith('3')) return WB_STATUS.redir;
    return WB_STATUS.err;
  };

  return (
    <div className="mb-3.5">
      <SectionTitle>WAYBACK MACHINE</SectionTitle>
      <div className="mb-2.5 text-xs opacity-60">
        Pertama: {wb.first_seen ?? '—'} · Terakhir: {wb.last_seen ?? '—'} · Total: {wb.total ?? 0}
      </div>
      {wb.snapshots?.map((snap, i) => (
        <a
          key={i}
          href={snap.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2.5 py-1.5 px-2.5 bg-background-card rounded-md border border-[#1e2d3d] no-underline text-inherit text-xs mb-1"
        >
          <span className="font-mono opacity-60 whitespace-nowrap">{snap.timestamp}</span>
          <span className={wbStatusCls(snap.status)}>{snap.status}</span>
          <span className="opacity-40 text-[10px] overflow-hidden text-ellipsis whitespace-nowrap">{snap.url}</span>
        </a>
      ))}
    </div>
  );
}

// ── Breach ─────────────────────────────────────────────────────────────

function BreachSection({ breach }: { breach: OsintBreach }) {
  if (!breach) return null;
  return (
    <div className="mb-3.5">
      <SectionTitle>DATA BREACH</SectionTitle>
      {breach.breach_count === 0 && (
        <Banner type="success">Tidak ditemukan di database breach yang diketahui</Banner>
      )}
      {breach.breaches?.map((b, i) => (
        <div key={i} className="py-2.5 px-3 bg-[#1a0a0a] border border-[#7f1d1d] rounded-lg mb-2">
          <div className="font-semibold text-[13px]">{b.name}</div>
          {b.domain && <div className="opacity-50 text-[11px]">{b.domain}</div>}
          <div className="text-[11px] opacity-60 mt-0.5">
            {b.date && `Tanggal: ${b.date}`}
            {b.count != null && ` · ${b.count.toLocaleString()} akun`}
          </div>
          {b.data_classes && (
            <div className="mt-1 flex flex-wrap gap-[3px]">
              {b.data_classes.map(dc => (
                <span key={dc} className="bg-[#7f1d1d] py-px px-1.5 rounded-[3px] text-[10px]">{dc}</span>
              ))}
            </div>
          )}
        </div>
      ))}
      {breach.note && <Banner type="info">{breach.note}</Banner>}
    </div>
  );
}

// ── Whois ──────────────────────────────────────────────────────────────

function WhoisSection({ whois }: { whois: OsintWhois }) {
  if (!whois?.ok) return null;
  const parsed = whois.parsed ?? {};
  const keys = Object.keys(parsed);
  return (
    <div className="mb-3.5">
      <SectionTitle>WHOIS</SectionTitle>
      {keys.length > 0 && (
        <KVGrid items={keys.map(k => ({ label: k, value: String(parsed[k] ?? '') }))} />
      )}
      {whois.raw_snippet && (
        <details className="mt-2">
          <summary className="cursor-pointer text-[11px] opacity-60">Raw WHOIS snippet ▼</summary>
          <pre className="text-[10px] overflow-auto max-h-[200px] mt-1.5 opacity-70 font-mono whitespace-pre-wrap">
            {whois.raw_snippet}
          </pre>
        </details>
      )}
    </div>
  );
}

// ── Geo Info ───────────────────────────────────────────────────────────

function GeoInfo({ geo }: { geo: OsintGeo }) {
  if (!geo) return null;
  return (
    <KVGrid items={[
      { label: 'Negara', value: geo.country },
      { label: 'Region', value: geo.regionName },
      { label: 'Kota', value: geo.city },
      { label: 'ISP', value: geo.isp },
      { label: 'Org', value: geo.org },
      { label: 'AS', value: geo.as },
      { label: 'Proxy', value: geo.proxy ? '⚠ Ya' : undefined },
      { label: 'Hosting', value: geo.hosting ? '☁ Ya' : undefined },
    ]} />
  );
}

// ── HTTP Probe ─────────────────────────────────────────────────────────

function HttpProbeRow({ port, probe }: { port: number; probe?: OsintHttpProbe }) {
  if (!probe) return null;
  return (
    <div className="mb-1.5">
      <div className="opacity-60 text-[11px] font-mono">Port {port}</div>
      <div className="text-[13px] font-mono">
        {probe.status != null && <Badge label={`HTTP ${probe.status}`} bg={probe.status < 400 ? '#14532d' : '#7c2d12'} />}
        {probe.tech?.map(t => <Badge key={t} label={t} bg="#1e3a5f" />)}
      </div>
    </div>
  );
}

// ── Reputation Panel ───────────────────────────────────────────────────

function ReputationPanel({ rep }: { rep: OsintReputation }) {
  if (!rep) return null;
  const score = rep.score ?? 0;
  const color = score >= 75 ? '#ef4444' : score >= 25 ? '#f59e0b' : '#22c55e';
  return (
    <div className="flex items-center gap-4 mb-3">
      <div className="text-center">
        <div className="text-[32px] font-black font-mono" style={{ color }}>{score}</div>
        <div className="text-[10px] opacity-50">ABUSE SCORE</div>
      </div>
      <div className="grid grid-cols-2 gap-2 flex-1">
        <KVGrid items={[
          { label: 'Source', value: rep.source },
          { label: 'Reports', value: rep.reports },
          { label: 'ISP', value: rep.isp },
          { label: 'Classification', value: rep.classification },
          { label: 'Usage', value: rep.usage_type },
          { label: 'Country', value: rep.country },
          { label: 'TOR', value: rep.is_tor ? 'Ya' : undefined },
          { label: 'Last Reported', value: rep.last_reported },
        ]} />
      </div>
    </div>
  );
}

// ── Dork Links Grid ────────────────────────────────────────────────────

function DorkGrid({ dorks }: { dorks: Array<{ label: string; query: string; url: string }> }) {
  if (!dorks?.length) return null;
  return (
    <div className="mb-3.5">
      <SectionTitle>GOOGLE DORK</SectionTitle>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-2">
        {dorks.map(d => (
          <a
            key={d.url}
            href={d.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 py-2.5 px-3 bg-background-card rounded-lg border border-[#1e3a5f] no-underline text-inherit transition-colors text-xs font-semibold hover:bg-[#0c1929]"
          >
            <div>
              <div className="text-[#60a5fa]">{d.label}</div>
              <div className="text-[10px] opacity-40 mt-0.5 overflow-hidden text-ellipsis whitespace-nowrap max-w-[180px]">
                {d.query}
              </div>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════
// TYPE-SPECIFIC RENDERERS
// ════════════════════════════════════════════════════════════════════════

function UsernameResult({ data }: { data: OsintSearchResult }) {
  const common = (data.username?.length ?? 0) <= 6;
  return (
    <>
      {common && (
        <Banner type="warn">
          ⚠ Username ≤6 karakter — kemungkinan false-positive lebih tinggi
        </Banner>
      )}
      {data.platforms && data.platforms.length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>TERVERIFIKASI ({data.platforms.length})</SectionTitle>
          <PlatformGrid platforms={data.platforms} verified />
        </div>
      )}
      {data.unverified && data.unverified.length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>BELUM TERVERIFIKASI ({data.unverified.length})</SectionTitle>
          <PlatformGrid platforms={data.unverified} verified={false} />
        </div>
      )}
      {data.github && <GitHubSection gh={data.github} />}
      {data.wayback && <WaybackSection wb={data.wayback} />}
    </>
  );
}

function EmailResult({ data, onScanUsername }: { data: OsintSearchResult; onScanUsername?: (u: string) => void }) {
  return (
    <>
      <KVGrid items={[
        { label: 'Email', value: data.email ?? data.query },
        { label: 'Mail Server', value: data.mail_server_provider },
        { label: 'Free Provider', value: data.format_analysis?.is_free_provider ? 'Ya' : 'Tidak' },
        { label: 'Disposable', value: data.format_analysis?.is_disposable ? '⚠ Ya' : 'Tidak' },
      ]} />

      {data.has_gravatar && data.gravatar && (
        <div className="mb-3.5">
          <img src={data.gravatar} alt="Gravatar" className="w-20 h-20 rounded-full border-2 border-[#4ade80] mb-3" />
        </div>
      )}

      {data.mx_records && data.mx_records.length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>MX RECORDS</SectionTitle>
          {data.mx_records.map(mx => <Badge key={mx} label={mx} bg="#1e3a5f" />)}
        </div>
      )}

      {data.domain_ips && data.domain_ips.length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>DOMAIN IPs</SectionTitle>
          {data.domain_ips.map(ip => <Badge key={ip} label={ip} bg="#7c2d12" />)}
        </div>
      )}

      {data.username_candidates && data.username_candidates.length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>USERNAME CANDIDATES</SectionTitle>
          {data.username_candidates.map(u => (
            <button
              key={u}
              className="text-[11px] m-0.5 py-[3px] px-2.5 bg-background-card border border-border-dim rounded text-foreground font-mono cursor-pointer transition-all hover:border-accent-steel hover:text-accent-steel"
              onClick={() => onScanUsername?.(u)}
            >
              {u}
            </button>
          ))}
        </div>
      )}

      {data.crt_sh_subdomains && data.crt_sh_subdomains.length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>CRT.SH SUBDOMAINS ({data.crt_sh_subdomains.length})</SectionTitle>
          {data.crt_sh_subdomains.map(sd => <Badge key={sd} label={sd} bg="#1e3a5f" />)}
        </div>
      )}

      {data.breach && <BreachSection breach={data.breach} />}
      {data.github && <GitHubSection gh={data.github} />}
    </>
  );
}

function DomainResult({ data }: { data: OsintSearchResult }) {
  return (
    <>
      <KVGrid items={[
        { label: 'Domain', value: data.domain ?? data.query },
        { label: 'HTTP Status', value: data.http_status },
        { label: 'Subdomain Count', value: data.subdomain_count },
      ]} />

      {data.resolved_ips && data.resolved_ips.length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>RESOLVED IPs</SectionTitle>
          {data.resolved_ips.map(ip => <Badge key={ip} label={ip} bg="#7c2d12" />)}
        </div>
      )}

      {data.open_ports && data.open_ports.length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>OPEN PORTS</SectionTitle>
          {data.open_ports.map(p => (
            <span key={p.port} className="inline-block py-[3px] px-2.5 m-0.5 rounded bg-[#7c2d12] text-xs font-mono">
              {p.port} <span className="opacity-70">{p.service}</span>
            </span>
          ))}
        </div>
      )}

      {data.tech_hints && data.tech_hints.length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>TECH STACK</SectionTitle>
          {data.tech_hints.map(t => <Badge key={t} label={t} bg="#1e3a5f" />)}
        </div>
      )}

      {data.ssl_cert && (
        <div className="mb-3.5">
          <SectionTitle>SSL CERTIFICATE</SectionTitle>
          {data.ssl_cert.error ? (
            <Banner type="danger">⚠ {data.ssl_cert.error}</Banner>
          ) : (
            <KVGrid items={[
              { label: 'Issuer', value: data.ssl_cert.issuer?.organizationName },
              { label: 'CN', value: data.ssl_cert.issuer?.commonName },
              { label: 'Expires', value: data.ssl_cert.not_after },
              { label: 'SAN', value: data.ssl_cert.san?.join(', ') },
            ]} />
          )}
        </div>
      )}

      {data.subdomains_crtsh && data.subdomains_crtsh.length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>SUBDOMAINS ({data.subdomains_crtsh.length})</SectionTitle>
          {data.subdomains_crtsh.map(sd => <Badge key={sd} label={sd} bg="#1e3a5f" />)}
        </div>
      )}

      {data.dns && Object.keys(data.dns).length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>DNS RECORDS</SectionTitle>
          <KVGrid items={Object.entries(data.dns).map(([k, v]) => ({
            label: k, value: (v as string[]).join(', '),
          }))} />
        </div>
      )}

      {data.ip_info?.map((info, i) => (
        <div key={i} className="mb-3.5">
          <SectionTitle>IP INFO #{i + 1}</SectionTitle>
          {info.reverse_dns && <Banner type="info">Reverse DNS: {info.reverse_dns}</Banner>}
          {info.geo && <GeoInfo geo={info.geo} />}
        </div>
      ))}

      {data.whois && <WhoisSection whois={data.whois} />}
      {data.wayback && <WaybackSection wb={data.wayback} />}
    </>
  );
}

function IpResult({ data }: { data: OsintSearchResult }) {
  return (
    <>
      <KVGrid items={[
        { label: 'IP', value: data.ip ?? data.query },
        { label: 'Reverse DNS', value: data.reverse_dns },
      ]} />

      {data.geo && <GeoInfo geo={data.geo} />}

      {data.open_ports && data.open_ports.length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>OPEN PORTS</SectionTitle>
          {data.open_ports.map(p => (
            <span key={p.port} className="inline-block py-[3px] px-2.5 m-0.5 rounded bg-[#7c2d12] text-xs font-mono">
              {p.port} <span className="opacity-70">{p.service}</span>
            </span>
          ))}
        </div>
      )}

      <div className="mb-3.5">
        <SectionTitle>HTTP PROBES</SectionTitle>
        <HttpProbeRow port={80} probe={data.http_80} />
        <HttpProbeRow port={443} probe={data.http_443} />
        <HttpProbeRow port={8080} probe={data.http_8080} />
        <HttpProbeRow port={8443} probe={data.http_8443} />
      </div>

      {data.reputation && <ReputationPanel rep={data.reputation} />}
      {data.whois && <WhoisSection whois={data.whois} />}
    </>
  );
}

function PhoneResult({ data }: { data: OsintSearchResult }) {
  return (
    <>
      <KVGrid items={[
        { label: 'Input', value: data.input ?? data.query },
        { label: 'E.164', value: data.format_e164 },
        { label: 'Lokal', value: data.format_local },
        { label: 'Negara', value: data.country },
        { label: 'Kode', value: data.country_code },
        { label: 'Nomor Lokal', value: data.local_number },
        { label: 'Carrier', value: data.detected_carrier },
      ]} />

      {data.possible_carriers && data.possible_carriers.length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>POSSIBLE CARRIERS</SectionTitle>
          {data.possible_carriers.map(c => <Badge key={c} label={c} bg="#1e3a5f" />)}
        </div>
      )}

      {data.dorks && <DorkGrid dorks={data.dorks} />}
    </>
  );
}

function NameResult({ data, onScanUsername }: { data: OsintSearchResult; onScanUsername?: (u: string) => void }) {
  return (
    <>
      <KVGrid items={[
        { label: 'Nama', value: data.name ?? data.query },
        { label: 'First', value: data.parts?.first },
        { label: 'Last', value: data.parts?.last },
      ]} />

      {data.dorks && <DorkGrid dorks={data.dorks} />}

      {data.gravatar_hits && data.gravatar_hits.length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>GRAVATAR HITS</SectionTitle>
          {data.gravatar_hits.map(g => (
            <div key={g.email} className="flex items-center gap-2 py-2 px-3 bg-[#0f2a1a] border border-[#11ff66] rounded-lg">
              <img src={g.gravatar_url} alt="" className="w-9 h-9 rounded-full" />
              <span className="text-xs font-semibold text-[#4ade80]">{g.email}</span>
            </div>
          ))}
        </div>
      )}

      {data.username_candidates && data.username_candidates.length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>USERNAME CANDIDATES</SectionTitle>
          {data.username_candidates.map(u => (
            <button
              key={u}
              className="text-[11px] m-0.5 py-[3px] px-2.5 bg-background-card border border-border-dim rounded text-foreground font-mono cursor-pointer transition-all hover:border-accent-steel hover:text-accent-steel"
              onClick={() => onScanUsername?.(u)}
            >
              {u}
            </button>
          ))}
        </div>
      )}

      {data.email_permutations && data.email_permutations.length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>EMAIL PERMUTATIONS</SectionTitle>
          {data.email_permutations.map(e => <Badge key={e} label={e} bg="#14532d" />)}
        </div>
      )}
    </>
  );
}

function PlateResult({ data }: { data: OsintSearchResult }) {
  return (
    <>
      <KVGrid items={[
        { label: 'Plat', value: data.plate ?? data.query },
        { label: 'Prefix', value: data.prefix },
        { label: 'Nomor', value: data.number },
        { label: 'Suffix', value: data.suffix },
        { label: 'Provinsi', value: data.provinsi },
        { label: 'Wilayah', value: data.wilayah },
        { label: 'Sub Wilayah', value: data.sub_wilayah },
        { label: 'Kendaraan', value: data.kendaraan },
      ]} />

      {data.dorks && data.dorks.length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>DORK LINKS</SectionTitle>
          <div className="flex flex-wrap gap-1.5">
            {data.dorks.map(d => (
              <a
                key={d.url}
                href={d.url}
                target="_blank"
                rel="noopener noreferrer"
                className="py-1 px-2.5 bg-background-card border border-border-dim rounded text-[11px] no-underline text-[#10b981] hover:opacity-75"
              >
                {d.label}
              </a>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

function GpsResult({ data }: { data: OsintSearchResult }) {
  const hasCoords = data.lat != null && data.lon != null;
  return (
    <>
      <KVGrid items={[
        { label: 'Lat', value: data.lat },
        { label: 'Lon', value: data.lon },
        { label: 'Alamat', value: data.display_name },
        { label: 'Negara', value: data.country },
        { label: 'Kota', value: data.city },
        { label: 'Kecamatan', value: data.suburb },
        { label: 'Kode Pos', value: data.postcode },
        { label: 'Jalan', value: data.road },
      ]} />

      {hasCoords && (
        <a
          href={`https://www.google.com/maps?q=${data.lat},${data.lon}`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-block py-[7px] px-4 bg-[#14532d] text-white rounded-md text-xs no-underline mb-3.5 hover:opacity-85"
        >
          📍 Buka di Google Maps
        </a>
      )}

      {data.dorks && <DorkGrid dorks={data.dorks} />}
    </>
  );
}

function UrlResult({ data }: { data: OsintSearchResult }) {
  return (
    <>
      <KVGrid items={[
        { label: 'URL', value: data.query },
        { label: 'Status', value: data.status },
        { label: 'Final URL', value: data.final_url },
        { label: 'Redirects', value: data.redirect_count },
      ]} />

      {data.security && Object.keys(data.security).length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>SECURITY CHECKS</SectionTitle>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(data.security).map(([k, v]) => (
              <span
                key={k}
                className={`py-[3px] px-2 rounded text-[11px] ${v ? 'bg-[#14532d]' : 'bg-[#7f1d1d]'}`}
              >
                {v ? '✓' : '✗'} {k}
              </span>
            ))}
          </div>
        </div>
      )}

      {data.redirects && data.redirects.length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>REDIRECT CHAIN</SectionTitle>
          {data.redirects.map((r, i) => (
            <div key={i} className="flex items-center gap-2 mb-1">
              <span className="text-[10px] opacity-50 w-4">{i + 1}</span>
              <Badge label={String(r.status)} bg={r.status < 400 ? '#14532d' : '#7c2d12'} />
              <span className="text-[11px] overflow-hidden text-ellipsis whitespace-nowrap flex-1">{r.url}</span>
            </div>
          ))}
        </div>
      )}

      {data.tech && data.tech.length > 0 && (
        <div className="mb-3.5">
          <SectionTitle>TECH DETECTED</SectionTitle>
          {data.tech.map(t => <Badge key={t} label={t} bg="#1e3a5f" />)}
        </div>
      )}

      {data.wayback && <WaybackSection wb={data.wayback} />}
    </>
  );
}

// ════════════════════════════════════════════════════════════════════════
// MAIN RESULTS PANEL
// ════════════════════════════════════════════════════════════════════════

interface ResultsPanelProps {
  data: OsintSearchResult;
  onBuildGraph?: () => void;
  onSaveToDossier?: () => void;
  onScanUsername?: (username: string) => void;
}

export function ResultsPanel({ data, onBuildGraph, onSaveToDossier, onScanUsername }: ResultsPanelProps) {
  if (!data) return null;

  if (!data.ok) {
    return <div className="text-destructive text-xs p-3">⚠ {(data as Record<string, unknown>).error as string ?? 'Scan gagal'}</div>;
  }

  const typeLabel = (data.type ?? 'unknown').toUpperCase();
  const icon = TYPE_ICONS[data.type] ?? '❓';

  // Summary badges
  const badges: Array<{ label: string; bg: string }> = [
    { label: `${icon} ${typeLabel}`, bg: '#1e3a5f' },
  ];
  if (data.found_count != null) badges.push({ label: `${data.found_count} ditemukan`, bg: '#14532d' });
  if (data.checked != null) badges.push({ label: `${data.checked} dicek`, bg: '#44403c' });
  if (data.elapsed_s != null) badges.push({ label: `${data.elapsed_s.toFixed(1)}s`, bg: '#44403c' });
  if (data.platforms?.length) badges.push({ label: `${data.platforms.length} verified`, bg: '#166534' });
  if (data.unverified?.length) badges.push({ label: `${data.unverified.length} unverified`, bg: '#92400e' });

  return (
    <div>
      {/* Summary Bar */}
      <div className="flex flex-wrap items-center gap-1.5 py-2.5 px-3.5 bg-background-card rounded-md mb-3">
        <span className="text-sm font-bold font-mono">
          {data.query ?? data.name ?? data.email ?? data.domain ?? data.ip ?? ''}
        </span>
        {badges.map(b => <Badge key={b.label} label={b.label} bg={b.bg} />)}
        <div className="ml-auto flex gap-1.5">
          {onBuildGraph && (
            <button
              className="text-[11px] py-[3px] px-2.5 border-none rounded cursor-pointer font-mono font-bold transition-opacity whitespace-nowrap hover:opacity-85 bg-[#10b981] text-black"
              onClick={onBuildGraph}
            >
              🕸 Build Graph
            </button>
          )}
          {onSaveToDossier && (
            <button
              className="text-[11px] py-[3px] px-2.5 border-none rounded cursor-pointer font-mono font-bold transition-opacity whitespace-nowrap hover:opacity-85 bg-secondary text-black"
              onClick={onSaveToDossier}
            >
              📋 Lampirkan ke Dossier
            </button>
          )}
        </div>
      </div>

      {/* Type-specific content */}
      {data.type === 'username' && <UsernameResult data={data} />}
      {data.type === 'email'    && <EmailResult data={data} onScanUsername={onScanUsername} />}
      {data.type === 'domain'   && <DomainResult data={data} />}
      {data.type === 'ip'       && <IpResult data={data} />}
      {data.type === 'phone'    && <PhoneResult data={data} />}
      {data.type === 'name'     && <NameResult data={data} onScanUsername={onScanUsername} />}
      {data.type === 'plate'    && <PlateResult data={data} />}
      {data.type === 'gps'      && <GpsResult data={data} />}
      {data.type === 'url'      && <UrlResult data={data} />}
    </div>
  );
}
