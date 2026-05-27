import os


class Settings:
    api_host: str = os.environ.get("STOCKS_API_HOST", "127.0.0.1")
    api_port: int = int(os.environ.get("STOCKS_API_PORT", "8000"))
    default_range: str = os.environ.get("STOCKS_DEFAULT_RANGE", "6mo")
    default_interval: str = os.environ.get("STOCKS_DEFAULT_INTERVAL", "1d")
    yfinance_timeout_seconds: float = float(os.environ.get("STOCKS_YF_TIMEOUT", "15"))
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.environ.get("STOCKS_CORS_ORIGINS", "*").split(",")
        if origin.strip()
    ]
    allowed_ranges: tuple[str, ...] = (
        "1mo",
        "3mo",
        "6mo",
        "1y",
        "2y",
        "5y",
        "ytd",
        "max",
    )
    allowed_intervals: tuple[str, ...] = (
        "1d",
        "1wk",
        "1mo",
    )
    symbol_max_length: int = 15
    symbol_min_length: int = 1


settings = Settings()
