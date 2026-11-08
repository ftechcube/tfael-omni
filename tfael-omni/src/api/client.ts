// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — API Client with Bearer token injection & ETag support
// ═══════════════════════════════════════════════════════════════════════

type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'DELETE';

interface FetchOptions {
  method?: HttpMethod;
  body?: unknown;
  headers?: Record<string, string>;
  /** Pass previous ETag for conditional GET */
  etag?: string;
  /** Skip auth header (for login) */
  noAuth?: boolean;
}

interface ApiResult<T> {
  data: T;
  status: number;
  etag?: string;
  notModified: boolean;
}

// Token storage — will be managed by AuthContext
let _token: string | null = null;
let _onUnauthorized: (() => void) | null = null;

export function setApiToken(token: string | null) {
  _token = token;
}

export function setOnUnauthorized(cb: () => void) {
  _onUnauthorized = cb;
}

export function getApiToken(): string | null {
  return _token;
}

/**
 * Core fetch wrapper.
 * - Injects Bearer token on all authenticated requests
 * - Handles 304 Not Modified with ETag
 * - Auto-triggers logout on 401/403
 * - Masquerades server as nginx/1.24.0 (server-side)
 */
export async function apiFetch<T = unknown>(
  endpoint: string,
  options: FetchOptions = {}
): Promise<ApiResult<T>> {
  const { method = 'GET', body, headers = {}, etag, noAuth } = options;

  const reqHeaders: Record<string, string> = {
    ...headers,
  };

  // Auth injection
  if (!noAuth && _token) {
    reqHeaders['Authorization'] = `Bearer ${_token}`;
  }

  // JSON body
  if (body !== undefined) {
    reqHeaders['Content-Type'] = 'application/json';
  }

  // Conditional GET with ETag
  if (etag) {
    reqHeaders['If-None-Match'] = etag;
  }

  const res = await fetch(endpoint, {
    method,
    headers: reqHeaders,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  // 304 Not Modified — data unchanged
  if (res.status === 304) {
    return {
      data: undefined as unknown as T,
      status: 304,
      etag: res.headers.get('ETag') || etag,
      notModified: true,
    };
  }

  // 401/403 — session expired or forbidden
  if (res.status === 401 || res.status === 403) {
    _onUnauthorized?.();
    throw new ApiError(res.status, 'Sesi berakhir. Silakan login kembali.');
  }

  // Parse JSON
  const responseEtag = res.headers.get('ETag') || undefined;

  if (!res.ok) {
    let errorMsg = `HTTP ${res.status}`;
    try {
      const errBody = await res.json();
      errorMsg = errBody.error || errBody.message || errorMsg;
    } catch {
      // non-JSON error body
    }
    throw new ApiError(res.status, errorMsg);
  }

  // Blob response (for exports)
  const contentType = res.headers.get('Content-Type') || '';
  if (contentType.includes('application/octet-stream') || contentType.includes('application/json') === false) {
    // Check if it's actually JSON
    const text = await res.text();
    try {
      const data = JSON.parse(text) as T;
      return { data, status: res.status, etag: responseEtag, notModified: false };
    } catch {
      // Not JSON — return as-is (will need special handling)
      return { data: text as unknown as T, status: res.status, etag: responseEtag, notModified: false };
    }
  }

  const data = await res.json() as T;
  return { data, status: res.status, etag: responseEtag, notModified: false };
}

/** Convenience: POST with JSON body */
export function apiPost<T = unknown>(endpoint: string, body: unknown, opts?: Omit<FetchOptions, 'method' | 'body'>) {
  return apiFetch<T>(endpoint, { ...opts, method: 'POST', body });
}

/** Convenience: PATCH */
export function apiPatch<T = unknown>(endpoint: string, body: unknown, opts?: Omit<FetchOptions, 'method' | 'body'>) {
  return apiFetch<T>(endpoint, { ...opts, method: 'PATCH', body });
}

/** Convenience: DELETE */
export function apiDelete<T = unknown>(endpoint: string, opts?: Omit<FetchOptions, 'method'>) {
  return apiFetch<T>(endpoint, { ...opts, method: 'DELETE' });
}

/** Typed API error */
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}
