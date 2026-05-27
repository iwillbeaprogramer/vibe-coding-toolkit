from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class StockQuote(BaseModel):
    price: Optional[float] = Field(None, description="현재가")
    previous_close: Optional[float] = Field(None, description="전일 종가")
    change: Optional[float] = Field(None, description="가격 변동")
    change_percent: Optional[float] = Field(None, description="등락률(%)")
    open: Optional[float] = Field(None, description="시가")
    day_high: Optional[float] = Field(None, description="당일 고가")
    day_low: Optional[float] = Field(None, description="당일 저가")
    volume: Optional[int] = Field(None, description="거래량")
    as_of: Optional[datetime] = Field(None, description="데이터 기준 시각")


class StockFundamentals(BaseModel):
    market_cap: Optional[float] = Field(None, description="시가총액")
    pe_ratio: Optional[float] = Field(None, description="PER")
    eps: Optional[float] = Field(None, description="EPS")
    dividend_yield: Optional[float] = Field(None, description="배당수익률")
    fifty_two_week_high: Optional[float] = Field(None, description="52주 고가")
    fifty_two_week_low: Optional[float] = Field(None, description="52주 저가")
    average_volume: Optional[int] = Field(None, description="평균 거래량")


class StockProfile(BaseModel):
    sector: Optional[str] = Field(None, description="섹터")
    industry: Optional[str] = Field(None, description="산업")
    description: Optional[str] = Field(None, description="설명")


class ChartPoint(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class StockDetailResponse(BaseModel):
    symbol: str
    name: Optional[str] = None
    asset_type: Optional[str] = Field(None, description="EQUITY, ETF, ...")
    exchange: Optional[str] = None
    currency: Optional[str] = None
    quote: StockQuote
    fundamentals: StockFundamentals
    profile: StockProfile
    chart: list[ChartPoint]


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None
