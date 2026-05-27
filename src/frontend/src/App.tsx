import { useCallback, useEffect, useState } from "react";
import { LineChart } from "lucide-react";
import { SearchBar } from "./components/SearchBar";
import { StockDetail } from "./components/StockDetail";
import { StockChart } from "./components/StockChart";
import { fetchStockChart, fetchStockDetail, ApiError } from "./services/api";
import type {
  ChartPeriod,
  ChartResponse,
  SearchResult,
  StockDetail as StockDetailModel,
} from "./types";

const DEFAULT_PERIOD: ChartPeriod = "1mo";

interface DetailState {
  status: "idle" | "loading" | "ready" | "error";
  data: StockDetailModel | null;
  error?: string;
}

interface ChartState {
  status: "idle" | "loading" | "ready" | "error";
  data: ChartResponse | null;
  error?: string;
}

function App() {
  const [selected, setSelected] = useState<SearchResult | null>(null);
  const [period, setPeriod] = useState<ChartPeriod>(DEFAULT_PERIOD);
  const [detailState, setDetailState] = useState<DetailState>({ status: "idle", data: null });
  const [chartState, setChartState] = useState<ChartState>({ status: "idle", data: null });

  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    setDetailState({ status: "loading", data: null });
    fetchStockDetail(selected.symbol, controller.signal)
      .then((data) => setDetailState({ status: "ready", data }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        const message = error instanceof ApiError ? error.message : "상세 정보를 불러오지 못했습니다.";
        setDetailState({ status: "error", data: null, error: message });
      });
    return () => controller.abort();
  }, [selected]);

  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    setChartState({ status: "loading", data: null });
    fetchStockChart(selected.symbol, period, controller.signal)
      .then((data) => setChartState({ status: "ready", data }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        const message = error instanceof ApiError ? error.message : "차트 데이터를 불러오지 못했습니다.";
        setChartState({ status: "error", data: null, error: message });
      });
    return () => controller.abort();
  }, [selected, period]);

  const handleSelect = useCallback((result: SearchResult) => {
    setSelected(result);
    setPeriod(DEFAULT_PERIOD);
  }, []);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark">
            <LineChart size={20} strokeWidth={2.4} />
          </span>
          <div>
            <div>Equinox Markets</div>
            <div className="tagline">premium stock insight</div>
          </div>
        </div>
        <span className="status-banner">실시간 데이터 또는 자동 폴백</span>
      </header>

      <section className="search-section">
        <SearchBar onSelect={handleSelect} />
      </section>

      {!selected && (
        <div className="empty-state">
          <span className="glow">검색하여 종목을 선택해 보세요</span>
          <p>
            티커(AAPL, MSFT, 005930.KS) 또는 회사명을 입력하면 시가/종가/PER 등 핵심 지표와 가격·거래량 차트를 한 화면에서 확인할 수 있습니다.
          </p>
        </div>
      )}

      {selected && (
        <main className="dashboard">
          <div>
            {detailState.status === "loading" && <div className="loading-shimmer" />}
            {detailState.status === "error" && (
              <div className="message">{detailState.error}</div>
            )}
            {detailState.status === "ready" && detailState.data && (
              <StockDetail detail={detailState.data} />
            )}
          </div>
          <div>
            <StockChart
              symbol={selected.symbol}
              data={chartState.data}
              loading={chartState.status === "loading"}
              error={chartState.status === "error" ? chartState.error ?? null : null}
              period={period}
              onPeriodChange={setPeriod}
            />
          </div>
        </main>
      )}

      <footer className="footer">© Equinox Markets · 가격은 정보 제공 목적이며 투자 자문이 아닙니다.</footer>
    </div>
  );
}

export default App;
