// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Utility functions (Shadcn/ui convention)
// ═══════════════════════════════════════════════════════════════════════

import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Merge Tailwind classes — the Shadcn/ui standard `cn()` helper.
 * Combines clsx (conditional classes) with tailwind-merge (dedup).
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
