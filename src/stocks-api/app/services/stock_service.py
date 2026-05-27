from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException

from app.config import settings
from app.models.stock import (
    ChartPoint,
    StockDetailResponse,
    StockFundamentals,
    StockProfile,
    StockQuote,
)

logger = logging.getLogger(__name__)


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def _safe_int(value: Any) -> Optional[int]:
    f = _safe_float(value)
    if f is None:
        return None
    return int(f)


def _safe_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _classify_asset_type(info: dict[str, Any]) -> Optional[str]:
    quote_type = _safe_str(info.get("quoteType"))
    if quote_type:
        return quote_type.upper()
    if info.get("longBusinessSummary"):
        return "EQUITY"
    return None


def _build_quote(info: dict[str, Any], history) -> StockQuote:
    price = _safe_float(
        info.get("regularMarketPrice")
        or info.get("currentPrice")
        or info.get("previousClose")
    )
    previous_close = _safe_float(
        info.get("regularMarketPreviousClose") or info.get("previousClose")
    )
    if (price is None or previous_close is None) and history is not None and not history.empty:
        last_row = history.iloc[-1]
        if price is None:
            price = _safe_float(last_row.get("Close"))
        if previous_close is None and len(history) >= 2:
            previous_close = _safe_float(history.iloc[-2].get("Close"))

    change = None
    change_percent = None
    if price is not None and previous_close not in (None, 0):
        change = price - previous_close
        change_percent = (change / previous_close) * 100.0

    as_of_ts = info.get("regularMarketTime")
    as_of: Optional[datetime] = None
    if isinstance(as_of_ts, (int, float)) and as_of_ts > 0:
        as_of = datetime.fromtimestamp(as_of_ts, tz=timezone.utc)
    elif history is not None and not history.empty:
        last_index = history.index[-1]
        try:
            as_of = last_index.to_pydatetime()
            if as_of.tzinfo is None:
                as_of = as_of.replace(tzinfo=timezone.utc)
        except AttributeError:
            as_of = None

    return StockQuote(
        price=price,
        previous_close=previous_close,
        change=change,
        change_percent=change_percent,
        open=_safe_float(info.get("regularMarketOpen") or info.get("open")),
        day_high=_safe_float(info.get("regularMarketDayHigh") or info.get("dayHigh")),
        day_low=_safe_float(info.get("regularMarketDayLow") or info.get("dayLow")),
        volume=_safe_int(info.get("regularMarketVolume") or info.get("volume")),
        as_of=as_of,
    )


def _build_fundamentals(info: dict[str, Any]) -> StockFundamentals:
    return StockFundamentals(
        market_cap=_safe_float(info.get("marketCap") or info.get("totalAssets")),
        pe_ratio=_safe_float(info.get("trailingPE") or info.get("forwardPE")),
        eps=_safe_float(info.get("trailingEps") or info.get("forwardEps")),
        dividend_yield=_safe_float(info.get("dividendYield") or info.get("yield")),
        fifty_two_week_high=_safe_float(info.get("fiftyTwoWeekHigh")),
        fifty_two_week_low=_safe_float(info.get("fiftyTwoWeekLow")),
        average_volume=_safe_int(info.get("averageVolume") or info.get("averageDailyVolume10Day")),
    )


def _build_profile(info: dict[str, Any]) -> StockProfile:
    description = _safe_str(
        info.get("longBusinessSummary") or info.get("description")
    )
    return StockProfile(
        sector=_safe_str(info.get("sector")),
        industry=_safe_str(info.get("industry") or info.get("category")),
        description=description,
    )


def _build_chart(history) -> list[ChartPoint]:
    points: list[ChartPoint] = []
    if history is None or history.empty:
        return points
    for index, row in history.iterrows():
        open_v = _safe_float(row.get("Open"))
        high_v = _safe_float(row.get("High"))
        low_v = _safe_float(row.get("Low"))
        close_v = _safe_float(row.get("Close"))
        volume_v = _safe_int(row.get("Volume"))
        if None in (open_v, high_v, low_v, close_v):
            continue
        try:
            ts = index.to_pydatetime()
        except AttributeError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        points.append(
            ChartPoint(
                timestamp=ts,
                open=open_v,
                high=high_v,
                low=low_v,
                close=close_v,
                volume=volume_v if volume_v is not None else 0,
            )
        )
    return points


def _is_empty_info(info: Optional[dict[str, Any]]) -> bool:
    if not info:
        return True
    meaningful_keys = (
        "regularMarketPrice",
        "currentPrice",
        "previousClose",
        "longName",
        "shortName",
    )
    return not any(info.get(key) is not None for key in meaningful_keys)


def _load_and_validate_ticker_data(
    symbol: str,
    range_: str,
    interval: str,
    ticker_factory,
) -> tuple[dict[str, Any], Any]:
    """외부 공급자에서 info/history를 안전하게 가져오고 404/502 사전 판별을 수행한다."""

    try:
        ticker = ticker_factory(symbol)
    except Exception as exc:  # noqa: BLE001 - 외부 라이브러리 호출 보호
        logger.exception("ticker_factory failed for symbol=%s", symbol)
        raise HTTPException(
            status_code=502,
            detail={
                "code": "upstream_init_failed",
                "message": "시세 공급자 초기화에 실패했습니다.",
                "details": {"symbol": symbol, "error": str(exc)},
            },
        ) from exc

    try:
        info: dict[str, Any] = getattr(ticker, "info", None) or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("ticker.info failed for symbol=%s: %s", symbol, exc)
        info = {}

    try:
        history = ticker.history(period=range_, interval=interval)
    except Exception as exc:  # noqa: BLE001
        logger.exception("ticker.history failed for symbol=%s", symbol)
        raise HTTPException(
            status_code=502,
            detail={
                "code": "upstream_history_failed",
                "message": "시세 공급자에서 차트 데이터를 가져오지 못했습니다.",
                "details": {"symbol": symbol, "error": str(exc)},
            },
        ) from exc

    history_is_empty = history is None or getattr(history, "empty", True)
    if history_is_empty and _is_empty_info(info):
        raise HTTPException(
            status_code=404,
            detail={
                "code": "symbol_not_found",
                "message": f"'{symbol}' 종목을 찾을 수 없습니다.",
                "details": {"symbol": symbol},
            },
        )

    return info, history


def fetch_stock_detail(
    symbol: str,
    range_: str,
    interval: str,
    ticker_factory=None,
) -> StockDetailResponse:
    """티커 정보를 외부 데이터 공급자에서 조회하여 응답 모델로 가공한다."""

    if ticker_factory is None:
        import yfinance as yf

        ticker_factory = yf.Ticker

    info, history = _load_and_validate_ticker_data(symbol, range_, interval, ticker_factory)

    quote = _build_quote(info, history)
    fundamentals = _build_fundamentals(info)
    profile = _build_profile(info)
    chart = _build_chart(history)

    if quote.price is None and not chart:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "symbol_no_data",
                "message": f"'{symbol}' 종목의 시세/차트 데이터를 확인할 수 없습니다.",
                "details": {"symbol": symbol},
            },
        )

    name = _safe_str(info.get("longName") or info.get("shortName")) or symbol

    return StockDetailResponse(
        symbol=symbol,
        name=name,
        asset_type=_classify_asset_type(info),
        exchange=_safe_str(info.get("exchange") or info.get("fullExchangeName")),
        currency=_safe_str(info.get("currency")),
        quote=quote,
        fundamentals=fundamentals,
        profile=profile,
        chart=chart,
    )


def validate_query_params(range_: str, interval: str) -> None:
    if range_ not in settings.allowed_ranges:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_range",
                "message": "지원하지 않는 range 값입니다.",
                "details": {"allowed": list(settings.allowed_ranges), "received": range_},
            },
        )
    if interval not in settings.allowed_intervals:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_interval",
                "message": "지원하지 않는 interval 값입니다.",
                "details": {"allowed": list(settings.allowed_intervals), "received": interval},
            },
        )
