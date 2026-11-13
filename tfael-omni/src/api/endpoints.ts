// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — All API Endpoint Functions
// Organized by workspace / module
//
// NOTE: All functions (except fetchOverview which needs etag/notModified)
// unwrap ApiResult and return the JSON data directly so callers can do:
//   const res = await adminListUsers();
//   if (res.ok) ...
// ═══════════════════════════════════════════════════════════════════════

import { apiFetch, apiPost, apiPatch, apiDelete } from './client';
import type {
  OverviewData, GeoConversion, TriangulationResult, CellLocateResult,
  ForcePingResult, CctvDetectResult, AnprResult,
  OsintSearchResult, OsintEmailHeaderResult, OsintMetadataResult,
  ForensicEvidence, AdminUser, RolePermission,
  AuditEntry, GraphNode, GraphEdge, GraphStatsResponse,
  CentralityResult, CommunityResult, ShortestPathResult,
  ThreatScoreResult, AttackPathResult, TargetProfileResult,
  SoarPlaybookRequest, ApiResponse, CctvCamera, KGNode, KGEdge,
} from '@/types/api';

// ── Overview (keeps full ApiResult for ETag / 304 support) ─────────
export function fetchOverview(etag?: string) {
  return apiFetch<OverviewData>('/api/v2/overview', { etag });
}

export function fetchExport() {
  return apiFetch<Blob>('/api/v2/export').then(r => r.data);
}

// ── C4ISR ───────────────────────────────────────────────────────────
export function geoConvert(lat: number, lon: number) {
  return apiFetch<GeoConversion>(`/api/v2/geo/convert?lat=${lat}&lon=${lon}`).then(r => r.data);
}

export function forcePing(unitId: string, spoofAttack = false) {
  return apiPost<ForcePingResult>('/api/v2/c2/force-ping', {
    unit_id: unitId,
    spoof_attack: spoofAttack,
  }).then(r => r.data);
}

export function triangulate(unitId: string) {
  return apiPost<TriangulationResult>('/api/v2/telemetry/triangulate', {
    unit_id: unitId,
  }).then(r => r.data);
}

export function cellLocate(data: {
  radio: string;
  mcc: number;
  mnc: number;
  cells: Array<{ lac: number; cid: number; signal?: number }>;
  attach_unit_id?: string;
}) {
  return apiPost<CellLocateResult>('/api/v2/telemetry/cell-locate', data).then(r => r.data);
}

export function importGpx(gpxData: string, name: string) {
  return apiPost<ApiResponse & { name?: string; num_points?: number; total_km?: number }>(
    '/api/v2/routes/import', { gpx: gpxData, name }).then(r => r.data);
}

export function clearRoutes() {
  return apiPost<ApiResponse>('/api/v2/routes/clear', {}).then(r => r.data);
}

export function sendOffgridPacket(channel: string, rawPacket: string) {
  return apiPost<ApiResponse>('/api/v2/telemetry/offgrid', {
    channel, raw_packet: rawPacket,
  }).then(r => r.data);
}

export function addAnnotation(data: { lat: number; lon: number; label: string; color?: string }) {
  return apiPost<ApiResponse>('/api/v2/annotations/add', data).then(r => r.data);
}

export function deleteAnnotation(id: string) {
  return apiPost<ApiResponse>('/api/v2/annotations/delete', { id }).then(r => r.data);
}

export function clearAnnotations(category?: string) {
  return apiPost<ApiResponse>(category ? '/api/v2/annotations/clear' : '/api/v2/annotations/clear-all',
    category ? { category } : {}).then(r => r.data);
}

export function fetchCctvList() {
  return apiFetch<{ ok: boolean; cams: CctvCamera[] }>('/api/v2/vision/cctv-list').then(r => r.data);
}

export function cctvDetect(streamUrl: string) {
  return apiPost<CctvDetectResult>('/api/v2/vision/cctv-detect', { stream_url: streamUrl }).then(r => r.data);
}

export function cctvSweep() {
  return apiFetch<ApiResponse & { cams?: Array<{ name: string; location: string; lat: number | null; lon: number | null; vehicles: number | null; level: string }> }>('/api/v2/vision/cctv-sweep').then(r => r.data);
}

export function detectVision(imageB64: string) {
  return apiPost<ApiResponse & { detections?: Array<{ label: string; confidence: number }> }>(
    '/api/v2/vision/detect', { image_b64: imageB64 }).then(r => r.data);
}

export function anprCctv(streamUrl: string) {
  return apiPost<AnprResult>('/api/v2/vision/anpr-cctv', { stream_url: streamUrl }).then(r => r.data);
}

export function anprImage(imageB64: string) {
  return apiPost<AnprResult>('/api/v2/vision/anpr-image', { image_b64: imageB64 }).then(r => r.data);
}

export function liveDevice(data: Record<string, unknown>) {
  return apiPost<ApiResponse>('/api/v2/telemetry/live-device', data).then(r => r.data);
}

export function hostGeoip() {
  return apiFetch<ApiResponse & { lat?: number; lon?: number; city?: string; isp?: string; ip?: string }>(
    '/api/v2/telemetry/host-geoip').then(r => r.data);
}

export function smsGateway(data: Record<string, unknown>) {
  return apiPost<ApiResponse>('/api/v2/sms-gateway', data).then(r => r.data);
}

// ── OSINT ───────────────────────────────────────────────────────────
export function osintSearch(query: string) {
  return apiPost<OsintSearchResult>('/api/v2/osint/search', { query }).then(r => r.data);
}

export function osintUsername(username: string) {
  return apiPost<OsintSearchResult>('/api/v2/osint/username', { username }).then(r => r.data);
}

export function osintEmail(email: string) {
  return apiPost<OsintSearchResult>('/api/v2/osint/email', { email }).then(r => r.data);
}

export function osintDomain(domain: string) {
  return apiPost<OsintSearchResult>('/api/v2/osint/domain', { domain }).then(r => r.data);
}

export function osintIp(ip: string) {
  return apiPost<OsintSearchResult>('/api/v2/osint/ip', { ip }).then(r => r.data);
}

export function osintPhone(phone: string) {
  return apiPost<OsintSearchResult>('/api/v2/osint/phone', { phone }).then(r => r.data);
}

export function osintGraph(osintResult: OsintSearchResult) {
  return apiPost<ApiResponse & { nodes?: KGNode[]; edges?: KGEdge[] }>(
    '/api/v2/osint/graph', { osint_result: osintResult }).then(r => r.data);
}

export function osintEmailHeader(rawHeader: string) {
  return apiPost<OsintEmailHeaderResult>('/api/v2/osint/email-header', { raw_header: rawHeader }).then(r => r.data);
}

export function osintMetadata(dataB64: string, filename: string) {
  return apiPost<OsintMetadataResult>('/api/v2/osint/metadata', { data_b64: dataB64, filename }).then(r => r.data);
}

export function osintSaveToProfile(targetId: string, scannerData: OsintSearchResult, graphData?: { nodes: KGNode[]; edges: KGEdge[] } | null) {
  return apiPost<ApiResponse>('/api/v2/osint/save-to-profile', {
    target_id: targetId, scanner_data: scannerData, graph_data: graphData ?? null,
  }).then(r => r.data);
}

// ── Targets ─────────────────────────────────────────────────────────
export function createTarget(data: unknown) {
  return apiPost<ApiResponse>('/api/v2/targets/recon', data).then(r => r.data);
}

export function reconStatus(jobId: string) {
  return apiFetch<ApiResponse>(`/api/v2/targets/recon/status?job_id=${jobId}`).then(r => r.data);
}

export function deleteTarget(targetId: string) {
  return apiDelete<ApiResponse>(`/api/v2/targets/${targetId}`).then(r => r.data);
}

export function patchTarget(targetId: string, data: { code_name: string }) {
  return apiPatch<ApiResponse>(`/api/v2/targets/${targetId}`, data).then(r => r.data);
}

// ── Intelligence Graph ──────────────────────────────────────────────
export function fetchLinkGraph() {
  return apiFetch<{ ok: boolean; nodes: GraphNode[]; edges: GraphEdge[] }>('/api/v2/link-graph').then(r => r.data);
}

export function fetchGraphStats() {
  return apiFetch<GraphStatsResponse>('/api/v2/graph/stats').then(r => r.data);
}

export function graphNeighborhood(nodeId: string, maxHops = 2) {
  return apiPost<ApiResponse>('/api/v2/graph/neighborhood', { node_id: nodeId, max_hops: maxHops }).then(r => r.data);
}

export function graphShortestPath(nodeA: string, nodeB: string) {
  return apiPost<ShortestPathResult>('/api/v2/graph/shortest-path', { node_a: nodeA, node_b: nodeB }).then(r => r.data);
}

export function graphCentrality(topN = 20) {
  return apiPost<CentralityResult>('/api/v2/graph/centrality', { top_n: topN }).then(r => r.data);
}

export function graphCommunities() {
  return apiPost<CommunityResult>('/api/v2/graph/communities', {}).then(r => r.data);
}

export function graphTemporal(hours = 24) {
  return apiPost<ApiResponse>('/api/v2/graph/temporal', { hours }).then(r => r.data);
}

export function graphShared(minTargets = 2) {
  return apiPost<ApiResponse>('/api/v2/graph/shared', { min_targets: minTargets }).then(r => r.data);
}

export function graphRebuild() {
  return apiPost<ApiResponse>('/api/v2/graph/rebuild', {}).then(r => r.data);
}

export function graphThreatScores(topN = 30) {
  return apiPost<ThreatScoreResult>('/api/v2/graph/threat-scores', { top_n: topN }).then(r => r.data);
}

export function graphMultiCentrality(topN = 20) {
  return apiPost<ApiResponse>('/api/v2/graph/multi-centrality', { top_n: topN }).then(r => r.data);
}

export function graphAttackPaths(targetId: string, maxPaths = 10, maxDepth = 6) {
  return apiPost<AttackPathResult>('/api/v2/graph/attack-paths', {
    target_id: targetId, max_paths: maxPaths, max_depth: maxDepth,
  }).then(r => r.data);
}

export function graphTemporalPatterns(hours = 168) {
  return apiPost<ApiResponse>('/api/v2/graph/temporal-patterns', { hours }).then(r => r.data);
}

export function graphPredictLinks(topN = 20, minCommon = 2) {
  return apiPost<ApiResponse>('/api/v2/graph/predict-links', { top_n: topN, min_common: minCommon }).then(r => r.data);
}

export function graphTargetProfile(targetId: string) {
  return apiPost<TargetProfileResult>('/api/v2/graph/target-profile', { target_id: targetId }).then(r => r.data);
}

// ── SIEM ────────────────────────────────────────────────────────────
export function simulateImpossibleTravel() {
  return apiPost<ApiResponse>('/api/v2/siem/simulate-impossible-travel', {}).then(r => r.data);
}

export function runSoarPlaybook(data: SoarPlaybookRequest) {
  return apiPost<ApiResponse>('/api/v2/siem/soar', data).then(r => r.data);
}

// ── DFIR ────────────────────────────────────────────────────────────
export function forensicsIngest(data: unknown) {
  return apiPost<{ ok: boolean; evidence: ForensicEvidence }>('/api/v2/forensics/ingest', data).then(r => r.data);
}

export function forensicsVerifyChain() {
  return apiFetch<ApiResponse>('/api/v2/forensics/verify-chain').then(r => r.data);
}

// ── Admin ───────────────────────────────────────────────────────────
export function adminListUsers() {
  return apiFetch<{ ok: boolean; users: AdminUser[]; rows?: AdminUser[] }>('/api/v2/admin/users').then(r => r.data);
}

export function adminCreateUser(data: {
  username: string; full_name?: string; rank_title?: string; role: string;
}) {
  return apiPost<ApiResponse & { user_id?: string; temp_password?: string }>(
    '/api/v2/admin/users', data).then(r => r.data);
}

export function adminUpdateUser(data: {
  user_id: string; role?: string; status?: string;
  full_name?: string; rank_title?: string;
}) {
  return apiPost<ApiResponse>('/api/v2/admin/users/update', data).then(r => r.data);
}

export function adminResetPassword(userId: string) {
  return apiPost<ApiResponse & { temp_password?: string }>(
    '/api/v2/admin/users/reset-password', { user_id: userId }).then(r => r.data);
}

export function adminDeleteUser(userId: string) {
  return apiPost<ApiResponse>('/api/v2/admin/users/delete', { user_id: userId }).then(r => r.data);
}

export function adminListRoles() {
  return apiFetch<{
    ok: boolean;
    roles: string[];
    permissions: Array<[string, string]>;
    matrix: Record<string, Record<string, boolean>>;
  }>('/api/v2/admin/roles').then(r => r.data);
}

export function adminUpdateRole(role: string, perm: string, allowed: boolean) {
  return apiPost<ApiResponse>('/api/v2/admin/roles/update', { role, perm, allowed }).then(r => r.data);
}

export function adminAuditLog(params: { limit?: number; category?: string; actor?: string; result?: string } = {}) {
  const qs = new URLSearchParams();
  if (params.limit) qs.set('limit', String(params.limit));
  if (params.category) qs.set('category', params.category);
  if (params.actor) qs.set('actor', params.actor);
  if (params.result) qs.set('result', params.result);
  // Backend returns `rows`, not `entries`
  return apiFetch<{ ok: boolean; rows?: AuditEntry[]; entries?: AuditEntry[] }>(`/api/v2/admin/audit?${qs}`).then(r => r.data);
}

export function adminVerifyAuditChain() {
  return apiFetch<ApiResponse>('/api/v2/admin/audit/verify-chain').then(r => r.data);
}

// ── Cognitive Domain / BotRadar ─────────────────────────────
export interface CogAccount {
  account_id: string; platform: string; username: string;
  display_name: string; bot_score: number; bot_label: string;
  bot_confidence?: number; cluster_id: number; followers: number; following: number;
  post_count: number; account_age_days: number;
}
export interface CogDashboard {
  ok: boolean;
  summary: {
    total_accounts: number; bots: number; suspicious: number;
    low_signal: number; bot_ratio: number; network_edges: number;
  };
  top_flagged_accounts: CogAccount[];
  recent_cib_events: any[];
  top_narratives: any[];
}
export interface CogGraphData {
  ok: boolean;
  nodes: Array<{
    id: string; username: string; bot_score: number;
    bot_label: string; cluster_id: number; degree: number;
    betweenness: number;
  }>;
  edges: Array<{ source: string; target: string; relation: string; weight: number }>;
  total_nodes: number; total_edges: number; communities: number;
}
export function cogScrape(data: { platform: string; query?: string; channel?: string; max_posts?: number }) {
  return apiPost<ApiResponse & { job_id: string; posts_collected: number; accounts_found: number }>('/api/v2/cognitive/scrape', data).then(r => r.data);
}
export function cogBotDetect(data: { job_id?: string; topic?: string } = {}) {
  return apiPost<ApiResponse & { total_analyzed: number; bots_detected: number; suspicious: number; low_signal: number; top_bots: any[] }>('/api/v2/cognitive/bot-detect', data).then(r => r.data);
}
export function cogBotScore(account_id: string) {
  return apiPost<ApiResponse & { account_id: string; bot_score: number; bot_label: string; signals: Record<string, any> }>('/api/v2/cognitive/bot-score', { account_id }).then(r => r.data);
}
export function cogCibDetect(data: { window_seconds?: number; min_accounts?: number; min_similarity?: number; job_id?: string } = {}) {
  return apiPost<ApiResponse & { events: any[]; total_events: number }>('/api/v2/cognitive/cib-detect', data).then(r => r.data);
}
export function cogAmplification(data: { min_accounts?: number; job_id?: string } = {}) {
  return apiPost<ApiResponse & { narratives: any[]; total_narratives: number }>('/api/v2/cognitive/amplification', data).then(r => r.data);
}
export function cogNetworkGraph(data: { job_id?: string } = {}) {
  return apiPost<CogGraphData>('/api/v2/cognitive/network-graph', data).then(r => r.data);
}
export function cogNarrative(data: { topic: string; job_id?: string }) {
  return apiPost<ApiResponse & { topic: string; posts_found: number; unique_accounts: number; avg_hoax_score: number; classification: string; spread_velocity_per_hour: number; top_spreaders: any[]; top_hashtags: any[]; hoax_indicators: any[] }>('/api/v2/cognitive/narrative', data).then(r => r.data);
}
export function cogSurge(data: { age_threshold_days?: number; min_accounts?: number; job_id?: string } = {}) {
  return apiPost<ApiResponse & { surge_detected: boolean; total_accounts: number; new_accounts: number; new_account_ratio: number; severity: string; new_account_list: any[] }>('/api/v2/cognitive/surge', data).then(r => r.data);
}
export function cogFullPipeline(data: { platform: string; query?: string; channel?: string; max_posts?: number; cib_window_sec?: number; min_cib_accounts?: number }) {
  return apiPost<ApiResponse & { job_id: string; pipeline_stages: Record<string, any>; summary: any }>('/api/v2/cognitive/full-pipeline', data).then(r => r.data);
}
export function cogSeedDemo(data: { force?: boolean } = {}) {
  return apiPost<ApiResponse & { seeded: boolean; accounts?: number; posts?: number; job_id?: string }>('/api/v2/cognitive/seed-demo', data).then(r => r.data);
}
export function cogTwitterCookieTest() {
  return apiPost<ApiResponse & { status: string; detail: string }>('/api/v2/cognitive/twitter-cookie-test', {}).then(r => r.data);
}
export function cogDashboard(data: { job_id?: string } = {}) {
  return apiPost<CogDashboard>('/api/v2/cognitive/dashboard', data).then(r => r.data);
}
export function cogAccountDetail(account_id: string) {
  return apiPost<ApiResponse & { account: CogAccount; posts: any[]; connections: any[]; signals: Record<string, any> }>('/api/v2/cognitive/account-detail', { account_id }).then(r => r.data);
}
export function cogIngestGraph(data: { job_id?: string } = {}) {
  return apiPost<ApiResponse & { ingested: { nodes: number; edges: number; alerts: number } }>('/api/v2/cognitive/ingest-graph', data).then(r => r.data);
}
