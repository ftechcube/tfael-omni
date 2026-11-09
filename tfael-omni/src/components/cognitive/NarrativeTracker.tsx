// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Narrative & CIB Tracker
// Coordinated behavior events, hashtag amplification, hoax classification
// ═══════════════════════════════════════════════════════════════════════

import { useState, useEffect, useCallback } from 'react';
import { cogCibDetect, cogAmplification, cogNarrative, cogSurge } from '@/api/endpoints';
import { Icon } from '@/components/icons/Icon';
import { cn } from '@/lib/utils';

const SEVERITY_STYLES: Record<string, string> = {
  CRITICAL: 'bg-red-900/50 text-red-300 border-red-700/50',
  HIGH:     'bg-orange-900/50 text-orange-300 border-orange-700/50',
  MEDIUM:   'bg-yellow-900/50 text-yellow-300 border-yellow-700/50',
  LOW:      'bg-green-900/50 text-green-300 border-green-700/50',
};

const CLASS_STYLES: Record<string, string> = {
  HIGH_RISK_DISINFORMATION: 'bg-red-900/50 text-red-300',
  SUSPICIOUS_NARRATIVE:     'bg-yellow-900/50 text-yellow-300',
  LOW_RISK:                 'bg-green-900/50 text-green-300',
  AMPLIFIED:                'bg-orange-900/50 text-orange-300',
  UNCLASSIFIED:             'bg-zinc-800/50 text-zinc-300',
};

interface Props {
  jobId?: string;
}

export function NarrativeTracker({ jobId }: Props) {
  const [cibEvents, setCibEvents] = useState<any[]>([]);
  const [narratives, setNarratives] = useState<any[]>([]);
  const [surgeData, setSurgeData] = useState<any>(null);
  const [narrativeAnalysis, setNarrativeAnalysis] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [analysisTopic, setAnalysisTopic] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [cib, amp, surge] = await Promise.all([
        cogCibDetect({ job_id: jobId }),
        cogAmplification({ job_id: jobId }),
        cogSurge({ job_id: jobId }),
      ]);
      if (cib?.ok) setCibEvents(cib.events || []);
      if (amp?.ok) setNarratives(amp.narratives || []);
      if (surge?.ok) setSurgeData(surge);
    } catch { /* ignore */ }
    setLoading(false);
  }, [jobId]);

  useEffect(() => { loadData(); }, [loadData]);

  const runNarrativeAnalysis = async () => {
    if (!analysisTopic.trim()) return;
    try {
      const res = await cogNarrative({ topic: analysisTopic, job_id: jobId });
      if (res?.ok) setNarrativeAnalysis(res);
    } catch { /* ignore */ }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-foreground-muted font-mono text-xs">
        <div className="w-5 h-5 border-2 border-border-dim border-t-primary rounded-full animate-spin mr-2" />
        Memuat data Narrative Intelligence...
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 p-3 h-full overflow-auto">
      {/* ── New Account Surge Alert ──────────────────── */}
      {surgeData?.surge_detected && (
        <div className={cn(
          'flex items-center gap-3 px-3 py-2 rounded-sm border font-mono text-xs',
          SEVERITY_STYLES[surgeData.severity] || SEVERITY_STYLES.MEDIUM
        )}>
          <Icon name="alert" size={16} />
          <div className="flex-1">
            <span className="font-bold">LONJAKAN AKUN BARU TERDETEKSI — </span>
            {surgeData.new_accounts} dari {surgeData.total_accounts} akun
            ({(surgeData.new_account_ratio * 100).toFixed(1)}%) berumur &lt;30 hari
          </div>
          <span className="font-bold uppercase text-[10px] tracking-wider">{surgeData.severity}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* ── CIB Events ───────────────────────────────── */}
        <div className="bg-background-card border border-border-dim rounded-sm overflow-hidden">
          <div className="flex items-center gap-2 px-3 py-2 border-b border-border-dim bg-background-panel">
            <Icon name="alert" size={14} className="text-red-400" />
            <span className="font-mono text-xs font-bold uppercase tracking-wide text-foreground">
              Coordinated Behavior ({cibEvents.length})
            </span>
          </div>

          <div className="overflow-auto max-h-72">
            {cibEvents.length > 0 ? cibEvents.map(ev => (
              <div key={ev.event_id} className="px-3 py-2 border-b border-border-dim/30 space-y-1">
                <div className="flex items-center justify-between">
                  <span className={cn(
                    'px-1.5 py-0.5 rounded text-[10px] font-bold border',
                    SEVERITY_STYLES[ev.severity] || SEVERITY_STYLES.MEDIUM
                  )}>
                    {ev.severity}
                  </span>
                  <span className="text-[10px] text-foreground-muted font-mono">{ev.detected_at}</span>
                </div>
                <div className="text-xs text-foreground font-mono">{ev.description}</div>
                {ev.accounts && (
                  <div className="flex flex-wrap gap-1">
                    {(typeof ev.accounts === 'string' ? JSON.parse(ev.accounts) : ev.accounts)
                      .slice(0, 5).map((a: string) => (
                        <span key={a} className="px-1 py-0.5 bg-background-deep rounded text-[9px] text-foreground-muted font-mono">
                          {a}
                        </span>
                      ))}
                  </div>
                )}
              </div>
            )) : (
              <div className="flex flex-col items-center justify-center h-32 text-foreground-muted text-xs font-mono gap-1">
                <Icon name="check" size={20} className="text-green-500" />
                <span>Tidak ada coordinated behavior terdeteksi.</span>
              </div>
            )}
          </div>
        </div>

        {/* ── Hashtag Amplification ─────────────────────── */}
        <div className="bg-background-card border border-border-dim rounded-sm overflow-hidden">
          <div className="flex items-center gap-2 px-3 py-2 border-b border-border-dim bg-background-panel">
            <Icon name="broadcast" size={14} className="text-orange-400" />
            <span className="font-mono text-xs font-bold uppercase tracking-wide text-foreground">
              Hashtag Amplification ({narratives.length})
            </span>
          </div>

          <div className="overflow-auto max-h-72">
            {narratives.length > 0 ? narratives.map(n => (
              <div key={n.narrative_id || n.hashtag} className="px-3 py-2 border-b border-border-dim/30 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold text-primary font-mono">{n.hashtag}</span>
                  <span className="text-[10px] text-foreground-muted">{n.unique_accounts} akun</span>
                </div>
                <div className="text-[10px] text-foreground-muted font-mono">
                  Seed: <span className="text-foreground">{n.seed_account}</span>
                  {' · '}{n.total_posts} post
                  {' · '}{n.time_span_hours}h spread
                </div>
                {n.amplifier_accounts?.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {n.amplifier_accounts.slice(0, 4).map((a: string) => (
                      <span key={a} className="px-1 py-0.5 bg-orange-900/20 rounded text-[9px] text-orange-400 font-mono">
                        {a}
                      </span>
                    ))}
                    {n.amplifier_accounts.length > 4 && (
                      <span className="px-1 py-0.5 text-[9px] text-foreground-muted">
                        +{n.amplifier_accounts.length - 4} lainnya
                      </span>
                    )}
                  </div>
                )}
              </div>
            )) : (
              <div className="flex flex-col items-center justify-center h-32 text-foreground-muted text-xs font-mono gap-1">
                <Icon name="check" size={20} className="text-green-500" />
                <span>Tidak ada amplifikasi terkoordinasi.</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Narrative Analysis ───────────────────────── */}
      <div className="bg-background-card border border-border-dim rounded-sm overflow-hidden">
        <div className="flex items-center gap-2 px-3 py-2 border-b border-border-dim bg-background-panel">
          <Icon name="search" size={14} className="text-primary" />
          <span className="font-mono text-xs font-bold uppercase tracking-wide text-foreground">
            Analisis Narasi & Hoax Detection
          </span>
        </div>

        <div className="p-3 space-y-2">
          <div className="flex gap-2">
            <input
              className="flex-1 px-2 py-1.5 bg-background-deep border border-border-dim rounded-sm font-mono text-xs text-foreground placeholder:text-foreground-muted/50 focus:outline-none focus:border-primary/50"
              placeholder="Masukkan topik untuk analisis narasi..."
              value={analysisTopic}
              onChange={e => setAnalysisTopic(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && runNarrativeAnalysis()}
            />
            <button
              className="px-3 py-1.5 bg-primary text-background-deep font-mono text-xs font-bold rounded-sm hover:bg-primary/80 disabled:opacity-50"
              onClick={runNarrativeAnalysis}
              disabled={!analysisTopic.trim()}
            >
              Analisis
            </button>
          </div>

          {narrativeAnalysis && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-2">
              <MiniStat label="Post Ditemukan" value={narrativeAnalysis.posts_found} />
              <MiniStat label="Akun Unik" value={narrativeAnalysis.unique_accounts} />
              <MiniStat label="Skor Hoax" value={`${(narrativeAnalysis.avg_hoax_score * 100).toFixed(0)}%`} />
              <div className="bg-background-deep rounded-sm p-2 flex flex-col gap-0.5">
                <span className="text-[9px] text-foreground-muted font-mono uppercase">Klasifikasi</span>
                <span className={cn(
                  'text-xs font-mono font-bold px-1.5 py-0.5 rounded self-start',
                  CLASS_STYLES[narrativeAnalysis.classification] || CLASS_STYLES.UNCLASSIFIED
                )}>
                  {narrativeAnalysis.classification}
                </span>
              </div>

              {narrativeAnalysis.top_hashtags?.length > 0 && (
                <div className="col-span-2 bg-background-deep rounded-sm p-2">
                  <span className="text-[9px] text-foreground-muted font-mono uppercase">Top Hashtags</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {narrativeAnalysis.top_hashtags.map((h: any) => (
                      <span key={h.tag} className="px-1.5 py-0.5 bg-primary/10 text-primary rounded text-[10px] font-mono">
                        {h.tag} ({h.count})
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {narrativeAnalysis.hoax_indicators?.length > 0 && (
                <div className="col-span-2 bg-background-deep rounded-sm p-2">
                  <span className="text-[9px] text-foreground-muted font-mono uppercase">Indikator Hoax</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {narrativeAnalysis.hoax_indicators.map((ind: any) => (
                      <span key={ind.indicator} className="px-1.5 py-0.5 bg-red-900/20 text-red-400 rounded text-[10px] font-mono">
                        {ind.indicator} ×{ind.count}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-background-deep rounded-sm p-2 flex flex-col gap-0.5">
      <span className="text-[9px] text-foreground-muted font-mono uppercase">{label}</span>
      <span className="text-sm text-foreground font-mono font-bold">{value}</span>
    </div>
  );
}

