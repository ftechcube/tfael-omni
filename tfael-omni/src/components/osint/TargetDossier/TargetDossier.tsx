// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Target Dossier & Pelacakan (Tailwind migration)
// Target management, codename CRUD, save-to-profile modal
// ═══════════════════════════════════════════════════════════════════════

import { useState, useCallback, useEffect } from 'react';
import { cn } from '@/lib/utils';
import type { Target, OsintSearchResult, KGNode, KGEdge } from '@/types/api';
import {
  createTarget, deleteTarget, patchTarget, reconStatus,
  osintSaveToProfile,
} from '@/api/endpoints';
import { useApp } from '@/context/AppContext';
import { useToast } from '@/hooks/useToast';
import { Modal } from '@/components/ui/Modal/Modal';
import { Button } from '@/components/ui/Button/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog/ConfirmDialog';

// ── Risk badge lookup ─────────────────────────────────────────────────

const RISK_CLS: Record<string, string> = {
  critical: 'bg-[#7f1d1d] text-[#fca5a5]',
  high:     'bg-[#7c2d12] text-[#fb923c]',
  medium:   'bg-[#451a03] text-[#fcd34d]',
  low:      'bg-[#14532d] text-[#86efac]',
};

// ── Save-to-Profile Modal ──────────────────────────────────────────────

interface SaveToProfileModalProps {
  open: boolean;
  onClose: () => void;
  targets: Target[];
  scanData: OsintSearchResult | null;
  graphData: { nodes: KGNode[]; edges: KGEdge[] } | null;
}

function SaveToProfileModal({ open, onClose, targets, scanData, graphData }: SaveToProfileModalProps) {
  const [selectedId, setSelectedId] = useState('');
  const [newCodeName, setNewCodeName] = useState('');
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  const handleSaveExisting = useCallback(async () => {
    if (!selectedId || !scanData) return;
    setSaving(true);
    try {
      const res = await osintSaveToProfile(selectedId, scanData, graphData);
      if (res.ok) {
        toast('Data berhasil disimpan ke profil target', 'success');
        onClose();
      } else {
        toast((res as Record<string, unknown>).error as string ?? 'Gagal menyimpan', 'error');
      }
    } catch {
      toast('Gagal menyimpan ke profil', 'error');
    } finally {
      setSaving(false);
    }
  }, [selectedId, scanData, graphData, toast, onClose]);

  const handleQuickCreate = useCallback(async () => {
    if (!newCodeName.trim() || !scanData) return;
    setSaving(true);
    try {
      // Create target via recon endpoint
      const res = await createTarget({
        code_name: newCodeName.trim(),
        identifiers: { query: scanData.query, type: scanData.type },
      });
      if (res.ok) {
        // Poll status until done (max 30 attempts)
        const jobId = (res as Record<string, unknown>).job_id as string;
        if (jobId) {
          let done = false;
          for (let i = 0; i < 30 && !done; i++) {
            await new Promise(r => setTimeout(r, 2000));
            const status = await reconStatus(jobId);
            if (status.ok && !(status as Record<string, unknown>).pending) {
              done = true;
              const targetId = (status as Record<string, unknown>).target_id as string;
              if (targetId) {
                await osintSaveToProfile(targetId, scanData, graphData);
              }
            }
          }
        }
        toast('Target dibuat dan data dilampirkan', 'success');
        onClose();
      } else {
        toast((res as Record<string, unknown>).error as string ?? 'Gagal membuat target', 'error');
      }
    } catch {
      toast('Gagal membuat target', 'error');
    } finally {
      setSaving(false);
    }
  }, [newCodeName, scanData, graphData, toast, onClose]);

  return (
    <Modal open={open} onClose={onClose} title="💾 Simpan ke Profil Target">
      <div className="flex flex-col gap-2.5">
        {targets.length > 0 && (
          <>
            <div className="text-xs font-semibold mb-1">Pilih Target yang Ada</div>
            <select
              className="w-full py-1.5 px-2.5 bg-background-card border border-border-dim rounded text-foreground font-mono text-xs"
              value={selectedId}
              onChange={e => setSelectedId(e.target.value)}
            >
              <option value="">— Pilih target —</option>
              {targets.map(t => (
                <option key={t.target_id} value={t.target_id}>
                  {t.code_name} (Risk: {t.risk_level})
                </option>
              ))}
            </select>
            <Button
              variant="primary"
              size="sm"
              onClick={handleSaveExisting}
              disabled={!selectedId || saving}
            >
              {saving ? '⏳ Menyimpan…' : '📋 Simpan ke Target'}
            </Button>

            <div className="text-center text-[10px] opacity-40 my-1">— atau —</div>
          </>
        )}

        <div className="text-xs font-semibold mb-1">Buat Target Baru</div>
        <input
          className="w-full py-1.5 px-2.5 bg-background-card border border-border-dim rounded text-foreground font-mono text-xs focus:outline-none focus:border-accent-steel"
          value={newCodeName}
          onChange={e => setNewCodeName(e.target.value)}
          placeholder="Code name baru…"
        />
        <Button
          variant="amber"
          size="sm"
          onClick={handleQuickCreate}
          disabled={!newCodeName.trim() || saving}
        >
          {saving ? '⏳ Membuat…' : '✨ Buat & Lampirkan'}
        </Button>
      </div>
    </Modal>
  );
}

// ── Main Dossier Panel ─────────────────────────────────────────────────

interface TargetDossierProps {
  scanResult?: OsintSearchResult | null;
  graphData?: { nodes: KGNode[]; edges: KGEdge[] } | null;
}

export function TargetDossier({ scanResult, graphData }: TargetDossierProps) {
  const { overview, refreshOverview } = useApp();
  const targets = overview?.targets ?? [];
  const { toast } = useToast();

  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  // Open save modal from parent (via prop or manual)
  const openSaveModal = useCallback(() => {
    if (!scanResult) {
      toast('Lakukan scan terlebih dahulu', 'warning');
      return;
    }
    setSaveModalOpen(true);
  }, [scanResult, toast]);

  // Rename target
  const handleStartRename = useCallback((t: Target) => {
    setEditingId(t.target_id);
    setEditValue(t.code_name);
  }, []);

  const handleFinishRename = useCallback(async () => {
    if (!editingId || !editValue.trim()) {
      setEditingId(null);
      return;
    }
    try {
      const res = await patchTarget(editingId, { code_name: editValue.trim() });
      if (res.ok) {
        toast('Code name diperbarui', 'success');
        refreshOverview();
      }
    } catch {
      toast('Gagal memperbarui code name', 'error');
    }
    setEditingId(null);
  }, [editingId, editValue, toast, refreshOverview]);

  // Delete target
  const handleDelete = useCallback(async (targetId: string) => {
    try {
      const res = await deleteTarget(targetId);
      if (res.ok) {
        toast('Target dihapus', 'success');
        refreshOverview();
      } else {
        toast('Gagal menghapus target', 'error');
      }
    } catch {
      toast('Gagal menghapus target', 'error');
    }
    setDeleteConfirm(null);
  }, [toast, refreshOverview]);

  const riskClass = (level: string) =>
    RISK_CLS[level.toLowerCase()] ?? RISK_CLS.low;

  return (
    <div className="p-3">
      <div className="flex items-center gap-2 mb-3">
        <button
          className="py-[5px] px-3 border border-border-dim rounded bg-background-card text-foreground font-mono text-[11px] cursor-pointer transition-all hover:border-accent-steel hover:text-accent-steel"
          onClick={refreshOverview}
        >
          🔄 Refresh
        </button>
        {scanResult && (
          <button
            className="py-[5px] px-3 bg-[#10b981] border border-[#10b981] rounded text-black font-mono text-[11px] font-bold cursor-pointer hover:opacity-85"
            onClick={openSaveModal}
          >
            📋 Lampirkan Hasil Scan
          </button>
        )}
      </div>

      {targets.length === 0 ? (
        <div className="text-center py-10 px-4 opacity-30 text-[13px] font-mono">
          Belum ada target. Lakukan scan dan simpan ke dossier.
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-2.5">
          {targets.map(t => (
            <div
              key={t.target_id}
              className="p-3 bg-background-card border border-border-dim rounded-lg transition-colors hover:border-border-accent"
            >
              <div className="flex justify-between items-start mb-1.5">
                {editingId === t.target_id ? (
                  <input
                    className="bg-background-card border border-accent-steel rounded-[3px] py-0.5 px-1.5 text-foreground font-mono text-[13px] w-[140px]"
                    value={editValue}
                    onChange={e => setEditValue(e.target.value)}
                    onBlur={handleFinishRename}
                    onKeyDown={e => e.key === 'Enter' && handleFinishRename()}
                    autoFocus
                  />
                ) : (
                  <span className="text-sm font-bold font-mono">{t.code_name}</span>
                )}
                <span className={`py-0.5 px-2 rounded text-[10px] font-bold ${riskClass(t.risk_level)}`}>
                  {t.risk_level} ({t.risk_score})
                </span>
              </div>
              <div className="text-[11px] opacity-50 mb-1.5">
                ID: {t.target_id.slice(0, 8)}…
                {t.scan_count != null && ` · ${t.scan_count} scan`}
                {t.last_seen && ` · ${new Date(t.last_seen).toLocaleDateString('id-ID')}`}
              </div>
              {t.sources && t.sources.length > 0 && (
                <div className="text-[10px] opacity-40">
                  Sumber: {t.sources.join(', ')}
                </div>
              )}
              <div className="flex gap-1.5 mt-2">
                <button
                  className="py-[3px] px-2 bg-transparent border border-border-dim rounded-[3px] text-foreground-muted font-mono text-[10px] cursor-pointer hover:border-accent-steel hover:text-accent-steel"
                  onClick={() => handleStartRename(t)}
                >
                  ✏ Rename
                </button>
                <button
                  className="py-[3px] px-2 bg-transparent border border-border-dim rounded-[3px] text-foreground-muted font-mono text-[10px] cursor-pointer hover:border-destructive hover:text-destructive"
                  onClick={() => setDeleteConfirm(t.target_id)}
                >
                  🗑 Hapus
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-2 text-[10px] opacity-40 font-mono">{targets.length} target terdaftar</div>

      {/* Save to profile modal */}
      <SaveToProfileModal
        open={saveModalOpen}
        onClose={() => setSaveModalOpen(false)}
        targets={targets}
        scanData={scanResult ?? null}
        graphData={graphData ?? null}
      />

      {/* Delete confirmation */}
      <ConfirmDialog
        open={!!deleteConfirm}
        title="Hapus Target"
        message="Yakin ingin menghapus target ini? Tindakan tidak dapat dibatalkan."
        confirmLabel="Hapus"
        danger
        onConfirm={() => deleteConfirm && handleDelete(deleteConfirm)}
        onClose={() => setDeleteConfirm(null)}
      />
    </div>
  );
}
