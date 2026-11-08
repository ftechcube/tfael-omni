// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Shared API Types
// ═══════════════════════════════════════════════════════════════════════

/** Standard API response envelope */
export interface ApiResponse<T = unknown> {
  ok: boolean;
  error?: string;
  data?: T;
}

// ── Auth ────────────────────────────────────────────────────────────
export interface LoginRequest {
  username: string;
  password: string;
}

export interface UserInfo {
  user_id: string;
  username: string;
  full_name: string;
  rank_title: string;
  role: string;
  must_reset: boolean;
}

export interface LoginResponse {
  ok: boolean;
  token: string;
  user: UserInfo;
  permissions: Record<string, boolean>;
  error?: string;
}

export interface SessionInfo {
  ok: boolean;
  user: UserInfo;
  permissions: Record<string, boolean>;
}

export type Permission =
  | 'run_c2'
  | 'run_recon'
  | 'view_siem'
  | 'run_soar'
  | 'manage_forensics'
  | 'manage_users'
  | 'manage_config'
  | 'view_audit'
  | 'view_c4isr'
  | 'print_bap';

// ── Overview / Dashboard ────────────────────────────────────────────
export interface Geofence {
  id: string;
  name: string;
  color: string;
  points: [number, number][];
}

export interface BtsTower {
  tower_id: string;
  operator: string;
  lat: number;
  lon: number;
  radius_m: number;
}

export interface ImpossibleTravel {
  source_ip: string;
  from_city: string;
  to_city: string;
  from_lat: number;
  from_lon: number;
  to_lat: number;
  to_lon: number;
  distance_km: number;
  time_hours: number;
}

export interface Annotation {
  id: string;
  type: 'marker' | 'circle';
  lat: number;
  lon: number;
  label?: string;
  color?: string;
  radius?: number;
  author?: string;
  created_at?: string;
}

export interface ActiveRoute {
  name: string;
  total_km: number;
  num_points: number;
  points: [number, number][];
}

export interface CctvHeatmapEntry {
  name: string;
  location: string;
  lat: number | null;
  lon: number | null;
  vehicles: number | null;
  level: 'LANCAR' | 'SEDANG' | 'PADAT' | 'OFFLINE';
}

export interface OverviewData {
  ok: boolean;
  targets: Target[];
  targets_total: number;
  siem_alerts: SiemAlert[];
  units: Unit[];
  recent_scans: RecentScan[];
  forensic_evidences: ForensicEvidence[];
  graph_stats: { nodes: number; edges: number };
  geofences: Geofence[];
  bts_towers: BtsTower[];
  impossible_travel: ImpossibleTravel[];
  annotations: Annotation[];
  active_route: ActiveRoute | null;
  bts_tower_count: number;
  lan_ip?: string;
}

export interface Target {
  target_id: string;
  code_name: string;
  risk_score: number;
  risk_level: string;
  last_seen?: string;
  lat?: number;
  lon?: number;
  location_source?: string;
  geoip_accuracy_km?: number;
  sources?: string[];
  scan_count?: number;
  created_at?: string;
  plate?: string;
}

export type UnitStatusColor = 'GREEN' | 'YELLOW' | 'BLUE' | 'RED';

export interface Unit {
  unit_id: string;
  callsign: string;
  name: string;
  role: string;
  status_color: UnitStatusColor;
  channel: string;
  lat: number;
  lon: number;
  alt_m: number;
  speed_kmh: number;
  battery_pct: number;
  signal_dbm: number;
  last_seen: string;
  mcc: number;
  mnc: number;
  lac: number;
  cid: number;
  bts_radius_m: number;
  trail: [number, number][];
}

// ── C4ISR Responses ────────────────────────────────────────────────
export interface ForcePingResult {
  ok: boolean;
  spoof_blocked?: boolean;
  verify_status?: string;
  crypto_processing_ms?: number;
  fix_source?: string;
  simulated?: boolean;
  position?: { lat: number; lon: number };
  command_packet: {
    packet_hex: string;
    hmac_tag_hex: string;
    nonce_hex: string;
    gsm_pdu_hex: string;
    udh_port?: number;
  };
  encrypted_reply: {
    wire_size_bytes: number;
    ciphertext_hex: string;
    auth_tag_hex: string;
  };
  verification_meta?: {
    received_hmac: string;
    expected_hmac: string;
  };
  siem_alert_triggered?: string;
}

export interface TriangulationResult {
  ok: boolean;
  error?: string;
  method?: string;
  mode?: string;
  num_towers?: number;
  lat?: number;
  lon?: number;
  accuracy_m?: number;
  residual_rms_m?: number;
  error_vs_truth_m?: number;
  within_accuracy?: boolean;
  ground_truth?: { lat: number; lon: number };
  model?: { ref_rssi_dbm: number; path_loss_exp: number };
  towers?: Array<{
    tower_id: string;
    operator: string;
    rssi_dbm: number;
    est_distance_m: number;
  }>;
}

export interface CellLocateResult {
  ok: boolean;
  error?: string;
  detail?: string;
  pending?: boolean;
  cached?: boolean;
  provider?: string;
  lat?: number;
  lon?: number;
  accuracy_m?: number;
  num_cells?: number;
  radio?: string;
  balance_remaining?: number;
  attached_unit_id?: string;
}

export interface CctvDetectResult {
  ok: boolean;
  error?: string;
  available?: boolean;
  count?: number;
  frame_wh?: [number, number];
  summary?: Record<string, number>;
  frame_b64?: string;
}

export interface AnprResult {
  ok: boolean;
  error?: string;
  vehicles?: number;
  plates_read?: number;
  watchlist_size?: number;
  plates?: Array<{ plate: string; watchlist_hit: boolean }>;
  hits?: Array<{
    plate: string;
    target: { code_name: string; target_id: string };
  }>;
  camera?: { name: string; lat: number | null; lon: number | null };
  frame_b64?: string;
  note?: string;
}

export interface SiemAlert {
  id: string;
  title: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  source_ip?: string;
  dest_ip?: string;
  timestamp: string;
  status?: string;
  mitre_id?: string;
  mitre_tactic?: string;
  description?: string;
  sigma_rule?: string;
  user_or_unit?: string;
  soar_action_taken?: string;
  cyber_lat?: number;
  cyber_lon?: number;
  phys_lat?: number;
  phys_lon?: number;
  distance_km?: number;
  velocity_kmh?: number;
}

export interface RecentScan {
  type: string;
  query: string;
  timestamp: string;
}

// ── OSINT ───────────────────────────────────────────────────────────
export type OsintSearchType =
  | 'username' | 'email' | 'domain' | 'ip' | 'phone'
  | 'name' | 'plate' | 'gps' | 'url';

export interface OsintSearchRequest {
  type: OsintSearchType;
  query: string;
}

/** Generic OSINT result — "data" varies by type */
export interface OsintSearchResult {
  ok: boolean;
  type: OsintSearchType;
  query: string;
  // identity fields (vary by type)
  name?: string;
  username?: string;
  email?: string;
  domain?: string;
  ip?: string;
  normalized?: string;
  input?: string;
  plate?: string;
  // username-type
  found_count?: number;
  checked?: number;
  elapsed_s?: number;
  platforms?: OsintPlatform[];
  unverified?: OsintPlatform[];
  github?: OsintGitHub;
  wayback?: OsintWayback;
  // email-type
  mail_server_provider?: string;
  has_gravatar?: boolean;
  gravatar?: string;
  format_analysis?: { is_free_provider?: boolean; is_disposable?: boolean };
  mx_records?: string[];
  domain_ips?: string[];
  username_candidates?: string[];
  crt_sh_subdomains?: string[];
  breach?: OsintBreach;
  whois?: OsintWhois;
  // domain-type
  resolved_ips?: string[];
  http_status?: number;
  ip_info?: Array<{ geo?: OsintGeo; reverse_dns?: string }>;
  open_ports?: Array<{ port: number; service: string }>;
  tech_hints?: string[];
  ssl_cert?: { issuer?: { organizationName?: string; commonName?: string }; not_after?: string; san?: string[]; error?: string };
  subdomains_crtsh?: string[];
  subdomain_count?: number;
  dns?: Record<string, string[]>;
  // ip-type
  geo?: OsintGeo;
  reverse_dns?: string;
  reputation?: OsintReputation;
  http_80?: OsintHttpProbe;
  http_443?: OsintHttpProbe;
  http_8080?: OsintHttpProbe;
  http_8443?: OsintHttpProbe;
  // phone-type
  format_e164?: string;
  format_local?: string;
  country?: string;
  country_code?: string;
  local_number?: string;
  detected_carrier?: string;
  possible_carriers?: string[];
  // name-type
  parts?: { first?: string; last?: string };
  dorks?: Array<{ label: string; query: string; url: string }>;
  gravatar_hits?: Array<{ email: string; gravatar_url: string }>;
  email_permutations?: string[];
  // plate-type
  provinsi?: string;
  wilayah?: string;
  sub_wilayah?: string;
  prefix?: string;
  number?: string;
  suffix?: string;
  kendaraan?: string;
  // gps-type
  lat?: number;
  lon?: number;
  display_name?: string;
  state?: string;
  city?: string;
  suburb?: string;
  postcode?: string;
  road?: string;
  // url-type
  status?: number;
  final_url?: string;
  redirect_count?: number;
  redirects?: Array<{ status: number; url: string }>;
  tech?: string[];
  security?: Record<string, boolean>;
  // catch-all
  [key: string]: unknown;
}

export interface OsintPlatform {
  platform: string;
  url: string;
  found?: boolean;
  confidence?: string;
}

export interface OsintGeo {
  country?: string;
  regionName?: string;
  city?: string;
  isp?: string;
  org?: string;
  as?: string;
  lat?: number;
  lon?: number;
  proxy?: boolean;
  hosting?: boolean;
}

export interface OsintHttpProbe {
  status?: number;
  tech?: string[];
}

export interface OsintReputation {
  score?: number;
  source?: string;
  reports?: number;
  country?: string;
  isp?: string;
  classification?: string;
  usage_type?: string;
  is_tor?: boolean;
  noise?: boolean;
  last_reported?: string;
  note?: string;
}

export interface OsintGitHub {
  ok: boolean;
  username?: string;
  profile?: {
    name?: string;
    bio?: string;
    avatar_url?: string;
    html_url?: string;
    followers?: number;
    public_repos?: number;
    location?: string;
  };
  emails?: string[];
  repos?: Array<{ name: string; url: string; stars?: number; description?: string }>;
}

export interface OsintWayback {
  ok: boolean;
  first_seen?: string;
  last_seen?: string;
  total?: number;
  snapshots?: Array<{ timestamp: string; status: string; url: string }>;
}

export interface OsintBreach {
  ok?: boolean;
  breach_count?: number;
  breaches?: Array<{
    name: string;
    domain?: string;
    date?: string;
    count?: number;
    data_classes?: string[];
  }>;
  pastes?: Array<{ source: string; date?: string }>;
  has_gravatar?: boolean;
  note?: string;
}

export interface OsintWhois {
  ok: boolean;
  parsed?: Record<string, unknown>;
  raw_snippet?: string;
}

export interface OsintEmailHeaderResult {
  ok: boolean;
  error?: string;
  from?: string;
  to?: string;
  subject?: string;
  date?: string;
  spf?: string;
  dkim?: string;
  dmarc?: string;
  hop_count?: number;
  hops?: Array<{ hop: number; from?: string; by?: string; ips?: string[] }>;
  ip_details?: Array<{ ip: string; country?: string; city?: string; isp?: string }>;
}

export interface OsintMetadataResult {
  ok: boolean;
  error?: string;
  format?: string;
  gps?: { lat: number; lon: number; alt_m?: number; date?: string };
  tags?: Record<string, unknown>;
  note?: string;
}

/** Scan history entry (stored in localStorage) */
export interface ScanHistoryEntry {
  ts: string;
  type: OsintSearchType;
  query: string;
  ok: boolean;
  data: OsintSearchResult;
}

// ── Knowledge Graph (per-scan) ──────────────────────────────────────
export interface KGNode {
  id: string;
  label: string;
  type: string;
  data?: { url?: string; [key: string]: unknown };
  meta?: Record<string, unknown>;
  // D3 simulation props
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
}

export interface KGEdge {
  source: string | KGNode;
  target: string | KGNode;
  rel?: string;
  label?: string;
}

// ── Intelligence Graph (unified) ────────────────────────────────────
export interface GraphNode {
  id: string;
  label: string;
  type: string;
  meta?: {
    risk_score?: number;
    risk_level?: string;
    lat?: number;
    lon?: number;
    [key: string]: unknown;
  };
  properties?: Record<string, unknown>;
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
}

export interface GraphEdge {
  source: string | GraphNode;
  target: string | GraphNode;
  rel?: string;
  last_seen?: string;
  rel_type?: string;
}

export interface GraphStatsResponse {
  ok: boolean;
  total_nodes: number;
  total_edges: number;
  total_targets?: number;
  top_types?: Array<{ type: string; count: number }>;
  node_types?: Record<string, number>;
}

export interface CentralityResult {
  ok: boolean;
  top: Array<{ id: string; centrality: number }>;
}

export interface CommunityResult {
  ok: boolean;
  total_communities: number;
  communities: Array<{ members: string[] }>;
}

export interface ShortestPathResult {
  ok: boolean;
  found: boolean;
  hops: number;
  path: string[];
  edges?: Array<{ source: string; target: string }>;
}

export interface ThreatScoreResult {
  ok: boolean;
  total_scored: number;
  tier_breakdown: Record<string, number>;
  scored: Array<{
    node_id: string;
    label?: string;
    type?: string;
    score: number;
    tier: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
    factors?: {
      degree_norm?: number;
      type_weight?: number;
      bridge_score?: number;
    };
  }>;
}

export interface AttackPathResult {
  ok: boolean;
  paths: Array<{
    path: string[];
    weakness_score: number;
    vector?: string;
  }>;
  pivot_points: Array<{ node_id: string; frequency: number }>;
  attack_vectors: Record<string, number>;
  assessment: { risk_level: string };
}

export interface TargetProfileResult {
  ok: boolean;
  profile_grade: string;
  profile_score: number;
  scores: {
    exposure_score?: number;
    digital_score?: number;
    network_score?: number;
    opsec_score?: number;
    opsec_grade?: string;
  };
  infrastructure: Record<string, unknown[]>;
  digital_footprint: Record<string, unknown[]>;
  physical_indicators: Record<string, unknown[]>;
  intelligence_gaps: string[];
}

// ── SIEM ────────────────────────────────────────────────────────────
export interface HostTelemetry {
  hostname: string;
  os: string;
  uptime: number;
  cpu_pct: number;
  mem_pct: number;
  disk_pct: number;
  net_conns: number;
  processes: number;
  geo?: { city: string; country: string; lat: number; lon: number };
}

export interface SoarPlaybookRequest {
  action: string;
  alert_id: string;
  params?: Record<string, unknown>;
}

// ── DFIR ────────────────────────────────────────────────────────────
export interface ForensicEvidence {
  id: string;
  filename: string;
  type: string;
  sha256: string;
  size: number;
  ingested_at: string;
  analysis?: {
    ela?: unknown;
    yara?: YaraMatch[];
    sqlite_tables?: string[];
    pcap_summary?: unknown;
  };
}

export interface YaraMatch {
  rule: string;
  severity?: string;
  desc?: string;
  engine?: string;
  meta?: Record<string, string>;
  strings?: Array<{ offset: number; identifier: string; data: string }>;
}

export interface ChainOfCustody {
  hash: string;
  prev_hash: string;
  timestamp: string;
  action: string;
  actor: string;
}

// ── Admin ───────────────────────────────────────────────────────────
export interface AdminUser {
  user_id: string;
  username: string;
  role: string;
  active: boolean;
  created_at: string;
  last_login?: string;
  full_name?: string;
  rank_title?: string;
}

export interface RolePermission {
  role: string;
  permissions: Record<string, boolean>;
}

export interface AuditEntry {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  category: string;
  result: string;
  detail?: string;
}

// ── C4ISR ───────────────────────────────────────────────────────────
export interface GeoConversion {
  mgrs: string;
  utm: string;
  dms: string;
  decimal: { lat: number; lon: number };
}

export interface TriangulationResult {
  ok: boolean;
  estimated_lat: number;
  estimated_lon: number;
  accuracy_m: number;
  method: string;
}

export interface CctvCamera {
  name: string;
  location: string;
  stream_url: string;
  lat?: number;
  lon?: number;
  status?: string;
}
