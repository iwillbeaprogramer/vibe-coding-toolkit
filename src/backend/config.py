"""Backend runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    cors_origins: tuple[str, ...]
    min_search_length: int
    max_search_length: int
    allowed_periods: tuple[str, ...]
    default_period: str
    force_mock: bool


def loadSettings() -> Settings:
    rawOrigins = os.environ.get("STOCK_API_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    origins = tuple(origin.strip() for origin in rawOrigins.split(",") if origin.strip())
    return Settings(
        host=os.environ.get("STOCK_API_HOST", "0.0.0.0"),
        port=int(os.environ.get("STOCK_API_PORT", "8000")),
        cors_origins=origins,
        min_search_length=2,
        max_search_length=80,
        allowed_periods=("1d", "5d", "1mo", "6mo", "1y", "5y"),
        default_period="1mo",
        force_mock=os.environ.get("STOCK_API_FORCE_MOCK", "").lower() in ("1", "true", "yes"),
    )


settings = loadSettings()
