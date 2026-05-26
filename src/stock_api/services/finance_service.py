"""Finance service that turns raw yfinance data into the API DTOs."""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, List, Optional, Tuple

from ..core.exceptions import (
    InvalidSymbolError,
    SymbolNotFoundError,
    UpstreamDataError,
)
from ..models.schemas import (
    Chart,
    ChartPoint,
    Metrics,
    Profile,
    Quote,
    StockDetail,
)

logger = logging.getLogger(__name__)

# Mirrors the WPF-side validation rule: 1~15 chars of [A-Za-z0-9.-]
_SYMBOL_PATTERN = re.compile(r"^[A-Za-z0-9.\-]{1,15}$")

_ALLOWED_RANGES = {"1mo", "6mo", "1y"}


def normalize_symbol(raw: str | None) -> str:
    """Trim and upper-case; raise InvalidSymbolError if the input is unusable."""
    if raw is None:
        raise InvalidSymbolError("종목 심볼이 비어 있습니다.")
    candidate = raw.strip().upper()
    if not candidate:
        raise InvalidSymbolError("종목 심볼이 비어 있습니다.")
    if not _SYMBOL_PATTERN.match(candidate):
        raise InvalidSymbolError(
            "허용되지 않는 종목 심볼 형식입니다.",
            detail="1~15자 영문/숫자/점/하이픈만 허용됩니다.",
        )
    return candidate


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _coerce_int(value: Any) -> Optional[int]:
    f = _coerce_float(value)
    if f is None:
        return None
    return int(f)


@dataclass
class RawTickerData:
    """Provider-agnostic snapshot consumed by the assembler."""

    info: dict
    history: List[Tuple[str, Any, Any, Any, Any, Any]]  # date_iso, open, high, low, close, volume


TickerLoader = Callable[[str, str], RawTickerData]


def _default_loader(symbol: str, range_: str) -> RawTickerData:
    """Default loader that pulls live data from yfinance.

    Kept as a thin adapter so unit tests can inject a fake loader instead of
    hitting the network.
    """
    try:
        import yfinance as yf  # local import: keeps tests runnable without yfinance
    except Exception as exc:  # pragma: no cover - import safety net
        raise UpstreamDataError(
            "데이터 공급처를 사용할 수 없습니다.", detail=str(exc)
        ) from exc

    try:
        ticker = yf.Ticker(symbol)
        info = dict(getattr(ticker, "info", {}) or {})
        history_df = ticker.history(period=range_, interval="1d", auto_adjust=False)
    except Exception as exc:
        logger.warning("yfinance call failed for %s: %s", symbol, exc)
        raise UpstreamDataError(
            "데이터 공급처에서 정보를 가져오지 못했습니다.", detail=str(exc)
        ) from exc

    rows: List[Tuple[str, Any, Any, Any, Any, Any]] = []
    if history_df is not None and not history_df.empty:
        for ts, row in history_df.iterrows():
            try:
                date_iso = ts.strftime("%Y-%m-%d")
            except Exception:
                date_iso = str(ts)
            rows.append(
                (
                    date_iso,
                    row.get("Open"),
                    row.get("High"),
                    row.get("Low"),
                    row.get("Close"),
                    row.get("Volume"),
                )
            )

    return RawTickerData(info=info, history=rows)


def _looks_empty(raw: RawTickerData) -> bool:
    """Treat a missing-price + empty-history payload as 'symbol not found'."""
    info = raw.info or {}
    has_any_price = any(
        info.get(k) is not None
        for k in (
            "regularMarketPrice",
            "currentPrice",
            "previousClose",
            "regularMarketPreviousClose",
        )
    )
    return not has_any_price and not raw.history


def _build_quote(info: dict, history: Iterable) -> Quote:
    price = _coerce_float(info.get("regularMarketPrice") or info.get("currentPrice"))
    prev_close = _coerce_float(
        info.get("regularMarketPreviousClose") or info.get("previousClose")
    )
    open_ = _coerce_float(info.get("regularMarketOpen") or info.get("open"))
    day_high = _coerce_float(info.get("regularMarketDayHigh") or info.get("dayHigh"))
    day_low = _coerce_float(info.get("regularMarketDayLow") or info.get("dayLow"))
    volume = _coerce_int(info.get("regularMarketVolume") or info.get("volume"))

    # Fall back to the most recent history row if info-level fields are missing.
    last_row = None
    history_list = list(history)
    if history_list:
        last_row = history_list[-1]
        if price is None:
            price = _coerce_float(last_row[4])  # close
        if open_ is None:
            open_ = _coerce_float(last_row[1])
        if day_high is None:
            day_high = _coerce_float(last_row[2])
        if day_low is None:
            day_low = _coerce_float(last_row[3])
        if volume is None:
            volume = _coerce_int(last_row[5])
        if prev_close is None and len(history_list) >= 2:
            prev_close = _coerce_float(history_list[-2][4])

    change: Optional[float] = None
    change_pct: Optional[float] = None
    if price is not None and prev_close is not None and prev_close != 0:
        change = price - prev_close
        change_pct = (change / prev_close) * 100.0

    return Quote(
        price=price,
        previous_close=prev_close,
        open=open_,
        day_high=day_high,
        day_low=day_low,
        volume=volume,
        change=change,
        change_percent=change_pct,
    )


def _build_metrics(info: dict) -> Metrics:
    return Metrics(
        fifty_two_week_high=_coerce_float(info.get("fiftyTwoWeekHigh")),
        fifty_two_week_low=_coerce_float(info.get("fiftyTwoWeekLow")),
        market_cap=_coerce_float(info.get("marketCap")),
        pe_ratio=_coerce_float(info.get("trailingPE") or info.get("forwardPE")),
        eps=_coerce_float(info.get("trailingEps") or info.get("forwardEps")),
        dividend_yield=_coerce_float(info.get("dividendYield")),
        beta=_coerce_float(info.get("beta")),
        average_volume=_coerce_int(info.get("averageVolume")),
    )


def _build_profile(info: dict) -> Profile:
    return Profile(
        short_name=info.get("shortName"),
        long_name=info.get("longName"),
        sector=info.get("sector"),
        industry=info.get("industry"),
        summary=info.get("longBusinessSummary"),
        website=info.get("website"),
        country=info.get("country"),
    )


def _build_chart(history: List[Tuple[str, Any, Any, Any, Any, Any]], range_: str) -> Chart:
    points = [
        ChartPoint(
            date=row[0],
            open=_coerce_float(row[1]),
            high=_coerce_float(row[2]),
            low=_coerce_float(row[3]),
            close=_coerce_float(row[4]),
            volume=_coerce_int(row[5]),
        )
        for row in history
    ]
    return Chart(interval="1d", range=range_, points=points)


def fetch_stock_detail(
    raw_symbol: str,
    range_: str = "6mo",
    *,
    loader: TickerLoader | None = None,
) -> StockDetail:
    """Fetch and assemble the full stock detail payload for ``raw_symbol``.

    ``loader`` is injectable for tests; production code uses the yfinance-backed
    default that lazily imports the library.
    """
    symbol = normalize_symbol(raw_symbol)
    if range_ not in _ALLOWED_RANGES:
        raise InvalidSymbolError(
            "지원하지 않는 차트 기간입니다.",
            detail=f"허용 값: {sorted(_ALLOWED_RANGES)}",
        )

    use_loader = loader or _default_loader
    raw = use_loader(symbol, range_)

    if _looks_empty(raw):
        raise SymbolNotFoundError(
            f"'{symbol}' 종목을 찾을 수 없습니다.",
        )

    info = raw.info or {}
    quote = _build_quote(info, raw.history)
    metrics = _build_metrics(info)
    profile = _build_profile(info)
    chart = _build_chart(raw.history, range_)

    return StockDetail(
        symbol=symbol,
        name=profile.long_name or profile.short_name,
        exchange=info.get("exchange") or info.get("fullExchangeName"),
        currency=info.get("currency"),
        quote=quote,
        metrics=metrics,
        profile=profile,
        chart=chart,
        fetched_at=datetime.now(timezone.utc),
        source="yfinance",
    )
