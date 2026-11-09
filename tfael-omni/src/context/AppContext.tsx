import {
  createContext, useContext, useCallback, useEffect, useMemo, useRef, useState,
  type ReactNode,
} from 'react';
import { fetchOverview } from '@/api/endpoints';
import { useAuth } from './AuthContext';
import type { OverviewData } from '@/types/api';

export type WorkspaceId = 'c4isr' | 'osint' | 'siem' | 'dfir' | 'intelligence' | 'cognitive' | 'admin';

interface AppState {
  workspace: WorkspaceId;
  overview: OverviewData | null;
  loading: boolean;
  utcTime: string;
}

interface AppContextValue extends AppState {
  setWorkspace: (ws: WorkspaceId) => void;
  refreshOverview: () => Promise<void>;
}

const AppCtx = createContext<AppContextValue | null>(null);

const SYNC_INTERVAL = 4000;  // 4s auto-sync

export function AppProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  const [state, setState] = useState<AppState>({
    workspace: 'c4isr',
    overview: null,
    loading: false,
    utcTime: new Date().toISOString().slice(11, 19) + 'Z',
  });

  const etagRef = useRef<string | undefined>();

  // ── UTC Clock (1s) ────────────────────────────────────────────
  useEffect(() => {
    const id = setInterval(() => {
      setState(s => ({
        ...s,
        utcTime: new Date().toISOString().slice(11, 19) + 'Z',
      }));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  // ── Overview polling (4s, with ETag/304) ──────────────────────
  const refreshOverview = useCallback(async () => {
    if (!token) return;
    try {
      const { data, etag, notModified } = await fetchOverview(etagRef.current);
      if (notModified) return; // no change
      etagRef.current = etag;
      setState(s => ({ ...s, overview: data, loading: false }));
    } catch {
      // silently retry next cycle
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;

    setState(s => ({ ...s, loading: true }));
    refreshOverview();

    const id = setInterval(refreshOverview, SYNC_INTERVAL);
    return () => clearInterval(id);
  }, [token, refreshOverview]);

  // ── Visibility API: pause polling when tab hidden ─────────────
  useEffect(() => {
    const handler = () => {
      if (document.visibilityState === 'visible') {
        refreshOverview();
      }
    };
    document.addEventListener('visibilitychange', handler);
    return () => document.removeEventListener('visibilitychange', handler);
  }, [refreshOverview]);

  const setWorkspace = useCallback((ws: WorkspaceId) => {
    setState(s => ({ ...s, workspace: ws }));
  }, []);

  const value = useMemo<AppContextValue>(
    () => ({ ...state, setWorkspace, refreshOverview }),
    [state, setWorkspace, refreshOverview]
  );

  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppCtx);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}
