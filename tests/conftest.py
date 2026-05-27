from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "src" / "stocks-api"

if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


@pytest.fixture
def fake_ticker_factory():
    """Returns a factory that produces fakes mimicking yfinance.Ticker."""

    import pandas as pd
    from datetime import datetime, timedelta, timezone

    class _FakeTicker:
        def __init__(self, symbol: str, *, has_data: bool = True):
            self.symbol = symbol
            self._has_data = has_data
            if has_data:
                self.info = {
                    "symbol": symbol,
                    "shortName": f"{symbol} Test",
                    "longName": f"{symbol} Test Long Name",
                    "quoteType": "ETF" if symbol == "QLD" else "EQUITY",
                    "exchange": "NMS",
                    "currency": "USD",
                    "regularMarketPrice": 100.5,
                    "regularMarketPreviousClose": 98.0,
                    "regularMarketOpen": 99.0,
                    "regularMarketDayHigh": 101.0,
                    "regularMarketDayLow": 97.5,
                    "regularMarketVolume": 1_234_567,
                    "regularMarketTime": int(datetime(2026, 5, 26, 20, tzinfo=timezone.utc).timestamp()),
                    "marketCap": 5_000_000_000,
                    "trailingPE": 18.5,
                    "trailingEps": 5.43,
                    "dividendYield": 0.012,
                    "fiftyTwoWeekHigh": 120.0,
                    "fiftyTwoWeekLow": 75.0,
                    "averageVolume": 2_000_000,
                    "sector": "Financial Services" if symbol != "QLD" else None,
                    "industry": "Asset Management" if symbol != "QLD" else None,
                    "category": "Trading--Leveraged Equity" if symbol == "QLD" else None,
                    "longBusinessSummary": "샘플 종목 설명입니다.",
                }
            else:
                self.info = {}

        def history(self, period: str = "6mo", interval: str = "1d"):
            if not self._has_data:
                return pd.DataFrame()
            start = datetime(2025, 12, 1, tzinfo=timezone.utc)
            rows = []
            indices = []
            for i in range(10):
                day = start + timedelta(days=i)
                indices.append(day)
                base = 100 + i
                rows.append(
                    {
                        "Open": base,
                        "High": base + 1.5,
                        "Low": base - 1.2,
                        "Close": base + 0.5,
                        "Volume": 1_000_000 + i * 1000,
                    }
                )
            df = pd.DataFrame(rows, index=pd.DatetimeIndex(indices))
            return df

    def factory(symbol: str):
        if symbol == "UNKNOWN" or symbol == "NODATA":
            return _FakeTicker(symbol, has_data=False)
        return _FakeTicker(symbol, has_data=True)

    return factory


@pytest.fixture
def client(monkeypatch, fake_ticker_factory):
    """FastAPI TestClient with yfinance patched to a deterministic fake."""

    from fastapi.testclient import TestClient

    from app.services import stock_service as svc

    original_fetch = svc.fetch_stock_detail

    def patched_fetch(symbol, range_, interval, ticker_factory=None):
        return original_fetch(symbol, range_, interval, ticker_factory=fake_ticker_factory)

    monkeypatch.setattr(svc, "fetch_stock_detail", patched_fetch)

    from app.api import stocks as stocks_module

    monkeypatch.setattr(stocks_module, "fetch_stock_detail", patched_fetch)

    from main import create_app

    app = create_app()
    return TestClient(app)
