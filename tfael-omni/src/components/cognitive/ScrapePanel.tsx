// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Social Media Scrape Control Panel
// Launch scraping jobs, run full pipeline, monitor progress
// ═══════════════════════════════════════════════════════════════════════

import { useState } from 'react';
import { cogScrape, cogFullPipeline } from '@/api/endpoints';
import { Icon } from '@/components/icons/Icon';
import { cn } from '@/lib/utils';

interface Props {
  onJobComplete?: (jobId: string) => void;
}

export function ScrapePanel({ onJobComplete }: Props) {
  const [platform, setPlatform] = useState<'twitter' | 'telegram'>('twitter');
  const [query, setQuery] = useState('');
  const [channel, setChannel] = useState('');
  const [maxPosts, setMaxPosts] = useState(200);
  const [running, setRunning] = useState(false);
  const [mode, setMode] = useState<'scrape' | 'full'>('full');
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');

  const handleRun = async () => {
    setRunning(true);
    setError('');
    setResult(null);

    try {
      let res: any;
      if (mode === 'full') {
        res = await cogFullPipeline({
          platform,
          query: platform === 'twitter' ? query : '',
          channel: platform === 'telegram' ? channel : '',
          max_posts: maxPosts,
        });
      } else {
        res = await cogScrape({
          platform,
          query: platform === 'twitter' ? query : undefined,
          channel: platform === 'telegram' ? channel : undefined,
          max_posts: maxPosts,
        });
      }

      if (res?.ok) {
        setResult(res);
        onJobComplete?.(res.job_id);
      } else {
        setError(res?.error || 'Gagal menjalankan operasi.');
      }
    } catch (e: any) {
      setError(e.message || 'Network error.');
    }
    setRunning(false);
  };

  const canRun = platform === 'twitter' ? query.trim().length > 0 : channel.trim().length > 0;

  return (
    <div className="flex flex-col gap-3 p-3 h-full overflow-auto">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* ── Config Panel ─────────────────────────────── */}
        <div className="bg-background-card border border-border-dim rounded-sm overflow-hidden">
          <div className="flex items-center gap-2 px-3 py-2 border-b border-border-dim bg-background-panel">
            <Icon name="broadcast" size={14} className="text-primary" />
            <span className="font-mono text-xs font-bold uppercase tracking-wide text-foreground">
              Konfigurasi Scraping
            </span>
          </div>

          <div className="p-3 space-y-3">
            {/* Mode */}
            <div className="space-y-1">
              <label className="text-[10px] font-mono text-foreground-muted uppercase tracking-wider">Mode</label>
              <div className="flex gap-1">
                {[
                  { id: 'full', label: 'Full Pipeline', desc: 'Scrape + Bot Detection + CIB + Graph + Hoax' },
                  { id: 'scrape', label: 'Scrape Only', desc: 'Kumpulkan data saja' },
                ].map(m => (
                  <button
                    key={m.id}
                    className={cn(
                      'flex-1 px-2 py-1.5 rounded-sm font-mono text-[10px] border transition-colors',
                      mode === m.id
                        ? 'bg-primary/20 border-primary/50 text-primary'
                        : 'bg-background-deep border-border-dim text-foreground-muted hover:bg-background-panel'
                    )}
                    onClick={() => setMode(m.id as any)}
                  >
                    {m.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Platform */}
            <div className="space-y-1">
              <label className="text-[10px] font-mono text-foreground-muted uppercase tracking-wider">Platform</label>
              <div className="flex gap-1">
                {[
                  { id: 'twitter', label: 'Twitter / X', icon: '𝕏' },
                  { id: 'telegram', label: 'Telegram', icon: '✈' },
                ].map(p => (
                  <button
                    key={p.id}
                    className={cn(
                      'flex-1 px-2 py-1.5 rounded-sm font-mono text-[10px] border transition-colors',
                      platform === p.id
                        ? 'bg-primary/20 border-primary/50 text-primary'
                        : 'bg-background-deep border-border-dim text-foreground-muted hover:bg-background-panel'
                    )}
                    onClick={() => setPlatform(p.id as any)}
                  >
                    {p.icon} {p.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Query / Channel */}
            {platform === 'twitter' ? (
              <div className="space-y-1">
                <label className="text-[10px] font-mono text-foreground-muted uppercase tracking-wider">
                  Kata Kunci Pencarian
                </label>
                <input
                  className="w-full px-2 py-1.5 bg-background-deep border border-border-dim rounded-sm font-mono text-xs text-foreground placeholder:text-foreground-muted/50 focus:outline-none focus:border-primary/50"
                  placeholder="Contoh: #TNI operasi militer 2026"
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                />
              </div>
            ) : (
              <div className="space-y-1">
                <label className="text-[10px] font-mono text-foreground-muted uppercase tracking-wider">
                  Nama Channel
                </label>
                <input
                  className="w-full px-2 py-1.5 bg-background-deep border border-border-dim rounded-sm font-mono text-xs text-foreground placeholder:text-foreground-muted/50 focus:outline-none focus:border-primary/50"
                  placeholder="Contoh: detikcom (tanpa @)"
                  value={channel}
                  onChange={e => setChannel(e.target.value)}
                />
              </div>
            )}

            {/* Max Posts */}
            <div className="space-y-1">
              <label className="text-[10px] font-mono text-foreground-muted uppercase tracking-wider">
                Max Postingan: {maxPosts}
              </label>
              <input
                type="range"
                min={50}
                max={500}
                step={50}
                value={maxPosts}
                onChange={e => setMaxPosts(Number(e.target.value))}
                className="w-full accent-primary"
              />
            </div>

            {/* Run Button */}
            <button
              className={cn(
                'w-full flex items-center justify-center gap-2 px-3 py-2 rounded-sm font-mono text-xs font-bold uppercase tracking-wide transition-colors',
                canRun && !running
                  ? 'bg-primary text-background-deep hover:bg-primary/80'
                  : 'bg-background-deep text-foreground-muted cursor-not-allowed'
              )}
              onClick={handleRun}
              disabled={!canRun || running}
            >
              {running ? (
                <>
                  <div className="w-4 h-4 border-2 border-background-deep/30 border-t-background-deep rounded-full animate-spin" />
                  {mode === 'full' ? 'Menjalankan Full Pipeline...' : 'Scraping...'}
                </>
              ) : (
                <>
                  <Icon name="play" size={14} />
                  {mode === 'full' ? 'Jalankan Full Pipeline' : 'Mulai Scraping'}
                </>
              )}
            </button>

            {error && (
              <div className="px-2 py-1.5 bg-red-900/20 border border-red-700/30 rounded-sm text-red-400 text-[10px] font-mono">
                {error}
              </div>
            )}
          </div>
        </div>

        {/* ── Results Panel ─────────────────────────────── */}
        <div className="bg-background-card border border-border-dim rounded-sm overflow-hidden">
          <div className="flex items-center gap-2 px-3 py-2 border-b border-border-dim bg-background-panel">
            <Icon name="chart" size={14} className="text-primary" />
            <span className="font-mono text-xs font-bold uppercase tracking-wide text-foreground">
              Hasil Operasi
            </span>
          </div>

          <div className="p-3">
            {result ? (
              <div className="space-y-2 font-mono text-xs">
                {result.job_id && (
                  <div className="flex justify-between">
                    <span className="text-foreground-muted">Job ID:</span>
                    <span className="text-primary font-bold">{result.job_id}</span>
                  </div>
                )}

                {/* Full Pipeline Stages */}
                {result.pipeline_stages && (
                  <div className="space-y-1">
                    <div className="text-[10px] font-bold text-foreground-muted uppercase tracking-wider mb-1">
                      Pipeline Stages
                    </div>
                    {Object.entries(result.pipeline_stages).map(([stage, data]: [string, any]) => (
                      <div key={stage} className="flex items-center gap-2 px-2 py-1 bg-background-deep rounded-sm">
                        <span className={cn(
                          'w-1.5 h-1.5 rounded-full',
                          data.status === 'OK' ? 'bg-green-500' : data.status === 'SKIPPED' ? 'bg-yellow-500' : 'bg-red-500'
                        )} />
                        <span className="flex-1 text-foreground-muted text-[10px]">{stage}</span>
                        <span className="text-foreground text-[10px]">{data.status}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Summary */}
                {result.summary && (
                  <div className="space-y-1 mt-2 p-2 bg-background-deep rounded-sm">
                    <div className="text-[10px] font-bold text-foreground-muted uppercase tracking-wider">Ringkasan</div>
                    {Object.entries(result.summary).map(([k, v]) => (
                      <div key={k} className="flex justify-between text-[10px]">
                        <span className="text-foreground-muted">{k.replace(/_/g, ' ')}:</span>
                        <span className="text-foreground font-bold">{String(v)}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Scrape-only results */}
                {result.posts_collected !== undefined && !result.pipeline_stages && (
                  <div className="space-y-1">
                    <div className="flex justify-between">
                      <span className="text-foreground-muted">Posts:</span>
                      <span className="text-foreground">{result.posts_collected}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-foreground-muted">Accounts:</span>
                      <span className="text-foreground">{result.accounts_found}</span>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-32 gap-2 text-foreground-muted text-xs font-mono">
                <Icon name="globe" size={24} />
                <span>Belum ada operasi dijalankan.</span>
                <span className="text-[10px] text-center">
                  Pilih platform, masukkan kata kunci,
                  <br />lalu tekan tombol untuk memulai.
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

