import { useMemo } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ChartPeriod, ChartResponse } from "../types";
import { CHART_PERIODS } from "../types";

interface Props {
  data: ChartResponse | null;
  period: ChartPeriod;
  loading: boolean;
  error?: string | null;
  onPeriodChange: (period: ChartPeriod) => void;
  symbol: string;
}

interface ChartRow {
  timestamp: string;
  label: string;
  close: number | null;
  volume: number | null;
}

const PERIOD_LABELS: Record<ChartPeriod, string> = {
  "1d": "1D",
  "5d": "5D",
  "1mo": "1M",
  "6mo": "6M",
  "1y": "1Y",
  "5y": "5Y",
};

function formatTimestamp(value: string, period: ChartPeriod): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  if (period === "1d" || period === "5d") {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  if (period === "1mo" || period === "6mo") {
    return date.toLocaleDateString([], { month: "short", day: "numeric" });
  }
  return date.toLocaleDateString([], { year: "2-digit", month: "short" });
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: ChartRow }> }) {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0].payload;
  return (
    <div
      style={{
        background: "rgba(11, 14, 33, 0.92)",
        border: "1px solid rgba(255,255,255,0.1)",
        padding: "10px 14px",
        borderRadius: 12,
        fontSize: 12,
        color: "var(--text-primary)",
        boxShadow: "0 10px 30px rgba(0,0,0,0.4)",
      }}
    >
      <div style={{ color: "var(--text-secondary)", marginBottom: 4 }}>{row.label}</div>
      <div>가격: {row.close == null ? "N/A" : row.close.toFixed(2)}</div>
      <div>거래량: {row.volume == null ? "N/A" : row.volume.toLocaleString()}</div>
    </div>
  );
}

export function StockChart({ data, period, loading, error, onPeriodChange, symbol }: Props) {
  const rows = useMemo<ChartRow[]>(() => {
    if (!data) return [];
    return data.points.map((point) => ({
      timestamp: point.timestamp,
      label: formatTimestamp(point.timestamp, period),
      close: point.close,
      volume: point.volume,
    }));
  }, [data, period]);

  return (
    <section className="chart-card" aria-label={`${symbol} 차트`}>
      <header className="chart-header">
        <div>
          <div className="chart-title">{symbol} 가격 & 거래량</div>
          <div style={{ color: "var(--text-secondary)", fontSize: 12, marginTop: 4 }}>
            기간 {PERIOD_LABELS[period]} · 간격 {data?.interval ?? "—"}
          </div>
        </div>
        <div className="period-tabs" role="tablist">
          {CHART_PERIODS.map((value) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={period === value}
              className={`period-tab${period === value ? " active" : ""}`}
              onClick={() => onPeriodChange(value)}
            >
              {PERIOD_LABELS[value]}
            </button>
          ))}
        </div>
      </header>

      {loading && <div className="loading-shimmer" aria-label="차트 로딩 중" />}

      {!loading && error && <div className="message">{error}</div>}

      {!loading && !error && rows.length === 0 && (
        <div className="message info">표시할 차트 데이터가 없습니다.</div>
      )}

      {!loading && !error && rows.length > 0 && (
        <div className="chart-body">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={rows} syncId="stockSync" margin={{ top: 10, right: 16, left: 8, bottom: 0 }}>
              <defs>
                <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#00e5ff" stopOpacity={0.55} />
                  <stop offset="100%" stopColor="#00e5ff" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis
                dataKey="label"
                stroke="rgba(232,236,255,0.4)"
                tick={{ fontSize: 11 }}
                minTickGap={24}
              />
              <YAxis
                stroke="rgba(232,236,255,0.4)"
                tick={{ fontSize: 11 }}
                domain={["auto", "auto"]}
                width={56}
              />
              <Tooltip content={<ChartTooltip />} />
              <Area
                type="monotone"
                dataKey="close"
                stroke="#00e5ff"
                strokeWidth={2}
                fill="url(#priceGradient)"
                isAnimationActive
              />
            </AreaChart>
          </ResponsiveContainer>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} syncId="stockSync" margin={{ top: 0, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis
                dataKey="label"
                stroke="rgba(232,236,255,0.4)"
                tick={{ fontSize: 11 }}
                minTickGap={24}
              />
              <YAxis stroke="rgba(232,236,255,0.4)" tick={{ fontSize: 11 }} width={56} />
              <Tooltip content={<ChartTooltip />} />
              <Bar dataKey="volume" fill="#7c5cff" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}
