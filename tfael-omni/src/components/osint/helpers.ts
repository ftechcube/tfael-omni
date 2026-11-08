// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — OSINT Shared Helpers & Constants
// ═══════════════════════════════════════════════════════════════════════

import type { OsintSearchType } from '@/types/api';

/** Placeholder text for each OSINT search type */
export const OSINT_PLACEHOLDERS: Record<OsintSearchType, string> = {
  name:     'cth: Rizki Nurlita Salsabila',
  username: 'cth: rizkinurlita',
  email:    'cth: target@gmail.com',
  domain:   'cth: example.com',
  ip:       'cth: 8.8.8.8',
  phone:    'cth: +628123456789',
  plate:    'cth: B 1234 ABC',
  gps:      'cth: -6.2088, 106.8456',
  url:      'cth: https://example.com/page',
};

/** Type icons for display */
export const TYPE_ICONS: Record<string, string> = {
  name:     '👤',
  username: '🔍',
  email:    '📧',
  domain:   '🌐',
  ip:       '🖥️',
  phone:    '📱',
  plate:    '🚗',
  gps:      '📍',
  url:      '🔗',
};

/** Knowledge Graph node type → color mapping */
export const KG_COLORS: Record<string, string> = {
  person:              '#a78bfa',
  username:            '#60a5fa',
  email:               '#34d399',
  domain:              '#fbbf24',
  subdomain:           '#f59e0b',
  ip:                  '#f87171',
  phone:               '#fb923c',
  platform:            '#22d3ee',
  platform_unverified: '#6b7280',
  organization:        '#e879f9',
  location:            '#86efac',
  service:             '#94a3b8',
  breach:              '#ef4444',
  default:             '#94a3b8',
};

/** Knowledge Graph node type → icon mapping */
export const KG_ICONS: Record<string, string> = {
  person:              '👤',
  username:            '🔑',
  email:               '📧',
  domain:              '🌐',
  subdomain:           '🔗',
  ip:                  '🖥️',
  phone:               '📱',
  platform:            '✓',
  platform_unverified: '?',
  organization:        '🏢',
  location:            '📍',
  service:             '⚙️',
  breach:              '🔓',
  default:             '●',
};

/** Scan history localStorage key & limit */
export const HISTORY_KEY = 'tfael_scan_history';
export const HISTORY_MAX = 50;

/** Get KG color for a node type */
export function kgColor(type: string): string {
  return KG_COLORS[type] ?? KG_COLORS.default;
}

/** Get KG icon for a node type */
export function kgIcon(type: string): string {
  return KG_ICONS[type] ?? KG_ICONS.default;
}
