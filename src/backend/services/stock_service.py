"""Stock data service with yfinance primary and mock fallback."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from ..config import settings
from . import mock_data

logger = logging.getLogger(__name__)


class StockNotFoundError(Exception):
    pass


class UpstreamUnavailableError(Exception):
    pass


class InvalidPeriodError(Exception):
    pass


def _tryImportYfinance():
    if settings.force_mock:
        return None
    try:
        import yfinance  # type: ignore

        return yfinance
    except Exception as exc:  # pragma: no cover - import guard
        logger.warning("yfinance import failed: %s", exc)
        return None


_yf = _tryImportYfinance()


def searchSymbols(query: str) -> dict[str, Any]:
    cleaned = query.strip()
    if len(cleaned) < settings.min_search_length:
        raise ValueError("검색어는 최소 2자 이상이어야 합니다.")
    if len(cleaned) > settings.max_search_length:
        raise ValueError("검색어가 너무 깁니다.")

    results = _searchLive(cleaned)
    if results:
        return {"query": cleaned, "results": results, "source": "live"}

    mockResults = mock_data.searchMockSymbols(cleaned)
    return {"query": cleaned, "results": mockResults, "source": "mock"}


def getStockDetail(symbol: str) -> dict[str, Any]:
    normalized = _normalizeSymbol(symbol)
    detail = _detailLive(normalized)
    if detail is not None:
        return detail
    if mock_data.isMockKnown(normalized):
        return mock_data.buildMockDetail(normalized)
    raise StockNotFoundError(normalized)


def getStockChart(symbol: str, period: str) -> dict[str, Any]:
    if period not in settings.allowed_periods:
        raise InvalidPeriodError(period)
    normalized = _normalizeSymbol(symbol)
    chart = _chartLive(normalized, period)
    if chart is not None:
        return chart
    if mock_data.isMockKnown(normalized):
        return mock_data.buildMockChart(normalized, period)
    raise StockNotFoundError(normalized)


def _normalizeSymbol(symbol: str) -> str:
    cleaned = (symbol or "").strip().upper()
    if not cleaned:
        raise ValueError("종목 코드가 비어있습니다.")
    return cleaned


def _searchLive(query: str) -> list[dict[str, Any]]:
    if _yf is None:
        return []
    try:
        searchFn = getattr(_yf, "Search", None)
        if searchFn is None:
            return []
        response = searchFn(query, max_results=10)
        rawQuotes = getattr(response, "quotes", None) or []
        results: list[dict[str, Any]] = []
        for quote in rawQuotes:
            symbol = quote.get("symbol")
            if not symbol:
                continue
            results.append(
                {
                    "symbol": str(symbol),
                    "name": str(quote.get("shortname") or quote.get("longname") or symbol),
                    "exchange": str(quote.get("exchDisp") or quote.get("exchange") or "N/A"),
                    "currency": str(quote.get("currency") or "N/A"),
                    "market": str(quote.get("market") or quote.get("region") or "N/A"),
                }
            )
        return results
    except Exception as exc:
        logger.warning("yfinance search failed for %s: %s", query, exc)
        return []


def _detailLive(symbol: str) -> Optional[dict[str, Any]]:
    if _yf is None:
        return None
    try:
        ticker = _yf.Ticker(symbol)
        info: dict[str, Any] = {}
        try:
            info = dict(ticker.info or {})
        except Exception as exc:  # pragma: no cover - yfinance internal
            logger.warning("yfinance info failed for %s: %s", symbol, exc)
            info = {}
        if not info:
            return None
        price = _firstNumber(
            info.get("regularMarketPrice"),
            info.get("currentPrice"),
            info.get("previousClose"),
        )
        if price is None:
            return None
        return {
            "symbol": symbol,
            "name": str(info.get("shortName") or info.get("longName") or symbol),
            "exchange": _strOrNone(info.get("exchange") or info.get("fullExchangeName")),
            "currency": _strOrNone(info.get("currency")),
            "market": _strOrNone(info.get("market") or info.get("region")),
            "price": price,
            "open": _firstNumber(info.get("regularMarketOpen"), info.get("open")),
            "close": _firstNumber(info.get("regularMarketPrice"), info.get("currentPrice")),
            "previous_close": _firstNumber(info.get("regularMarketPreviousClose"), info.get("previousClose")),
            "high": _firstNumber(info.get("regularMarketDayHigh"), info.get("dayHigh")),
            "low": _firstNumber(info.get("regularMarketDayLow"), info.get("dayLow")),
            "volume": _firstNumber(info.get("regularMarketVolume"), info.get("volume")),
            "average_volume": _firstNumber(info.get("averageVolume"), info.get("averageDailyVolume10Day")),
            "market_cap": _firstNumber(info.get("marketCap")),
            "pe_ratio": _firstNumber(info.get("trailingPE"), info.get("forwardPE")),
            "eps": _firstNumber(info.get("trailingEps"), info.get("forwardEps")),
            "dividend_yield": _normalizeDividendYield(info.get("dividendYield")),
            "week_high_52": _firstNumber(info.get("fiftyTwoWeekHigh")),
            "week_low_52": _firstNumber(info.get("fiftyTwoWeekLow")),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "source": "live",
        }
    except Exception as exc:
        logger.warning("yfinance detail failed for %s: %s", symbol, exc)
        return None


def _chartLive(symbol: str, period: str) -> Optional[dict[str, Any]]:
    if _yf is None:
        return None
    intervalMap = {
        "1d": "5m",
        "5d": "30m",
        "1mo": "1d",
        "6mo": "1d",
        "1y": "1d",
        "5y": "1wk",
    }
    interval = intervalMap.get(period, "1d")
    try:
        ticker = _yf.Ticker(symbol)
        history = ticker.history(period=period, interval=interval, auto_adjust=False)
        if history is None or getattr(history, "empty", True):
            return None
        points: list[dict[str, Any]] = []
        for idx, row in history.iterrows():
            timestamp = _toIsoTimestamp(idx)
            points.append(
                {
                    "timestamp": timestamp,
                    "open": _firstNumber(row.get("Open")),
                    "high": _firstNumber(row.get("High")),
                    "low": _firstNumber(row.get("Low")),
                    "close": _firstNumber(row.get("Close")),
                    "volume": _firstNumber(row.get("Volume")),
                }
            )
        if not points:
            return None
        return {
            "symbol": symbol,
            "period": period,
            "interval": interval,
            "points": points,
            "source": "live",
        }
    except Exception as exc:
        logger.warning("yfinance chart failed for %s: %s", symbol, exc)
        return None


def _firstNumber(*values: Any) -> Optional[float]:
    for value in values:
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number != number:  # NaN check
            continue
        return number
    return None


def _normalizeDividendYield(value: Any) -> Optional[float]:
    # yfinance returns dividendYield as either a ratio (e.g. 0.018) or a percent
    # (e.g. 1.8). Always emit a ratio so the frontend can render with value * 100.
    number = _firstNumber(value)
    if number is None:
        return None
    return number / 100.0 if number > 1 else number


def _strOrNone(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _toIsoTimestamp(index: Any) -> str:
    isoFn = getattr(index, "isoformat", None)
    if callable(isoFn):
        return str(isoFn())
    return str(index)
