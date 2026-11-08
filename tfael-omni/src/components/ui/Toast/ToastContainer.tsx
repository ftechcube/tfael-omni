// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Toast Container (Tailwind migration)
// Fixed-position toast notification stack
// ═══════════════════════════════════════════════════════════════════════

import { useToast, type ToastType } from '@/hooks/useToast';
import { cn } from '@/lib/utils';

const ICONS: Record<ToastType, string> = {
  ok: '✓',
  error: '✕',
  warn: '⚠',
  info: 'ℹ',
};

const TYPE_CLS: Record<ToastType, string> = {
  ok:    'bg-[rgba(147,173,87,0.15)] border-[#10b981] text-[#10b981]',
  error: 'bg-[rgba(217,87,61,0.15)] border-destructive text-destructive',
  warn:  'bg-[rgba(242,169,59,0.15)] border-secondary text-secondary',
  info:  'bg-[rgba(111,147,160,0.15)] border-accent-steel text-accent-steel',
};

export function ToastContainer() {
  const { toasts, dismiss } = useToast();

  return (
    <div className="fixed bottom-5 right-5 z-[9999] flex flex-col gap-2 pointer-events-none" role="status" aria-live="polite">
      {toasts.map(t => (
        <div
          key={t.id}
          className={cn(
            'flex items-center gap-2.5 py-2.5 px-4 rounded-md text-xs font-semibold pointer-events-auto animate-slide-up cursor-pointer max-w-[360px] shadow-[0_4px_16px_rgba(0,0,0,0.4)] border',
            TYPE_CLS[t.type],
          )}
          onClick={() => dismiss(t.id)}
        >
          <span className="text-sm shrink-0">{ICONS[t.type]}</span>
          <span className="flex-1">{t.message}</span>
        </div>
      ))}
    </div>
  );
}
