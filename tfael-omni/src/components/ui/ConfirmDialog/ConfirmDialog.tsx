// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Confirm Dialog (Tailwind migration)
// Simple confirmation modal with cancel / confirm buttons
// ═══════════════════════════════════════════════════════════════════════

import { Modal } from '@/components/ui/Modal/Modal';
import { Button } from '@/components/ui/Button/Button';

interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title?: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  loading?: boolean;
}

export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title = 'Konfirmasi',
  message,
  confirmLabel = 'Ya',
  danger,
  loading,
}: ConfirmDialogProps) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <>
          <Button onClick={onClose} disabled={loading}>Batal</Button>
          <Button
            variant={danger ? 'danger' : 'primary'}
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? '...' : confirmLabel}
          </Button>
        </>
      }
    >
      <p className="text-[13px] text-foreground m-0 leading-relaxed">
        {message}
      </p>
    </Modal>
  );
}
