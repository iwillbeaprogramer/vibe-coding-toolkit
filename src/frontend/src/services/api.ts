import type { ChartPeriod, ChartResponse, SearchResponse, StockDetail } from "../types";

const API_BASE = (import.meta.env?.VITE_API_BASE as string | undefined) ?? "/api";

export class ApiError extends Error {
  status: number;
  code: string;
  retryable: boolean;

  constructor(status: number, code: string, message: string, retryable: boolean) {
    super(message);
    this.status = status;
    this.code = code;
    this.retryable = retryable;
  }
}

async function parseError(response: Response): Promise<ApiError> {
  let code = "unknown_error";
  let message = `요청이 실패했습니다 (HTTP ${response.status})`;
  let retryable = response.status >= 500;
  try {
    const payload = await response.json();
    const detail = payload?.detail ?? payload;
    if (detail && typeof detail === "object") {
      code = String(detail.error ?? code);
      message = String(detail.message ?? message);
      retryable = Boolean(detail.retryable ?? retryable);
    }
  } catch {
    // ignore JSON parse error, fall through with defaults
  }
  return new ApiError(response.status, code, message, retryable);
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { Accept: "application/json", ...(init?.headers ?? {}) },
    });
  } catch (error) {
    throw new ApiError(0, "network_error", "네트워크에 연결할 수 없습니다.", true);
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as T;
}

export function searchStocks(query: string, signal?: AbortSignal): Promise<SearchResponse> {
  const trimmed = query.trim();
  const params = new URLSearchParams({ q: trimmed });
  return fetchJson<SearchResponse>(`/search?${params.toString()}`, { signal });
}

export function fetchStockDetail(symbol: string, signal?: AbortSignal): Promise<StockDetail> {
  return fetchJson<StockDetail>(`/stocks/${encodeURIComponent(symbol)}`, { signal });
}

export function fetchStockChart(
  symbol: string,
  period: ChartPeriod,
  signal?: AbortSignal,
): Promise<ChartResponse> {
  const params = new URLSearchParams({ period });
  return fetchJson<ChartResponse>(
    `/stocks/${encodeURIComponent(symbol)}/chart?${params.toString()}`,
    { signal },
  );
}
