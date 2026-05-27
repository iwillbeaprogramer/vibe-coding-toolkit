"""Mock stock data for offline / fallback mode."""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Iterable

MOCK_UNIVERSE: dict[str, dict[str, object]] = {
    "AAPL": {
        "name": "Apple Inc.",
        "exchange": "NASDAQ",
        "currency": "USD",
        "market": "US",
        "base_price": 192.5,
        "market_cap": 2_980_000_000_000,
        "pe_ratio": 31.2,
        "eps": 6.16,
        "dividend_yield": 0.0048,
    },
    "MSFT": {
        "name": "Microsoft Corporation",
        "exchange": "NASDAQ",
        "currency": "USD",
        "market": "US",
        "base_price": 415.0,
        "market_cap": 3_100_000_000_000,
        "pe_ratio": 35.4,
        "eps": 11.72,
        "dividend_yield": 0.0072,
    },
    "GOOGL": {
        "name": "Alphabet Inc.",
        "exchange": "NASDAQ",
        "currency": "USD",
        "market": "US",
        "base_price": 158.3,
        "market_cap": 1_950_000_000_000,
        "pe_ratio": 26.7,
        "eps": 5.93,
        "dividend_yield": 0.0,
    },
    "AMZN": {
        "name": "Amazon.com, Inc.",
        "exchange": "NASDAQ",
        "currency": "USD",
        "market": "US",
        "base_price": 182.1,
        "market_cap": 1_900_000_000_000,
        "pe_ratio": 51.0,
        "eps": 3.57,
        "dividend_yield": 0.0,
    },
    "TSLA": {
        "name": "Tesla, Inc.",
        "exchange": "NASDAQ",
        "currency": "USD",
        "market": "US",
        "base_price": 244.9,
        "market_cap": 780_000_000_000,
        "pe_ratio": 73.4,
        "eps": 3.34,
        "dividend_yield": 0.0,
    },
    "NVDA": {
        "name": "NVIDIA Corporation",
        "exchange": "NASDAQ",
        "currency": "USD",
        "market": "US",
        "base_price": 880.5,
        "market_cap": 2_170_000_000_000,
        "pe_ratio": 68.1,
        "eps": 12.93,
        "dividend_yield": 0.0003,
    },
    "META": {
        "name": "Meta Platforms, Inc.",
        "exchange": "NASDAQ",
        "currency": "USD",
        "market": "US",
        "base_price": 491.0,
        "market_cap": 1_250_000_000_000,
        "pe_ratio": 28.0,
        "eps": 17.54,
        "dividend_yield": 0.004,
    },
    "005930.KS": {
        "name": "Samsung Electronics",
        "exchange": "KRX",
        "currency": "KRW",
        "market": "KR",
        "base_price": 78000.0,
        "market_cap": 466_000_000_000_000,
        "pe_ratio": 14.2,
        "eps": 5491.0,
        "dividend_yield": 0.018,
    },
    "035720.KS": {
        "name": "Kakao Corp.",
        "exchange": "KRX",
        "currency": "KRW",
        "market": "KR",
        "base_price": 45200.0,
        "market_cap": 20_000_000_000_000,
        "pe_ratio": 42.5,
        "eps": 1063.0,
        "dividend_yield": 0.0012,
    },
    "035420.KS": {
        "name": "NAVER Corporation",
        "exchange": "KRX",
        "currency": "KRW",
        "market": "KR",
        "base_price": 184500.0,
        "market_cap": 30_500_000_000_000,
        "pe_ratio": 19.6,
        "eps": 9412.0,
        "dividend_yield": 0.0034,
    },
}


PERIOD_CONFIG: dict[str, tuple[int, str, int]] = {
    # period -> (points, interval label, seconds-between-points)
    "1d": (78, "5m", 5 * 60),
    "5d": (130, "30m", 30 * 60),
    "1mo": (22, "1d", 24 * 60 * 60),
    "6mo": (130, "1d", 24 * 60 * 60),
    "1y": (252, "1d", 24 * 60 * 60),
    "5y": (260, "1wk", 7 * 24 * 60 * 60),
}


def listMockSymbols() -> list[str]:
    return list(MOCK_UNIVERSE.keys())


def searchMockSymbols(query: str) -> list[dict[str, str]]:
    normalized = query.strip().lower()
    if not normalized:
        return []
    matches: list[dict[str, str]] = []
    for symbol, meta in MOCK_UNIVERSE.items():
        name = str(meta["name"])
        if normalized in symbol.lower() or normalized in name.lower():
            matches.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "exchange": str(meta["exchange"]),
                    "currency": str(meta["currency"]),
                    "market": str(meta["market"]),
                }
            )
    return matches


def buildMockDetail(symbol: str) -> dict[str, object]:
    meta = MOCK_UNIVERSE.get(symbol.upper()) or _syntheticMeta(symbol)
    basePrice = float(meta["base_price"])  # type: ignore[arg-type]
    rng = random.Random(f"detail::{symbol.upper()}")
    drift = (rng.random() - 0.5) * 0.04
    price = round(basePrice * (1 + drift), 2)
    previousClose = round(basePrice, 2)
    openPrice = round(previousClose * (1 + (rng.random() - 0.5) * 0.01), 2)
    high = round(max(price, openPrice) * (1 + rng.random() * 0.015), 2)
    low = round(min(price, openPrice) * (1 - rng.random() * 0.015), 2)
    volume = float(int(rng.uniform(5_000_000, 80_000_000)))
    avgVolume = float(int(volume * rng.uniform(0.8, 1.2)))
    week52High = round(basePrice * 1.25, 2)
    week52Low = round(basePrice * 0.7, 2)
    return {
        "symbol": symbol.upper(),
        "name": str(meta["name"]),
        "exchange": str(meta["exchange"]),
        "currency": str(meta["currency"]),
        "market": str(meta["market"]),
        "price": price,
        "open": openPrice,
        "close": price,
        "previous_close": previousClose,
        "high": high,
        "low": low,
        "volume": volume,
        "average_volume": avgVolume,
        "market_cap": float(meta["market_cap"]),  # type: ignore[arg-type]
        "pe_ratio": float(meta["pe_ratio"]),  # type: ignore[arg-type]
        "eps": float(meta["eps"]),  # type: ignore[arg-type]
        "dividend_yield": float(meta["dividend_yield"]),  # type: ignore[arg-type]
        "week_high_52": week52High,
        "week_low_52": week52Low,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "source": "mock",
    }


def buildMockChart(symbol: str, period: str) -> dict[str, object]:
    if period not in PERIOD_CONFIG:
        raise ValueError(f"unsupported period: {period}")
    meta = MOCK_UNIVERSE.get(symbol.upper()) or _syntheticMeta(symbol)
    basePrice = float(meta["base_price"])  # type: ignore[arg-type]
    points, intervalLabel, stepSeconds = PERIOD_CONFIG[period]
    rng = random.Random(f"chart::{symbol.upper()}::{period}")
    series: list[dict[str, object]] = []
    price = basePrice * 0.9
    now = datetime.now(timezone.utc)
    start = now - timedelta(seconds=stepSeconds * (points - 1))
    for index in range(points):
        timestamp = start + timedelta(seconds=stepSeconds * index)
        wave = math.sin(index / max(points / 6.0, 1.0)) * basePrice * 0.03
        noise = (rng.random() - 0.5) * basePrice * 0.02
        openPrice = price
        closePrice = max(0.01, openPrice + wave + noise)
        high = max(openPrice, closePrice) * (1 + rng.random() * 0.01)
        low = min(openPrice, closePrice) * (1 - rng.random() * 0.01)
        volume = float(int(rng.uniform(2_000_000, 40_000_000)))
        series.append(
            {
                "timestamp": timestamp.isoformat(),
                "open": round(openPrice, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(closePrice, 4),
                "volume": volume,
            }
        )
        price = closePrice
    return {
        "symbol": symbol.upper(),
        "period": period,
        "interval": intervalLabel,
        "points": series,
        "source": "mock",
    }


def _syntheticMeta(symbol: str) -> dict[str, object]:
    rng = random.Random(f"synthetic::{symbol.upper()}")
    return {
        "name": f"{symbol.upper()} Holdings",
        "exchange": "UNKNOWN",
        "currency": "USD",
        "market": "OTHER",
        "base_price": round(rng.uniform(15.0, 350.0), 2),
        "market_cap": float(int(rng.uniform(5e8, 5e11))),
        "pe_ratio": round(rng.uniform(8.0, 60.0), 2),
        "eps": round(rng.uniform(0.5, 12.0), 2),
        "dividend_yield": round(rng.uniform(0.0, 0.04), 4),
    }


def isMockKnown(symbol: str) -> bool:
    return symbol.upper() in MOCK_UNIVERSE


def filterAllowedPeriods(periods: Iterable[str]) -> list[str]:
    return [p for p in periods if p in PERIOD_CONFIG]
