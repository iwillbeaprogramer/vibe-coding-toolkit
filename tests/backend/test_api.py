from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from src.backend import main
from src.backend.schemas import (
    ChartPoint,
    DataProvider,
    EtfMetrics,
    FundamentalMetrics,
    PriceSummary,
    SearchResult,
    StockDetailResponse,
)
from src.backend.services import ExternalProviderError, SymbolNotFoundError, clearCaches


client = TestClient(main.app)


def teardown_function() -> None:
    clearCaches()


def test_search_returns_symbol_results(monkeypatch) -> None:
    def fakeSearch(query: str) -> list[SearchResult]:
        assert query == "QLD"
        return [
            SearchResult(
                symbol="QLD",
                name="ProShares Ultra QQQ",
                exchange="NYSEARCA",
                assetType="ETF",
                currency="USD",
            )
        ]

    monkeypatch.setattr(main, "searchSymbols", fakeSearch)

    response = client.get("/api/search?q=QLD")

    assert response.status_code == 200
    assert response.json()[0]["symbol"] == "QLD"
    assert response.json()[0]["assetType"] == "ETF"


def test_search_rejects_empty_query() -> None:
    response = client.get("/api/search?q=")

    assert response.status_code == 400
    assert "검색어" in response.json()["detail"]


def test_stock_detail_returns_price_and_chart(monkeypatch) -> None:
    def fakeDetail(ticker: str, period: str) -> StockDetailResponse:
        assert ticker == "QLD"
        assert period == "1mo"
        return StockDetailResponse(
            symbol="QLD",
            name="ProShares Ultra QQQ",
            exchange="NYSEARCA",
            assetType="ETF",
            quoteType="ETF",
            website=None,
            summary=None,
            price=PriceSummary(currentPrice=102.4, previousClose=101.0, currency="USD"),
            fundamentals=FundamentalMetrics(trailingPE=None),
            etf=EtfMetrics(expenseRatio=0.0095, fundFamily="ProShares"),
            chart=[ChartPoint(date=date(2026, 5, 27), open=100, high=103, low=99, close=102.4, volume=1200)],
            period="1mo",
            provider=DataProvider(
                fetchedAt=datetime.now(timezone.utc),
                note="무료 Yahoo Finance 기반 지연 시세입니다.",
            ),
        )

    monkeypatch.setattr(main, "getStockDetail", fakeDetail)

    response = client.get("/api/stock/QLD?period=1mo")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "QLD"
    assert payload["price"]["currentPrice"] == 102.4
    assert payload["chart"][0]["close"] == 102.4


def test_stock_detail_maps_unknown_symbol_to_404(monkeypatch) -> None:
    def fakeDetail(ticker: str, period: str) -> StockDetailResponse:
        raise SymbolNotFoundError("not found")

    monkeypatch.setattr(main, "getStockDetail", fakeDetail)

    response = client.get("/api/stock/INVALID_TICKER_123?period=1mo")

    assert response.status_code == 404


def test_stock_detail_maps_provider_failure_to_502(monkeypatch) -> None:
    def fakeDetail(ticker: str, period: str) -> StockDetailResponse:
        raise ExternalProviderError("provider failed")

    monkeypatch.setattr(main, "getStockDetail", fakeDetail)

    response = client.get("/api/stock/QLD?period=1mo")

    assert response.status_code == 502
    assert response.json()["detail"] == "provider failed"
