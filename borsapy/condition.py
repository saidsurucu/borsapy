"""Condition parser and evaluator for technical scanning.

This module provides a parser for trading conditions like "rsi < 30" or
"price > sma_20 and volume > 1000000". It supports:
- Simple comparisons: price > 300, rsi < 30
- Compound conditions: rsi < 30 and volume > 1000000
- Nested parentheses: (rsi < 30 or rsi > 70) and volume > 1000000
- Crossover detection: sma_20 crosses_above sma_50
- Lookback conditions: rsi was < 30 yesterday
- Offset access: sma_20[5] (5 bars ago)

Examples:
    >>> parser = ConditionParser("rsi < 30")
    >>> parser.required_indicators()
    {'rsi': 14}
    >>> parser.evaluate({'rsi': 28.5})
    True

    >>> parser = ConditionParser("sma_20 crosses_above sma_50")
    >>> parser.required_indicators()
    {'sma': [20, 50]}
    >>> parser.evaluate({'sma_20': 285, 'sma_50': 280}, history_df)
    True
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from operator import eq, ge, gt, le, lt, ne
from typing import Any, Callable

import numpy as np
import pandas as pd

__all__ = ["ConditionParser", "ConditionNode", "ParseError"]


class ParseError(Exception):
    """Raised when condition parsing fails."""

    pass


@dataclass
class ConditionNode:
    """AST node for parsed conditions.

    Attributes:
        type: Node type - "comparison", "crossover", "lookback", "and", "or"
        left: Left operand (ConditionNode, field name, or value)
        right: Right operand (ConditionNode, field name, or value)
        operator: Comparison operator (>, <, ==, etc.) or crossover type
        offset: Bar offset for historical access (0 = current)
        lookback_days: Days to look back for "was" conditions
    """

    type: str
    left: ConditionNode | str | float | None = None
    right: ConditionNode | str | float | None = None
    operator: str | None = None
    offset: int = 0
    lookback_days: int = 0


class ConditionParser:
    """Parse and evaluate trading condition strings.

    Supports quote fields (price, volume, change_percent) and technical
    indicators (rsi, sma_20, ema_12, macd, bb_upper, etc.).

    Examples:
        >>> parser = ConditionParser("rsi < 30 and volume > 1000000")
        >>> parser.required_indicators()
        {'rsi': 14}
        >>> parser.evaluate({'rsi': 28.5, 'volume': 1500000})
        True
    """

    # Comparison operators
    OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
        ">": gt,
        "<": lt,
        ">=": ge,
        "<=": le,
        "==": eq,
        "!=": ne,
    }

    # Logical operators
    LOGICAL_OPS = {"and", "or"}

    # Crossover operators
    CROSSOVER_OPS = {"crosses", "crosses_above", "crosses_below"}

    # Lookback keywords
    LOOKBACK_MAP = {
        "yesterday": 1,
        "1_day_ago": 1,
        "2_days_ago": 2,
        "3_days_ago": 3,
        "4_days_ago": 4,
        "5_days_ago": 5,
        "1_week_ago": 5,  # Trading days
    }

    # Quote field aliases
    QUOTE_FIELDS = {
        "price": "last",
        "close": "last",
        "vol": "volume",
        "change": "change_percent",
        "cap": "market_cap",
        "last": "last",
        "open": "open",
        "high": "high",
        "low": "low",
        "volume": "volume",
        "change_percent": "change_percent",
        "market_cap": "market_cap",
        "bid": "bid",
        "ask": "ask",
    }

    # Indicator patterns: regex -> (indicator_name, default_period)
    INDICATOR_PATTERNS: dict[str, tuple[str, int | None]] = {
        r"^rsi(?:_(\d+))?$": ("rsi", 14),
        r"^sma_(\d+)$": ("sma", None),
        r"^ema_(\d+)$": ("ema", None),
        r"^bb_(upper|middle|lower)$": ("bb", 20),
        r"^macd$": ("macd", None),
        r"^signal$": ("macd_signal", None),
        r"^histogram$": ("macd_histogram", None),
        r"^adx(?:_(\d+))?$": ("adx", 14),
        r"^stoch_([kd])$": ("stoch", 14),
        r"^atr(?:_(\d+))?$": ("atr", 14),
        r"^obv$": ("obv", None),
        r"^vwap$": ("vwap", None),
    }

    # Offset pattern: field[N] means N bars ago
    OFFSET_PATTERN = re.compile(r"^(.+?)\[(\d+)\]$")

    def __init__(self, condition: str) -> None:
        """Initialize parser with condition string.

        Args:
            condition: Trading condition to parse (e.g., "rsi < 30")

        Raises:
            ParseError: If condition syntax is invalid
        """
        self._raw = condition.strip()
        self._tokens: list[str] = []
        self._pos = 0
        self._ast: ConditionNode | None = None
        self._required_indicators: dict[str, list[int]] = {}
        self._max_lookback = 0

        # Parse on init
        self._parse()

    def _tokenize(self) -> list[str]:
        """Tokenize the condition string.

        Returns:
            List of tokens (identifiers, operators, parentheses, numbers)
        """
        tokens = []
        i = 0
        s = self._raw

        while i < len(s):
            # Skip whitespace
            if s[i].isspace():
                i += 1
                continue

            # Parentheses
            if s[i] in "()":
                tokens.append(s[i])
                i += 1
                continue

            # Multi-char operators
            if i + 1 < len(s):
                two_char = s[i : i + 2]
                if two_char in (">=", "<=", "==", "!="):
                    tokens.append(two_char)
                    i += 2
                    continue

            # Single-char operators
            if s[i] in "><":
                tokens.append(s[i])
                i += 1
                continue

            # Numbers (including negative and decimals)
            # But check for N_days_ago pattern first (e.g., 2_days_ago)
            if s[i].isdigit() or (s[i] == "-" and i + 1 < len(s) and s[i + 1].isdigit()):
                j = i
                if s[j] == "-":
                    j += 1
                while j < len(s) and (s[j].isdigit() or s[j] == "."):
                    j += 1
                # Check if this is N_days_ago pattern (lookback keyword)
                if j < len(s) and s[j] == "_":
                    # Look ahead for _days_ago or _day_ago or _week_ago
                    rest = s[j:].lower()
                    for suffix in ("_days_ago", "_day_ago", "_week_ago"):
                        if rest.startswith(suffix):
                            j += len(suffix)
                            tokens.append(s[i:j])
                            i = j
                            break
                    else:
                        # Not a lookback keyword, treat as number
                        # Handle suffixes like 1M, 1K
                        if j < len(s) and s[j].upper() in "KMB":
                            j += 1
                        tokens.append(s[i:j])
                        i = j
                    continue
                # Handle suffixes like 1M, 1K
                if j < len(s) and s[j].upper() in "KMB":
                    j += 1
                tokens.append(s[i:j])
                i = j
                continue

            # Identifiers (words, underscores, brackets for offset)
            if s[i].isalpha() or s[i] == "_":
                j = i
                bracket_depth = 0
                while j < len(s):
                    c = s[j]
                    if c == "[":
                        bracket_depth += 1
                        j += 1
                    elif c == "]":
                        bracket_depth -= 1
                        j += 1
                        if bracket_depth == 0:
                            break
                    elif c.isalnum() or c == "_":
                        j += 1
                    elif bracket_depth > 0:
                        j += 1
                    else:
                        break
                tokens.append(s[i:j])
                i = j
                continue

            # Unknown character - skip
            i += 1

        return tokens

    def _parse(self) -> None:
        """Parse the condition into an AST."""
        self._tokens = self._tokenize()
        if not self._tokens:
            raise ParseError("Empty condition")
        self._pos = 0
        self._ast = self._parse_or_expression()

        # Check for leftover tokens
        if self._pos < len(self._tokens):
            raise ParseError(
                f"Unexpected token after expression: {self._tokens[self._pos]}"
            )

    def _current_token(self) -> str | None:
        """Get current token without consuming."""
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _consume(self) -> str:
        """Consume and return current token."""
        if self._pos >= len(self._tokens):
            raise ParseError("Unexpected end of condition")
        token = self._tokens[self._pos]
        self._pos += 1
        return token

    def _parse_or_expression(self) -> ConditionNode:
        """Parse OR expression (lowest precedence)."""
        left = self._parse_and_expression()

        while self._current_token() == "or":
            self._consume()  # consume 'or'
            right = self._parse_and_expression()
            left = ConditionNode(type="or", left=left, right=right)

        return left

    def _parse_and_expression(self) -> ConditionNode:
        """Parse AND expression."""
        left = self._parse_primary()

        while self._current_token() == "and":
            self._consume()  # consume 'and'
            right = self._parse_primary()
            left = ConditionNode(type="and", left=left, right=right)

        return left

    def _parse_primary(self) -> ConditionNode:
        """Parse primary expression (comparison, crossover, lookback, or parenthesized)."""
        token = self._current_token()

        # Parenthesized expression
        if token == "(":
            self._consume()  # consume '('
            node = self._parse_or_expression()
            if self._current_token() != ")":
                raise ParseError("Missing closing parenthesis")
            self._consume()  # consume ')'
            return node

        # Must be a comparison, crossover, or lookback
        return self._parse_condition()

    def _parse_condition(self) -> ConditionNode:
        """Parse a single condition (comparison, crossover, or lookback)."""
        # Get left operand
        left_token = self._consume()
        left, left_offset = self._parse_operand(left_token)

        # Check for "was" (lookback condition)
        if self._current_token() == "was":
            self._consume()  # consume 'was'
            return self._parse_lookback(left, left_offset)

        # Check for crossover
        if self._current_token() in self.CROSSOVER_OPS:
            crossover_type = self._consume()
            right_token = self._consume()
            right, right_offset = self._parse_operand(right_token)

            # Track required indicators
            self._track_indicator(left)
            self._track_indicator(right)

            # Track lookback for crossover (need at least 2 bars)
            offset = max(left_offset, right_offset, 1)
            self._max_lookback = max(self._max_lookback, offset + 1)

            return ConditionNode(
                type="crossover",
                left=left,
                right=right,
                operator=crossover_type,
                offset=offset,
            )

        # Standard comparison
        op = self._current_token()
        if op not in self.OPERATORS:
            raise ParseError(f"Expected comparison operator, got: {op}")
        self._consume()  # consume operator

        right_token = self._consume()
        right, right_offset = self._parse_operand(right_token)

        # Track required indicators
        self._track_indicator(left)
        self._track_indicator(right)

        # Track lookback
        offset = max(left_offset, right_offset)
        self._max_lookback = max(self._max_lookback, offset)

        return ConditionNode(
            type="comparison",
            left=left,
            right=right,
            operator=op,
            offset=offset,
        )

    def _parse_lookback(self, field: str, field_offset: int) -> ConditionNode:
        """Parse lookback condition: field was <op> <value> <time_keyword>."""
        # Get operator
        op = self._current_token()
        if op not in self.OPERATORS:
            raise ParseError(f"Expected operator after 'was', got: {op}")
        self._consume()

        # Get value
        value_token = self._consume()
        value, _ = self._parse_operand(value_token)

        # Get time keyword
        time_kw = self._current_token()
        if time_kw not in self.LOOKBACK_MAP:
            raise ParseError(f"Expected time keyword (yesterday, 2_days_ago, ...), got: {time_kw}")
        self._consume()

        lookback_days = self.LOOKBACK_MAP[time_kw]
        total_offset = field_offset + lookback_days
        self._max_lookback = max(self._max_lookback, total_offset)

        # Track indicator
        self._track_indicator(field)

        return ConditionNode(
            type="lookback",
            left=field,
            right=value,
            operator=op,
            lookback_days=lookback_days,
            offset=total_offset,
        )

    def _parse_operand(self, token: str) -> tuple[str | float, int]:
        """Parse an operand token into value and offset.

        Returns:
            Tuple of (field_name_or_value, offset)
        """
        # Check for offset: field[N]
        offset = 0
        match = self.OFFSET_PATTERN.match(token)
        if match:
            token = match.group(1)
            offset = int(match.group(2))

        # Try to parse as number
        try:
            # Handle K, M, B suffixes
            if token.upper().endswith("K"):
                return float(token[:-1]) * 1_000, offset
            elif token.upper().endswith("M"):
                return float(token[:-1]) * 1_000_000, offset
            elif token.upper().endswith("B"):
                return float(token[:-1]) * 1_000_000_000, offset
            return float(token), offset
        except ValueError:
            pass

        # It's a field name
        return token.lower(), offset

    def _track_indicator(self, field: str | float) -> None:
        """Track required indicator from field name."""
        if isinstance(field, (int, float)):
            return

        field = str(field).lower()

        # Check if it's a quote field
        if field in self.QUOTE_FIELDS:
            return

        # Check indicator patterns
        for pattern, (indicator, default_period) in self.INDICATOR_PATTERNS.items():
            match = re.match(pattern, field)
            if match:
                groups = match.groups()
                if groups and groups[0]:
                    # Extract period from match (e.g., sma_20 -> 20)
                    try:
                        period = int(groups[0])
                    except ValueError:
                        period = default_period or 14
                else:
                    period = default_period or 14

                if indicator not in self._required_indicators:
                    self._required_indicators[indicator] = []
                if period not in self._required_indicators[indicator]:
                    self._required_indicators[indicator].append(period)
                return

    def parse(self) -> ConditionNode:
        """Get the parsed AST.

        Returns:
            Root ConditionNode of the AST
        """
        if self._ast is None:
            raise ParseError("Parsing failed")
        return self._ast

    def required_indicators(self) -> dict[str, list[int]]:
        """Get required indicators and their periods.

        Returns:
            Dict mapping indicator names to list of periods needed.

        Examples:
            >>> parser = ConditionParser("rsi < 30 and sma_20 > sma_50")
            >>> parser.required_indicators()
            {'rsi': [14], 'sma': [20, 50]}
        """
        return self._required_indicators.copy()

    def required_lookback(self) -> int:
        """Get maximum lookback period needed for evaluation.

        Returns:
            Number of historical bars needed
        """
        return self._max_lookback

    def evaluate(
        self,
        data: dict[str, Any],
        history: pd.DataFrame | None = None,
    ) -> bool:
        """Evaluate condition against provided data.

        Args:
            data: Dictionary with current values (price, rsi, sma_20, etc.)
            history: Optional DataFrame with historical data for crossover/lookback

        Returns:
            True if condition is met, False otherwise

        Examples:
            >>> parser = ConditionParser("rsi < 30")
            >>> parser.evaluate({'rsi': 28.5})
            True
        """
        if self._ast is None:
            return False
        return self._evaluate_node(self._ast, data, history)

    def _evaluate_node(
        self,
        node: ConditionNode,
        data: dict[str, Any],
        history: pd.DataFrame | None,
    ) -> bool:
        """Recursively evaluate AST node."""
        if node.type == "and":
            return self._evaluate_node(
                node.left, data, history  # type: ignore
            ) and self._evaluate_node(node.right, data, history)  # type: ignore

        if node.type == "or":
            return self._evaluate_node(
                node.left, data, history  # type: ignore
            ) or self._evaluate_node(node.right, data, history)  # type: ignore

        if node.type == "comparison":
            return self._evaluate_comparison(node, data, history)

        if node.type == "crossover":
            return self._evaluate_crossover(node, data, history)

        if node.type == "lookback":
            return self._evaluate_lookback(node, data, history)

        return False

    def _evaluate_comparison(
        self,
        node: ConditionNode,
        data: dict[str, Any],
        history: pd.DataFrame | None,
    ) -> bool:
        """Evaluate a comparison node."""
        left_val = self._get_value(node.left, data, history, node.offset)
        right_val = self._get_value(node.right, data, history, node.offset)

        if left_val is None or right_val is None:
            return False

        if np.isnan(left_val) or np.isnan(right_val):
            return False

        op_func = self.OPERATORS.get(node.operator or ">")
        if op_func is None:
            return False

        return bool(op_func(left_val, right_val))

    def _evaluate_crossover(
        self,
        node: ConditionNode,
        data: dict[str, Any],
        history: pd.DataFrame | None,
    ) -> bool:
        """Evaluate a crossover condition."""
        if history is None or len(history) < 2:
            return False

        left_series = self._get_series(node.left, data, history)
        right_series = self._get_series(node.right, data, history)

        if left_series is None or right_series is None:
            return False

        return self._check_crossover(
            left_series, right_series, node.operator or "crosses", node.offset
        )

    def _evaluate_lookback(
        self,
        node: ConditionNode,
        data: dict[str, Any],
        history: pd.DataFrame | None,
    ) -> bool:
        """Evaluate a lookback condition (was X yesterday)."""
        if history is None or len(history) < node.lookback_days + 1:
            return False

        # Get value from N days ago
        left_val = self._get_value(
            node.left, data, history, offset=node.lookback_days
        )
        right_val = self._get_value(node.right, data, history, offset=0)

        if left_val is None or right_val is None:
            return False

        if np.isnan(left_val) or np.isnan(right_val):
            return False

        op_func = self.OPERATORS.get(node.operator or ">")
        if op_func is None:
            return False

        return bool(op_func(left_val, right_val))

    def _get_value(
        self,
        operand: str | float | ConditionNode | None,
        data: dict[str, Any],
        history: pd.DataFrame | None,
        offset: int = 0,
    ) -> float | None:
        """Get value of an operand."""
        if operand is None:
            return None

        if isinstance(operand, (int, float)):
            return float(operand)

        if isinstance(operand, ConditionNode):
            # This shouldn't happen for leaf values
            return None

        field = str(operand).lower()

        # Resolve quote field aliases
        if field in self.QUOTE_FIELDS:
            field = self.QUOTE_FIELDS[field]

        # If offset, get from history
        if offset > 0 and history is not None:
            return self._get_value_at_offset(field, history, offset, data)

        # Get from current data
        if field in data:
            return float(data[field])

        # Try with underscores for indicator names (e.g., sma_20)
        for key in data:
            if key.lower() == field:
                return float(data[key])

        return None

    def _get_value_at_offset(
        self,
        field: str,
        history: pd.DataFrame,
        offset: int,
        data: dict[str, Any],
    ) -> float | None:
        """Get value from history at given offset (N bars ago)."""
        if history is None or len(history) <= offset:
            return None

        # Map field to column name
        col_map = {
            "last": "Close",
            "price": "Close",
            "close": "Close",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "volume": "Volume",
        }

        col = col_map.get(field)

        if col and col in history.columns:
            idx = len(history) - 1 - offset
            if idx >= 0:
                return float(history[col].iloc[idx])

        # Check for indicator columns
        for col in history.columns:
            if col.lower() == field or col.lower().replace("_", "") == field.replace(
                "_", ""
            ):
                idx = len(history) - 1 - offset
                if idx >= 0:
                    return float(history[col].iloc[idx])

        # If it's a calculated indicator in data, we need to recalculate
        # For now, return None if not in history
        return None

    def _get_series(
        self,
        operand: str | float | ConditionNode | None,
        data: dict[str, Any],
        history: pd.DataFrame,
    ) -> pd.Series | None:
        """Get a series for crossover detection."""
        if operand is None:
            return None

        if isinstance(operand, (int, float)):
            # Constant value - return series of that value
            return pd.Series([float(operand)] * len(history), index=history.index)

        if isinstance(operand, ConditionNode):
            return None

        field = str(operand).lower()

        # Map field to column
        col_map = {
            "last": "Close",
            "price": "Close",
            "close": "Close",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "volume": "Volume",
        }

        col = col_map.get(field)
        if col and col in history.columns:
            return history[col]

        # Check for indicator columns
        for col in history.columns:
            if col.lower() == field or col.lower().replace("_", "") == field.replace(
                "_", ""
            ):
                return history[col]

        return None

    def _check_crossover(
        self,
        series1: pd.Series,
        series2: pd.Series,
        direction: str,
        offset: int = 0,
    ) -> bool:
        """Check if series1 crossed series2.

        Args:
            series1: First series (e.g., SMA20)
            series2: Second series (e.g., SMA50)
            direction: "crosses", "crosses_above", or "crosses_below"
            offset: Number of bars ago to check

        Returns:
            True if crossover occurred
        """
        if len(series1) < 2 or len(series2) < 2:
            return False

        # Get indices accounting for offset
        idx = len(series1) - 1 - offset
        prev_idx = idx - 1

        if prev_idx < 0:
            return False

        curr_diff = series1.iloc[idx] - series2.iloc[idx]
        prev_diff = series1.iloc[prev_idx] - series2.iloc[prev_idx]

        # Check crossover conditions
        if direction == "crosses_above":
            return bool(prev_diff <= 0 and curr_diff > 0)
        elif direction == "crosses_below":
            return bool(prev_diff >= 0 and curr_diff < 0)
        elif direction == "crosses":
            # Either direction
            return bool(
                (prev_diff <= 0 and curr_diff > 0) or (prev_diff >= 0 and curr_diff < 0)
            )

        return False

    def __repr__(self) -> str:
        return f"ConditionParser('{self._raw}')"
