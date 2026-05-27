"""API tests for the stock dashboard backend."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.backend import main as main_module
from src.backend.services import stock_service


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(main_module.app)


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_search_too_short_returns_422(client: TestClient) -> None:
    response = client.get("/api/search", params={"q": "a"})
    assert response.status_code == 422


def test_search_returns_mock_results(client: TestClient) -> None:
    response = client.get("/api/search", params={"q": "App"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "mock"
    assert any(item["symbol"] == "AAPL" for item in payload["results"])


def test_search_korean_match(client: TestClient) -> None:
    response = client.get("/api/search", params={"q": "Samsung"})
    assert response.status_code == 200
    payload = response.json()
    assert any(item["symbol"] == "005930.KS" for item in payload["results"])


def test_detail_known_symbol(client: TestClient) -> None:
    response = client.get("/api/stocks/MSFT")
    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "MSFT"
    assert payload["source"] == "mock"
    assert payload["price"] is not None
    assert payload["pe_ratio"] is not None


def test_detail_unknown_symbol_returns_404(client: TestClient) -> None:
    response = client.get("/api/stocks/ZZZZZZZ-NOPE")
    # When force_mock is on and the symbol is unknown, the service raises StockNotFoundError.
    assert response.status_code == 404
    body = response.json()
    assert body["detail"]["error"] == "not_found"


def test_chart_default_period(client: TestClient) -> None:
    response = client.get("/api/stocks/AAPL/chart")
    assert response.status_code == 200
    payload = response.json()
    assert payload["period"] == "1mo"
    assert len(payload["points"]) > 5
    first = payload["points"][0]
    assert "timestamp" in first
    assert "close" in first
    assert "volume" in first


def test_chart_invalid_period(client: TestClient) -> None:
    response = client.get("/api/stocks/AAPL/chart", params={"period": "10y"})
    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["error"] == "invalid_period"


def test_chart_supports_all_allowed_periods(client: TestClient) -> None:
    for period in ("1d", "5d", "1mo", "6mo", "1y", "5y"):
        response = client.get("/api/stocks/AAPL/chart", params={"period": period})
        assert response.status_code == 200, period
        payload = response.json()
        assert payload["period"] == period
        assert payload["points"], f"empty points for {period}"


def test_chart_unknown_symbol_returns_404(client: TestClient) -> None:
    response = client.get("/api/stocks/UNKNOWN-XXX/chart", params={"period": "1mo"})
    assert response.status_code == 404


def test_service_search_strips_whitespace() -> None:
    payload = stock_service.searchSymbols("  AAPL  ")
    assert payload["query"] == "AAPL"
    assert payload["source"] == "mock"
    assert payload["results"]


def test_service_rejects_empty_query() -> None:
    with pytest.raises(ValueError):
        stock_service.searchSymbols("")


def test_service_rejects_long_query() -> None:
    with pytest.raises(ValueError):
        stock_service.searchSymbols("A" * 200)


def test_service_invalid_period_raises() -> None:
    with pytest.raises(stock_service.InvalidPeriodError):
        stock_service.getStockChart("AAPL", "9999")
