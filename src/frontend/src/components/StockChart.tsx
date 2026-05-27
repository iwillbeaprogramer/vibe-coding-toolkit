import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';
import type { ChartPeriod, ChartPoint } from '../types';

const PERIODS: Array<{ label: string; value: ChartPeriod }> = [
  { label: '1D', value: '1d' },
  { label: '1M', value: '1mo' },
  { label: '6M', value: '6mo' },
  { label: '1Y', value: '1y' },
  { label: '5Y', value: '5y' }
];

type StockChartProps = {
  chart: ChartPoint[];
  period: ChartPeriod;
  onPeriodChange: (period: ChartPeriod) => void;
  isLoading: boolean;
};

export default function StockChart({ chart, period, onPeriodChange, isLoading }: StockChartProps) {
  return (
    <section className="panel chartPanel" aria-busy={isLoading}>
      <div className="panelHeader">
        <div>
          <p className="eyebrow">Price history</p>
          <h2>가격 차트</h2>
        </div>
        <div className="segmentedControl" aria-label="차트 기간">
          {PERIODS.map((item) => (
            <button
              type="button"
              className={item.value === period ? 'active' : ''}
              key={item.value}
              onClick={() => onPeriodChange(item.value)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="chartSurface">
        {chart.length === 0 ? (
          <div className="emptyChart">차트 데이터 없음</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chart} margin={{ top: 16, right: 12, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(174 72% 43%)" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="hsl(174 72% 43%)" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="hsl(220 18% 23%)" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: 'hsl(218 14% 72%)', fontSize: 12 }} tickLine={false} axisLine={false} />
              <YAxis
                domain={['dataMin', 'dataMax']}
                tick={{ fill: 'hsl(218 14% 72%)', fontSize: 12 }}
                tickLine={false}
                axisLine={false}
                width={56}
              />
              <Tooltip content={<ChartTooltip />} />
              <Area type="monotone" dataKey="close" stroke="hsl(174 72% 43%)" strokeWidth={2.5} fill="url(#priceFill)" />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) {
    return null;
  }
  const row = payload[0].payload as ChartPoint;
  return (
    <div className="chartTooltip">
      <strong>{label}</strong>
      <span>종가 {formatNumber(row.close)}</span>
      <span>시가 {formatNumber(row.open)} · 고가 {formatNumber(row.high)}</span>
      <span>저가 {formatNumber(row.low)} · 거래량 {formatNumber(row.volume)}</span>
    </div>
  );
}

function formatNumber(value?: number | null) {
  if (value == null) {
    return '데이터 없음';
  }
  return new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 2 }).format(value);
}
