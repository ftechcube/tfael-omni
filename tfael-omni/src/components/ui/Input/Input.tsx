// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Input / Select / TextArea (Tailwind migration)
// Form controls with label and error support
// ═══════════════════════════════════════════════════════════════════════

import { forwardRef, type InputHTMLAttributes, type TextareaHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

const INPUT_BASE = 'bg-background-deep border border-border-dim rounded-sm py-[7px] px-2.5 text-[13px] font-sans text-foreground outline-none transition-colors focus:border-accent-steel placeholder:text-foreground-muted placeholder:opacity-50';

/* ── Text Input ─────────────────────────────────────────────────────── */
interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  mono?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, mono, className, ...rest }, ref) => (
    <div className={cn('flex flex-col gap-1', className)}>
      {label && <label className="text-[11px] font-semibold uppercase tracking-wide text-foreground-muted font-mono">{label}</label>}
      <input
        ref={ref}
        className={cn(INPUT_BASE, mono && 'font-mono text-xs', error && 'border-destructive')}
        {...rest}
      />
      {error && <span className="text-[11px] text-destructive">{error}</span>}
    </div>
  )
);
Input.displayName = 'Input';

/* ── Select ─────────────────────────────────────────────────────────── */
interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps {
  label?: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  className?: string;
  disabled?: boolean;
}

export function Select({ label, value, options, onChange, className, disabled }: SelectProps) {
  return (
    <div className={cn('flex flex-col gap-1', className)}>
      {label && <label className="text-[11px] font-semibold uppercase tracking-wide text-foreground-muted font-mono">{label}</label>}
      <select
        className={cn(INPUT_BASE, "appearance-none bg-[length:12px_12px] bg-[position:right_8px_center] bg-no-repeat cursor-pointer pr-7")}
        style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='%236b5e47'%3E%3Cpath d='M2 4l4 4 4-4'/%3E%3C/svg%3E")` }}
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={disabled}
      >
        {options.map(o => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  );
}

/* ── Textarea ───────────────────────────────────────────────────────── */
interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  mono?: boolean;
}

export const TextArea = forwardRef<HTMLTextAreaElement, TextAreaProps>(
  ({ label, error, mono, className, ...rest }, ref) => (
    <div className={cn('flex flex-col gap-1', className)}>
      {label && <label className="text-[11px] font-semibold uppercase tracking-wide text-foreground-muted font-mono">{label}</label>}
      <textarea
        ref={ref}
        className={cn(INPUT_BASE, 'min-h-[80px] resize-y', mono && 'font-mono text-xs', error && 'border-destructive')}
        {...rest}
      />
      {error && <span className="text-[11px] text-destructive">{error}</span>}
    </div>
  )
);
TextArea.displayName = 'TextArea';
