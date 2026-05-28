import { AppSettings, ReadyResponse } from '../types';

const DEFAULT_BASE = 'http://localhost:8000';

/**
 * Read the user's persisted settings out of the Zustand `rhq_store`
 * key. Zustand persist wraps state under a `state` field, so a naive
 * `JSON.parse` returns the wrapper — we have to drill in.
 *
 * The store name + nesting come from `store/index.ts`; if you rename
 * the persist key, update both places together.
 */
function getSettings(): Partial<AppSettings> {
  try {
    const raw = localStorage.getItem('rhq_store');
    if (!raw) return {};
    const parsed = JSON.parse(raw) as { state?: { settings?: Partial<AppSettings> } };
    return parsed.state?.settings ?? {};
  } catch {
    return {};
  }
}

export function getBaseUrl(): string {
  return getSettings().apiBaseUrl || DEFAULT_BASE;
}

function getApiKey(): string {
  return getSettings().apiKey || '';
}

function headers(): Record<string, string> {
  const h: Record<string, string> = { 'Content-Type': 'application/json' };
  const key = getApiKey();
  if (key) h['X-API-Key'] = key;
  return h;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${getBaseUrl()}${path}`;
  const res = await fetch(url, { ...init, headers: { ...headers(), ...init?.headers } });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; version: string; providers_available: string[] }>('/health'),
  ready:  () => request<ReadyResponse>('/ready'),

  submitQuery: (body: {
    query: string;
    mode: string;
    pipeline_mode: string;
    format: string;
    options: Record<string, unknown>;
  }) =>
    request<{ query_id: string; websocket_url: string; estimated_completion_s: number; warnings: string[] }>(
      '/api/v1/query',
      { method: 'POST', body: JSON.stringify(body) },
    ),

  getStatus: (queryId: string) => request<import('../types').QueryStatus>(`/api/v1/query/${queryId}/status`),
  getResult: (queryId: string) => request<import('../types').QueryResult>(`/api/v1/query/${queryId}/result`),

  getAgents: () => request<import('../types').AgentsResponse>('/api/v1/agents'),

  getLogs: (queryId: string, params?: { level?: string; stage?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.level) qs.set('level', params.level);
    if (params?.stage) qs.set('stage', params.stage);
    if (params?.limit) qs.set('limit', String(params.limit));
    const q = qs.toString();
    return request<{ logs: Array<{ id: number; level: string; stage: string; message: string; data?: unknown; created_at: string }> }>(
      `/api/v1/logs/${queryId}${q ? `?${q}` : ''}`,
    );
  },

  createWebSocket: (queryId: string): WebSocket => {
    const base = getBaseUrl().replace(/^http/, 'ws');
    const key = getApiKey();
    return new WebSocket(`${base}/ws/${queryId}${key ? `?api_key=${encodeURIComponent(key)}` : ''}`);
  },
};
