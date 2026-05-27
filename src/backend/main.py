from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .schemas import ErrorResponse, SearchResult, StockDetailResponse
from .services import (
    ExternalProviderError,
    InvalidInputError,
    SymbolNotFoundError,
    getStockDetail,
    searchSymbols,
)


app = FastAPI(
    title="Stock Insight API",
    description="Local FastAPI backend for stock and ETF lookup.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def getHealth() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/api/search",
    response_model=list[SearchResult],
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def search(q: str = Query("")) -> list[SearchResult]:
    try:
        return searchSymbols(q)
    except InvalidInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ExternalProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get(
    "/api/stock/{ticker}",
    response_model=StockDetailResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def getStock(
    ticker: str,
    period: str = Query("1mo"),
) -> StockDetailResponse:
    try:
        return getStockDetail(ticker, period)
    except InvalidInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SymbolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExternalProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
