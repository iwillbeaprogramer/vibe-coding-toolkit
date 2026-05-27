import { useMemo } from "react";
import type { StockDetail as StockDetailModel } from "../types";

interface Props {
  detail: StockDetailModel;
}

interface MetricRow {
  label: string;
  value: string;
}

const NA = "N/A";

function formatNumber(value: number | null, fractionDigits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NA;
  return value.toLocaleString(undefined, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

function formatCurrency(value: number | null, currency: string | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NA;
  if (currency && currency !== "N/A") {
    try {
      return new Intl.NumberFormat(undefined, {
        style: "currency",
        currency,
        maximumFractionDigits: 2,
      }).format(value);
    } catch {
      // Fallback to plain numeric formatting if Intl rejects the currency.
    }
  }
  return formatNumber(value);
}

function formatLargeNumber(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NA;
  const abs = Math.abs(value);
  const units: Array<[number, string]> = [
    [1_000_000_000_000, "T"],
    [1_000_000_000, "B"],
    [1_000_000, "M"],
    [1_000, "K"],
  ];
  for (const [threshold, suffix] of units) {
    if (abs >= threshold) {
      return `${(value / threshold).toFixed(2)}${suffix}`;
    }
  }
  return value.toLocaleString();
}

function formatPercent(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NA;
  const ratio = Math.abs(value) <= 1 ? value * 100 : value;
  return `${ratio.toFixed(2)}%`;
}

function formatDate(value: string | null): string {
  if (!value) return NA;
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function StockDetail({ detail }: Props) {
  const change = useMemo(() => {
    if (detail.price == null || detail.previous_close == null) return null;
    const diff = detail.price - detail.previous_close;
    const ratio = detail.previous_close !== 0 ? diff / detail.previous_close : 0;
    return { diff, ratio };
  }, [detail.price, detail.previous_close]);

  const metrics: MetricRow[] = [
    { label: "시가", value: formatCurrency(detail.open, detail.currency) },
    { label: "종가", value: formatCurrency(detail.close, detail.currency) },
    { label: "전일 종가", value: formatCurrency(detail.previous_close, detail.currency) },
    { label: "고가", value: formatCurrency(detail.high, detail.currency) },
    { label: "저가", value: formatCurrency(detail.low, detail.currency) },
    { label: "거래량", value: formatLargeNumber(detail.volume) },
    { label: "평균 거래량", value: formatLargeNumber(detail.average_volume) },
    { label: "시가총액", value: formatLargeNumber(detail.market_cap) },
    { label: "PER", value: formatNumber(detail.pe_ratio) },
    { label: "EPS", value: formatNumber(detail.eps) },
    { label: "배당수익률", value: formatPercent(detail.dividend_yield) },
    { label: "52주 최고", value: formatCurrency(detail.week_high_52, detail.currency) },
    { label: "52주 최저", value: formatCurrency(detail.week_low_52, detail.currency) },
    { label: "거래소", value: detail.exchange || NA },
    { label: "통화", value: detail.currency || NA },
    { label: "마지막 갱신", value: formatDate(detail.last_updated) },
  ];

  return (
    <section className="detail-card" aria-label={`${detail.symbol} 상세 지표`}>
      <div className="detail-headline">
        <span className="sub">{detail.market ?? NA} · {detail.exchange ?? NA}</span>
        <h1>
          {detail.name}
          <span style={{ color: "var(--accent-cyan)", marginLeft: 12 }}>{detail.symbol}</span>
        </h1>
      </div>
      <div className="detail-price">
        <span className="price">{formatCurrency(detail.price, detail.currency)}</span>
        {change && (
          <span className={`change${change.diff < 0 ? " negative" : ""}`}>
            {change.diff >= 0 ? "▲" : "▼"} {formatNumber(Math.abs(change.diff))} ({formatPercent(change.ratio)})
          </span>
        )}
        <span className={`status-banner ${detail.source}`}>{detail.source.toUpperCase()} 데이터</span>
      </div>
      <div className="detail-grid">
        {metrics.map((metric) => (
          <div className="detail-cell" key={metric.label}>
            <span className="label">{metric.label}</span>
            <span className="value">{metric.value}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
