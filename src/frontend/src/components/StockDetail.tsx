import { Building2, Globe2, TrendingDown, TrendingUp } from 'lucide-react';
import type { StockDetailResponse } from '../types';

type StockDetailProps = {
  detail: StockDetailResponse | null;
  isLoading: boolean;
};

export default function StockDetail({ detail, isLoading }: StockDetailProps) {
  if (!detail) {
    return (
      <section className="panel emptyState">
        <h2>종목을 검색하세요</h2>
        <p>티커를 입력하면 가격, 거래량, 밸류에이션, ETF 지표를 한 화면에서 확인할 수 있습니다.</p>
      </section>
    );
  }

  const change = toChange(detail.price.currentPrice, detail.price.previousClose);

  return (
    <section className="panel detailPanel" aria-busy={isLoading}>
      <div className="securityHeader">
        <div>
          <p className="eyebrow">{detail.exchange ?? '데이터 없음'} · {detail.assetType ?? '데이터 없음'}</p>
          <h2>{detail.symbol}</h2>
          <p className="securityName">{detail.name ?? '데이터 없음'}</p>
        </div>
        <div className={`changeBadge ${change.value >= 0 ? 'up' : 'down'}`}>
          {change.value >= 0 ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
          <span>{change.label}</span>
        </div>
      </div>

      <div className="priceBlock">
        <span className="currency">{detail.price.currency ?? ''}</span>
        <strong>{formatNumber(detail.price.currentPrice)}</strong>
        <small>현재가</small>
      </div>

      <div className="metricGrid">
        <Metric label="전일 종가" value={formatNumber(detail.price.previousClose)} />
        <Metric label="시가" value={formatNumber(detail.price.open)} />
        <Metric label="고가" value={formatNumber(detail.price.dayHigh)} />
        <Metric label="저가" value={formatNumber(detail.price.dayLow)} />
        <Metric label="거래량" value={formatNumber(detail.price.volume)} />
        <Metric label="평균 거래량" value={formatNumber(detail.price.averageVolume)} />
        <Metric label="시가총액" value={formatCompact(detail.price.marketCap)} />
        <Metric label="52주 범위" value={`${formatNumber(detail.price.fiftyTwoWeekLow)} / ${formatNumber(detail.price.fiftyTwoWeekHigh)}`} />
      </div>

      <section className="subSection">
        <h3>기본 지표</h3>
        <div className="metricGrid compact">
          <Metric label="Trailing PER" value={formatNumber(detail.fundamentals.trailingPE)} />
          <Metric label="Forward PER" value={formatNumber(detail.fundamentals.forwardPE)} />
          <Metric label="EPS" value={formatNumber(detail.fundamentals.epsTrailingTwelveMonths)} />
          <Metric label="배당수익률" value={formatPercent(detail.fundamentals.dividendYield)} />
          <Metric label="Beta" value={formatNumber(detail.fundamentals.beta)} />
          <Metric label="섹터" value={detail.fundamentals.sector ?? '데이터 없음'} />
        </div>
      </section>

      <section className="subSection">
        <h3>ETF / 펀드 정보</h3>
        <div className="metricGrid compact">
          <Metric label="비용보수" value={formatPercent(detail.etf.expenseRatio)} />
          <Metric label="카테고리" value={detail.etf.category ?? '데이터 없음'} />
          <Metric label="운용사" value={detail.etf.fundFamily ?? '데이터 없음'} />
          <Metric label="총자산" value={formatCompact(detail.etf.totalAssets)} />
        </div>
      </section>

      <footer className="companyFooter">
        <span><Building2 size={15} /> {detail.fundamentals.industry ?? '데이터 없음'}</span>
        {detail.website ? <a href={detail.website} target="_blank" rel="noreferrer"><Globe2 size={15} /> 웹사이트</a> : null}
      </footer>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metricTile">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function toChange(current?: number | null, previous?: number | null) {
  if (current == null || previous == null || previous === 0) {
    return { value: 0, label: '데이터 없음' };
  }
  const value = current - previous;
  const percent = (value / previous) * 100;
  return { value, label: `${value >= 0 ? '+' : ''}${value.toFixed(2)} (${percent.toFixed(2)}%)` };
}

function formatNumber(value?: number | null) {
  if (value == null) {
    return '데이터 없음';
  }
  return new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 2 }).format(value);
}

function formatCompact(value?: number | null) {
  if (value == null) {
    return '데이터 없음';
  }
  return new Intl.NumberFormat('ko-KR', { notation: 'compact', maximumFractionDigits: 2 }).format(value);
}

function formatPercent(value?: number | null) {
  if (value == null) {
    return '데이터 없음';
  }
  return `${(value * 100).toFixed(2)}%`;
}
