"""FastAPI 진입점.

WPF 데스크톱 클라이언트에 종목 요약과 차트용 시계열 데이터를 제공한다.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services import (
    StockServiceError,
    loadHistory,
    loadSummary,
)


logger = logging.getLogger("stock_api")

app = FastAPI(title="Stock Dashboard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.exception_handler(StockServiceError)
async def handleStockServiceError(_: Request, exc: StockServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": str(exc)}},
    )


@app.get("/health")
def getHealth() -> dict:
    return {"status": "ok"}


@app.get("/api/stocks/{symbol}/summary")
def getStockSummary(
    symbol: str = Path(..., min_length=1, max_length=15),
) -> dict:
    try:
        return loadSummary(symbol)
    except StockServiceError:
        raise
    except Exception as exc:
        logger.exception("summary 처리 중 예상치 못한 오류")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/stocks/{symbol}/history")
def getStockHistory(
    symbol: str = Path(..., min_length=1, max_length=15),
    range: str = Query("1mo"),
    interval: str = Query("1d"),
) -> dict:
    try:
        return loadHistory(symbol, range, interval)
    except StockServiceError:
        raise
    except Exception as exc:
        logger.exception("history 처리 중 예상치 못한 오류")
        raise HTTPException(status_code=500, detail=str(exc))
