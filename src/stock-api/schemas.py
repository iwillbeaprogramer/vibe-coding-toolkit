"""WPF-FastAPI 간 주식 상세 정보 데이터 계약 (Pydantic 모델)."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class QuoteData(BaseModel):
    """종목 요약 시세 데이터."""

    price: Optional[float] = Field(default=None, description="현재가 (지연 가능)")
    previous_close: Optional[float] = Field(default=None, description="전일 종가")
    open: Optional[float] = Field(default=None, description="당일 시가")
    day_high: Optional[float] = Field(default=None, description="당일 고가")
    day_low: Optional[float] = Field(default=None, description="당일 저가")
    volume: Optional[int] = Field(default=None, description="당일 거래량")
    average_volume: Optional[int] = Field(default=None, description="평균 거래량")
    change: Optional[float] = Field(default=None, description="전일 대비 변화액")
    change_percent: Optional[float] = Field(default=None, description="전일 대비 변화율(%)")
    fifty_two_week_high: Optional[float] = Field(default=None)
    fifty_two_week_low: Optional[float] = Field(default=None)
    market_cap: Optional[int] = Field(default=None, description="시가총액 또는 ETF 순자산")
    currency: Optional[str] = Field(default=None)
    exchange: Optional[str] = Field(default=None)
    quote_type: Optional[str] = Field(default=None, description="EQUITY, ETF 등")
    sector: Optional[str] = Field(default=None)
    industry: Optional[str] = Field(default=None)


class ChartPoint(BaseModel):
    """차트용 OHLCV 한 행."""

    date: str = Field(description="ISO-8601 날짜 문자열 (예: 2026-05-26)")
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: float
    volume: Optional[int] = None


class StockResponse(BaseModel):
    """티커 상세 조회 응답."""

    symbol: str = Field(description="정규화된 티커 (대문자)")
    name: Optional[str] = Field(default=None, description="회사명 또는 ETF 정식 명")
    quote: QuoteData
    chart: List[ChartPoint] = Field(
        default_factory=list,
        description="최근 1년 일봉 OHLCV 시계열 (오래된 순)",
    )
    provider: str = Field(default="yfinance", description="데이터 공급자")
    fetched_at: str = Field(description="응답 생성 시각 (ISO-8601 UTC)")
    cached: bool = Field(default=False, description="캐시 히트 여부")
    note: str = Field(
        default=(
            "시세 정보는 데이터 제공처 사정에 의해 최소 15분 지연될 수 있으며, "
            "투자 조언이 아닙니다."
        ),
    )


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
