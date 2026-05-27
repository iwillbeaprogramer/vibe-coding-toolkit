"""Pydantic request/response schemas for the stock API."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    symbol: str
    name: str
    exchange: str = "N/A"
    currency: str = "N/A"
    market: str = "N/A"


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    source: str = Field(description="라이브 공급원이면 'live', 목업이면 'mock'")


class StockDetail(BaseModel):
    symbol: str
    name: str
    exchange: Optional[str] = None
    currency: Optional[str] = None
    market: Optional[str] = None
    price: Optional[float] = None
    open: Optional[float] = None
    close: Optional[float] = None
    previous_close: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[float] = None
    average_volume: Optional[float] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    eps: Optional[float] = None
    dividend_yield: Optional[float] = None
    week_high_52: Optional[float] = None
    week_low_52: Optional[float] = None
    last_updated: Optional[str] = None
    source: str = "live"


class ChartPoint(BaseModel):
    timestamp: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None


class ChartResponse(BaseModel):
    symbol: str
    period: str
    interval: str
    points: list[ChartPoint]
    source: str = "live"


class ErrorResponse(BaseModel):
    error: str
    message: str
    retryable: bool = False
