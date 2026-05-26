"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from .core.exceptions import register_exception_handlers
from .models.schemas import ErrorResponse, StockDetail
from .services import finance_service


def create_app() -> FastAPI:
    app = FastAPI(
        title="Stock Detail API",
        version="0.1.0",
        description=(
            "WPF 클라이언트에 종목 상세 정보와 차트 데이터를 제공하는 로컬 API."
            " 데이터는 yfinance 기반이며 지연될 수 있습니다 (정보 제공용)."
        ),
    )

    # Loopback-only is fine for local dev; CORS is permissive for the WPF client.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get(
        "/api/stock/{symbol}",
        response_model=StockDetail,
        responses={
            400: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
        },
    )
    def get_stock(
        symbol: str,
        range_: str = Query("6mo", alias="range", description="1mo | 6mo | 1y"),
    ) -> StockDetail:
        return finance_service.fetch_stock_detail(symbol, range_)

    return app


app = create_app()


if __name__ == "__main__":  # pragma: no cover - manual entry point
    import uvicorn

    uvicorn.run("stock_api.main:app", host="127.0.0.1", port=8000, reload=True)
