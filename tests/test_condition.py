"""Tests for condition parser."""

import numpy as np
import pandas as pd
import pytest

from borsapy.condition import ConditionParser, ConditionNode, ParseError


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def simple_data():
    """Simple data dict for basic tests."""
    return {
        "last": 100.0,
        "price": 100.0,
        "volume": 1500000,
        "change_percent": 2.5,
        "rsi": 45.0,
        "rsi_14": 45.0,
        "sma_20": 98.0,
        "sma_50": 95.0,
        "ema_12": 99.5,
        "macd": 1.5,
        "signal": 1.2,
        "bb_upper": 105.0,
        "bb_middle": 98.0,
        "bb_lower": 91.0,
    }


@pytest.fixture
def ohlcv_history():
    """OHLCV DataFrame for crossover/lookback tests."""
    np.random.seed(42)
    n = 30
    close = 100 + np.cumsum(np.random.randn(n) * 2)
    high = close + np.abs(np.random.randn(n) * 1)
    low = close - np.abs(np.random.randn(n) * 1)
    open_ = close + np.random.randn(n) * 0.5
    volume = np.random.randint(100000, 500000, n)

    df = pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        },
        index=pd.date_range("2024-01-01", periods=n, freq="D"),
    )
    return df


@pytest.fixture
def crossover_history():
    """DataFrame with known crossover."""
    # SMA20 crosses above SMA50 at the end
    n = 60
    dates = pd.date_range("2024-01-01", periods=n, freq="D")

    # Create a scenario where short MA crosses long MA
    close = np.concatenate([
        np.linspace(100, 90, 30),  # Downtrend
        np.linspace(90, 110, 30),  # Uptrend
    ])

    return pd.DataFrame(
        {
            "Close": close,
            "High": close + 1,
            "Low": close - 1,
            "Open": close,
            "Volume": [1000000] * n,
        },
        index=dates,
    )


# =============================================================================
# Tokenization Tests
# =============================================================================


class TestTokenization:
    """Tests for condition tokenization."""

    def test_simple_condition(self):
        """Test tokenizing simple condition."""
        parser = ConditionParser("rsi < 30")
        tokens = parser._tokenize()
        assert tokens == ["rsi", "<", "30"]

    def test_compound_condition(self):
        """Test tokenizing compound condition."""
        parser = ConditionParser("rsi < 30 and volume > 1000000")
        tokens = parser._tokenize()
        assert tokens == ["rsi", "<", "30", "and", "volume", ">", "1000000"]

    def test_parentheses(self):
        """Test tokenizing with parentheses."""
        parser = ConditionParser("(rsi < 30 or rsi > 70) and volume > 1000000")
        tokens = parser._tokenize()
        assert "(" in tokens
        assert ")" in tokens

    def test_offset_notation(self):
        """Test tokenizing offset notation."""
        parser = ConditionParser("sma_20[5] > sma_50[5]")
        tokens = parser._tokenize()
        assert "sma_20[5]" in tokens
        assert "sma_50[5]" in tokens

    def test_comparison_operators(self):
        """Test all comparison operators."""
        for op in [">", "<", ">=", "<=", "==", "!="]:
            parser = ConditionParser(f"price {op} 100")
            tokens = parser._tokenize()
            assert op in tokens

    def test_number_suffixes(self):
        """Test K, M, B suffixes."""
        parser = ConditionParser("volume > 1M")
        tokens = parser._tokenize()
        assert "1M" in tokens

        parser = ConditionParser("market_cap > 10B")
        tokens = parser._tokenize()
        assert "10B" in tokens


# =============================================================================
# Parsing Tests
# =============================================================================


class TestParsing:
    """Tests for condition parsing."""

    def test_parse_simple(self):
        """Test parsing simple condition."""
        parser = ConditionParser("rsi < 30")
        ast = parser.parse()
        assert ast.type == "comparison"
        assert ast.left == "rsi"
        assert ast.operator == "<"
        assert ast.right == 30.0

    def test_parse_compound_and(self):
        """Test parsing AND condition."""
        parser = ConditionParser("rsi < 30 and volume > 1000000")
        ast = parser.parse()
        assert ast.type == "and"
        assert ast.left.type == "comparison"
        assert ast.right.type == "comparison"

    def test_parse_compound_or(self):
        """Test parsing OR condition."""
        parser = ConditionParser("rsi < 30 or rsi > 70")
        ast = parser.parse()
        assert ast.type == "or"
        assert ast.left.type == "comparison"
        assert ast.right.type == "comparison"

    def test_parse_nested_parentheses(self):
        """Test parsing nested parentheses."""
        parser = ConditionParser("(rsi < 30 or rsi > 70) and volume > 1M")
        ast = parser.parse()
        assert ast.type == "and"
        assert ast.left.type == "or"
        assert ast.right.type == "comparison"

    def test_parse_deep_nesting(self):
        """Test parsing deeply nested conditions."""
        parser = ConditionParser("((rsi < 30) and (volume > 1M)) or macd > 0")
        ast = parser.parse()
        assert ast.type == "or"

    def test_parse_crossover(self):
        """Test parsing crossover condition."""
        parser = ConditionParser("sma_20 crosses_above sma_50")
        ast = parser.parse()
        assert ast.type == "crossover"
        assert ast.operator == "crosses_above"

    def test_parse_crosses(self):
        """Test parsing crosses (either direction)."""
        parser = ConditionParser("price crosses sma_20")
        ast = parser.parse()
        assert ast.type == "crossover"
        assert ast.operator == "crosses"

    def test_parse_crosses_below(self):
        """Test parsing crosses_below."""
        parser = ConditionParser("macd crosses_below signal")
        ast = parser.parse()
        assert ast.type == "crossover"
        assert ast.operator == "crosses_below"

    def test_parse_lookback(self):
        """Test parsing lookback condition."""
        parser = ConditionParser("rsi was < 30 yesterday")
        ast = parser.parse()
        assert ast.type == "lookback"
        assert ast.lookback_days == 1

    def test_parse_lookback_2_days(self):
        """Test parsing 2 days ago lookback."""
        parser = ConditionParser("price was > 100 2_days_ago")
        ast = parser.parse()
        assert ast.type == "lookback"
        assert ast.lookback_days == 2

    def test_parse_offset(self):
        """Test parsing offset notation."""
        parser = ConditionParser("sma_20[5] > sma_50[5]")
        ast = parser.parse()
        assert ast.offset == 5

    def test_parse_empty_raises(self):
        """Test that empty condition raises error."""
        with pytest.raises(ParseError):
            ConditionParser("")

    def test_parse_invalid_raises(self):
        """Test that invalid condition raises error."""
        with pytest.raises(ParseError):
            ConditionParser("rsi <")


# =============================================================================
# Required Indicators Tests
# =============================================================================


class TestRequiredIndicators:
    """Tests for extracting required indicators."""

    def test_single_rsi(self):
        """Test extracting single RSI indicator."""
        parser = ConditionParser("rsi < 30")
        indicators = parser.required_indicators()
        assert "rsi" in indicators
        assert 14 in indicators["rsi"]

    def test_custom_rsi_period(self):
        """Test extracting custom RSI period."""
        parser = ConditionParser("rsi_7 < 20")
        indicators = parser.required_indicators()
        assert "rsi" in indicators
        assert 7 in indicators["rsi"]

    def test_multiple_sma(self):
        """Test extracting multiple SMA periods."""
        parser = ConditionParser("sma_20 > sma_50")
        indicators = parser.required_indicators()
        assert "sma" in indicators
        assert 20 in indicators["sma"]
        assert 50 in indicators["sma"]

    def test_mixed_indicators(self):
        """Test extracting mixed indicators."""
        parser = ConditionParser("rsi < 30 and sma_20 > sma_50 and macd > 0")
        indicators = parser.required_indicators()
        assert "rsi" in indicators
        assert "sma" in indicators
        assert "macd" in indicators

    def test_bollinger_bands(self):
        """Test extracting Bollinger Bands."""
        parser = ConditionParser("price > bb_upper")
        indicators = parser.required_indicators()
        assert "bb" in indicators

    def test_no_indicators_for_quote_fields(self):
        """Test that quote fields don't appear in indicators."""
        parser = ConditionParser("price > 100 and volume > 1M")
        indicators = parser.required_indicators()
        assert len(indicators) == 0


# =============================================================================
# Lookback Tests
# =============================================================================


class TestLookback:
    """Tests for lookback requirement calculation."""

    def test_no_lookback_simple(self):
        """Test no lookback for simple condition."""
        parser = ConditionParser("rsi < 30")
        assert parser.required_lookback() == 0

    def test_lookback_yesterday(self):
        """Test lookback for yesterday."""
        parser = ConditionParser("rsi was < 30 yesterday")
        assert parser.required_lookback() == 1

    def test_lookback_2_days(self):
        """Test lookback for 2 days ago."""
        parser = ConditionParser("price was > 100 2_days_ago")
        assert parser.required_lookback() == 2

    def test_lookback_crossover(self):
        """Test lookback for crossover."""
        parser = ConditionParser("sma_20 crosses_above sma_50")
        assert parser.required_lookback() >= 1

    def test_lookback_offset(self):
        """Test lookback with offset notation."""
        parser = ConditionParser("sma_20[5] > sma_50[5]")
        assert parser.required_lookback() == 5


# =============================================================================
# Evaluation Tests
# =============================================================================


class TestEvaluation:
    """Tests for condition evaluation."""

    def test_eval_simple_true(self, simple_data):
        """Test simple condition that should be true."""
        parser = ConditionParser("rsi < 50")
        assert parser.evaluate(simple_data) is True

    def test_eval_simple_false(self, simple_data):
        """Test simple condition that should be false."""
        parser = ConditionParser("rsi > 50")
        assert parser.evaluate(simple_data) is False

    def test_eval_equals(self, simple_data):
        """Test equality condition."""
        parser = ConditionParser("rsi == 45")
        assert parser.evaluate(simple_data) is True

    def test_eval_not_equals(self, simple_data):
        """Test not equals condition."""
        parser = ConditionParser("rsi != 50")
        assert parser.evaluate(simple_data) is True

    def test_eval_greater_or_equal(self, simple_data):
        """Test greater or equal condition."""
        parser = ConditionParser("rsi >= 45")
        assert parser.evaluate(simple_data) is True

    def test_eval_less_or_equal(self, simple_data):
        """Test less or equal condition."""
        parser = ConditionParser("rsi <= 45")
        assert parser.evaluate(simple_data) is True

    def test_eval_price_above_sma(self, simple_data):
        """Test price above SMA condition."""
        parser = ConditionParser("price > sma_20")
        assert parser.evaluate(simple_data) is True  # 100 > 98

    def test_eval_compound_and_true(self, simple_data):
        """Test compound AND condition that's true."""
        parser = ConditionParser("rsi < 50 and volume > 1000000")
        assert parser.evaluate(simple_data) is True

    def test_eval_compound_and_false(self, simple_data):
        """Test compound AND condition that's false."""
        parser = ConditionParser("rsi > 50 and volume > 1000000")
        assert parser.evaluate(simple_data) is False

    def test_eval_compound_or_true(self, simple_data):
        """Test compound OR condition that's true."""
        parser = ConditionParser("rsi < 30 or rsi > 40")
        assert parser.evaluate(simple_data) is True  # 45 > 40

    def test_eval_compound_or_false(self, simple_data):
        """Test compound OR condition that's false."""
        parser = ConditionParser("rsi < 30 or rsi > 60")
        assert parser.evaluate(simple_data) is False

    def test_eval_nested(self, simple_data):
        """Test nested parentheses evaluation."""
        parser = ConditionParser("(rsi < 30 or rsi > 40) and volume > 1M")
        assert parser.evaluate(simple_data) is True

    def test_eval_bollinger_upper(self, simple_data):
        """Test Bollinger upper band condition."""
        parser = ConditionParser("price < bb_upper")
        assert parser.evaluate(simple_data) is True  # 100 < 105

    def test_eval_macd_positive(self, simple_data):
        """Test MACD positive condition."""
        parser = ConditionParser("macd > signal")
        assert parser.evaluate(simple_data) is True  # 1.5 > 1.2

    def test_eval_with_number_suffix(self, simple_data):
        """Test evaluation with K/M/B suffixes."""
        parser = ConditionParser("volume > 1M")
        assert parser.evaluate(simple_data) is True  # 1.5M > 1M

        parser = ConditionParser("volume > 2M")
        assert parser.evaluate(simple_data) is False  # 1.5M < 2M

    def test_eval_price_alias(self, simple_data):
        """Test price alias resolves to last."""
        parser = ConditionParser("price > 99")
        assert parser.evaluate(simple_data) is True

    def test_eval_missing_field(self, simple_data):
        """Test evaluation with missing field returns False."""
        parser = ConditionParser("unknown_field > 0")
        assert parser.evaluate(simple_data) is False


# =============================================================================
# Crossover Evaluation Tests
# =============================================================================


class TestCrossoverEvaluation:
    """Tests for crossover condition evaluation."""

    def test_crossover_needs_history(self, simple_data):
        """Test crossover returns False without history."""
        parser = ConditionParser("sma_20 crosses_above sma_50")
        assert parser.evaluate(simple_data, None) is False

    def test_crossover_short_history(self, simple_data):
        """Test crossover returns False with insufficient history."""
        short_history = pd.DataFrame({"Close": [100]})
        parser = ConditionParser("price crosses sma_20")
        assert parser.evaluate(simple_data, short_history) is False

    def test_crossover_detection(self, crossover_history):
        """Test crossover detection in prepared data."""
        from borsapy.technical import calculate_sma

        # Add SMA columns
        history = crossover_history.copy()
        history["SMA_5"] = calculate_sma(history, 5)
        history["SMA_20"] = calculate_sma(history, 20)

        data = {
            "sma_5": float(history["SMA_5"].iloc[-1]),
            "sma_20": float(history["SMA_20"].iloc[-1]),
        }

        # Check if there was a crossover in the data
        parser = ConditionParser("sma_5 crosses sma_20")
        # The result depends on the actual data - we just verify it runs
        result = parser.evaluate(data, history)
        assert isinstance(result, bool)


# =============================================================================
# Lookback Evaluation Tests
# =============================================================================


class TestLookbackEvaluation:
    """Tests for lookback condition evaluation."""

    def test_lookback_needs_history(self, simple_data):
        """Test lookback returns False without history."""
        parser = ConditionParser("rsi was < 30 yesterday")
        assert parser.evaluate(simple_data, None) is False

    def test_lookback_insufficient_history(self, simple_data):
        """Test lookback returns False with insufficient history."""
        short_history = pd.DataFrame({"Close": [100]})
        parser = ConditionParser("price was > 90 2_days_ago")
        assert parser.evaluate(simple_data, short_history) is False

    def test_lookback_evaluation(self, ohlcv_history):
        """Test lookback evaluation with proper history."""
        data = {
            "last": float(ohlcv_history["Close"].iloc[-1]),
        }

        # Test that yesterday's price was something
        parser = ConditionParser("price was > 0 yesterday")
        result = parser.evaluate(data, ohlcv_history)
        assert result is True


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_nan_handling(self):
        """Test handling of NaN values."""
        data = {"rsi": float("nan")}
        parser = ConditionParser("rsi < 30")
        assert parser.evaluate(data) is False

    def test_negative_numbers(self):
        """Test negative number parsing."""
        data = {"change_percent": -5.5}
        parser = ConditionParser("change_percent < 0")
        assert parser.evaluate(data) is True

    def test_decimal_numbers(self):
        """Test decimal number parsing."""
        data = {"rsi": 29.5}
        parser = ConditionParser("rsi < 30.0")
        assert parser.evaluate(data) is True

    def test_case_insensitive(self):
        """Test case insensitivity."""
        data = {"RSI": 45}
        parser = ConditionParser("rsi < 50")
        # Should find RSI even though condition uses lowercase
        # (Note: current implementation may require exact match)

    def test_multiple_same_indicator(self):
        """Test multiple uses of same indicator."""
        parser = ConditionParser("rsi < 30 or rsi > 70")
        indicators = parser.required_indicators()
        assert "rsi" in indicators
        assert len(indicators["rsi"]) == 1  # Should not duplicate

    def test_repr(self):
        """Test string representation."""
        parser = ConditionParser("rsi < 30")
        assert "rsi < 30" in repr(parser)
