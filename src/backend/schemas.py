from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    symbol: str
    name: str | None = None
    exchange: str | None = None
    assetType: str | None = None
    currency: str | None = None


class ChartPoint(BaseModel):
    date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None


class PriceSummary(BaseModel):
    currentPrice: float | None = None
    previousClose: float | None = None
    open: float | None = None
    dayHigh: float | None = None
    dayLow: float | None = None
    volume: int | None = None
    averageVolume: int | None = None
    marketCap: int | None = None
    fiftyTwoWeekHigh: float | None = None
    fiftyTwoWeekLow: float | None = None
    currency: str | None = None


class FundamentalMetrics(BaseModel):
    trailingPE: float | None = None
    forwardPE: float | None = None
    epsTrailingTwelveMonths: float | None = None
    dividendYield: float | None = None
    beta: float | None = None
    sector: str | None = None
    industry: str | None = None


class EtfMetrics(BaseModel):
    expenseRatio: float | None = None
    category: str | None = None
    fundFamily: str | None = None
    totalAssets: int | None = None
    leverage: str | None = None


class DataProvider(BaseModel):
    name: str = "Yahoo Finance"
    fetchedAt: datetime
    delayed: bool = True
    note: str


class StockDetailResponse(BaseModel):
    symbol: str
    name: str | None = None
    exchange: str | None = None
    assetType: str | None = None
    quoteType: str | None = None
    website: str | None = None
    summary: str | None = None
    price: PriceSummary
    fundamentals: FundamentalMetrics
    etf: EtfMetrics
    chart: list[ChartPoint] = Field(default_factory=list)
    period: Literal["1d", "1mo", "6mo", "1y", "5y"]
    provider: DataProvider


class ErrorResponse(BaseModel):
    detail: str
