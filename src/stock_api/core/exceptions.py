"""Application-level exceptions and FastAPI exception handlers."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class StockAPIError(Exception):
    """Base error for the stock API."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class InvalidSymbolError(StockAPIError):
    status_code = 400
    error_code = "invalid_symbol"


class SymbolNotFoundError(StockAPIError):
    status_code = 404
    error_code = "symbol_not_found"


class UpstreamDataError(StockAPIError):
    """Raised when the upstream data provider fails or rate-limits us."""

    status_code = 502
    error_code = "upstream_data_error"


def _payload(exc: StockAPIError) -> dict:
    return {
        "error_code": exc.error_code,
        "message": exc.message,
        "detail": exc.detail,
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Install handlers that translate StockAPIError into the standard envelope."""

    @app.exception_handler(StockAPIError)
    async def handle_stock_error(_: Request, exc: StockAPIError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_payload(exc))
