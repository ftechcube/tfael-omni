// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Login Screen (Tailwind migration)
// Full-screen login with brand, classification banner, form
// ═══════════════════════════════════════════════════════════════════════

import { useState, type FormEvent } from 'react';
import { useAuth } from '@/context/AuthContext';
import { Icon } from '@/components/icons/Icon';
import { cn } from '@/lib/utils';

export function LoginScreen() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!username || !password) return;

    setError('');
    setLoading(true);
    try {
      await login(username, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login gagal');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col min-h-screen bg-background-deep">
      {/* Classification */}
      <div className="text-center font-mono text-2xs font-bold tracking-[0.12em] py-0.5 bg-secondary text-background-deep shrink-0">
        RESTRICTED // FOUO
      </div>

      {/* Login Card */}
      <div className="m-auto w-full max-w-[380px] p-9 max-[480px]:mx-4 max-[480px]:p-6 bg-background-panel border border-border-dim rounded-lg flex flex-col gap-6">
        {/* Brand */}
        <div className="flex flex-col items-center gap-2 text-center">
          <div className="w-[52px] h-[52px] flex items-center justify-center bg-background-deep border border-border-dim rounded-md">
            <Icon name="satellite" size={28} color="#8c9663" />
          </div>
          <div className="font-mono text-2xl font-extrabold text-primary tracking-[0.12em]">
            TFAEL<span className="text-sm font-bold text-foreground-muted ml-1 opacity-50">OMNI</span>
          </div>
          <div className="text-2xs font-semibold uppercase tracking-[0.1em] text-foreground-muted opacity-50">
            Tactical Field Analysis &amp; Electronic Liaison
          </div>
        </div>

        {/* Form */}
        <form className="flex flex-col gap-3.5" onSubmit={handleSubmit}>
          <div className="flex flex-col gap-1">
            <label className="font-mono text-2xs font-bold uppercase tracking-wide text-foreground-muted">
              CALLSIGN
            </label>
            <input
              className={cn(
                'bg-background-muted border border-border-dim rounded-sm px-3 py-2.5 font-mono text-[13px] text-foreground outline-none transition-colors',
                'focus:border-primary placeholder:text-foreground-muted/40 disabled:opacity-50'
              )}
              type="text"
              autoComplete="username"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="operator"
              autoFocus
              disabled={loading}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="font-mono text-2xs font-bold uppercase tracking-wide text-foreground-muted">
              ACCESS CODE
            </label>
            <input
              className={cn(
                'bg-background-muted border border-border-dim rounded-sm px-3 py-2.5 font-mono text-[13px] text-foreground outline-none transition-colors',
                'focus:border-primary placeholder:text-foreground-muted/40 disabled:opacity-50'
              )}
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              disabled={loading}
            />
          </div>

          {error && (
            <div className="flex items-center gap-1.5 text-xs text-destructive px-2.5 py-1.5 bg-destructive/10 rounded-sm">
              <Icon name="alert" size={14} /> {error}
            </div>
          )}

          <button
            className={cn(
              'bg-primary text-background-deep rounded-sm py-2.5 font-mono text-xs font-bold uppercase tracking-wide transition-opacity mt-1',
              'hover:opacity-85 disabled:opacity-40 disabled:cursor-not-allowed'
            )}
            type="submit"
            disabled={loading || !username || !password}
          >
            {loading ? 'AUTHENTICATING...' : 'AUTHENTICATE'}
          </button>
        </form>

        {/* Footer */}
        <div className="flex items-center justify-center gap-1.5 text-2xs text-foreground-muted opacity-40">
          <Icon name="lock" size={12} />
          <span>Encrypted session · On-premise deployment</span>
        </div>
      </div>

      {/* Bottom classification */}
      <div className="text-center font-mono text-2xs font-bold tracking-[0.12em] py-0.5 bg-secondary text-background-deep shrink-0">
        RESTRICTED // FOUO
      </div>
    </div>
  );
}
