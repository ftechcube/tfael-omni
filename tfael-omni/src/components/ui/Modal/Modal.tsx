// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Modal (Tailwind migration)
// Portal-based dialog with ESC close and body scroll lock
// ═══════════════════════════════════════════════════════════════════════

import { useEffect, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/lib/utils';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}

export function Modal({ open, onClose, title, children, footer, wide }: ModalProps) {
  // ESC key to close
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  // Prevent body scroll
  useEffect(() => {
    if (open) document.body.style.overflow = 'hidden';
    else document.body.style.overflow = '';
    return () => { document.body.style.overflow = ''; };
  }, [open]);

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 bg-black/65 flex items-center justify-center z-[9000] animate-fade-in p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className={cn(
          'bg-background-panel border border-border-dim rounded-lg w-full max-h-[85vh] flex flex-col animate-slide-up',
          wide ? 'max-w-[720px]' : 'max-w-[520px]',
        )}
        onClick={e => e.stopPropagation()}
      >
        {title && (
          <div className="flex items-center justify-between py-3.5 px-[18px] border-b border-border-dim">
            <div className="text-[15px] font-bold">{title}</div>
            <button
              className="bg-transparent border-none text-foreground-muted text-[22px] cursor-pointer px-1 leading-none hover:text-foreground"
              onClick={onClose}
              aria-label="Tutup"
            >
              ×
            </button>
          </div>
        )}
        <div className="flex-1 overflow-y-auto p-[18px]">{children}</div>
        {footer && (
          <div className="flex justify-end gap-2 py-3 px-[18px] border-t border-border-dim">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
