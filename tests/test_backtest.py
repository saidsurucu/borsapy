"""Tests for the Backtest Engine module."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from borsapy.backtest import Backtest, BacktestResult, Trade, backtest
from borsapy.exceptions import APIError

# ============================================================================
# Trade Tests
# ============================================================================


class TestTrade:
    """Tests for Trade dataclass."""

    def test_trade_creation(self):
        """Test basic trade creation."""
        trade = Trade(
            entry_time=datetime(2024, 1, 1, 10, 0),
            entry_price=100.0,
            side="long",
            shares=10,
        )
        assert trade.entry_price == 100.0
        assert trade.side == "long"
        assert trade.shares == 10
        assert trade.exit_time is None
        assert trade.exit_price is None

    def test_trade_is_closed(self):
        """Test is_closed property."""
        # Open trade
        open_trade = Trade(
            entry_time=datetime(2024, 1, 1, 10, 0),
            entry_price=100.0,
            shares=10,
        )
        assert not open_trade.is_closed

        # Closed trade
        closed_trade = Trade(
            entry_time=datetime(2024, 1, 1, 10, 0),
            entry_price=100.0,
            exit_time=datetime(2024, 1, 2, 10, 0),
            exit_price=110.0,
            shares=10,
        )
        assert closed_trade.is_closed

    def test_trade_profit_long(self):
        """Test profit calculation for long trades."""
        trade = Trade(
            entry_time=datetime(2024, 1, 1, 10, 0),
            entry_price=100.0,
            exit_time=datetime(2024, 1, 2, 10, 0),
            exit_price=110.0,
            side="long",
            shares=10,
            commission=5.0,
        )
        # Profit = (110 - 100) * 10 - 5 = 95
        assert trade.profit == 95.0

    def test_trade_profit_short(self):
        """Test profit calculation for short trades."""
        trade = Trade(
            entry_time=datetime(2024, 1, 1, 10, 0),
            entry_price=100.0,
            exit_time=datetime(2024, 1, 2, 10, 0),
            exit_price=90.0,
            side="short",
            shares=10,
            commission=5.0,
        )
        # Profit = (100 - 90) * 10 - 5 = 95
        assert trade.profit == 95.0

    def test_trade_profit_open_returns_none(self):
        """Test that open trades return None for profit."""
        trade = Trade(
            entry_time=datetime(2024, 1, 1, 10, 0),
            entry_price=100.0,
            shares=10,
        )
        assert trade.profit is None

    def test_trade_profit_pct(self):
        """Test profit percentage calculation."""
        trade = Trade(
            entry_time=datetime(2024, 1, 1, 10, 0),
            entry_price=100.0,
            exit_time=datetime(2024, 1, 2, 10, 0),
            exit_price=110.0,
            side="long",
            shares=10,
            commission=0.0,
        )
        # Profit% = 100 / 1000 * 100 = 10%
        assert trade.profit_pct == 10.0

    def test_trade_duration(self):
        """Test trade duration calculation."""
        trade = Trade(
            entry_time=datetime(2024, 1, 1, 10, 0),
            entry_price=100.0,
            exit_time=datetime(2024, 1, 3, 10, 0),
            exit_price=110.0,
            shares=10,
        )
        # duration returns float (days)
        assert trade.duration == 2.0


# ============================================================================
# BacktestResult Tests
# ============================================================================


class TestBacktestResult:
    """Tests for BacktestResult dataclass."""

    @pytest.fixture
    def sample_result(self) -> BacktestResult:
        """Create a sample backtest result for testing."""
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        # Deterministic equity curve that ends at 101970 (100000 + 1970)
        # to match the trade profits
        equity = pd.Series(
            np.linspace(100000, 101970, 100), index=dates
        )
        drawdown = pd.Series(np.zeros(100) * -0.01, index=dates)
        buy_hold = pd.Series(
            np.linspace(100000, 100500, 100), index=dates
        )

        trades = [
            Trade(
                entry_time=datetime(2024, 1, 10),
                entry_price=100,
                exit_time=datetime(2024, 1, 20),
                exit_price=110,
                side="long",
                shares=100,
                commission=10,
            ),
            Trade(
                entry_time=datetime(2024, 2, 1),
                entry_price=105,
                exit_time=datetime(2024, 2, 10),
                exit_price=100,
                side="long",
                shares=100,
                commission=10,
            ),
            Trade(
                entry_time=datetime(2024, 3, 1),
                entry_price=100,
                exit_time=datetime(2024, 3, 15),
                exit_price=115,
                side="long",
                shares=100,
                commission=10,
            ),
        ]

        return BacktestResult(
            symbol="THYAO",
            period="1y",
            interval="1d",
            strategy_name="test_strategy",
            initial_capital=100000,
            commission=0.001,
            trades=trades,
            equity_curve=equity,
            drawdown_curve=drawdown,
            buy_hold_curve=buy_hold,
        )

    def test_net_profit(self, sample_result):
        """Test net profit calculation."""
        assert sample_result.net_profit is not None
        # Trade 1: (110-100)*100 - 10 = 990
        # Trade 2: (100-105)*100 - 10 = -510
        # Trade 3: (115-100)*100 - 10 = 1490
        # Total: 990 - 510 + 1490 = 1970
        assert sample_result.net_profit == 1970

    def test_net_profit_pct(self, sample_result):
        """Test net profit percentage."""
        assert sample_result.net_profit_pct is not None
        # 1970 / 100000 * 100 = 1.97%
        assert abs(sample_result.net_profit_pct - 1.97) < 0.01

    def test_total_trades(self, sample_result):
        """Test total trades count."""
        assert sample_result.total_trades == 3

    def test_winning_losing_trades(self, sample_result):
        """Test winning/losing trade counts."""
        assert sample_result.winning_trades == 2
        assert sample_result.losing_trades == 1

    def test_win_rate(self, sample_result):
        """Test win rate calculation."""
        # 2 winning / 3 total = 66.67%
        assert abs(sample_result.win_rate - 66.67) < 0.1

    def test_profit_factor(self, sample_result):
        """Test profit factor calculation."""
        # Gross profit: 990 + 1490 = 2480
        # Gross loss: 510
        # Profit factor: 2480 / 510 = 4.86
        assert sample_result.profit_factor > 0

    def test_avg_trade(self, sample_result):
        """Test average trade calculation."""
        # Total profit: 1970, trades: 3
        assert abs(sample_result.avg_trade - 656.67) < 1

    def test_avg_winning_trade(self, sample_result):
        """Test average winning trade."""
        # (990 + 1490) / 2 = 1240
        assert abs(sample_result.avg_winning_trade - 1240) < 1

    def test_avg_losing_trade(self, sample_result):
        """Test average losing trade."""
        # -510 / 1 = -510
        assert abs(sample_result.avg_losing_trade - (-510)) < 1

    def test_trades_df(self, sample_result):
        """Test trades DataFrame generation."""
        df = sample_result.trades_df
        assert len(df) == 3
        assert "entry_time" in df.columns
        assert "exit_time" in df.columns
        assert "profit" in df.columns
        assert "profit_pct" in df.columns

    def test_to_dict(self, sample_result):
        """Test dict conversion."""
        d = sample_result.to_dict()
        assert d["symbol"] == "THYAO"
        assert d["total_trades"] == 3
        assert "net_profit" in d
        assert "sharpe_ratio" in d

    def test_summary(self, sample_result):
        """Test summary generation."""
        summary = sample_result.summary()
        assert "THYAO" in summary
        assert "Total Trades" in summary
        assert "Win Rate" in summary


class TestBacktestResultEdgeCases:
    """Test edge cases for BacktestResult."""

    def test_empty_trades(self):
        """Test result with no trades."""
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        result = BacktestResult(
            symbol="THYAO",
            period="1y",
            interval="1d",
            strategy_name="no_trades",
            initial_capital=100000,
            commission=0.001,
            trades=[],
            equity_curve=pd.Series([100000] * 10, index=dates),
            drawdown_curve=pd.Series([0.0] * 10, index=dates),
            buy_hold_curve=pd.Series([100000] * 10, index=dates),
        )
        assert result.total_trades == 0
        assert result.net_profit == 0
        assert result.win_rate == 0.0

    def test_single_winning_trade(self):
        """Test result with single winning trade."""
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        trades = [
            Trade(
                entry_time=datetime(2024, 1, 2),
                entry_price=100,
                exit_time=datetime(2024, 1, 5),
                exit_price=110,
                shares=100,
                commission=0,
            )
        ]
        result = BacktestResult(
            symbol="THYAO",
            period="1y",
            interval="1d",
            strategy_name="single_trade",
            initial_capital=100000,
            commission=0,
            trades=trades,
            equity_curve=pd.Series([100000] * 10, index=dates),
            drawdown_curve=pd.Series([0.0] * 10, index=dates),
            buy_hold_curve=pd.Series([100000] * 10, index=dates),
        )
        assert result.total_trades == 1
        assert result.winning_trades == 1
        assert result.losing_trades == 0
        assert result.win_rate == 100.0


# ============================================================================
# Backtest Class Tests
# ============================================================================


class TestBacktest:
    """Tests for Backtest class."""

    @pytest.fixture
    def mock_history(self) -> pd.DataFrame:
        """Create mock historical data."""
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        data = {
            "Open": np.random.rand(100) * 10 + 95,
            "High": np.random.rand(100) * 10 + 100,
            "Low": np.random.rand(100) * 10 + 90,
            "Close": np.random.rand(100) * 10 + 95,
            "Volume": np.random.randint(1000000, 5000000, 100),
        }
        return pd.DataFrame(data, index=dates)

    def test_backtest_initialization(self):
        """Test Backtest initialization."""

        def my_strategy(candle, position, indicators):
            return "HOLD"

        bt = Backtest(
            symbol="THYAO",
            strategy=my_strategy,
            period="1y",
            capital=100000,
            commission=0.001,
        )
        assert bt.symbol == "THYAO"
        assert bt.period == "1y"
        assert bt.capital == 100000
        assert bt.commission == 0.001

    @patch("borsapy.ticker.Ticker")
    def test_backtest_run_simple(self, mock_ticker_class, mock_history):
        """Test simple backtest run."""
        # Setup mock
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_history
        mock_ticker_class.return_value = mock_ticker

        def hold_strategy(candle, position, indicators):
            return "HOLD"

        bt = Backtest(
            symbol="THYAO",
            strategy=hold_strategy,
            period="1y",
            capital=100000,
        )
        result = bt.run()

        assert isinstance(result, BacktestResult)
        assert result.symbol == "THYAO"
        assert result.total_trades == 0  # HOLD strategy = no trades

    @patch("borsapy.ticker.Ticker")
    def test_backtest_buy_sell_strategy(self, mock_ticker_class, mock_history):
        """Test backtest with buy/sell signals."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_history
        mock_ticker_class.return_value = mock_ticker

        # Simple alternating strategy
        call_count = [0]

        def alternating_strategy(candle, position, indicators):
            call_count[0] += 1
            if call_count[0] % 20 == 0 and position is None:
                return "BUY"
            elif call_count[0] % 20 == 10 and position == "long":
                return "SELL"
            return "HOLD"

        bt = Backtest(
            symbol="THYAO",
            strategy=alternating_strategy,
            period="1y",
            capital=100000,
        )
        result = bt.run()

        assert isinstance(result, BacktestResult)
        # Should have some trades with alternating strategy

    @patch("borsapy.ticker.Ticker")
    def test_backtest_with_indicators(self, mock_ticker_class, mock_history):
        """Test backtest with technical indicators."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_history
        mock_ticker_class.return_value = mock_ticker

        def indicator_strategy(candle, position, indicators):
            if "rsi" in indicators and indicators["rsi"] is not None:
                if indicators["rsi"] < 30 and position is None:
                    return "BUY"
                elif indicators["rsi"] > 70 and position == "long":
                    return "SELL"
            return "HOLD"

        bt = Backtest(
            symbol="THYAO",
            strategy=indicator_strategy,
            period="1y",
            capital=100000,
            indicators=["rsi"],
        )
        result = bt.run()

        assert isinstance(result, BacktestResult)

    def test_backtest_invalid_symbol(self):
        """Test backtest with invalid symbol."""

        def my_strategy(candle, position, indicators):
            return "HOLD"

        bt = Backtest(
            symbol="INVALID_SYMBOL_12345",
            strategy=my_strategy,
            period="1y",
        )
        # Should raise error on run (ValueError for no data, APIError for invalid symbol)
        with pytest.raises((ValueError, APIError)):
            bt.run()


# ============================================================================
# Convenience Function Tests
# ============================================================================


class TestBacktestFunction:
    """Tests for backtest() convenience function."""

    @patch("borsapy.ticker.Ticker")
    def test_backtest_function(self, mock_ticker_class):
        """Test backtest() convenience function."""
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        mock_history = pd.DataFrame(
            {
                "Open": [100] * 100,
                "High": [105] * 100,
                "Low": [95] * 100,
                "Close": [102] * 100,
                "Volume": [1000000] * 100,
            },
            index=dates,
        )

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_history
        mock_ticker_class.return_value = mock_ticker

        def my_strategy(candle, position, indicators):
            return "HOLD"

        result = backtest("THYAO", my_strategy, period="1y")
        assert isinstance(result, BacktestResult)


# ============================================================================
# Strategy Edge Cases
# ============================================================================


class TestStrategyEdgeCases:
    """Test edge cases in strategy execution."""

    @pytest.fixture
    def mock_history(self) -> pd.DataFrame:
        """Create mock historical data."""
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        return pd.DataFrame(
            {
                "Open": [100.0] * 100,
                "High": [105.0] * 100,
                "Low": [95.0] * 100,
                "Close": [102.0] * 100,
                "Volume": [1000000] * 100,
            },
            index=dates,
        )

    @patch("borsapy.ticker.Ticker")
    def test_strategy_returns_none(self, mock_ticker_class, mock_history):
        """Test strategy that returns None."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_history
        mock_ticker_class.return_value = mock_ticker

        def none_strategy(candle, position, indicators):
            return None

        bt = Backtest(symbol="THYAO", strategy=none_strategy, period="1y")
        result = bt.run()
        assert result.total_trades == 0

    @patch("borsapy.ticker.Ticker")
    def test_strategy_with_exception(self, mock_ticker_class, mock_history):
        """Test strategy that raises exception is handled gracefully."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_history
        mock_ticker_class.return_value = mock_ticker

        def bad_strategy(candle, position, indicators):
            raise ValueError("Strategy error")

        bt = Backtest(symbol="THYAO", strategy=bad_strategy, period="1y")
        # Strategy exceptions are caught and treated as HOLD
        result = bt.run()
        assert result.total_trades == 0


# ============================================================================
# Integration Tests
# ============================================================================


class TestBacktestIntegration:
    """Integration tests for backtest module."""

    @pytest.mark.skip(reason="Integration test - requires network")
    def test_real_backtest(self):
        """Test backtest with real data."""

        def simple_strategy(candle, position, indicators):
            if position is None and candle["close"] < candle["open"]:
                return "BUY"
            elif position == "long" and candle["close"] > candle["open"]:
                return "SELL"
            return "HOLD"

        result = backtest("THYAO", simple_strategy, period="3mo")

        assert isinstance(result, BacktestResult)
        assert result.symbol == "THYAO"
        assert len(result.equity_curve) > 0

    @pytest.mark.skip(reason="Integration test - requires network")
    def test_real_backtest_with_indicators(self):
        """Test backtest with real data and indicators."""

        def rsi_strategy(candle, position, indicators):
            rsi = indicators.get("rsi")
            if rsi is None:
                return "HOLD"
            if rsi < 30 and position is None:
                return "BUY"
            elif rsi > 70 and position == "long":
                return "SELL"
            return "HOLD"

        result = backtest(
            "THYAO", rsi_strategy, period="3mo", indicators=["rsi"]
        )

        assert isinstance(result, BacktestResult)
        assert result.symbol == "THYAO"
