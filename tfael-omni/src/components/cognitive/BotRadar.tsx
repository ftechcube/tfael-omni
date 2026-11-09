// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — BotRadar Dashboard
// Bot detection results, account scoring, signal breakdown,
// mini network graph, topic header, behavior pattern summary
// ═══════════════════════════════════════════════════════════════════════

import { useState, useEffect, useCallback, useMemo } from 'react';
import { cogDashboard, cogAccountDetail, cogNetworkGraph } from '@/api/endpoints';
import type { CogAccount, CogDashboard, CogGraphData } from '@/api/endpoints';
import { Icon } from '@/components/icons/Icon';
import { cn } from '@/lib/utils';

const LABEL_STYLES: Record<string, string> = {
  BOT_HIGH:       'bg-red-900/40 text-red-400 border-red-700/50',
  BOT_MEDIUM:     'bg-orange-900/40 text-orange-400 border-orange-700/50',
  SUSPICIOUS:     'bg-yellow-900/40 text-yellow-400 border-yellow-700/50',
  LIKELY_ORGANIC: 'bg-green-900/40 text-green-400 border-green-700/50',
  UNKNOWN:        'bg-zinc-800/40 text-zinc-400 border-zinc-600/50',
  PENDING:        'bg-zinc-800/40 text-zinc-400 border-zinc-600/50',
  CHANNEL:        'bg-blue-900/40 text-blue-400 border-blue-700/50',
};

const NODE_COLORS: Record<string, string> = {
  BOT_HIGH:       '#ef4444',
  BOT_MEDIUM:     '#f97316',
  SUSPICIOUS:     '#eab308',
  LIKELY_ORGANIC: '#3b82f6',
  UNKNOWN:        '#64748b',
  CHANNEL:        '#06b6d4',
};

const SIGNAL_LABELS: Record<string, string> = {
  time_entropy:         'Entropi Waktu',
  text_similarity:      'Kemiripan Teks',
  ff_ratio_anomaly:     'Rasio FF Anomali',
  posting_regularity:   'Regularitas Posting',
  burst_posting:        'Burst Posting',
  username_entropy:     'Entropi Username',
  default_profile:      'Profil Default',
  age_activity_anomaly: 'Anomali Usia/Aktivitas',
};

// ── DEMO DATA — fallback when backend is offline ─────────────────────
function generateDemoData(): { dashboard: CogDashboard; graph: CogGraphData } {
  const botNames = [
    'user_88213', 'berita_cepat77', 'info_viral_id', 'news_update_99',
    'share_fakta01', 'trending_now88', 'viral_banget12', 'kabar_terkini',
    'hot_topik_id', 'buzzer_squad55', 'auto_post_007', 'bot_farm_x1',
  ];
  const organicNames = [
    'andi_jkt', 'sari_bdg', 'budi_sby', 'nina_mdn', 'reza_smg',
    'dewi_solo', 'fajar_mlg', 'putri_dpk', 'hendra_bks', 'maya_tgr',
  ];

  const accounts: CogAccount[] = [
    ...botNames.map((u, i) => ({
      account_id: `BOT-${i}`, platform: 'twitter', username: u,
      display_name: u.replace(/_/g, ' '), bot_score: 70 + Math.random() * 28,
      bot_label: Math.random() > 0.4 ? 'BOT_HIGH' : 'BOT_MEDIUM',
      cluster_id: i % 3, followers: Math.floor(Math.random() * 50),
      following: Math.floor(Math.random() * 2000 + 500),
      post_count: Math.floor(Math.random() * 5000 + 1000),
      account_age_days: Math.floor(Math.random() * 30 + 1),
    })),
    ...organicNames.map((u, i) => ({
      account_id: `ORG-${i}`, platform: 'twitter', username: u,
      display_name: u.replace(/_/g, ' '), bot_score: Math.random() * 35,
      bot_label: 'LIKELY_ORGANIC', cluster_id: 3 + (i % 2),
      followers: Math.floor(Math.random() * 2000 + 100),
      following: Math.floor(Math.random() * 500 + 50),
      post_count: Math.floor(Math.random() * 500 + 10),
      account_age_days: Math.floor(Math.random() * 1500 + 180),
    })),
  ];

  accounts.sort((a, b) => b.bot_score - a.bot_score);

  const botCount = accounts.filter(a => a.bot_score >= 60).length;
  const susCount = accounts.filter(a => a.bot_score >= 40 && a.bot_score < 60).length;
  const orgCount = accounts.filter(a => a.bot_score < 40).length;

  // graph nodes + edges
  const nodes = accounts.map(a => ({
    id: a.account_id, username: a.username, bot_score: a.bot_score,
    bot_label: a.bot_label, cluster_id: a.cluster_id,
    degree: Math.floor(Math.random() * 8 + 1),
    betweenness: Math.random() * 0.15,
  }));

  const edges: CogGraphData['edges'] = [];
  // intra-cluster connections (bots connect to bots)
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      if (nodes[i].cluster_id === nodes[j].cluster_id && Math.random() > 0.45) {
        edges.push({
          source: nodes[i].id, target: nodes[j].id,
          relation: 'retweet', weight: Math.random() * 2 + 0.5,
        });
      } else if (Math.random() > 0.92) {
        edges.push({
          source: nodes[i].id, target: nodes[j].id,
          relation: 'mention', weight: Math.random(),
        });
      }
    }
  }

  return {
    dashboard: {
      ok: true,
      summary: {
        total_accounts: accounts.length,
        bots: botCount, suspicious: susCount, organic: orgCount,
        bot_ratio: botCount / accounts.length,
        network_edges: edges.length,
      },
      top_flagged_accounts: accounts.slice(0, 20),
      recent_cib_events: [
        {
          event_id: 'CIB-001', event_type: 'COORDINATED_POSTING',
          description: '8 akun posting konten identik dalam 45 detik',
          accounts_json: JSON.stringify(botNames.slice(0, 8)),
          window_seconds: 45, similarity: 0.96,
          detected_at: new Date().toISOString(), severity: 'HIGH',
        },
        {
          event_id: 'CIB-002', event_type: 'HASHTAG_AMPLIFICATION',
          description: '#isu-demo diamplifikasi 12 akun baru secara serentak',
          accounts_json: JSON.stringify(botNames.slice(0, 12)),
          window_seconds: 120, similarity: 0.89,
          detected_at: new Date().toISOString(), severity: 'MEDIUM',
        },
      ],
      top_narratives: [
        {
          narrative_id: 'NAR-001', topic_query: '#isu-demo',
          hashtag: '#isu-demo', classification: 'SUSPECT_AMPLIFIED',
          hoax_score: 0.72, total_reach: 45200,
        },
      ],
    },
    graph: {
      ok: true, nodes, edges,
      total_nodes: nodes.length, total_edges: edges.length,
      communities: 5,
    },
  };
}

// ── DEMO account detail ──────────────────────────────────────────────
function generateDemoAccountDetail(accountId: string, accounts: CogAccount[]) {
  const acct = accounts.find(a => a.account_id === accountId);
  if (!acct) return null;
  const isBot = acct.bot_score >= 60;
  return {
    ok: true,
    account: acct,
    posts: Array.from({ length: 8 }, (_, i) => ({
      post_id: `${accountId}-P${i}`,
      content: isBot
        ? `Ini adalah fakta yang harus kalian ketahui tentang isu terbaru! Sebarkan! #isu-demo #viral`
        : `Menurut gw sih perlu dikaji lebih lanjut ya, jangan gampang percaya berita ${i}`,
      timestamp: new Date(Date.now() - i * 3600000).toISOString(),
    })),
    connections: [],
    signals: {
      time_entropy:       { raw: isBot ? 0.85 : 0.2, normalized: isBot ? 0.85 : 0.2 },
      text_similarity:    { raw: isBot ? 0.92 : 0.15, normalized: isBot ? 0.92 : 0.15 },
      ff_ratio_anomaly:   { raw: isBot ? 0.78 : 0.1, normalized: isBot ? 0.78 : 0.1 },
      posting_regularity: { raw: isBot ? 0.88 : 0.25, normalized: isBot ? 0.88 : 0.25 },
      burst_posting:      { raw: isBot ? 0.95 : 0.05, normalized: isBot ? 0.95 : 0.05 },
      username_entropy:   { raw: isBot ? 0.7 : 0.3, normalized: isBot ? 0.7 : 0.3 },
    },
  };
}

interface Props {
  jobId?: string;
}

export function BotRadar({ jobId }: Props) {
  const [dashboard, setDashboard] = useState<CogDashboard | null>(null);
  const [graphData, setGraphData] = useState<CogGraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState<string | null>(null);
  const [accountDetail, setAccountDetail] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [demoMode, setDemoMode] = useState(false);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    try {
      const res = await cogDashboard(jobId ? { job_id: jobId } : {});
      if (res?.ok) {
        setDashboard(res);
        // also load graph data
        try {
          const gRes = await cogNetworkGraph(jobId ? { job_id: jobId } : {});
          if (gRes?.ok) setGraphData(gRes);
        } catch { /* graph optional */ }
        setDemoMode(false);
      } else {
        throw new Error('no data');
      }
    } catch {
      // fallback to demo mode
      const demo = generateDemoData();
      setDashboard(demo.dashboard);
      setGraphData(demo.graph);
      setDemoMode(true);
    }
    setLoading(false);
  }, [jobId]);

  useEffect(() => { loadDashboard(); }, [loadDashboard]);

  const loadAccountDetail = useCallback(async (accountId: string) => {
    setSelectedAccount(accountId);
    setDetailLoading(true);
    if (demoMode) {
      // simulate async for demo
      await new Promise(r => setTimeout(r, 300));
      const detail = generateDemoAccountDetail(accountId, dashboard?.top_flagged_accounts || []);
      if (detail) setAccountDetail(detail);
      setDetailLoading(false);
      return;
    }
    try {
      const res = await cogAccountDetail(accountId);
      if (res?.ok) setAccountDetail(res);
    } catch { /* ignore */ }
    setDetailLoading(false);
  }, [demoMode, dashboard]);

  // ── Compute mini-graph layout ──────────────────────────────────────
  const GW = 380, GH = 280;
  const nodePositions = useMemo(() => {
    if (!graphData?.nodes?.length) return new Map<string, { x: number; y: number }>();
    return computeMiniLayout(graphData.nodes, graphData.edges, GW, GH);
  }, [graphData]);

  // ── Detect behavior patterns ───────────────────────────────────────
  const patterns = useMemo(() => {
    if (!dashboard) return [];
    const p: string[] = [];
    const s = dashboard.summary;
    if (s.bots > 0) {
      const newAccts = dashboard.top_flagged_accounts.filter(
        a => a.account_age_days < 30 && a.bot_score >= 60
      );
      if (newAccts.length >= 3) p.push('akun baru');
    }
    if (dashboard.recent_cib_events?.length > 0) p.push('posting serentak');
    if (s.bot_ratio > 0.3) p.push('rasio bot tinggi');
    if (dashboard.top_narratives?.some((n: any) => n.hoax_score > 0.5)) p.push('amplifikasi hashtag');
    if (s.network_edges > s.total_accounts * 2) p.push('jaringan padat');
    if (p.length === 0) p.push('belum terdeteksi pola');
    return p;
  }, [dashboard]);

  // ── Topic info ─────────────────────────────────────────────────────
  const topicLabel = useMemo(() => {
    if (!dashboard?.top_narratives?.length) return null;
    const nar = dashboard.top_narratives[0] as any;
    return nar?.topic_query || nar?.hashtag || null;
  }, [dashboard]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-foreground-muted font-mono text-xs">
        <div className="w-5 h-5 border-2 border-border-dim border-t-primary rounded-full animate-spin mr-2" />
        Memuat data BotRadar...
      </div>
    );
  }

  if (!dashboard) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-2 text-foreground-muted font-mono text-xs">
        <Icon name="search" size={32} />
        <span>Belum ada data. Jalankan scraping terlebih dahulu.</span>
      </div>
    );
  }

  const s = dashboard.summary;

  return (
    <div className="flex flex-col gap-3 p-3 h-full overflow-auto">

      {/* ── Demo Mode Badge ────────────────────────────── */}
      {demoMode && (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-yellow-900/20 border border-yellow-700/30 rounded-sm">
          <Icon name="alert" size={12} className="text-yellow-400" />
          <span className="font-mono text-[10px] text-yellow-400">
            DEMO MODE — Backend offline, menampilkan dummy data untuk testing UI
          </span>
          <button
            className="ml-auto text-[10px] font-mono text-yellow-400 underline hover:text-yellow-300"
            onClick={loadDashboard}
          >
            Retry
          </button>
        </div>
      )}

      {/* ── Summary Cards ─────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2">
        <StatCard label="Total Akun" value={s.total_accounts} icon="user" />
        <StatCard label="Bot Terdeteksi" value={s.bots} icon="bug" color="text-red-400" />
        <StatCard label="Mencurigakan" value={s.suspicious} icon="alert" color="text-yellow-400" />
        <StatCard label="Organik" value={s.organic} icon="check" color="text-green-400" />
        <StatCard label="Rasio Bot" value={`${(s.bot_ratio * 100).toFixed(1)}%`} icon="chart" color="text-orange-400" />
        <StatCard label="Jaringan" value={`${s.network_edges} edge`} icon="graph" color="text-blue-400" />
      </div>

      {/* ── Main Content: Graph + Flagged List ─────────── */}
      <div className="flex gap-3 flex-1 min-h-0">

        {/* ── LEFT: Mini Network Graph ─────────────────── */}
        <div className="w-[420px] shrink-0 bg-background-card border border-border-dim rounded-sm overflow-hidden flex flex-col">
          {/* Graph Header with Topic */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-border-dim bg-background-panel">
            <div className="flex items-center gap-2">
              <Icon name="graph" size={14} className="text-primary" />
              <span className="font-mono text-xs font-bold uppercase tracking-wide text-foreground">BotRadar</span>
            </div>
            {topicLabel && (
              <span className="font-mono text-[10px] text-foreground-muted">
                Topik: <span className="text-secondary">{topicLabel}</span>
                {' — '}
                <span className="text-foreground">{s.total_accounts.toLocaleString()}</span> akun dianalisis
              </span>
            )}
          </div>

          {/* SVG Graph */}
          <div className="flex-1 relative" style={{ minHeight: GH }}>
            {graphData && graphData.nodes.length > 0 ? (
              <svg viewBox={`0 0 ${GW} ${GH}`} className="w-full h-full">
                <rect width={GW} height={GH} fill="transparent" />

                {/* Edges */}
                {graphData.edges.map((e, i) => {
                  const src = nodePositions.get(e.source);
                  const tgt = nodePositions.get(e.target);
                  if (!src || !tgt) return null;
                  const isHovered = hoveredNode === e.source || hoveredNode === e.target;
                  return (
                    <line key={i}
                      x1={src.x} y1={src.y} x2={tgt.x} y2={tgt.y}
                      stroke={isHovered ? '#8c9663' : '#334155'}
                      strokeWidth={Math.min(1.5, e.weight)}
                      opacity={isHovered ? 0.7 : 0.25}
                    />
                  );
                })}

                {/* Nodes */}
                {graphData.nodes.map(node => {
                  const pos = nodePositions.get(node.id);
                  if (!pos) return null;
                  const isBot = node.bot_score >= 60;
                  const r = Math.max(3.5, Math.min(9, node.degree * 1.2 + 2.5));
                  const color = NODE_COLORS[node.bot_label] || '#64748b';
                  const isHovered = hoveredNode === node.id;
                  const isSelected = selectedAccount === node.id;

                  return (
                    <g key={node.id}
                      onMouseEnter={() => setHoveredNode(node.id)}
                      onMouseLeave={() => setHoveredNode(null)}
                      onClick={() => loadAccountDetail(node.id)}
                      style={{ cursor: 'pointer' }}
                    >
                      {(isHovered || isSelected) && (
                        <circle cx={pos.x} cy={pos.y} r={r + 4}
                          fill="none" stroke={color} strokeWidth={1.5} opacity={0.5}
                        />
                      )}
                      <circle cx={pos.x} cy={pos.y} r={r}
                        fill={color}
                        opacity={isHovered || isSelected ? 1 : 0.75}
                        stroke={isSelected ? '#fff' : 'none'}
                        strokeWidth={isSelected ? 1.5 : 0}
                      />
                    </g>
                  );
                })}
              </svg>
            ) : (
              <div className="flex items-center justify-center h-full text-foreground-muted font-mono text-xs">
                Tidak ada data graf
              </div>
            )}

            {/* Legend overlay */}
            <div className="absolute bottom-2 left-2 bg-background-deep/80 backdrop-blur-sm rounded-sm p-1.5 space-y-0.5">
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full bg-red-500" />
                <span className="text-[8px] font-mono text-foreground-muted">Akun bot</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full bg-blue-500" />
                <span className="text-[8px] font-mono text-foreground-muted">Akun organik</span>
              </div>
            </div>

            {/* Hovered node tooltip */}
            {hoveredNode && graphData && (() => {
              const n = graphData.nodes.find(nd => nd.id === hoveredNode);
              const pos = nodePositions.get(hoveredNode);
              if (!n || !pos) return null;
              return (
                <div
                  className="absolute pointer-events-none bg-background-deep/95 border border-border-dim rounded-sm px-2 py-1 font-mono text-[10px] z-10"
                  style={{ left: Math.min(pos.x + 12, GW - 120), top: Math.max(pos.y - 30, 4) }}
                >
                  <div className="text-foreground font-bold">@{n.username}</div>
                  <div className="text-foreground-muted">
                    Score: <span className={n.bot_score >= 60 ? 'text-red-400' : 'text-green-400'}>{n.bot_score.toFixed(0)}%</span>
                  </div>
                </div>
              );
            })()}
          </div>

          {/* ── Behavior Patterns ──────────────────────── */}
          <div className="px-3 py-2 border-t border-border-dim bg-background-panel">
            <span className="font-mono text-[10px] text-foreground-muted">
              Pola:{' '}
              {patterns.map((p, i) => (
                <span key={p}>
                  <span className="text-secondary">{p}</span>
                  {i < patterns.length - 1 && <span className="text-foreground-dim">, </span>}
                </span>
              ))}
            </span>
          </div>
        </div>

        {/* ── RIGHT: Flagged Accounts + Detail ─────────── */}
        <div className="flex gap-3 flex-1 min-w-0">
          {/* Flagged Accounts Table */}
          <div className="flex-1 bg-background-card border border-border-dim rounded-sm overflow-hidden flex flex-col">
            <div className="flex items-center gap-2 px-3 py-2 border-b border-border-dim bg-background-panel">
              <Icon name="target" size={14} className="text-primary" />
              <span className="font-mono text-xs font-bold uppercase tracking-wide text-foreground">
                Akun ditandai
              </span>
              <span className="ml-auto font-mono text-[10px] text-foreground-muted">
                {dashboard.top_flagged_accounts.length} akun
              </span>
            </div>

            <div className="flex-1 overflow-auto">
              <table className="w-full text-xs font-mono">
                <thead className="sticky top-0 bg-background-panel text-foreground-muted">
                  <tr>
                    <th className="text-left px-3 py-1.5">Username</th>
                    <th className="text-right px-2 py-1.5">Bot Score</th>
                    <th className="text-left px-2 py-1.5">Label</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.top_flagged_accounts.map(a => (
                    <tr
                      key={a.account_id}
                      className={cn(
                        'border-b border-border-dim/30 cursor-pointer transition-colors',
                        selectedAccount === a.account_id
                          ? 'bg-primary/10'
                          : hoveredNode === a.account_id
                            ? 'bg-background-hover'
                            : 'hover:bg-background-panel/50'
                      )}
                      onClick={() => loadAccountDetail(a.account_id)}
                      onMouseEnter={() => setHoveredNode(a.account_id)}
                      onMouseLeave={() => setHoveredNode(null)}
                    >
                      <td className="px-3 py-1.5 text-foreground">@{a.username}</td>
                      <td className="px-2 py-1.5 text-right">
                        <BotScoreBar score={a.bot_score} />
                      </td>
                      <td className="px-2 py-1.5">
                        <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-bold border', LABEL_STYLES[a.bot_label] || LABEL_STYLES.UNKNOWN)}>
                          {a.bot_label}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Account Detail Panel */}
          {selectedAccount && (
            <div className="w-72 bg-background-card border border-border-dim rounded-sm overflow-auto flex flex-col">
              <div className="flex items-center justify-between px-3 py-2 border-b border-border-dim bg-background-panel">
                <span className="font-mono text-xs font-bold uppercase text-foreground">Detail Akun</span>
                <button
                  className="text-foreground-muted hover:text-foreground"
                  onClick={() => { setSelectedAccount(null); setAccountDetail(null); }}
                >
                  <Icon name="x" size={14} />
                </button>
              </div>

              {detailLoading ? (
                <div className="flex items-center justify-center h-32 text-foreground-muted text-xs">
                  <div className="w-4 h-4 border-2 border-border-dim border-t-primary rounded-full animate-spin mr-2" />
                  Loading...
                </div>
              ) : accountDetail ? (
                <div className="p-3 space-y-3 text-xs font-mono">
                  {/* Account info */}
                  <div className="space-y-1">
                    <div className="text-foreground font-bold text-sm">@{accountDetail.account?.username}</div>
                    <div className="text-foreground-muted">{accountDetail.account?.platform?.toUpperCase()}</div>
                    <div className="flex items-center gap-2">
                      <span className="text-foreground-muted">Bot Score:</span>
                      <BotScoreBar score={accountDetail.account?.bot_score || 0} />
                    </div>
                    {accountDetail.account?.account_age_days != null && (
                      <div className="text-foreground-muted text-[10px]">
                        Usia akun: <span className={accountDetail.account.account_age_days < 30 ? 'text-red-400' : 'text-foreground'}>
                          {accountDetail.account.account_age_days} hari
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Signal Breakdown */}
                  {accountDetail.signals && Object.keys(accountDetail.signals).length > 0 && (
                    <div className="space-y-1.5">
                      <div className="text-foreground-muted font-bold uppercase text-[10px] tracking-wider">Signal Breakdown</div>
                      {Object.entries(accountDetail.signals).map(([key, sig]: [string, any]) => (
                        <div key={key} className="flex items-center gap-2">
                          <span className="w-24 text-foreground-muted truncate text-[10px]">
                            {SIGNAL_LABELS[key] || key}
                          </span>
                          <div className="flex-1 h-1.5 bg-background-deep rounded-full overflow-hidden">
                            <div
                              className={cn(
                                'h-full rounded-full transition-all',
                                sig.normalized > 0.6 ? 'bg-red-500' : sig.normalized > 0.3 ? 'bg-yellow-500' : 'bg-green-500'
                              )}
                              style={{ width: `${Math.min(100, sig.normalized * 100)}%` }}
                            />
                          </div>
                          <span className="text-[10px] text-foreground-muted w-8 text-right">
                            {(sig.normalized * 100).toFixed(0)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Recent Posts */}
                  {accountDetail.posts?.length > 0 && (
                    <div className="space-y-1.5">
                      <div className="text-foreground-muted font-bold uppercase text-[10px] tracking-wider">
                        Postingan Terbaru ({accountDetail.posts.length})
                      </div>
                      <div className="max-h-48 overflow-auto space-y-1">
                        {accountDetail.posts.slice(0, 10).map((p: any) => (
                          <div key={p.post_id} className="p-1.5 bg-background-deep rounded text-[10px] text-foreground-muted">
                            {p.content?.slice(0, 120)}{p.content?.length > 120 ? '...' : ''}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ───────────────────────────────────────────────────

function StatCard({ label, value, icon, color }: {
  label: string; value: string | number; icon: any; color?: string;
}) {
  return (
    <div className="bg-background-card border border-border-dim rounded-sm p-2.5 flex flex-col gap-1">
      <div className="flex items-center gap-1.5">
        <Icon name={icon} size={12} className={color || 'text-foreground-muted'} />
        <span className="text-[10px] font-mono text-foreground-muted uppercase tracking-wide">{label}</span>
      </div>
      <span className={cn('text-lg font-mono font-bold', color || 'text-foreground')}>{value}</span>
    </div>
  );
}

function BotScoreBar({ score }: { score: number }) {
  const color = score >= 80 ? 'bg-red-500' : score >= 60 ? 'bg-orange-500' : score >= 40 ? 'bg-yellow-500' : 'bg-green-500';
  const textColor = score >= 80 ? 'text-red-400' : score >= 60 ? 'text-orange-400' : score >= 40 ? 'text-yellow-400' : 'text-green-400';
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-16 h-1.5 bg-background-deep rounded-full overflow-hidden">
        <div className={cn('h-full rounded-full', color)} style={{ width: `${Math.min(100, score)}%` }} />
      </div>
      <span className={cn('text-[10px] font-bold', textColor)}>{score.toFixed(0)}%</span>
    </div>
  );
}

// ── Mini force-directed layout ───────────────────────────────────────
function computeMiniLayout(
  nodes: CogGraphData['nodes'],
  edges: CogGraphData['edges'],
  W: number, H: number,
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();

  const clusters = new Map<number, typeof nodes>();
  for (const n of nodes) {
    const cid = n.cluster_id >= 0 ? n.cluster_id : -1;
    if (!clusters.has(cid)) clusters.set(cid, []);
    clusters.get(cid)!.push(n);
  }

  const clusterIds = Array.from(clusters.keys());
  const cx = W / 2, cy = H / 2;
  const orbitR = Math.min(W, H) * 0.3;

  clusterIds.forEach((cid, ci) => {
    const members = clusters.get(cid)!;
    const cAngle = (2 * Math.PI * ci) / Math.max(clusterIds.length, 1);
    const clusterCx = cx + orbitR * Math.cos(cAngle);
    const clusterCy = cy + orbitR * Math.sin(cAngle);

    const memberR = Math.min(60, 12 + members.length * 2.5);
    members.forEach((m, mi) => {
      const mAngle = (2 * Math.PI * mi) / Math.max(members.length, 1);
      const jitter = (seededRandom(m.id) - 0.5) * 16;
      positions.set(m.id, {
        x: Math.max(15, Math.min(W - 15, clusterCx + memberR * Math.cos(mAngle) + jitter)),
        y: Math.max(15, Math.min(H - 15, clusterCy + memberR * Math.sin(mAngle) + jitter)),
      });
    });
  });

  return positions;
}

function seededRandom(str: string): number {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = ((h << 5) - h + str.charCodeAt(i)) | 0;
  }
  return ((h & 0x7fffffff) % 1000) / 1000;
}

