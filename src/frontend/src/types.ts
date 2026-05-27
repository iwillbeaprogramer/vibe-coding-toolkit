export interface SearchResult {
  symbol: string;
  name: string;
  exchange: string;
  currency: string;
  market: string;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  source: "live" | "mock";
}

export interface StockDetail {
  symbol: string;
  name: string;
  exchange: string | null;
  currency: string | null;
  market: string | null;
  price: number | null;
  open: number | null;
  close: number | null;
  previous_close: number | null;
  high: number | null;
  low: number | null;
  volume: number | null;
  average_volume: number | null;
  market_cap: number | null;
  pe_ratio: number | null;
  eps: number | null;
  dividend_yield: number | null;
  week_high_52: number | null;
  week_low_52: number | null;
  last_updated: string | null;
  source: "live" | "mock";
}

export interface ChartPoint {
  timestamp: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
}

export interface ChartResponse {
  symbol: string;
  period: ChartPeriod;
  interval: string;
  points: ChartPoint[];
  source: "live" | "mock";
}

export type ChartPeriod = "1d" | "5d" | "1mo" | "6mo" | "1y" | "5y";

export const CHART_PERIODS: ChartPeriod[] = ["1d", "5d", "1mo", "6mo", "1y", "5y"];
