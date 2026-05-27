"""Placeholder verification that the React frontend scaffold is in place.

The full frontend test suite (RTL + Vitest) is out of scope for this stage.
These checks ensure the boilerplate files exist and contain the expected
entry points so the harness can later wire in a JS test runner if desired.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "src" / "frontend"


def test_frontend_package_manifest_exists() -> None:
    manifest = FRONTEND / "package.json"
    assert manifest.exists(), "frontend package.json is missing"
    content = manifest.read_text(encoding="utf-8")
    assert "recharts" in content
    assert "react" in content


def test_frontend_entry_files_exist() -> None:
    assert (FRONTEND / "index.html").exists()
    assert (FRONTEND / "src" / "main.tsx").exists()
    assert (FRONTEND / "src" / "App.tsx").exists()


def test_frontend_components_exist() -> None:
    for component in ("SearchBar.tsx", "StockDetail.tsx", "StockChart.tsx"):
        assert (FRONTEND / "src" / "components" / component).exists(), component


def test_frontend_api_service_exists() -> None:
    api = FRONTEND / "src" / "services" / "api.ts"
    assert api.exists()
    text = api.read_text(encoding="utf-8")
    assert "searchStocks" in text
    assert "fetchStockDetail" in text
    assert "fetchStockChart" in text
