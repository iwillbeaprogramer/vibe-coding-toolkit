"""Tests for the FastAPI stock detail endpoint and finance service."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from stock_api.core.exceptions import (
    InvalidSymbolError,
    SymbolNotFoundError,
    UpstreamDataError,
    register_exception_handlers,
)
from stock_api.main import create_app
from stock_api.services import finance_service
from stock_api.services.finance_service import (
    RawTickerData,
    fetch_stock_detail,
    normalize_symbol,
)


# ---------- helpers ----------

def _good_info() -> dict:
    return {
        "regularMarketPrice": 100.0,
        "regularMarketPreviousClose": 95.0,
        "regularMarketOpen": 96.0,
        "regularMarketDayHigh": 101.5,
        "regularMarketDayLow": 95.5,
        "regularMarketVolume": 12345678,
        "fiftyTwoWeekHigh": 110.0,
        "fiftyTwoWeekLow": 80.0,
        "marketCap": 5_000_000_000,
        "trailingPE": 25.5,
        "trailingEps": 4.2,
        "dividendYield": 0.015,
        "beta": 1.2,
        "averageVolume": 11_000_000,
        "shortName": "Test ETF",
        "longName": "Test ProShares ETF Trust",
        "exchange": "NMS",
        "currency": "USD",
        "sector": "Financial",
        "industry": "Asset Management",
        "longBusinessSummary": "A leveraged ETF used for testing.",
    }


def _good_history(n: int = 5):
    return [
        (f"2026-01-0{i + 1}", 90.0 + i, 92.0 + i, 89.0 + i, 91.0 + i, 1_000_000 + i)
        for i in range(n)
    ]


def _make_loader(info=None, history=None):
    def loader(symbol: str, range_: str) -> RawTickerData:
        return RawTickerData(info=info or {}, history=history or [])
    return loader


# ---------- normalize_symbol ----------

def test_normalize_symbol_trims_and_uppers():
    assert normalize_symbol("  qld ") == "QLD"
    assert normalize_symbol("brk-b") == "BRK-B"


def test_normalize_symbol_rejects_empty():
    with pytest.raises(InvalidSymbolError):
        normalize_symbol("   ")
    with pytest.raises(InvalidSymbolError):
        normalize_symbol(None)  # type: ignore[arg-type]


def test_normalize_symbol_rejects_illegal_chars():
    with pytest.raises(InvalidSymbolError):
        normalize_symbol("AA!PL")


def test_normalize_symbol_rejects_too_long():
    with pytest.raises(InvalidSymbolError):
        normalize_symbol("A" * 16)


# ---------- fetch_stock_detail ----------

def test_fetch_stock_detail_happy_path():
    loader = _make_loader(_good_info(), _good_history())
    detail = fetch_stock_detail("qld", "6mo", loader=loader)
    assert detail.symbol == "QLD"
    assert detail.quote.price == 100.0
    assert detail.quote.previous_close == 95.0
    assert detail.quote.change == pytest.approx(5.0)
    assert detail.quote.change_percent == pytest.approx(5.0 / 95.0 * 100, rel=1e-6)
    assert len(detail.chart.points) == 5
    assert detail.chart.range == "6mo"


def test_fetch_stock_detail_partial_fields_returns_na_friendly():
    # Provider returned price only — all other fields should be None ('N/A' on the UI side).
    loader = _make_loader({"regularMarketPrice": 50.0}, _good_history(2))
    detail = fetch_stock_detail("AAPL", "1mo", loader=loader)
    assert detail.quote.price == 50.0
    assert detail.metrics.pe_ratio is None
    assert detail.metrics.market_cap is None
    assert detail.profile.long_name is None


def test_fetch_stock_detail_unknown_symbol_raises():
    loader = _make_loader({}, [])
    with pytest.raises(SymbolNotFoundError):
        fetch_stock_detail("ZZZZ", "6mo", loader=loader)


def test_fetch_stock_detail_invalid_range():
    loader = _make_loader(_good_info(), _good_history())
    with pytest.raises(InvalidSymbolError):
        fetch_stock_detail("QLD", "5y", loader=loader)


def test_fetch_stock_detail_falls_back_to_history_for_quote():
    # When info has no price, the last history close should populate the quote.
    loader = _make_loader({}, _good_history(3))
    detail = fetch_stock_detail("QLD", "6mo", loader=loader)
    assert detail.quote.price == pytest.approx(93.0)
    assert detail.quote.previous_close == pytest.approx(92.0)


# ---------- HTTP layer ----------

def _build_app_with_loader(loader_fn) -> FastAPI:
    app = create_app()
    # Patch the default loader at module level so the endpoint picks it up.
    finance_service._default_loader = loader_fn  # type: ignore[attr-defined]
    return app


def test_endpoint_returns_payload(monkeypatch):
    monkeypatch.setattr(
        finance_service, "_default_loader", _make_loader(_good_info(), _good_history())
    )
    client = TestClient(create_app())
    res = client.get("/api/stock/qld")
    assert res.status_code == 200
    body = res.json()
    assert body["symbol"] == "QLD"
    assert body["quote"]["price"] == 100.0
    assert "points" in body["chart"]
    assert body["disclaimer"]  # disclaimer string is populated


def test_endpoint_404_for_unknown(monkeypatch):
    monkeypatch.setattr(finance_service, "_default_loader", _make_loader({}, []))
    client = TestClient(create_app())
    res = client.get("/api/stock/ZZZZ")
    assert res.status_code == 404
    body = res.json()
    assert body["error_code"] == "symbol_not_found"


def test_endpoint_400_for_invalid_symbol(monkeypatch):
    monkeypatch.setattr(
        finance_service, "_default_loader", _make_loader(_good_info(), _good_history())
    )
    client = TestClient(create_app())
    res = client.get("/api/stock/AA!PL")
    assert res.status_code == 400
    assert res.json()["error_code"] == "invalid_symbol"


def test_endpoint_502_when_upstream_fails(monkeypatch):
    def boom(symbol: str, range_: str) -> RawTickerData:
        raise UpstreamDataError("공급처 호출 실패", detail="HTTP 429")

    monkeypatch.setattr(finance_service, "_default_loader", boom)
    client = TestClient(create_app())
    res = client.get("/api/stock/QLD")
    assert res.status_code == 502
    body = res.json()
    assert body["error_code"] == "upstream_data_error"
    assert body["detail"] == "HTTP 429"


def test_endpoint_400_for_bad_range(monkeypatch):
    monkeypatch.setattr(
        finance_service, "_default_loader", _make_loader(_good_info(), _good_history())
    )
    client = TestClient(create_app())
    res = client.get("/api/stock/QLD?range=10y")
    assert res.status_code == 400


def test_health_endpoint():
    client = TestClient(create_app())
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_endpoint_serializes_nan_and_inf_metrics_as_null(monkeypatch):
    # yfinance occasionally returns NaN/Inf in numeric fields. _coerce_float must
    # absorb these so the response JSON stays valid (Pydantic v2 rejects NaN in
    # the default serializer) and the field reaches the WPF client as null.
    info = _good_info()
    info["trailingPE"] = float("nan")
    info["forwardPE"] = float("nan")
    info["beta"] = float("inf")
    info["marketCap"] = float("-inf")
    monkeypatch.setattr(
        finance_service, "_default_loader", _make_loader(info, _good_history())
    )
    client = TestClient(create_app())
    res = client.get("/api/stock/QLD")
    assert res.status_code == 200
    metrics = res.json()["metrics"]
    assert metrics["pe_ratio"] is None
    assert metrics["beta"] is None
    assert metrics["market_cap"] is None
