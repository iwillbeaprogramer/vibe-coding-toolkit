import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../../src/frontend/src/App';
import SearchBar from '../../src/frontend/src/components/SearchBar';

const detailPayload = {
  symbol: 'QLD',
  name: 'ProShares Ultra QQQ',
  exchange: 'NYSEARCA',
  assetType: 'ETF',
  quoteType: 'ETF',
  website: null,
  summary: null,
  price: {
    currentPrice: 102.4,
    previousClose: 101,
    open: 100,
    dayHigh: 103,
    dayLow: 99,
    volume: 1200,
    averageVolume: 2200,
    marketCap: null,
    fiftyTwoWeekHigh: 120,
    fiftyTwoWeekLow: 70,
    currency: 'USD'
  },
  fundamentals: {
    trailingPE: null,
    forwardPE: null,
    epsTrailingTwelveMonths: null,
    dividendYield: null,
    beta: null,
    sector: null,
    industry: null
  },
  etf: {
    expenseRatio: 0.0095,
    category: 'Trading Leveraged Equity',
    fundFamily: 'ProShares',
    totalAssets: 1000000,
    leverage: null
  },
  chart: [{ date: '2026-05-27', open: 100, high: 103, low: 99, close: 102.4, volume: 1200 }],
  period: '1mo',
  provider: {
    name: 'Yahoo Finance',
    fetchedAt: '2026-05-27T00:00:00.000Z',
    delayed: true,
    note: '무료 Yahoo Finance 기반 지연 시세입니다.'
  }
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('App', () => {
  it('renders loading state and loaded stock detail', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => detailPayload
    } as Response);

    render(<App />);

    expect(screen.getByLabelText('loading detail')).toBeInTheDocument();
    expect(await screen.findByText('ProShares Ultra QQQ')).toBeInTheDocument();
    expect(screen.getByText('102.4')).toBeInTheDocument();
  });

  it('renders retry action when the API fails', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({ detail: '데이터 제공자 응답 시간이 초과되었습니다.' })
    } as Response);

    render(<App />);

    expect(await screen.findByRole('button', { name: '다시 시도' })).toBeInTheDocument();
    expect(screen.getByText('데이터 제공자 응답 시간이 초과되었습니다.')).toBeInTheDocument();
  });
});

describe('SearchBar', () => {
  it('does not call autocomplete API for one character input', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => []
    } as Response);

    render(<SearchBar onSelect={vi.fn()} />);
    await userEvent.type(screen.getByLabelText('종목 검색'), 'Q');

    await waitFor(() => expect(fetchSpy).not.toHaveBeenCalled());
  });

  it('submits a direct ticker search', async () => {
    const onSelect = vi.fn();
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => []
    } as Response);

    render(<SearchBar onSelect={onSelect} />);
    await userEvent.type(screen.getByLabelText('종목 검색'), 'QLD');
    await userEvent.click(screen.getByRole('button', { name: '조회' }));

    expect(onSelect).toHaveBeenCalledWith('QLD');
  });
});
