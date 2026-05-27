from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.models.stock import StockDetailResponse
from app.services.stock_service import fetch_stock_detail, validate_query_params

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.\-]+$")


def _normalize_symbol(raw: str) -> str:
    if raw is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_symbol",
                "message": "종목 코드가 비어 있습니다.",
            },
        )
    symbol = raw.strip().upper()
    if not (settings.symbol_min_length <= len(symbol) <= settings.symbol_max_length):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_symbol_length",
                "message": (
                    f"종목 코드는 {settings.symbol_min_length}~{settings.symbol_max_length}자 사이여야 합니다."
                ),
                "details": {"received": raw, "length": len(symbol)},
            },
        )
    if not _SYMBOL_PATTERN.match(symbol):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_symbol_characters",
                "message": "종목 코드는 영문, 숫자, 점, 하이픈만 허용됩니다.",
                "details": {"received": raw},
            },
        )
    return symbol


@router.get("/{symbol}", response_model=StockDetailResponse)
def get_stock_detail(
    symbol: str,
    range: str = Query(default=settings.default_range, alias="range"),
    interval: str = Query(default=settings.default_interval),
) -> StockDetailResponse:
    normalized = _normalize_symbol(symbol)
    validate_query_params(range, interval)
    return fetch_stock_detail(normalized, range, interval)
