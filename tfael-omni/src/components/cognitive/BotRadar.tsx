// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — BotRadar Dashboard
// Bot detection results, account scoring, signal breakdown
// ═══════════════════════════════════════════════════════════════════════

import { useState, useEffect, useCallback } from 'react';
import { cogDashboard, cogBotScore, cogAccountDetail } from '@/api/endpoints';
import type { CogAccount, CogDashboard } from '@/api/endpoints';
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

const SIGNAL_LABELS: Record<string, string> = {
  time_entropy:       'Entropi Waktu',
  text_similarity:    'Kemiripan Teks',
  ff_ratio_anomaly:   'Rasio FF Anomali',
  posting_regularity: 'Regularitas Posting',
  burst_posting:      'Burst Posting',
  username_entropy:   'Entropi Username',
  default_profile:    'Profil Default',
  age_activity_anomaly: 'Anomali Usia/Aktivitas',
};

interface Props {
  jobId?: string;
}

export function BotRadar({ jobId }: Props) {
  const [dashboard, setDashboard] = useState<CogDashboard | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState<string | null>(null);
  const [accountDetail, setAccountDetail] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    try {
      const res = await cogDashboard(jobId ? { job_id: jobId } : {});
      if (res?.ok) setDashboard(res);
    } catch { /* ignore */ }
    setLoading(false);
  }, [jobId]);

  useEffect(() => { loadDashboard(); }, [loadDashboard]);

  const loadAccountDetail = useCallback(async (accountId: string) => {
    setSelectedAccount(accountId);
    setDetailLoading(true);
    try {
      const res = await cogAccountDetail(accountId);
      if (res?.ok) setAccountDetail(res);
    } catch { /* ignore */ }
    setDetailLoading(false);
  }, []);

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
      {/* ── Summary Cards ─────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2">
        <StatCard label="Total Akun" value={s.total_accounts} icon="user" />
        <StatCard label="Bot Terdeteksi" value={s.bots} icon="bug" color="text-red-400" />
        <StatCard label="Mencurigakan" value={s.suspicious} icon="alert" color="text-yellow-400" />
        <StatCard label="Organik" value={s.organic} icon="check" color="text-green-400" />
        <StatCard label="Rasio Bot" value={`${(s.bot_ratio * 100).toFixed(1)}%`} icon="chart" color="text-orange-400" />
        <StatCard label="Jaringan" value={`${s.network_edges} edge`} icon="graph" color="text-blue-400" />
      </div>

      <div className="flex gap-3 flex-1 min-h-0">
        {/* ── Flagged Accounts Table ───────────────────── */}
        <div className="flex-1 bg-background-card border border-border-dim rounded-sm overflow-hidden flex flex-col">
          <div className="flex items-center gap-2 px-3 py-2 border-b border-border-dim bg-background-panel">
            <Icon name="target" size={14} className="text-primary" />
            <span className="font-mono text-xs font-bold uppercase tracking-wide text-foreground">
              Akun Terflag ({dashboard.top_flagged_accounts.length})
            </span>
          </div>

          <div className="flex-1 overflow-auto">
            <table className="w-full text-xs font-mono">
              <thead className="sticky top-0 bg-background-panel text-foreground-muted">
                <tr>
                  <th className="text-left px-3 py-1.5">Username</th>
                  <th className="text-left px-2 py-1.5">Platform</th>
                  <th className="text-right px-2 py-1.5">Bot Score</th>
                  <th className="text-left px-2 py-1.5">Label</th>
                  <th className="text-right px-2 py-1.5">Cluster</th>
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
                        : 'hover:bg-background-panel/50'
                    )}
                    onClick={() => loadAccountDetail(a.account_id)}
                  >
                    <td className="px-3 py-1.5 text-foreground">@{a.username}</td>
                    <td className="px-2 py-1.5 text-foreground-muted uppercase">{a.platform}</td>
                    <td className="px-2 py-1.5 text-right">
                      <BotScoreBar score={a.bot_score} />
                    </td>
                    <td className="px-2 py-1.5">
                      <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-bold border', LABEL_STYLES[a.bot_label] || LABEL_STYLES.UNKNOWN)}>
                        {a.bot_label}
                      </span>
                    </td>
                    <td className="px-2 py-1.5 text-right text-foreground-muted">
                      {a.cluster_id >= 0 ? `C${a.cluster_id}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* ── Account Detail Panel ────────────────────── */}
        {selectedAccount && (
          <div className="w-80 bg-background-card border border-border-dim rounded-sm overflow-auto flex flex-col">
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
                </div>

                {/* Signal Breakdown */}
                {accountDetail.signals && Object.keys(accountDetail.signals).length > 0 && (
                  <div className="space-y-1.5">
                    <div className="text-foreground-muted font-bold uppercase text-[10px] tracking-wider">Signal Breakdown</div>
                    {Object.entries(accountDetail.signals).map(([key, sig]: [string, any]) => (
                      <div key={key} className="flex items-center gap-2">
                        <span className="w-28 text-foreground-muted truncate text-[10px]">
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
  );
}

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

