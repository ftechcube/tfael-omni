// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — App Shell (Tailwind migration)
// Routes: Login → TopBar + Workspace + StatusBar
// ═══════════════════════════════════════════════════════════════════════

import { lazy, Suspense } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useApp } from '@/context/AppContext';
import { TopBar } from '@/components/layout/TopBar';
import { ClassificationBanner } from '@/components/layout/ClassificationBanner';
import { StatusBar } from '@/components/layout/StatusBar';
import { LoginScreen } from '@/components/layout/LoginScreen';
import { ToastContainer } from '@/components/ui/Toast/ToastContainer';

// ── Lazy-loaded workspaces ────────────────────────────────────────────
const C4ISRWorkspace        = lazy(() => import('@/workspaces/C4ISRWorkspace'));
const OsintWorkspace        = lazy(() => import('@/workspaces/OsintWorkspace'));
const SiemWorkspace         = lazy(() => import('@/workspaces/SiemWorkspace'));
const DfirWorkspace         = lazy(() => import('@/workspaces/DfirWorkspace'));
const IntelligenceWorkspace = lazy(() => import('@/workspaces/IntelligenceWorkspace'));
const AdminWorkspace        = lazy(() => import('@/workspaces/AdminWorkspace'));

function WorkspaceLoader() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 min-h-[200px] h-full bg-background-deep text-foreground-muted font-mono text-xs">
      <div className="w-6 h-6 border-2 border-border-dim border-t-primary rounded-full animate-spin" />
      <span>Memuat modul...</span>
    </div>
  );
}

function WorkspaceRouter() {
  const { workspace } = useApp();

  return (
    <Suspense fallback={<WorkspaceLoader />}>
      {workspace === 'c4isr'        && <C4ISRWorkspace />}
      {workspace === 'osint'        && <OsintWorkspace />}
      {workspace === 'siem'         && <SiemWorkspace />}
      {workspace === 'dfir'         && <DfirWorkspace />}
      {workspace === 'intelligence' && <IntelligenceWorkspace />}
      {workspace === 'admin'        && <AdminWorkspace />}
    </Suspense>
  );
}

export default function App() {
  const { token, ready } = useAuth();

  // ── Wait for session restoration ──────────────────────────────────
  if (!ready) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 min-h-screen bg-background-deep text-foreground-muted font-mono text-xs">
        <div className="w-6 h-6 border-2 border-border-dim border-t-primary rounded-full animate-spin" />
        <span>Initializing secure session...</span>
      </div>
    );
  }

  // ── Not authenticated → Login ─────────────────────────────────────
  if (!token) {
    return <LoginScreen />;
  }

  // ── Authenticated → Main Shell ────────────────────────────────────
  return (
    <div className="flex flex-col h-screen overflow-hidden bg-background-deep">
      <ClassificationBanner />
      <TopBar />
      <main className="flex-1 overflow-hidden flex flex-col">
        <WorkspaceRouter />
      </main>
      <StatusBar />
      <ToastContainer />
    </div>
  );
}
