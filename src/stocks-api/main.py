from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.stocks import router as stocks_router
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stocks-api")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Stocks Dashboard API",
        description=(
            "WPF 주식 대시보드를 위한 로컬 REST API. "
            "yfinance를 통해 미국 상장 주식/ETF의 시세, 기본 지표, 차트 데이터를 제공한다. "
            "본 API는 정보 조회 목적이며 투자 자문이 아닙니다."
        ),
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins or ["*"],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict):
            payload = {
                "code": detail.get("code", "http_error"),
                "message": detail.get("message", "요청 처리 중 오류가 발생했습니다."),
                "details": detail.get("details"),
            }
        else:
            payload = {
                "code": "http_error",
                "message": str(detail) if detail else "요청 처리 중 오류가 발생했습니다.",
                "details": None,
            }
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error for path=%s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "message": "서버 내부 오류가 발생했습니다.",
                "details": {"error": str(exc)},
            },
        )

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok", "service": "stocks-api"}

    app.include_router(stocks_router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
