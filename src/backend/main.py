"""FastAPI entry point for the stock dashboard backend."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .schemas.stock import ChartResponse, SearchResponse, StockDetail
from .services import stock_service

logger = logging.getLogger(__name__)

app = FastAPI(title="Stock Dashboard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins) or ["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _errorPayload(code: str, message: str, retryable: bool = False) -> dict[str, Any]:
    return {"error": code, "message": message, "retryable": retryable}


@app.get("/api/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/search", response_model=SearchResponse)
def searchStocks(q: str = Query(..., min_length=1, max_length=120)) -> SearchResponse:
    try:
        payload = stock_service.searchSymbols(q)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=_errorPayload("invalid_query", str(exc)))
    return SearchResponse(**payload)


@app.get("/api/stocks/{symbol}", response_model=StockDetail)
def stockDetail(symbol: str) -> StockDetail:
    try:
        payload = stock_service.getStockDetail(symbol)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=_errorPayload("invalid_symbol", str(exc)))
    except stock_service.StockNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=_errorPayload("not_found", "해당 종목을 찾을 수 없습니다."),
        )
    except stock_service.UpstreamUnavailableError as exc:
        raise HTTPException(
            status_code=502,
            detail=_errorPayload("upstream_unavailable", str(exc), retryable=True),
        )
    return StockDetail(**payload)


@app.get("/api/stocks/{symbol}/chart", response_model=ChartResponse)
def stockChart(
    symbol: str,
    period: str = Query(default=settings.default_period),
) -> ChartResponse:
    try:
        payload = stock_service.getStockChart(symbol, period)
    except stock_service.InvalidPeriodError:
        raise HTTPException(
            status_code=400,
            detail=_errorPayload(
                "invalid_period",
                f"허용되지 않는 기간입니다. 허용 값: {', '.join(settings.allowed_periods)}",
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=_errorPayload("invalid_symbol", str(exc)))
    except stock_service.StockNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=_errorPayload("not_found", "해당 종목 차트 데이터를 찾을 수 없습니다."),
        )
    except stock_service.UpstreamUnavailableError as exc:
        raise HTTPException(
            status_code=502,
            detail=_errorPayload("upstream_unavailable", str(exc), retryable=True),
        )
    return ChartResponse(**payload)


@app.exception_handler(Exception)
async def unhandledExceptionHandler(_request, exc: Exception) -> JSONResponse:  # pragma: no cover - defensive
    logger.exception("unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": _errorPayload("internal_error", "서버 내부 오류가 발생했습니다.", retryable=True)},
    )
