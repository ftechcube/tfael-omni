import {
  createContext, useContext, useCallback, useEffect, useMemo, useState,
  type ReactNode,
} from 'react';
import { setApiToken, setOnUnauthorized } from '@/api/client';
import { login as apiLogin, logout as apiLogout, getSession } from '@/api/auth';
import type { Permission } from '@/types/api';

interface AuthState {
  token: string | null;
  user: string | null;
  role: string | null;
  permissions: Permission[];
  ready: boolean;          // true once initial session check finishes
}

interface AuthContextValue extends AuthState {
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  hasPerm: (p: Permission) => boolean;
}

const AuthCtx = createContext<AuthContextValue | null>(null);

const TOKEN_KEY = 'tfael_token';


// Backend returns permissions as {key: boolean} object; normalize to Permission[]
function normalizePerms(raw: unknown): Permission[] {
  if (Array.isArray(raw)) return raw as Permission[];
  if (raw && typeof raw === 'object') {
    return Object.entries(raw as Record<string, boolean>)
      .filter(([, v]) => v)
      .map(([k]) => k as Permission);
  }
  return [];
}

// Backend returns user as {user_id, username, full_name, ...} object; extract display name
function normalizeUser(raw: unknown): string | null {
  if (typeof raw === 'string') return raw;
  if (raw && typeof raw === 'object') {
    const u = raw as Record<string, unknown>;
    return (u.full_name as string) || (u.username as string) || null;
  }
  return null;
}

// Extract role from user object or top-level
function normalizeRole(data: Record<string, unknown>): string | null {
  if (typeof data.role === 'string') return data.role;
  if (data.user && typeof data.user === 'object') {
    return ((data.user as Record<string, unknown>).role as string) || null;
  }
  return null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    token: null,
    user: null,
    role: null,
    permissions: [],
    ready: false,
  });

  // ── Sync token to API client ──────────────────────────────────
  useEffect(() => {
    setApiToken(state.token);
  }, [state.token]);

  // ── 401/403 handler ───────────────────────────────────────────
  useEffect(() => {
    setOnUnauthorized(() => {
      localStorage.removeItem(TOKEN_KEY);
      setState({ token: null, user: null, role: null, permissions: [], ready: true });
    });
  }, []);

  // ── Restore session on mount ──────────────────────────────────
  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (!stored) {
      setState(s => ({ ...s, ready: true }));
      return;
    }
    setApiToken(stored);
    getSession()
      .then(({ data }) => {
        if (data.ok) {
          setState({
            token: stored,
            user: normalizeUser(data.user),
            role: normalizeRole(data as Record<string, unknown>),
            permissions: normalizePerms(data.permissions),
            ready: true,
          });
        } else {
          localStorage.removeItem(TOKEN_KEY);
          setState(s => ({ ...s, ready: true }));
        }
      })
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        setState(s => ({ ...s, ready: true }));
      });
  }, []);

  // ── Login ─────────────────────────────────────────────────────
  const login = useCallback(async (username: string, password: string) => {
    const { data } = await apiLogin({ username, password });
    if (!data.ok) throw new Error(data.error || 'Login gagal');
    localStorage.setItem(TOKEN_KEY, data.token);
    setApiToken(data.token);  // set immediately so child effects see it
    setState({
      token: data.token,
      user: normalizeUser(data.user),
      role: normalizeRole(data as Record<string, unknown>),
      permissions: normalizePerms(data.permissions),
      ready: true,
    });
  }, []);

  // ── Logout ────────────────────────────────────────────────────
  const logout = useCallback(async () => {
    try { await apiLogout(); } catch { /* best-effort */ }
    localStorage.removeItem(TOKEN_KEY);
    setApiToken(null);
    setState({ token: null, user: null, role: null, permissions: [], ready: true });
  }, []);

  // ── Permission check ─────────────────────────────────────────
  const hasPerm = useCallback(
    (p: Permission) => state.permissions.includes(p),
    [state.permissions]
  );

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, login, logout, hasPerm }),
    [state, login, logout, hasPerm]
  );

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
