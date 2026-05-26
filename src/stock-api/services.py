"""주식 데이터 조회 서비스.

yfinance를 활용해 외부 시장 데이터를 가져와 정제한다.
누락 필드와 외부 호출 실패를 명시적으로 처리한다.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.\-]{1,15}$")


def _defaultTickerFactory(symbol: str) -> Any:
    """yfinance.Ticker를 지연 임포트로 감싸 테스트 환경에서의 누락을 허용한다."""
    import yfinance as yf  # 지역 임포트로 미설치 환경에서도 모듈 로드를 가능하게 한다.

    return yf.Ticker(symbol)


class StockServiceError(Exception):
    """서비스 계층 공통 예외."""

    def __init__(self, message: str, *, code: str, status_code: int = 500):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class SymbolNotFoundError(StockServiceError):
    def __init__(self, symbol: str):
        super().__init__(
            f"심볼 '{symbol}'에 대한 데이터를 찾을 수 없습니다.",
            code="symbol_not_found",
            status_code=404,
        )


class InvalidSymbolError(StockServiceError):
    def __init__(self, symbol: str):
        super().__init__(
            f"심볼 '{symbol}'은 허용되지 않는 형식입니다.",
            code="invalid_symbol",
            status_code=400,
        )


class UpstreamDataError(StockServiceError):
    def __init__(self, message: str):
        super().__init__(message, code="upstream_error", status_code=502)


def normalizeSymbol(rawSymbol: Optional[str]) -> str:
    """티커 입력을 정규화하고 형식을 검증한다."""
    if rawSymbol is None:
        raise InvalidSymbolError("")
    cleaned = rawSymbol.strip().upper()
    if not cleaned:
        raise InvalidSymbolError(cleaned)
    if not SYMBOL_PATTERN.match(cleaned):
        raise InvalidSymbolError(cleaned)
    return cleaned


def _isNumberFinite(value: Any) -> bool:
    if value is None:
        return False
    try:
        floatValue = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(floatValue)


def _toFloat(value: Any) -> Optional[float]:
    if _isNumberFinite(value):
        return float(value)
    return None


def _toInt(value: Any) -> Optional[int]:
    if _isNumberFinite(value):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None
    return None


def _pickFirst(info: dict, keys: list[str]) -> Any:
    for key in keys:
        if key in info:
            value = info[key]
            if value is not None and value != "":
                return value
    return None


@dataclass
class TickerProvider:
    """yfinance 의존성을 외부에서 주입 가능하게 감싼다.

    테스트 시 가짜 구현으로 교체할 수 있다.
    """

    factory: Callable[[str], Any] = field(default=_defaultTickerFactory)

    def getTicker(self, symbol: str) -> Any:
        return self.factory(symbol)


def loadSummary(symbol: str, *, provider: Optional[TickerProvider] = None) -> dict:
    """종목 요약 정보를 반환한다."""
    normalized = normalizeSymbol(symbol)
    tickerProvider = provider or TickerProvider()
    try:
        ticker = tickerProvider.getTicker(normalized)
        info = _readTickerInfo(ticker)
    except StockServiceError:
        raise
    except Exception as exc:  # 외부 라이브러리 예외 전반
        raise UpstreamDataError(f"외부 데이터 공급원 호출에 실패했습니다: {exc}") from exc

    if not info:
        raise SymbolNotFoundError(normalized)

    price = _toFloat(
        _pickFirst(
            info,
            [
                "regularMarketPrice",
                "currentPrice",
                "regularMarketPreviousClose",
                "previousClose",
            ],
        )
    )
    prevClose = _toFloat(
        _pickFirst(info, ["regularMarketPreviousClose", "previousClose"])
    )
    if price is None and prevClose is None:
        # 두 가격 모두 없다면 의미 있는 정보가 없는 것으로 간주한다.
        raise SymbolNotFoundError(normalized)

    change = None
    changePercent = None
    if price is not None and prevClose not in (None, 0):
        change = price - prevClose
        changePercent = (change / prevClose) * 100.0

    return {
        "symbol": normalized,
        "name": _pickFirst(info, ["longName", "shortName", "displayName"]),
        "price": price,
        "prev_close": prevClose,
        "change": _toFloat(change),
        "change_percent": _toFloat(changePercent),
        "open": _toFloat(_pickFirst(info, ["regularMarketOpen", "open"])),
        "high": _toFloat(_pickFirst(info, ["regularMarketDayHigh", "dayHigh"])),
        "low": _toFloat(_pickFirst(info, ["regularMarketDayLow", "dayLow"])),
        "volume": _toInt(_pickFirst(info, ["regularMarketVolume", "volume"])),
        "average_volume": _toInt(
            _pickFirst(info, ["averageVolume", "averageDailyVolume10Day"])
        ),
        "market_cap": _toInt(_pickFirst(info, ["marketCap"])),
        "fifty_two_week_high": _toFloat(_pickFirst(info, ["fiftyTwoWeekHigh"])),
        "fifty_two_week_low": _toFloat(_pickFirst(info, ["fiftyTwoWeekLow"])),
        "currency": _pickFirst(info, ["currency"]),
        "exchange": _pickFirst(info, ["fullExchangeName", "exchange"]),
        "sector": _pickFirst(info, ["sector"]),
        "industry": _pickFirst(info, ["industry"]),
        "quote_type": _pickFirst(info, ["quoteType"]),
    }


def _readTickerInfo(ticker: Any) -> dict:
    """Ticker 객체에서 info 딕셔너리를 안전하게 읽는다."""
    getInfo = getattr(ticker, "get_info", None)
    if callable(getInfo):
        info = getInfo()
    else:
        info = getattr(ticker, "info", None)
    if not info:
        return {}
    if not isinstance(info, dict):
        return {}
    return info


VALID_RANGES = {
    "1d",
    "5d",
    "1mo",
    "3mo",
    "6mo",
    "1y",
    "2y",
    "5y",
    "10y",
    "ytd",
    "max",
}
VALID_INTERVALS = {
    "1m",
    "2m",
    "5m",
    "15m",
    "30m",
    "60m",
    "90m",
    "1h",
    "1d",
    "5d",
    "1wk",
    "1mo",
    "3mo",
}


def loadHistory(
    symbol: str,
    rangeValue: str = "1mo",
    intervalValue: str = "1d",
    *,
    provider: Optional[TickerProvider] = None,
) -> dict:
    """종목의 OHLCV 시계열을 반환한다."""
    normalized = normalizeSymbol(symbol)
    normalizedRange = (rangeValue or "1mo").strip().lower()
    normalizedInterval = (intervalValue or "1d").strip().lower()
    if normalizedRange not in VALID_RANGES:
        raise StockServiceError(
            f"허용되지 않는 range 값입니다: {rangeValue}",
            code="invalid_range",
            status_code=400,
        )
    if normalizedInterval not in VALID_INTERVALS:
        raise StockServiceError(
            f"허용되지 않는 interval 값입니다: {intervalValue}",
            code="invalid_interval",
            status_code=400,
        )

    tickerProvider = provider or TickerProvider()
    try:
        ticker = tickerProvider.getTicker(normalized)
        historyDf = ticker.history(period=normalizedRange, interval=normalizedInterval)
    except StockServiceError:
        raise
    except Exception as exc:
        raise UpstreamDataError(f"외부 데이터 공급원 호출에 실패했습니다: {exc}") from exc

    if historyDf is None or len(historyDf) == 0:
        raise SymbolNotFoundError(normalized)

    prices = _formatHistoryFrame(historyDf)
    if not prices:
        raise SymbolNotFoundError(normalized)

    return {
        "symbol": normalized,
        "range": normalizedRange,
        "interval": normalizedInterval,
        "prices": prices,
    }


def _formatHistoryFrame(historyDf: Any) -> list[dict]:
    """pandas DataFrame을 직렬화 가능한 prices 리스트로 변환한다."""
    rows: list[dict] = []
    try:
        records = historyDf.reset_index().to_dict("records")
    except Exception:
        return rows

    for record in records:
        rawDate = record.get("Date") or record.get("Datetime") or record.get("index")
        dateText = _formatDate(rawDate)
        if dateText is None:
            continue
        closeValue = _toFloat(record.get("Close"))
        if closeValue is None:
            # 종가가 없으면 차트로 의미가 없다.
            continue
        rows.append(
            {
                "date": dateText,
                "open": _toFloat(record.get("Open")),
                "high": _toFloat(record.get("High")),
                "low": _toFloat(record.get("Low")),
                "close": closeValue,
                "volume": _toInt(record.get("Volume")),
            }
        )
    return rows


def _formatDate(rawDate: Any) -> Optional[str]:
    if rawDate is None:
        return None
    isoFormatter = getattr(rawDate, "isoformat", None)
    if callable(isoFormatter):
        try:
            return isoFormatter()
        except Exception:
            pass
    try:
        return str(rawDate)
    except Exception:
        return None
