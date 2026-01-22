"""
Backtest Engine for trading strategy evaluation.

This module provides a framework for backtesting trading strategies
on historical OHLCV data with comprehensive performance metrics.

Features:
- Strategy function interface
- Technical indicator integration
- Performance metrics (Sharpe, Sortino, Profit Factor)
- Trade tracking and analysis
- Equity curve generation
- Buy & Hold comparison

Examples:
    >>> import borsapy as bp

    >>> def rsi_strategy(candle, position, indicators):
    ...     if indicators['rsi'] < 30 and position is None:
    ...         return 'BUY'
    ...     elif indicators['rsi'] > 70 and position == 'long':
    ...         return 'SELL'
    ...     return 'HOLD'

    >>> result = bp.backtest("THYAO", rsi_strategy, period="1y")
    >>> print(result.summary())
    >>> print(f"Sharpe: {result.sharpe_ratio:.2f}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Literal

import numpy as np
import pandas as pd

__all__ = ["Trade", "BacktestResult", "Backtest", "backtest"]


# Strategy signal types
Signal = Literal["BUY", "SELL", "HOLD"] | None
Position = Literal["long", "short"] | None

# Strategy function signature
StrategyFunc = Callable[[dict, Position, dict], Signal]


@dataclass
class Trade:
    """
    Represents a single trade in a backtest.

    Attributes:
        entry_time: When the trade was opened.
        entry_price: Price at entry.
        exit_time: When the trade was closed (None if open).
        exit_price: Price at exit (None if open).
        side: Trade direction ('long' or 'short').
        shares: Number of shares traded.
        commission: Total commission paid (entry + exit).
    """

    entry_time: datetime
    entry_price: float
    exit_time: datetime | None = None
    exit_price: float | None = None
    side: Literal["long", "short"] = "long"
    shares: float = 0.0
    commission: float = 0.0

    @property
    def is_closed(self) -> bool:
        """Check if trade is closed."""
        return self.exit_time is not None and self.exit_price is not None

    @property
    def profit(self) -> float | None:
        """Calculate profit in currency units (None if open)."""
        if not self.is_closed:
            return None
        assert self.exit_price is not None
        if self.side == "long":
            gross = (self.exit_price - self.entry_price) * self.shares
        else:
            gross = (self.entry_price - self.exit_price) * self.shares
        return gross - self.commission

    @property
    def profit_pct(self) -> float | None:
        """Calculate profit as percentage (None if open)."""
        if not self.is_closed or self.entry_price == 0:
            return None
        profit = self.profit
        if profit is None:
            return None
        entry_value = self.entry_price * self.shares
        return (profit / entry_value) * 100

    @property
    def duration(self) -> float | None:
        """Trade duration in days (None if open)."""
        if not self.is_closed:
            return None
        assert self.exit_time is not None
        delta = self.exit_time - self.entry_time
        return delta.total_seconds() / 86400  # Convert to days

    def to_dict(self) -> dict[str, Any]:
        """Convert trade to dictionary."""
        return {
            "entry_time": self.entry_time,
            "entry_price": self.entry_price,
            "exit_time": self.exit_time,
            "exit_price": self.exit_price,
            "side": self.side,
            "shares": self.shares,
            "commission": self.commission,
            "profit": self.profit,
            "profit_pct": self.profit_pct,
            "duration": self.duration,
        }


@dataclass
class BacktestResult:
    """
    Comprehensive backtest results with performance metrics.

    Follows TradingView/Mathieu2301 result format for familiarity.

    Attributes:
        symbol: Traded symbol.
        period: Test period (e.g., "1y").
        interval: Data interval (e.g., "1d").
        strategy_name: Name of the strategy function.
        initial_capital: Starting capital.
        commission: Commission rate used.
        trades: List of executed trades.
        equity_curve: Daily equity values.
        drawdown_curve: Daily drawdown values.
        buy_hold_curve: Buy & hold comparison values.
    """

    # Identification
    symbol: str
    period: str
    interval: str
    strategy_name: str

    # Configuration
    initial_capital: float
    commission: float

    # Results
    trades: list[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    drawdown_curve: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    buy_hold_curve: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))

    # === Performance Properties ===

    @property
    def final_equity(self) -> float:
        """Final portfolio value."""
        if self.equity_curve.empty:
            return self.initial_capital
        return float(self.equity_curve.iloc[-1])

    @property
    def net_profit(self) -> float:
        """Net profit in currency units."""
        return self.final_equity - self.initial_capital

    @property
    def net_profit_pct(self) -> float:
        """Net profit as percentage."""
        if self.initial_capital == 0:
            return 0.0
        return (self.net_profit / self.initial_capital) * 100

    @property
    def total_trades(self) -> int:
        """Total number of closed trades."""
        return len([t for t in self.trades if t.is_closed])

    @property
    def winning_trades(self) -> int:
        """Number of profitable trades."""
        return len([t for t in self.trades if t.is_closed and (t.profit or 0) > 0])

    @property
    def losing_trades(self) -> int:
        """Number of losing trades."""
        return len([t for t in self.trades if t.is_closed and (t.profit or 0) <= 0])

    @property
    def win_rate(self) -> float:
        """Percentage of winning trades."""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100

    @property
    def profit_factor(self) -> float:
        """Ratio of gross profits to gross losses."""
        gross_profit = sum(t.profit or 0 for t in self.trades if t.is_closed and (t.profit or 0) > 0)
        gross_loss = abs(sum(t.profit or 0 for t in self.trades if t.is_closed and (t.profit or 0) < 0))
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    @property
    def avg_trade(self) -> float:
        """Average profit per trade."""
        closed = [t for t in self.trades if t.is_closed]
        if not closed:
            return 0.0
        return sum(t.profit or 0 for t in closed) / len(closed)

    @property
    def avg_winning_trade(self) -> float:
        """Average profit of winning trades."""
        winners = [t for t in self.trades if t.is_closed and (t.profit or 0) > 0]
        if not winners:
            return 0.0
        return sum(t.profit or 0 for t in winners) / len(winners)

    @property
    def avg_losing_trade(self) -> float:
        """Average loss of losing trades."""
        losers = [t for t in self.trades if t.is_closed and (t.profit or 0) < 0]
        if not losers:
            return 0.0
        return sum(t.profit or 0 for t in losers) / len(losers)

    @property
    def max_consecutive_wins(self) -> int:
        """Maximum consecutive winning trades."""
        return self._max_consecutive(lambda t: (t.profit or 0) > 0)

    @property
    def max_consecutive_losses(self) -> int:
        """Maximum consecutive losing trades."""
        return self._max_consecutive(lambda t: (t.profit or 0) <= 0)

    def _max_consecutive(self, condition: Callable[[Trade], bool]) -> int:
        """Helper to find max consecutive trades matching condition."""
        closed = [t for t in self.trades if t.is_closed]
        if not closed:
            return 0
        max_count = 0
        current_count = 0
        for trade in closed:
            if condition(trade):
                current_count += 1
                max_count = max(max_count, current_count)
            else:
                current_count = 0
        return max_count

    @property
    def sharpe_ratio(self) -> float:
        """
        Sharpe ratio (risk-adjusted return).

        Assumes 252 trading days and risk-free rate from current 10Y bond.
        """
        if self.equity_curve.empty or len(self.equity_curve) < 2:
            return float("nan")

        returns = self.equity_curve.pct_change().dropna()
        if returns.std() == 0:
            return float("nan")

        # Get risk-free rate
        try:
            from borsapy.bond import risk_free_rate

            rf_annual = risk_free_rate()
        except Exception:
            rf_annual = 0.30  # Fallback 30%

        rf_daily = rf_annual / 252
        excess_returns = returns - rf_daily
        return float(np.sqrt(252) * excess_returns.mean() / excess_returns.std())

    @property
    def sortino_ratio(self) -> float:
        """
        Sortino ratio (downside risk-adjusted return).

        Uses downside deviation instead of standard deviation.
        """
        if self.equity_curve.empty or len(self.equity_curve) < 2:
            return float("nan")

        returns = self.equity_curve.pct_change().dropna()

        # Get risk-free rate
        try:
            from borsapy.bond import risk_free_rate

            rf_annual = risk_free_rate()
        except Exception:
            rf_annual = 0.30

        rf_daily = rf_annual / 252
        excess_returns = returns - rf_daily
        negative_returns = excess_returns[excess_returns < 0]

        if len(negative_returns) == 0 or negative_returns.std() == 0:
            return float("inf") if excess_returns.mean() > 0 else float("nan")

        downside_std = negative_returns.std()
        return float(np.sqrt(252) * excess_returns.mean() / downside_std)

    @property
    def max_drawdown(self) -> float:
        """Maximum drawdown as percentage."""
        if self.drawdown_curve.empty:
            return 0.0
        return float(self.drawdown_curve.min()) * 100

    @property
    def max_drawdown_duration(self) -> int:
        """Maximum drawdown duration in days."""
        if self.equity_curve.empty:
            return 0

        # Find periods where we're in drawdown
        running_max = self.equity_curve.cummax()
        in_drawdown = self.equity_curve < running_max

        max_duration = 0
        current_duration = 0

        for is_dd in in_drawdown:
            if is_dd:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:
                current_duration = 0

        return max_duration

    @property
    def buy_hold_return(self) -> float:
        """Buy & hold return as percentage."""
        if self.buy_hold_curve.empty:
            return 0.0
        first = self.buy_hold_curve.iloc[0]
        last = self.buy_hold_curve.iloc[-1]
        if first == 0:
            return 0.0
        return ((last - first) / first) * 100

    @property
    def vs_buy_hold(self) -> float:
        """Strategy outperformance vs buy & hold (percentage points)."""
        return self.net_profit_pct - self.buy_hold_return

    @property
    def calmar_ratio(self) -> float:
        """Calmar ratio (annualized return / max drawdown)."""
        if self.max_drawdown == 0:
            return float("inf") if self.net_profit_pct > 0 else 0.0
        # Annualize return (assuming 252 trading days)
        trading_days = len(self.equity_curve)
        if trading_days == 0:
            return 0.0
        annual_return = self.net_profit_pct * (252 / trading_days)
        return annual_return / abs(self.max_drawdown)

    # === Export Methods ===

    @property
    def trades_df(self) -> pd.DataFrame:
        """Get trades as DataFrame."""
        if not self.trades:
            return pd.DataFrame(
                columns=[
                    "entry_time",
                    "entry_price",
                    "exit_time",
                    "exit_price",
                    "side",
                    "shares",
                    "commission",
                    "profit",
                    "profit_pct",
                    "duration",
                ]
            )
        return pd.DataFrame([t.to_dict() for t in self.trades])

    def to_dict(self) -> dict[str, Any]:
        """
        Export results to dictionary.

        Compatible with TradingView/Mathieu2301 format.
        """
        return {
            # Identification
            "symbol": self.symbol,
            "period": self.period,
            "interval": self.interval,
            "strategy_name": self.strategy_name,
            # Configuration
            "initial_capital": self.initial_capital,
            "commission": self.commission,
            # Summary
            "net_profit": round(self.net_profit, 2),
            "net_profit_pct": round(self.net_profit_pct, 2),
            "final_equity": round(self.final_equity, 2),
            # Trade Statistics
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 2),
            "profit_factor": round(self.profit_factor, 2) if self.profit_factor != float("inf") else "inf",
            "avg_trade": round(self.avg_trade, 2),
            "avg_winning_trade": round(self.avg_winning_trade, 2),
            "avg_losing_trade": round(self.avg_losing_trade, 2),
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
            # Risk Metrics
            "sharpe_ratio": round(self.sharpe_ratio, 2) if not np.isnan(self.sharpe_ratio) else None,
            "sortino_ratio": round(self.sortino_ratio, 2) if not np.isnan(self.sortino_ratio) and self.sortino_ratio != float("inf") else None,
            "calmar_ratio": round(self.calmar_ratio, 2) if self.calmar_ratio != float("inf") else None,
            "max_drawdown": round(self.max_drawdown, 2),
            "max_drawdown_duration": self.max_drawdown_duration,
            # Comparison
            "buy_hold_return": round(self.buy_hold_return, 2),
            "vs_buy_hold": round(self.vs_buy_hold, 2),
        }

    def summary(self) -> str:
        """
        Generate human-readable performance summary.

        Returns:
            Formatted summary string.
        """
        d = self.to_dict()

        lines = [
            "=" * 60,
            f"BACKTEST RESULTS: {d['symbol']} ({d['strategy_name']})",
            "=" * 60,
            f"Period: {d['period']} | Interval: {d['interval']}",
            f"Initial Capital: {d['initial_capital']:,.2f} TL",
            f"Commission: {d['commission']*100:.2f}%",
            "",
            "--- PERFORMANCE ---",
            f"Net Profit: {d['net_profit']:,.2f} TL ({d['net_profit_pct']:+.2f}%)",
            f"Final Equity: {d['final_equity']:,.2f} TL",
            f"Buy & Hold: {d['buy_hold_return']:+.2f}%",
            f"vs B&H: {d['vs_buy_hold']:+.2f}%",
            "",
            "--- TRADE STATISTICS ---",
            f"Total Trades: {d['total_trades']}",
            f"Winning: {d['winning_trades']} | Losing: {d['losing_trades']}",
            f"Win Rate: {d['win_rate']:.1f}%",
            f"Profit Factor: {d['profit_factor']}",
            f"Avg Trade: {d['avg_trade']:,.2f} TL",
            f"Avg Winner: {d['avg_winning_trade']:,.2f} TL | Avg Loser: {d['avg_losing_trade']:,.2f} TL",
            f"Max Consecutive Wins: {d['max_consecutive_wins']} | Losses: {d['max_consecutive_losses']}",
            "",
            "--- RISK METRICS ---",
            f"Sharpe Ratio: {d['sharpe_ratio'] if d['sharpe_ratio'] else 'N/A'}",
            f"Sortino Ratio: {d['sortino_ratio'] if d['sortino_ratio'] else 'N/A'}",
            f"Calmar Ratio: {d['calmar_ratio'] if d['calmar_ratio'] else 'N/A'}",
            f"Max Drawdown: {d['max_drawdown']:.2f}%",
            f"Max DD Duration: {d['max_drawdown_duration']} days",
            "=" * 60,
        ]

        return "\n".join(lines)


class Backtest:
    """
    Backtest engine for evaluating trading strategies.

    Runs a strategy function over historical data and calculates
    comprehensive performance metrics.

    Attributes:
        symbol: Stock symbol to backtest.
        strategy: Strategy function to evaluate.
        period: Historical data period.
        interval: Data interval (e.g., "1d", "1h").
        capital: Initial capital.
        commission: Commission rate per trade (e.g., 0.001 = 0.1%).
        indicators: List of indicators to calculate.

    Examples:
        >>> def my_strategy(candle, position, indicators):
        ...     if indicators['rsi'] < 30:
        ...         return 'BUY'
        ...     elif indicators['rsi'] > 70:
        ...         return 'SELL'
        ...     return 'HOLD'

        >>> bt = Backtest("THYAO", my_strategy, period="1y")
        >>> result = bt.run()
        >>> print(result.sharpe_ratio)
    """

    # Indicator period warmup
    WARMUP_PERIOD = 50

    def __init__(
        self,
        symbol: str,
        strategy: StrategyFunc,
        period: str = "1y",
        interval: str = "1d",
        capital: float = 100_000.0,
        commission: float = 0.001,
        indicators: list[str] | None = None,
        slippage: float = 0.0,  # Future use
    ):
        """
        Initialize Backtest.

        Args:
            symbol: Stock symbol (e.g., "THYAO").
            strategy: Strategy function with signature:
                      strategy(candle, position, indicators) -> 'BUY'|'SELL'|'HOLD'|None
            period: Historical data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y).
            interval: Data interval (1m, 5m, 15m, 30m, 1h, 4h, 1d).
            capital: Initial capital in TL.
            commission: Commission rate per trade (0.001 = 0.1%).
            indicators: List of indicators to calculate. Options:
                       'rsi', 'rsi_7', 'sma_20', 'sma_50', 'sma_200',
                       'ema_12', 'ema_26', 'ema_50', 'macd', 'bollinger',
                       'atr', 'atr_20', 'stochastic', 'adx'
            slippage: Slippage per trade (for future use).
        """
        self.symbol = symbol.upper()
        self.strategy = strategy
        self.period = period
        self.interval = interval
        self.capital = capital
        self.commission = commission
        self.indicators = indicators or ["rsi", "sma_20", "ema_12", "macd"]
        self.slippage = slippage

        # Strategy name for reporting
        self._strategy_name = getattr(strategy, "__name__", "custom_strategy")

        # Data storage
        self._df: pd.DataFrame | None = None
        self._df_with_indicators: pd.DataFrame | None = None

    def _load_data(self) -> pd.DataFrame:
        """Load historical data from Ticker."""
        from borsapy.ticker import Ticker

        ticker = Ticker(self.symbol)
        df = ticker.history(period=self.period, interval=self.interval)

        if df is None or df.empty:
            raise ValueError(f"No historical data available for {self.symbol}")

        return df

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add indicator columns to DataFrame."""
        from borsapy.technical import (
            calculate_adx,
            calculate_atr,
            calculate_bollinger_bands,
            calculate_ema,
            calculate_macd,
            calculate_rsi,
            calculate_sma,
            calculate_stochastic,
        )

        result = df.copy()

        for ind in self.indicators:
            ind_lower = ind.lower()

            # RSI variants
            if ind_lower == "rsi":
                result["rsi"] = calculate_rsi(df, period=14)
            elif ind_lower.startswith("rsi_"):
                try:
                    period = int(ind_lower.split("_")[1])
                    result[f"rsi_{period}"] = calculate_rsi(df, period=period)
                except (IndexError, ValueError):
                    pass

            # SMA variants
            elif ind_lower.startswith("sma_"):
                try:
                    period = int(ind_lower.split("_")[1])
                    result[f"sma_{period}"] = calculate_sma(df, period=period)
                except (IndexError, ValueError):
                    pass

            # EMA variants
            elif ind_lower.startswith("ema_"):
                try:
                    period = int(ind_lower.split("_")[1])
                    result[f"ema_{period}"] = calculate_ema(df, period=period)
                except (IndexError, ValueError):
                    pass

            # MACD
            elif ind_lower == "macd":
                macd_df = calculate_macd(df)
                result["macd"] = macd_df["MACD"]
                result["macd_signal"] = macd_df["Signal"]
                result["macd_histogram"] = macd_df["Histogram"]

            # Bollinger Bands
            elif ind_lower in ("bollinger", "bb"):
                bb_df = calculate_bollinger_bands(df)
                result["bb_upper"] = bb_df["BB_Upper"]
                result["bb_middle"] = bb_df["BB_Middle"]
                result["bb_lower"] = bb_df["BB_Lower"]

            # ATR variants
            elif ind_lower == "atr":
                result["atr"] = calculate_atr(df, period=14)
            elif ind_lower.startswith("atr_"):
                try:
                    period = int(ind_lower.split("_")[1])
                    result[f"atr_{period}"] = calculate_atr(df, period=period)
                except (IndexError, ValueError):
                    pass

            # Stochastic
            elif ind_lower in ("stochastic", "stoch"):
                stoch_df = calculate_stochastic(df)
                result["stoch_k"] = stoch_df["Stoch_K"]
                result["stoch_d"] = stoch_df["Stoch_D"]

            # ADX
            elif ind_lower == "adx":
                result["adx"] = calculate_adx(df, period=14)

        return result

    def _get_indicators_at(self, idx: int) -> dict[str, float]:
        """Get indicator values at specific index."""
        if self._df_with_indicators is None:
            return {}

        row = self._df_with_indicators.iloc[idx]
        indicators = {}

        # Extract all non-OHLCV columns as indicators
        exclude_cols = {"Open", "High", "Low", "Close", "Volume", "Adj Close"}

        for col in self._df_with_indicators.columns:
            if col not in exclude_cols:
                val = row[col]
                if pd.notna(val):
                    indicators[col] = float(val)

        return indicators

    def _build_candle(self, idx: int) -> dict[str, Any]:
        """Build candle dict from DataFrame row."""
        if self._df is None:
            return {}

        row = self._df.iloc[idx]
        timestamp = self._df.index[idx]

        if isinstance(timestamp, pd.Timestamp):
            timestamp = timestamp.to_pydatetime()

        return {
            "timestamp": timestamp,
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": float(row.get("Volume", 0)) if "Volume" in row else 0,
            "_index": idx,
        }

    def run(self) -> BacktestResult:
        """
        Run the backtest.

        Returns:
            BacktestResult with all performance metrics.

        Raises:
            ValueError: If no data available for symbol.
        """
        # Load data
        self._df = self._load_data()
        self._df_with_indicators = self._calculate_indicators(self._df)

        # Initialize state
        cash = self.capital
        position: Position = None
        shares = 0.0
        trades: list[Trade] = []
        current_trade: Trade | None = None

        # Track equity curve
        equity_values = []
        dates = []

        # Buy & hold tracking
        initial_price = self._df["Close"].iloc[self.WARMUP_PERIOD]
        bh_shares = self.capital / initial_price

        # Run simulation
        for idx in range(self.WARMUP_PERIOD, len(self._df)):
            candle = self._build_candle(idx)
            indicators = self._get_indicators_at(idx)
            price = candle["close"]
            timestamp = candle["timestamp"]

            # Get strategy signal
            try:
                signal = self.strategy(candle, position, indicators)
            except Exception:
                signal = "HOLD"

            # Execute trades
            if signal == "BUY" and position is None:
                # Calculate shares to buy (use all available cash)
                entry_commission = cash * self.commission
                available = cash - entry_commission
                shares = available / price

                current_trade = Trade(
                    entry_time=timestamp,
                    entry_price=price,
                    side="long",
                    shares=shares,
                    commission=entry_commission,
                )

                cash = 0.0
                position = "long"

            elif signal == "SELL" and position == "long" and current_trade is not None:
                # Close position
                exit_value = shares * price
                exit_commission = exit_value * self.commission

                current_trade.exit_time = timestamp
                current_trade.exit_price = price
                current_trade.commission += exit_commission

                trades.append(current_trade)

                cash = exit_value - exit_commission
                shares = 0.0
                position = None
                current_trade = None

            # Track equity
            if position == "long":
                equity = shares * price
            else:
                equity = cash

            equity_values.append(equity)
            dates.append(timestamp)

        # Close any open position at end
        if position == "long" and current_trade is not None:
            final_price = self._df["Close"].iloc[-1]
            exit_value = shares * final_price
            exit_commission = exit_value * self.commission

            current_trade.exit_time = self._df.index[-1]
            if isinstance(current_trade.exit_time, pd.Timestamp):
                current_trade.exit_time = current_trade.exit_time.to_pydatetime()
            current_trade.exit_price = final_price
            current_trade.commission += exit_commission

            trades.append(current_trade)

        # Build curves
        equity_curve = pd.Series(equity_values, index=pd.DatetimeIndex(dates))

        # Calculate drawdown curve
        running_max = equity_curve.cummax()
        drawdown_curve = (equity_curve - running_max) / running_max

        # Buy & hold curve
        bh_values = self._df["Close"].iloc[self.WARMUP_PERIOD:] * bh_shares
        buy_hold_curve = pd.Series(bh_values.values, index=pd.DatetimeIndex(dates))

        return BacktestResult(
            symbol=self.symbol,
            period=self.period,
            interval=self.interval,
            strategy_name=self._strategy_name,
            initial_capital=self.capital,
            commission=self.commission,
            trades=trades,
            equity_curve=equity_curve,
            drawdown_curve=drawdown_curve,
            buy_hold_curve=buy_hold_curve,
        )


def backtest(
    symbol: str,
    strategy: StrategyFunc,
    period: str = "1y",
    interval: str = "1d",
    capital: float = 100_000.0,
    commission: float = 0.001,
    indicators: list[str] | None = None,
) -> BacktestResult:
    """
    Run a backtest with a single function call.

    Convenience function that creates a Backtest instance and runs it.

    Args:
        symbol: Stock symbol (e.g., "THYAO").
        strategy: Strategy function with signature:
                  strategy(candle, position, indicators) -> 'BUY'|'SELL'|'HOLD'|None
        period: Historical data period.
        interval: Data interval.
        capital: Initial capital.
        commission: Commission rate.
        indicators: List of indicators to calculate.

    Returns:
        BacktestResult with all performance metrics.

    Examples:
        >>> def rsi_strategy(candle, position, indicators):
        ...     if indicators.get('rsi', 50) < 30 and position is None:
        ...         return 'BUY'
        ...     elif indicators.get('rsi', 50) > 70 and position == 'long':
        ...         return 'SELL'
        ...     return 'HOLD'

        >>> result = bp.backtest("THYAO", rsi_strategy, period="1y")
        >>> print(f"Net Profit: {result.net_profit_pct:.2f}%")
        >>> print(f"Sharpe: {result.sharpe_ratio:.2f}")
    """
    bt = Backtest(
        symbol=symbol,
        strategy=strategy,
        period=period,
        interval=interval,
        capital=capital,
        commission=commission,
        indicators=indicators,
    )
    return bt.run()
