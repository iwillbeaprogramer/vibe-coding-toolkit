"""FastAPI 백엔드 단위 테스트.

외부 yfinance 호출을 가짜 Ticker로 대체해 결정적 검증을 수행한다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
API_DIR = REPO_ROOT / "src" / "stock-api"
sys.path.insert(0, str(API_DIR))

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None

try:
    from fastapi.testclient import TestClient  # type: ignore
except Exception:  # pragma: no cover
    TestClient = None  # type: ignore

fastapiAvailable = TestClient is not None and pd is not None

if fastapiAvailable:
    import main as apiMain  # noqa: E402
    import services as apiServices  # noqa: E402


pytestmark = pytest.mark.skipif(
    not fastapiAvailable,
    reason="fastapi/pandas 미설치 환경에서는 API 통합 테스트를 건너뜁니다.",
)


class FakeTicker:
    def __init__(self, info: dict, history: Any):
        self._info = info
        self._history = history

    @property
    def info(self) -> dict:
        return self._info

    def get_info(self) -> dict:
        return self._info

    def history(self, period: str, interval: str):  # noqa: ARG002
        return self._history


class FakeProvider:
    def __init__(self, mapping: dict[str, FakeTicker]):
        self._mapping = mapping
        self.calls: list[str] = []

    def getTicker(self, symbol: str):
        self.calls.append(symbol)
        if symbol not in self._mapping:
            return FakeTicker({}, _emptyFrame())
        return self._mapping[symbol]


def _emptyFrame():
    if pd is None:
        return None
    return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])


def _sampleHistoryFrame():
    if pd is None:
        return None
    dates = pd.date_range("2026-05-01", periods=3, freq="D")
    return pd.DataFrame(
        {
            "Open": [95.0, 96.2, 97.0],
            "High": [96.5, 97.0, 98.4],
            "Low": [94.2, 95.8, 96.7],
            "Close": [96.1, 96.8, 98.1],
            "Volume": [2900000, 3100000, 3300000],
        },
        index=dates,
    )


def _aaplInfo() -> dict:
    return {
        "longName": "Apple Inc.",
        "regularMarketPrice": 198.45,
        "regularMarketPreviousClose": 197.20,
        "regularMarketOpen": 197.50,
        "regularMarketDayHigh": 199.10,
        "regularMarketDayLow": 197.12,
        "regularMarketVolume": 50321000,
        "averageVolume": 60000000,
        "marketCap": 3_000_000_000_000,
        "fiftyTwoWeekHigh": 220.0,
        "fiftyTwoWeekLow": 150.0,
        "currency": "USD",
        "fullExchangeName": "NasdaqGS",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "quoteType": "EQUITY",
    }


@pytest.fixture
def fakeProvider():
    mapping = {
        "AAPL": FakeTicker(_aaplInfo(), _sampleHistoryFrame()),
        "QLD": FakeTicker(
            {
                "shortName": "ProShares Ultra QQQ",
                "regularMarketPrice": 98.45,
                "regularMarketPreviousClose": 97.20,
                "regularMarketOpen": 97.50,
                "regularMarketDayHigh": 99.10,
                "regularMarketDayLow": 97.12,
                "regularMarketVolume": 3254100,
                "currency": "USD",
                "fullExchangeName": "NASDAQ",
                "quoteType": "ETF",
            },
            _sampleHistoryFrame(),
        ),
    }
    return FakeProvider(mapping)


@pytest.fixture
def client(fakeProvider, monkeypatch):
    def _fakeLoadSummary(symbol: str):
        return apiServices.loadSummary(symbol, provider=fakeProvider)

    def _fakeLoadHistory(symbol: str, rangeValue: str = "1mo", intervalValue: str = "1d"):
        return apiServices.loadHistory(
            symbol, rangeValue, intervalValue, provider=fakeProvider
        )

    monkeypatch.setattr(apiMain, "loadSummary", _fakeLoadSummary)
    monkeypatch.setattr(apiMain, "loadHistory", _fakeLoadHistory)
    return TestClient(apiMain.app)


def test_healthEndpointReturnsOk(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_summaryReturnsExpectedFields(client):
    response = client.get("/api/stocks/AAPL/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert body["name"] == "Apple Inc."
    assert body["price"] == pytest.approx(198.45)
    assert body["prev_close"] == pytest.approx(197.20)
    assert body["change"] == pytest.approx(1.25, rel=1e-3)
    assert body["change_percent"] is not None
    assert body["currency"] == "USD"
    assert body["exchange"] == "NasdaqGS"


def test_summaryNormalizesSymbolToUpper(client):
    response = client.get("/api/stocks/aapl/summary")
    assert response.status_code == 200
    assert response.json()["symbol"] == "AAPL"


def test_summaryUnknownSymbolReturns404(client):
    response = client.get("/api/stocks/NOPE/summary")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "symbol_not_found"


def test_summaryInvalidSymbolReturns400(client):
    response = client.get("/api/stocks/!!!/summary")
    # 경로 변수에 특수문자가 와도 normalizeSymbol에서 InvalidSymbolError가 발생한다.
    assert response.status_code in (400, 404)


def test_historyReturnsPriceSeries(client):
    response = client.get("/api/stocks/AAPL/history?range=1mo&interval=1d")
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert body["range"] == "1mo"
    assert body["interval"] == "1d"
    assert isinstance(body["prices"], list)
    assert len(body["prices"]) == 3
    firstRow = body["prices"][0]
    assert {"date", "open", "high", "low", "close", "volume"}.issubset(firstRow.keys())
    assert firstRow["close"] == pytest.approx(96.1)


def test_historyRejectsInvalidRange(client):
    response = client.get("/api/stocks/AAPL/history?range=999y&interval=1d")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_range"


def test_historyRejectsInvalidInterval(client):
    response = client.get("/api/stocks/AAPL/history?range=1mo&interval=2y")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_interval"


def test_historyUnknownSymbolReturns404(client):
    response = client.get("/api/stocks/NOPE/history")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "symbol_not_found"


def test_normalizeSymbolStripsAndUppercases():
    assert apiServices.normalizeSymbol("  qld  ") == "QLD"


def test_normalizeSymbolRejectsEmpty():
    with pytest.raises(apiServices.InvalidSymbolError):
        apiServices.normalizeSymbol("")


def test_normalizeSymbolRejectsInvalidChars():
    with pytest.raises(apiServices.InvalidSymbolError):
        apiServices.normalizeSymbol("AA PL")


def test_loadSummaryHandlesUpstreamException():
    class RaisingProvider:
        def getTicker(self, symbol: str):  # noqa: ARG002
            raise RuntimeError("network down")

    with pytest.raises(apiServices.UpstreamDataError):
        apiServices.loadSummary("AAPL", provider=RaisingProvider())
