"""Pydantic schemas for the stock detail API."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Quote(BaseModel):
    """Latest snapshot of price-related values."""

    price: Optional[float] = Field(None, description="Current/last traded price")
    previous_close: Optional[float] = None
    open: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    volume: Optional[int] = None
    change: Optional[float] = Field(None, description="Absolute change vs previous close")
    change_percent: Optional[float] = Field(
        None, description="Percent change vs previous close (e.g. 1.23 means +1.23%)"
    )


class Metrics(BaseModel):
    """Additional indicators commonly used by retail investors."""

    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    eps: Optional[float] = None
    dividend_yield: Optional[float] = None
    beta: Optional[float] = None
    average_volume: Optional[int] = None


class Profile(BaseModel):
    """Company / fund descriptive information."""

    short_name: Optional[str] = None
    long_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    summary: Optional[str] = None
    website: Optional[str] = None
    country: Optional[str] = None


class ChartPoint(BaseModel):
    """Single OHLCV bar."""

    date: str = Field(..., description="ISO date (YYYY-MM-DD) of the bar")
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None


class Chart(BaseModel):
    """Time-series payload used to render the price chart."""

    interval: str = Field("1d", description="Bar interval (default '1d')")
    range: str = Field("6mo", description="Requested historical range")
    points: List[ChartPoint] = Field(default_factory=list)


class StockDetail(BaseModel):
    """Full payload returned by /api/stock/{symbol}."""

    symbol: str
    name: Optional[str] = None
    exchange: Optional[str] = None
    currency: Optional[str] = None
    quote: Quote
    metrics: Metrics
    profile: Profile
    chart: Chart
    fetched_at: datetime
    source: str = "yfinance"
    disclaimer: str = (
        "이 데이터는 정보 제공 목적이며 투자 자문이 아닙니다. 데이터는 지연될 수 있습니다."
    )


class ErrorResponse(BaseModel):
    """Uniform error envelope returned for 4xx/5xx responses."""

    error_code: str
    message: str
    detail: Optional[str] = None
