// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — OSINT Search Bar (Tailwind migration)
// ═══════════════════════════════════════════════════════════════════════

import { useState, useCallback, type KeyboardEvent } from 'react';
import { cn } from '@/lib/utils';
import type { OsintSearchType } from '@/types/api';
import { OSINT_PLACEHOLDERS, TYPE_ICONS } from '../helpers';

const SEARCH_TYPES: OsintSearchType[] = [
  'name', 'username', 'email', 'domain', 'ip', 'phone', 'plate', 'gps', 'url',
];

interface SearchBarProps {
  onSearch: (query: string, type: OsintSearchType) => void;
  onExport: () => void;
  loading?: boolean;
  hasResult?: boolean;
}

export function SearchBar({ onSearch, onExport, loading, hasResult }: SearchBarProps) {
  const [query, setQuery] = useState('');
  const [activeType, setActiveType] = useState<OsintSearchType>('name');

  const handleSearch = useCallback(() => {
    const q = query.trim();
    if (!q) return;
    onSearch(q, activeType);
  }, [query, onSearch, activeType]);

  const handleKey = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
  }, [handleSearch]);

  const handleTypeClick = useCallback((type: OsintSearchType) => {
    setActiveType(type);
  }, []);

  return (
    <div className="py-3 px-3.5">
      <div className="flex gap-2 mb-2">
        <input
          className="flex-1 bg-background-card border border-border-dim rounded-md py-2 px-3 text-foreground font-mono text-[13px] focus:outline-none focus:border-accent-steel"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={handleKey}
          placeholder={OSINT_PLACEHOLDERS[activeType] ?? ''}
          disabled={loading}
        />
        <button
          className="flex items-center gap-1.5 py-2 px-4 bg-[#10b981] text-black border-none rounded-md font-mono text-xs font-bold cursor-pointer whitespace-nowrap transition-opacity hover:opacity-85 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={handleSearch}
          disabled={loading || !query.trim()}
        >
          {loading ? '⏳ Scanning…' : '🔍 SCAN'}
        </button>
      </div>

      <div className="flex flex-wrap gap-1">
        {SEARCH_TYPES.map(t => (
          <button
            key={t}
            className={cn(
              'py-[3px] px-2.5 bg-background-card border border-border-dim rounded text-foreground-muted font-mono text-[10px] cursor-pointer transition-all hover:border-accent-steel hover:text-accent-steel',
              t === activeType && 'border-accent-steel text-accent-steel',
            )}
            onClick={() => handleTypeClick(t)}
          >
            {TYPE_ICONS[t]} {t.toUpperCase()}
          </button>
        ))}
        {hasResult && (
          <button
            className="ml-auto py-[3px] px-2.5 bg-transparent border border-secondary rounded text-secondary font-mono text-[10px] cursor-pointer transition-opacity hover:opacity-75"
            onClick={onExport}
          >
            📄 Export PDF
          </button>
        )}
      </div>
    </div>
  );
}
