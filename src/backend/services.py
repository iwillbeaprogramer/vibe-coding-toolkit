from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Any

import requests
import yfinance as yf

from .schemas import (
    ChartPoint,
    DataProvider,
    EtfMetrics,
    FundamentalMetrics,
    PriceSummary,
    SearchResult,
    StockDetailResponse,
)


SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
ALLOWED_PERIODS = {"1d", "1mo", "6mo", "1y", "5y"}
CACHE_TTL_SECONDS = 300
REQUEST_TIMEOUT_SECONDS = 8

_detailCache: dict[tuple[str, str], tuple[float, StockDetailResponse]] = {}
_searchCache: dict[str, tuple[float, list[SearchResult]]] = {}


class StockServiceError(Exception):
    """Base exception for service-level failures."""


class InvalidInputError(StockServiceError):
    pass


class SymbolNotFoundError(StockServiceError):
    pass


class ExternalProviderError(StockServiceError):
    pass


def validateQuery(query: str) -> str:
    cleaned = " ".join(query.strip().split())
    if not cleaned:
        raise InvalidInputError("검색어를 입력해 주세요.")
    if len(cleaned) > 20:
        raise InvalidInputError("검색어는 20자 이하로 입력해 주세요.")
    return cleaned


def validateTicker(ticker: str) -> str:
    cleaned = ticker.strip().upper()
    if not cleaned:
        raise InvalidInputError("티커를 입력해 주세요.")
    if len(cleaned) > 20:
        raise InvalidInputError("티커는 20자 이하로 입력해 주세요.")
    return cleaned


def validatePeriod(period: str) -> str:
    if period not in ALLOWED_PERIODS:
        raise InvalidInputError("지원하지 않는 차트 기간입니다.")
    return period


def searchSymbols(query: str) -> list[SearchResult]:
    cleaned = validateQuery(query)
    cached = _getCache(_searchCache, cleaned.upper())
    if cached is not None:
        return cached

    try:
        response = requests.get(
            SEARCH_URL,
            params={"q": cleaned, "quotesCount": 8, "newsCount": 0},
            headers={"User-Agent": "stock-dashboard/0.1"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.Timeout as exc:
        raise ExternalProviderError("데이터 제공자 응답 시간이 초과되었습니다.") from exc
    except requests.RequestException as exc:
        raise ExternalProviderError("데이터 제공자 검색 요청에 실패했습니다.") from exc
    except ValueError as exc:
        raise ExternalProviderError("데이터 제공자 응답을 해석할 수 없습니다.") from exc

    results = [
        SearchResult(
            symbol=str(item.get("symbol", "")).upper(),
            name=item.get("shortname") or item.get("longname"),
            exchange=item.get("exchange"),
            assetType=item.get("quoteType"),
            currency=item.get("currency"),
        )
        for item in payload.get("quotes", [])
        if item.get("symbol")
    ]
    _setCache(_searchCache, cleaned.upper(), results)
    return results


def getStockDetail(ticker: str, period: str = "1mo") -> StockDetailResponse:
    symbol = validateTicker(ticker)
    selectedPeriod = validatePeriod(period)
    cacheKey = (symbol, selectedPeriod)
    cached = _getCache(_detailCache, cacheKey)
    if cached is not None:
        return cached

    try:
        tickerObject = yf.Ticker(symbol)
        info = _safeDict(tickerObject.get_info())
        fastInfo = _safeDict(getattr(tickerObject, "fast_info", {}) or {})
        history = tickerObject.history(period=selectedPeriod, interval=_toInterval(selectedPeriod))
    except Exception as exc:
        raise ExternalProviderError("데이터 제공자 상세 조회에 실패했습니다.") from exc

    chart = _toChartPoints(history)
    if not chart and not _hasIdentity(info, symbol):
        raise SymbolNotFoundError(f"{symbol} 종목을 찾을 수 없습니다.")

    response = StockDetailResponse(
        symbol=symbol,
        name=_clean(info.get("longName") or info.get("shortName") or info.get("displayName")),
        exchange=_clean(info.get("exchange") or info.get("fullExchangeName")),
        assetType=_clean(info.get("quoteType") or info.get("typeDisp")),
        quoteType=_clean(info.get("quoteType")),
        website=_clean(info.get("website")),
        summary=_clean(info.get("longBusinessSummary")),
        price=_toPriceSummary(info, fastInfo),
        fundamentals=_toFundamentals(info),
        etf=_toEtfMetrics(info),
        chart=chart,
        period=selectedPeriod,  # type: ignore[arg-type]
        provider=DataProvider(
            fetchedAt=datetime.now(timezone.utc),
            note="무료 Yahoo Finance 기반 지연 시세입니다. 투자 조언이 아닌 정보 제공용입니다.",
        ),
    )
    _setCache(_detailCache, cacheKey, response)
    return response


def clearCaches() -> None:
    _detailCache.clear()
    _searchCache.clear()


def _getCache(cache: dict[Any, tuple[float, Any]], key: Any) -> Any | None:
    cached = cache.get(key)
    if cached is None:
        return None
    expiresAt, value = cached
    if expiresAt < time.time():
        cache.pop(key, None)
        return None
    return value


def _setCache(cache: dict[Any, tuple[float, Any]], key: Any, value: Any) -> None:
    cache[key] = (time.time() + CACHE_TTL_SECONDS, value)


def _safeDict(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    return value if isinstance(value, dict) else {}


def _toInterval(period: str) -> str:
    return "5m" if period == "1d" else "1d"


def _toChartPoints(history: Any) -> list[ChartPoint]:
    if history is None or getattr(history, "empty", True):
        return []

    points: list[ChartPoint] = []
    for index, row in history.iterrows():
        points.append(
            ChartPoint(
                date=_formatChartDate(index),
                open=_toFloat(row.get("Open")),
                high=_toFloat(row.get("High")),
                low=_toFloat(row.get("Low")),
                close=_toFloat(row.get("Close")),
                volume=_toInt(row.get("Volume")),
            )
        )
    return points


def _formatChartDate(index: Any) -> str:
    if hasattr(index, "to_pydatetime"):
        value = index.to_pydatetime()
    else:
        value = index

    if isinstance(value, datetime):
        if value.hour == 0 and value.minute == 0 and value.second == 0 and value.microsecond == 0:
            return value.date().isoformat()
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _toPriceSummary(info: dict[str, Any], fastInfo: dict[str, Any]) -> PriceSummary:
    return PriceSummary(
        currentPrice=_firstFloat(fastInfo, info, "last_price", "currentPrice", "regularMarketPrice"),
        previousClose=_firstFloat(fastInfo, info, "previous_close", "previousClose", "regularMarketPreviousClose"),
        open=_firstFloat(fastInfo, info, "open", "regularMarketOpen"),
        dayHigh=_firstFloat(fastInfo, info, "day_high", "dayHigh", "regularMarketDayHigh"),
        dayLow=_firstFloat(fastInfo, info, "day_low", "dayLow", "regularMarketDayLow"),
        volume=_firstInt(fastInfo, info, "last_volume", "volume", "regularMarketVolume"),
        averageVolume=_firstInt(fastInfo, info, "average_volume", "averageVolume"),
        marketCap=_firstInt(fastInfo, info, "market_cap", "marketCap"),
        fiftyTwoWeekHigh=_firstFloat(fastInfo, info, "year_high", "fiftyTwoWeekHigh"),
        fiftyTwoWeekLow=_firstFloat(fastInfo, info, "year_low", "fiftyTwoWeekLow"),
        currency=_clean(_firstValue(fastInfo, info, "currency", "financialCurrency")),
    )


def _toFundamentals(info: dict[str, Any]) -> FundamentalMetrics:
    return FundamentalMetrics(
        trailingPE=_toFloat(info.get("trailingPE")),
        forwardPE=_toFloat(info.get("forwardPE")),
        epsTrailingTwelveMonths=_toFloat(info.get("epsTrailingTwelveMonths")),
        dividendYield=_toFloat(info.get("dividendYield")),
        beta=_toFloat(info.get("beta")),
        sector=_clean(info.get("sector")),
        industry=_clean(info.get("industry")),
    )


def _toEtfMetrics(info: dict[str, Any]) -> EtfMetrics:
    return EtfMetrics(
        expenseRatio=_toFloat(info.get("annualReportExpenseRatio") or info.get("expenseRatio")),
        category=_clean(info.get("category")),
        fundFamily=_clean(info.get("fundFamily")),
        totalAssets=_toInt(info.get("totalAssets")),
        leverage=_clean(info.get("legalType") or info.get("morningStarOverallRating")),
    )


def _hasIdentity(info: dict[str, Any], symbol: str) -> bool:
    return bool(info.get("symbol") == symbol or info.get("shortName") or info.get("longName"))


def _firstValue(*sourcesAndKeys: Any) -> Any:
    sources = [item for item in sourcesAndKeys if isinstance(item, dict)]
    keys = [item for item in sourcesAndKeys if isinstance(item, str)]
    for key in keys:
        for source in sources:
            if source.get(key) is not None:
                return source.get(key)
    return None


def _firstFloat(*sourcesAndKeys: Any) -> float | None:
    return _toFloat(_firstValue(*sourcesAndKeys))


def _firstInt(*sourcesAndKeys: Any) -> int | None:
    return _toInt(_firstValue(*sourcesAndKeys))


def _toFloat(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _toInt(value: Any) -> int | None:
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None
