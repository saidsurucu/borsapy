"""Custom exceptions for borsapy."""


class BorsapyError(Exception):
    """Base exception for all borsapy errors."""

    pass


class TickerNotFoundError(BorsapyError):
    """Raised when a ticker symbol is not found."""

    def __init__(self, symbol: str):
        self.symbol = symbol
        super().__init__(f"Ticker not found: {symbol}")


class DataNotAvailableError(BorsapyError):
    """Raised when requested data is not available."""

    def __init__(self, message: str = "Data not available"):
        super().__init__(message)


class APIError(BorsapyError):
    """Raised when an API request fails."""

    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(
            f"API Error: {message}" + (f" (status: {status_code})" if status_code else "")
        )


class AuthenticationError(BorsapyError):
    """Raised when authentication fails."""

    pass


class RateLimitError(BorsapyError):
    """Raised when rate limit is exceeded."""

    pass


class InvalidPeriodError(BorsapyError):
    """Raised when an invalid period is specified."""

    def __init__(self, period: str):
        self.period = period
        valid_periods = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]
        super().__init__(f"Invalid period: {period}. Valid periods: {', '.join(valid_periods)}")


class InvalidIntervalError(BorsapyError):
    """Raised when an invalid interval is specified."""

    def __init__(self, interval: str):
        self.interval = interval
        valid_intervals = ["1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"]
        super().__init__(
            f"Invalid interval: {interval}. Valid intervals: {', '.join(valid_intervals)}"
        )
