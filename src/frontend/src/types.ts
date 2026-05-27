export type SearchResult = {
  symbol: string;
  name?: string | null;
  exchange?: string | null;
  assetType?: string | null;
  currency?: string | null;
};

export type ChartPoint = {
  date: string;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close?: number | null;
  volume?: number | null;
};

export type StockDetailResponse = {
  symbol: string;
  name?: string | null;
  exchange?: string | null;
  assetType?: string | null;
  quoteType?: string | null;
  website?: string | null;
  summary?: string | null;
  price: {
    currentPrice?: number | null;
    previousClose?: number | null;
    open?: number | null;
    dayHigh?: number | null;
    dayLow?: number | null;
    volume?: number | null;
    averageVolume?: number | null;
    marketCap?: number | null;
    fiftyTwoWeekHigh?: number | null;
    fiftyTwoWeekLow?: number | null;
    currency?: string | null;
  };
  fundamentals: {
    trailingPE?: number | null;
    forwardPE?: number | null;
    epsTrailingTwelveMonths?: number | null;
    dividendYield?: number | null;
    beta?: number | null;
    sector?: string | null;
    industry?: string | null;
  };
  etf: {
    expenseRatio?: number | null;
    category?: string | null;
    fundFamily?: string | null;
    totalAssets?: number | null;
    leverage?: string | null;
  };
  chart: ChartPoint[];
  period: ChartPeriod;
  provider: {
    name: string;
    fetchedAt: string;
    delayed: boolean;
    note: string;
  };
};

export type ChartPeriod = '1d' | '1mo' | '6mo' | '1y' | '5y';
