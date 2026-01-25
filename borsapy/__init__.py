"""
borsapy - Turkish Financial Markets Data Library

A yfinance-like API for BIST stocks, forex, crypto, funds, and economic data.

Examples:
    >>> import borsapy as bp

    # Get stock data
    >>> stock = bp.Ticker("THYAO")
    >>> stock.info  # Real-time quote
    >>> stock.history(period="1mo")  # OHLCV data
    >>> stock.balance_sheet  # Financial statements

    # Get forex/commodity data
    >>> usd = bp.FX("USD")
    >>> usd.current  # Current rate
    >>> usd.history(period="1mo")  # Historical data
    >>> usd.bank_rates  # Bank exchange rates
    >>> usd.bank_rate("akbank")  # Single bank rate
    >>> bp.banks()  # List supported banks
    >>> gold = bp.FX("gram-altin")

    # List all BIST companies
    >>> bp.companies()
    >>> bp.search_companies("banka")

    # Get crypto data
    >>> btc = bp.Crypto("BTCTRY")
    >>> btc.current  # Current price
    >>> btc.history(period="1mo")  # Historical OHLCV
    >>> bp.crypto_pairs()  # List available pairs

    # Get fund data
    >>> fund = bp.Fund("AAK")
    >>> fund.info  # Fund details
    >>> fund.history(period="1mo")  # Price history

    # Get inflation data
    >>> inf = bp.Inflation()
    >>> inf.latest()  # Latest TÜFE data
    >>> inf.calculate(100000, "2020-01", "2024-01")  # Inflation calculation

    # Economic calendar
    >>> cal = bp.EconomicCalendar()
    >>> cal.events(period="1w")  # This week's events
    >>> cal.today()  # Today's events
    >>> bp.economic_calendar(country="TR", importance="high")

    # Government bonds
    >>> bp.bonds()  # All bond yields
    >>> bond = bp.Bond("10Y")
    >>> bond.yield_rate  # Current 10Y yield
    >>> bp.risk_free_rate()  # For DCF calculations

    # Stock screener
    >>> bp.screen_stocks(template="high_dividend")
    >>> bp.screen_stocks(market_cap_min=1000, pe_max=15)
    >>> screener = bp.Screener()
    >>> screener.add_filter("dividend_yield", min=3).run()

    # Real-time streaming (low-latency)
    >>> stream = bp.TradingViewStream()
    >>> stream.connect()
    >>> stream.subscribe("THYAO")
    >>> quote = stream.get_quote("THYAO")  # Instant (~1ms)
    >>> quote['last']  # Last price
    >>> stream.disconnect()

    # Context manager
    >>> with bp.TradingViewStream() as stream:
    ...     stream.subscribe("THYAO")
    ...     quote = stream.wait_for_quote("THYAO")
    ...     print(quote['last'])

    # Symbol search
    >>> bp.search("banka")  # Search all markets
    >>> bp.search_bist("enerji")  # BIST only
    >>> bp.search_crypto("BTC")  # Crypto only
    >>> bp.search("THYAO", full_info=True)  # Detailed results

    # Heikin Ashi charts
    >>> df = stock.history(period="1y")
    >>> ha_df = bp.calculate_heikin_ashi(df)  # Returns HA_Open, HA_High, HA_Low, HA_Close
    >>> ha_df = stock.heikin_ashi(period="1y")  # Convenience method

    # Chart streaming (OHLCV candles via WebSocket)
    >>> stream = bp.TradingViewStream()
    >>> stream.connect()
    >>> stream.subscribe_chart("THYAO", "1m")  # 1-minute candles
    >>> candle = stream.get_candle("THYAO", "1m")
    >>> print(candle['close'])

    # Historical replay for backtesting
    >>> session = bp.create_replay("THYAO", period="1y", speed=100)
    >>> for candle in session.replay():
    ...     print(f"{candle['timestamp']}: {candle['close']}")

    # Backtest engine
    >>> def rsi_strategy(candle, position, indicators):
    ...     if indicators['rsi'] < 30 and position is None:
    ...         return 'BUY'
    ...     elif indicators['rsi'] > 70 and position == 'long':
    ...         return 'SELL'
    ...     return 'HOLD'
    >>> result = bp.backtest("THYAO", rsi_strategy, period="1y", indicators=['rsi'])
    >>> print(result.summary())
    >>> print(f"Win Rate: {result.win_rate:.1f}%")

    # Pine Script streaming indicators
    >>> stream = bp.TradingViewStream()
    >>> stream.connect()
    >>> stream.subscribe_chart("THYAO", "1m")
    >>> stream.add_study("THYAO", "1m", "RSI")
    >>> stream.add_study("THYAO", "1m", "MACD")
    >>> rsi = stream.get_study("THYAO", "1m", "RSI")
    >>> print(rsi['value'])
"""

# TradingView authentication for real-time data
from borsapy._providers.tradingview import (
    clear_tradingview_auth,
    get_tradingview_auth,
    set_tradingview_auth,
)
from borsapy.backtest import Backtest, BacktestResult, Trade, backtest
from borsapy.bond import Bond, bonds, risk_free_rate
from borsapy.calendar import EconomicCalendar, economic_calendar
from borsapy.charts import calculate_heikin_ashi
from borsapy.crypto import Crypto, crypto_pairs
from borsapy.eurobond import Eurobond, eurobonds
from borsapy.exceptions import (
    APIError,
    AuthenticationError,
    BorsapyError,
    DataNotAvailableError,
    InvalidIntervalError,
    InvalidPeriodError,
    RateLimitError,
    TickerNotFoundError,
)
from borsapy.fund import Fund, compare_funds, screen_funds, search_funds
from borsapy.fx import FX, banks, metal_institutions
from borsapy.index import Index, all_indices, index, indices
from borsapy.inflation import Inflation
from borsapy.market import companies, search_companies
from borsapy.multi import Tickers, download
from borsapy.portfolio import Portfolio
from borsapy.replay import ReplaySession, create_replay
from borsapy.scanner import ScanResult, TechnicalScanner, scan
from borsapy.screener import Screener, screen_stocks, screener_criteria, sectors, stock_indices
from borsapy.search import (
    search,
    search_bist,
    search_crypto,
    search_forex,
    search_index,
    search_viop,
    viop_contracts,
)

# TradingView streaming for real-time updates
from borsapy.stream import TradingViewStream, create_stream
from borsapy.tcmb import TCMB, policy_rate
from borsapy.technical import (
    TechnicalAnalyzer,
    add_indicators,
    calculate_adx,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_macd,
    calculate_obv,
    calculate_rsi,
    calculate_sma,
    calculate_stochastic,
    calculate_supertrend,
    calculate_tilson_t3,
    calculate_vwap,
)
from borsapy.ticker import Ticker
from borsapy.viop import VIOP

__version__ = "0.6.3"
__author__ = "Said Surucu"

__all__ = [
    # Main classes
    "Ticker",
    "Tickers",
    "FX",
    "Crypto",
    "Fund",
    "Portfolio",
    "Index",
    "Inflation",
    "VIOP",
    "Bond",
    "Eurobond",
    "TCMB",
    "EconomicCalendar",
    "Screener",
    "TradingViewStream",
    "ReplaySession",
    # Market functions
    "companies",
    "search_companies",
    "search",
    "search_bist",
    "search_crypto",
    "search_forex",
    "search_index",
    "search_viop",
    "viop_contracts",
    "banks",
    "metal_institutions",
    "crypto_pairs",
    "search_funds",
    "screen_funds",
    "compare_funds",
    "download",
    "index",
    "indices",
    "all_indices",
    # Bond functions
    "bonds",
    "risk_free_rate",
    # Eurobond functions
    "eurobonds",
    # TCMB functions
    "policy_rate",
    # Calendar functions
    "economic_calendar",
    # Screener functions
    "screen_stocks",
    "screener_criteria",
    "sectors",
    "stock_indices",
    # Technical Scanner
    "TechnicalScanner",
    "ScanResult",
    "scan",
    # Technical analysis
    "TechnicalAnalyzer",
    "add_indicators",
    "calculate_sma",
    "calculate_ema",
    "calculate_rsi",
    "calculate_macd",
    "calculate_bollinger_bands",
    "calculate_atr",
    "calculate_stochastic",
    "calculate_obv",
    "calculate_vwap",
    "calculate_adx",
    "calculate_supertrend",
    "calculate_tilson_t3",
    # Charts
    "calculate_heikin_ashi",
    # Replay
    "ReplaySession",
    "create_replay",
    # Exceptions
    "BorsapyError",
    "TickerNotFoundError",
    "DataNotAvailableError",
    "APIError",
    "AuthenticationError",
    "RateLimitError",
    "InvalidPeriodError",
    "InvalidIntervalError",
    # TradingView authentication (premium)
    "set_tradingview_auth",
    "get_tradingview_auth",
    "clear_tradingview_auth",
    # TradingView streaming (real-time)
    "TradingViewStream",
    "create_stream",
    # Backtest engine
    "Backtest",
    "BacktestResult",
    "Trade",
    "backtest",
]
