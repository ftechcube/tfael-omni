// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — SVG Icon System
// 48 inline SVG icons extracted from original index.html <defs> block.
// Air-gap safe — no external icon fonts or CDN.
// ═══════════════════════════════════════════════════════════════════════

import type { CSSProperties } from 'react';

/** All available icon names */
export type IconName =
  | 'satellite' | 'target' | 'shield' | 'flask' | 'settings'
  | 'broadcast' | 'map' | 'zap' | 'graph' | 'chart'
  | 'alert' | 'lock' | 'user' | 'key' | 'scroll'
  | 'pin' | 'camera' | 'search' | 'refresh' | 'plane'
  | 'check' | 'upload' | 'box' | 'scale' | 'plus'
  | 'play' | 'globe' | 'phone' | 'logout' | 'printer'
  | 'download' | 'tower' | 'triangulate' | 'car' | 'clock'
  | 'pause' | 'stop' | 'doc' | 'building' | 'monitor'
  | 'snow' | 'bug' | 'chain' | 'link' | 'mic'
  | 'battery' | 'signal' | 'x';

interface IconProps {
  name: IconName;
  size?: number;
  color?: string;
  style?: CSSProperties;
  className?: string;
}

const STROKE_DEFAULTS = {
  stroke: 'currentColor',
  strokeWidth: 1.5,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  fill: 'none',
};

/** Lookup: icon name → JSX path children */
const PATHS: Record<IconName, JSX.Element> = {
  satellite: <>
    <path d="M5 13a7 7 0 0 1 7 7"/><path d="M5 17a3 3 0 0 1 3 3"/><circle cx="5.8" cy="18.2" r="1.1"/>
    <path d="M14.5 9.5 19 5"/><path d="M12.5 7.5 8 12l4 4 4.5-4.5a3.2 3.2 0 0 0 0-4.5 3.2 3.2 0 0 0-4.5 0Z"/>
  </>,
  target: <>
    <circle cx="12" cy="12" r="7.5"/><circle cx="12" cy="12" r="3.5"/>
    <path d="M12 1.5v3M12 19.5v3M1.5 12h3M19.5 12h3"/>
  </>,
  shield: <path d="M12 3 5 6v5c0 4.4 3 7.6 7 9 4-1.4 7-4.6 7-9V6l-7-3Z"/>,
  flask: <>
    <path d="M9 3h6M10 3v6l-5.2 8.6A2 2 0 0 0 6.5 21h11a2 2 0 0 0 1.7-3L14 9V3"/>
    <path d="M7.5 15h9"/>
  </>,
  settings: <>
    <circle cx="12" cy="12" r="3"/>
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9 7 7M17 17l2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1"/>
  </>,
  broadcast: <>
    <circle cx="12" cy="12" r="2"/>
    <path d="M8.5 8.5a5 5 0 0 0 0 7M15.5 8.5a5 5 0 0 1 0 7M6 6a9 9 0 0 0 0 12M18 6a9 9 0 0 1 0 12"/>
  </>,
  map: <>
    <path d="m9 4-6 2v14l6-2 6 2 6-2V4l-6 2-6-2Z"/>
    <path d="M9 4v14M15 6v14"/>
  </>,
  zap: <path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z"/>,
  graph: <>
    <circle cx="12" cy="12" r="2.5"/><circle cx="5" cy="6" r="2"/><circle cx="19" cy="7" r="2"/><circle cx="17" cy="19" r="2"/>
    <path d="M10.3 10.6 6.3 7.2M13.9 11.2 17.2 8.3M12.9 14.2 16 17.3"/>
  </>,
  chart: <>
    <path d="M4 20h16"/>
    <rect x="6" y="11" width="3" height="7"/><rect x="11" y="7" width="3" height="11"/><rect x="16" y="4" width="3" height="14"/>
  </>,
  alert: <>
    <path d="M12 3.5 2.5 20h19L12 3.5Z"/>
    <path d="M12 10v4.5M12 17.5h.01"/>
  </>,
  lock: <>
    <rect x="5" y="11" width="14" height="9" rx="2"/>
    <path d="M8 11V8a4 4 0 0 1 8 0v3"/>
  </>,
  user: <>
    <circle cx="12" cy="8" r="3.5"/>
    <path d="M5 20a7 7 0 0 1 14 0"/>
  </>,
  key: <>
    <circle cx="8" cy="9" r="4"/>
    <path d="m11 12 8 8M16 17l2-2M18 19l2-2"/>
  </>,
  scroll: <>
    <rect x="6" y="4" width="12" height="16" rx="2"/>
    <path d="M9 8h6M9 12h6M9 16h4"/>
  </>,
  pin: <>
    <path d="M12 21s7-6 7-11a7 7 0 0 0-14 0c0 5 7 11 7 11Z"/>
    <circle cx="12" cy="10" r="2.5"/>
  </>,
  camera: <>
    <rect x="3" y="7" width="18" height="12" rx="2"/>
    <circle cx="12" cy="13" r="3.2"/>
    <path d="M8.5 7 10 5h4l1.5 2"/>
  </>,
  search: <>
    <circle cx="11" cy="11" r="6"/>
    <path d="m16 16 4 4"/>
  </>,
  refresh: <>
    <path d="M20 11a8 8 0 0 0-14-5L4 8M4 13a8 8 0 0 0 14 5l2-2"/>
    <path d="M4 4v4h4M20 20v-4h-4"/>
  </>,
  plane: <path d="M21 14.5 13.5 11V5a1.5 1.5 0 0 0-3 0v6L3 14.5v2l7.5-2v3L8 19.2V21l4-1 4 1v-1.8L13.5 17.5v-3l7.5 2v-2Z"/>,
  check: <path d="M5 12.5 10 17.5 19.5 6.5"/>,
  upload: <>
    <path d="M12 15V4M8 8l4-4 4 4"/>
    <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>
  </>,
  box: <>
    <path d="m12 3 8 4v10l-8 4-8-4V7l8-4Z"/>
    <path d="m4 7 8 4 8-4M12 11v10"/>
  </>,
  scale: <>
    <path d="M12 4v16M8 20h8"/>
    <path d="M6 7h12M12 5 6 7l-3 6h6L6 7ZM12 5l6 2 3 6h-6l3-6Z"/>
  </>,
  plus: <path d="M12 5v14M5 12h14"/>,
  play: <path d="M7 5v14l11-7-11-7Z"/>,
  globe: <>
    <circle cx="12" cy="12" r="9"/>
    <path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>
  </>,
  phone: <>
    <rect x="7" y="3" width="10" height="18" rx="2"/>
    <path d="M11 18h2"/>
  </>,
  logout: <>
    <path d="M14 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2v-2"/>
    <path d="m18 15 3-3-3-3M9 12h12"/>
  </>,
  printer: <>
    <path d="M7 8V3h10v5"/>
    <rect x="4" y="8" width="16" height="8" rx="1"/>
    <path d="M7 14h10v6H7z"/>
  </>,
  download: <>
    <path d="M12 3v13M7 11l5 5 5-5"/>
    <path d="M3 17v2a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-2"/>
  </>,
  tower: <>
    <path d="M12 8v13M8.5 21h7"/>
    <path d="M8 7.5a5.5 5.5 0 0 1 8 0M5.5 5a9 9 0 0 1 13 0"/>
    <circle cx="12" cy="7" r="1.2"/>
  </>,
  triangulate: <>
    <path d="M12 5 4 19h16L12 5Z"/>
    <circle cx="12" cy="5" r="1.3"/><circle cx="4" cy="19" r="1.3"/><circle cx="20" cy="19" r="1.3"/>
  </>,
  car: <>
    <path d="M3 13l1.6-4.8A2 2 0 0 1 6.5 7h11a2 2 0 0 1 1.9 1.4L21 13v4H3v-4Z"/>
    <path d="M6 17v1.5M18 17v1.5M3 13h18"/>
    <circle cx="7.5" cy="13.5" r="1"/><circle cx="16.5" cy="13.5" r="1"/>
  </>,
  clock: <>
    <circle cx="12" cy="12" r="8"/>
    <path d="M12 8v4l3 2"/>
  </>,
  pause: <>
    <rect x="7" y="5" width="3.5" height="14" rx="1"/>
    <rect x="13.5" y="5" width="3.5" height="14" rx="1"/>
  </>,
  stop: <rect x="6" y="6" width="12" height="12" rx="2"/>,
  doc: <>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z"/>
    <path d="M14 3v5h5M9 13h6M9 17h5"/>
  </>,
  building: <>
    <rect x="5" y="3" width="14" height="18" rx="1"/>
    <path d="M9 7h2M13 7h2M9 11h2M13 11h2M10 21v-3h4v3"/>
  </>,
  monitor: <>
    <rect x="3" y="4" width="18" height="12" rx="2"/>
    <path d="M8 20h8M12 16v4"/>
  </>,
  snow: <path d="M12 3v18M3 12h18M6 6l12 12M18 6 6 18"/>,
  bug: <>
    <rect x="8" y="7" width="8" height="11" rx="4"/>
    <path d="M6 12h12M12 7v11M9 18a3 3 0 0 0 6 0M5 9 3 8M19 9l2-1M5 15l-2 1M19 15l2 1M9.5 6 8 4M14.5 6 16 4"/>
  </>,
  chain: <path d="M9.5 13.5a3.5 3.5 0 0 0 5 0l3-3a3.5 3.5 0 0 0-5-5l-1.5 1.5M14.5 10.5a3.5 3.5 0 0 0-5 0l-3 3a3.5 3.5 0 0 0 5 5l1.5-1.5"/>,
  link: <path d="M9.5 13.5a3.5 3.5 0 0 0 5 0l3-3a3.5 3.5 0 0 0-5-5l-1.5 1.5M14.5 10.5a3.5 3.5 0 0 0-5 0l-3 3a3.5 3.5 0 0 0 5 5l1.5-1.5"/>,
  mic: <>
    <rect x="9" y="3" width="6" height="11" rx="3"/>
    <path d="M6 11a6 6 0 0 0 12 0M12 17v4M9 21h6"/>
  </>,
  battery: <>
    <rect x="3" y="8" width="16" height="9" rx="2"/>
    <path d="M21 11.5v2"/><path d="M6 10.5v4M9 10.5v4M12 10.5v4"/>
  </>,
  signal: <path d="M4 18v-2M9 18v-5M14 18v-8M19 18V5"/>,
  x: <path d="M6 6l12 12M18 6 6 18"/>,
};

export function Icon({ name, size = 18, color, style, className }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      className={className}
      style={{ color, flexShrink: 0, ...style }}
      {...STROKE_DEFAULTS}
    >
      {PATHS[name]}
    </svg>
  );
}
