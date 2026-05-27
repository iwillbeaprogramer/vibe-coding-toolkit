import type { ChartPeriod, SearchResult, StockDetailResponse } from './types';

async function requestJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? `요청에 실패했습니다. (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function searchSymbols(query: string, signal?: AbortSignal) {
  return requestJson<SearchResult[]>(`/api/search?q=${encodeURIComponent(query)}`, signal);
}

export function getStockDetail(symbol: string, period: ChartPeriod, signal?: AbortSignal) {
  return requestJson<StockDetailResponse>(
    `/api/stock/${encodeURIComponent(symbol)}?period=${period}`,
    signal
  );
}
