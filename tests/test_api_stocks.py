from __future__ import annotations


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_stock_detail_success_for_qld(client):
    response = client.get("/api/stocks/QLD")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["symbol"] == "QLD"
    assert body["name"]
    assert body["asset_type"] == "ETF"
    assert body["currency"] == "USD"

    quote = body["quote"]
    assert quote["price"] == 100.5
    assert quote["previous_close"] == 98.0
    assert quote["change"] is not None
    assert quote["change_percent"] is not None

    fundamentals = body["fundamentals"]
    assert fundamentals["market_cap"] == 5_000_000_000
    assert fundamentals["pe_ratio"] == 18.5

    profile = body["profile"]
    assert profile["description"]

    chart = body["chart"]
    assert isinstance(chart, list)
    assert len(chart) > 0
    first = chart[0]
    assert {"timestamp", "open", "high", "low", "close", "volume"} <= set(first.keys())


def test_get_stock_detail_normalizes_lowercase_and_whitespace(client):
    response = client.get("/api/stocks/  qld  ")
    assert response.status_code == 200
    assert response.json()["symbol"] == "QLD"


def test_invalid_symbol_too_long_returns_400(client):
    response = client.get("/api/stocks/ABCDEFGHIJKLMNOPQRST")
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "invalid_symbol_length"


def test_invalid_symbol_characters_returns_400(client):
    response = client.get("/api/stocks/QLD!")
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "invalid_symbol_characters"


def test_unknown_symbol_returns_404(client):
    response = client.get("/api/stocks/UNKNOWN")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] in {"symbol_not_found", "symbol_no_data"}
    assert "UNKNOWN" in body["message"]


def test_invalid_range_returns_400(client):
    response = client.get("/api/stocks/QLD", params={"range": "100y"})
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_range"


def test_invalid_interval_returns_400(client):
    response = client.get("/api/stocks/QLD", params={"interval": "1s"})
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_interval"


def test_upstream_history_failure_returns_502(failing_history_client):
    response = failing_history_client.get("/api/stocks/QLD")
    assert response.status_code == 502
    body = response.json()
    assert body["code"] == "upstream_history_failed"
    assert "QLD" in body["message"] or body["details"].get("symbol") == "QLD"
