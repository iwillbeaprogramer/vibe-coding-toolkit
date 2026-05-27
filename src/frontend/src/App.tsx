import { AlertCircle, BarChart3, RefreshCw, Search } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { getStockDetail } from './api';
import Disclaimers from './components/Disclaimers';
import SearchBar from './components/SearchBar';
import StockDetail from './components/StockDetail';
import StockChart from './components/StockChart';
import type { ChartPeriod, StockDetailResponse } from './types';

const DEFAULT_SYMBOL = 'QLD';

export default function App() {
  const [symbol, setSymbol] = useState(DEFAULT_SYMBOL);
  const [period, setPeriod] = useState<ChartPeriod>('1mo');
  const [detail, setDetail] = useState<StockDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDetail = useCallback((nextSymbol: string, nextPeriod: ChartPeriod) => {
    const controller = new AbortController();
    setIsLoading(true);
    setError(null);
    getStockDetail(nextSymbol, nextPeriod, controller.signal)
      .then((payload) => setDetail(payload))
      .catch((reason: Error) => {
        if (reason.name !== 'AbortError') {
          setError(reason.message);
        }
      })
      .finally(() => setIsLoading(false));
    return () => controller.abort();
  }, []);

  useEffect(() => loadDetail(symbol, period), [loadDetail, period, symbol]);

  function handleSelect(nextSymbol: string) {
    const normalized = nextSymbol.trim().toUpperCase();
    if (!normalized) {
      setError('검색어를 입력해 주세요.');
      return;
    }
    setSymbol(normalized);
  }

  function handleRetry() {
    loadDetail(symbol, period);
  }

  return (
    <main className="appShell">
      <header className="topBar">
        <div className="brandBlock">
          <div className="brandIcon" aria-hidden="true">
            <BarChart3 size={22} />
          </div>
          <div>
            <p className="eyebrow">Local market workstation</p>
            <h1>Stock Insight</h1>
          </div>
        </div>
        <SearchBar onSelect={handleSelect} />
      </header>

      {error ? (
        <section className="statusBanner error" role="alert">
          <AlertCircle size={18} />
          <span>{error}</span>
          <button type="button" className="iconTextButton" onClick={handleRetry}>
            <RefreshCw size={16} />
            다시 시도
          </button>
        </section>
      ) : null}

      <section className="dashboardGrid">
        <div className="detailColumn">
          {isLoading && !detail ? <SkeletonPanel /> : <StockDetail detail={detail} isLoading={isLoading} />}
        </div>
        <div className="chartColumn">
          <StockChart
            chart={detail?.chart ?? []}
            period={period}
            onPeriodChange={setPeriod}
            isLoading={isLoading}
          />
        </div>
      </section>

      <Disclaimers provider={detail?.provider} />
    </main>
  );
}

function SkeletonPanel() {
  return (
    <section className="panel skeletonPanel" aria-label="loading detail">
      <div className="skeleton title" />
      <div className="skeleton wide" />
      <div className="metricGrid">
        {Array.from({ length: 8 }).map((_, index) => (
          <div className="metricTile skeletonTile" key={index}>
            <div className="skeleton label" />
            <div className="skeleton value" />
          </div>
        ))}
      </div>
    </section>
  );
}
