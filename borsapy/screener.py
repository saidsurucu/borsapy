"""Stock Screener for BIST - yfinance-like API."""

from typing import Any

import pandas as pd

from borsapy._providers.isyatirim_screener import get_screener_provider


class Screener:
    """
    A yfinance-like interface for BIST stock screening.

    Data source: İş Yatırım

    Examples:
        >>> import borsapy as bp
        >>> screener = bp.Screener()
        >>> screener.add_filter("market_cap", min=1000)  # Min $1B market cap
        >>> screener.add_filter("dividend_yield", min=3)  # Min 3% dividend yield
        >>> results = screener.run()
           symbol                  name  market_cap  dividend_yield
        0   THYAO     Türk Hava Yolları      5234.5             4.2
        1   GARAN     Garanti Bankası       8123.4             5.1
        ...

        >>> # Using templates
        >>> results = bp.screen_stocks(template="high_dividend")

        >>> # Direct filtering
        >>> results = bp.screen_stocks(market_cap_min=1000, pe_max=15)
    """

    # Available templates
    TEMPLATES = [
        "small_cap",
        "mid_cap",
        "large_cap",
        "high_dividend",
        "high_upside",
        "low_upside",
        "high_volume",
        "low_volume",
        "buy_recommendation",
        "sell_recommendation",
        "high_net_margin",
        "high_return",
        "low_pe",
        "high_roe",
        "high_foreign_ownership",
    ]

    def __init__(self):
        """Initialize Screener."""
        self._provider = get_screener_provider()
        self._filters: list[tuple[str, str, str, str]] = []
        self._sector: str | None = None
        self._index: str | None = None
        self._recommendation: str | None = None

    # Default min/max values for criteria when only one bound is specified
    # API requires both min and max - these are sensible defaults
    CRITERIA_DEFAULTS = {
        "price": {"min": 0, "max": 100000},
        "market_cap": {"min": 0, "max": 5000000},  # TL millions
        "market_cap_usd": {"min": 0, "max": 100000},  # USD millions
        "pe": {"min": -1000, "max": 10000},
        "pb": {"min": -100, "max": 1000},
        "ev_ebitda": {"min": -100, "max": 1000},
        "ev_sales": {"min": -100, "max": 1000},
        "dividend_yield": {"min": 0, "max": 100},
        "dividend_yield_2025": {"min": 0, "max": 100},
        "roe": {"min": -200, "max": 500},
        "roa": {"min": -200, "max": 500},
        "net_margin": {"min": -200, "max": 500},
        "ebitda_margin": {"min": -200, "max": 500},
        "upside_potential": {"min": -100, "max": 500},
        "foreign_ratio": {"min": 0, "max": 100},
        "float_ratio": {"min": 0, "max": 100},
        "return_1w": {"min": -100, "max": 100},
        "return_1m": {"min": -100, "max": 200},
        "return_1y": {"min": -100, "max": 1000},
        "return_ytd": {"min": -100, "max": 1000},
        "volume_3m": {"min": 0, "max": 1000},
    }

    def add_filter(
        self,
        criteria: str,
        min: float | None = None,
        max: float | None = None,
        required: bool = False,
    ) -> "Screener":
        """
        Add a filter criterion.

        Args:
            criteria: Criteria name (market_cap, pe, dividend_yield, etc.).
            min: Minimum value.
            max: Maximum value.
            required: Whether this filter is required.

        Returns:
            Self for method chaining.

        Examples:
            >>> screener = Screener()
            >>> screener.add_filter("market_cap", min=1000)
            >>> screener.add_filter("pe", max=15)
        """
        # Map criteria name to ID
        criteria_map = self._provider.CRITERIA_MAP
        criteria_id = criteria_map.get(criteria.lower(), criteria)

        # Get default bounds for this criteria
        defaults = self.CRITERIA_DEFAULTS.get(criteria.lower(), {"min": -999999, "max": 999999})

        # API requires both min and max - use defaults when only one is provided
        if min is None and max is not None:
            min = defaults["min"]
        elif max is None and min is not None:
            max = defaults["max"]

        min_str = str(min) if min is not None else ""
        max_str = str(max) if max is not None else ""
        required_str = "True" if required else "False"

        self._filters.append((criteria_id, min_str, max_str, required_str))
        return self

    def set_sector(self, sector: str) -> "Screener":
        """
        Set sector filter.

        Args:
            sector: Sector name (e.g., "Bankacılık") or ID (e.g., "0001").

        Returns:
            Self for method chaining.
        """
        # Convert sector name to ID if needed
        if sector and not sector.startswith("0"):
            sectors_data = self._provider.get_sectors()
            for s in sectors_data:
                if s.get("name", "").lower() == sector.lower():
                    sector = s.get("id", sector)
                    break
        self._sector = sector
        return self

    def set_index(self, index: str) -> "Screener":
        """
        Set index filter.

        Args:
            index: Index name (e.g., "BIST 30", "BIST 100").

        Returns:
            Self for method chaining.
        """
        # Note: Index filtering may have limited support in the API
        self._index = index
        return self

    def set_recommendation(self, recommendation: str) -> "Screener":
        """
        Set recommendation filter.

        Args:
            recommendation: Recommendation type ("AL", "SAT", "TUT").

        Returns:
            Self for method chaining.
        """
        self._recommendation = recommendation.upper()
        return self

    def clear(self) -> "Screener":
        """
        Clear all filters.

        Returns:
            Self for method chaining.
        """
        self._filters = []
        self._sector = None
        self._index = None
        self._recommendation = None
        return self

    def run(self, template: str | None = None) -> pd.DataFrame:
        """
        Run the screener and return results.

        Args:
            template: Optional pre-defined template to use.

        Returns:
            DataFrame with matching stocks.
        """
        results = self._provider.screen(
            criterias=self._filters if self._filters else None,
            sector=self._sector,
            index=self._index,
            recommendation=self._recommendation,
            template=template,
        )

        if not results:
            return pd.DataFrame(columns=["symbol", "name"])

        return pd.DataFrame(results)

    def __repr__(self) -> str:
        return f"Screener(filters={len(self._filters)}, sector={self._sector}, index={self._index})"


def screen_stocks(
    template: str | None = None,
    sector: str | None = None,
    index: str | None = None,
    recommendation: str | None = None,
    # Common filters as direct parameters
    market_cap_min: float | None = None,
    market_cap_max: float | None = None,
    pe_min: float | None = None,
    pe_max: float | None = None,
    pb_min: float | None = None,
    pb_max: float | None = None,
    dividend_yield_min: float | None = None,
    dividend_yield_max: float | None = None,
    upside_potential_min: float | None = None,
    upside_potential_max: float | None = None,
    net_margin_min: float | None = None,
    net_margin_max: float | None = None,
    roe_min: float | None = None,
    roe_max: float | None = None,
) -> pd.DataFrame:
    """
    Screen BIST stocks based on criteria (convenience function).

    Args:
        template: Pre-defined template name:
            - "small_cap": Market cap < $1B
            - "mid_cap": Market cap $1B-$5B
            - "large_cap": Market cap > $5B
            - "high_dividend": Dividend yield > 2%
            - "high_upside": Positive upside potential
            - "buy_recommendation": BUY recommendations
            - "sell_recommendation": SELL recommendations
            - "high_net_margin": Net margin > 10%
            - "high_return": Positive weekly return
        sector: Sector filter (e.g., "Bankacılık").
        index: Index filter (e.g., "BIST30").
        recommendation: "AL", "SAT", or "TUT".
        market_cap_min/max: Market cap in million USD.
        pe_min/max: P/E ratio.
        pb_min/max: P/B ratio.
        dividend_yield_min/max: Dividend yield (%).
        upside_potential_min/max: Upside potential (%).
        net_margin_min/max: Net margin (%).
        roe_min/max: Return on equity (%).

    Returns:
        DataFrame with matching stocks.

    Examples:
        >>> import borsapy as bp

        >>> # Using template
        >>> bp.screen_stocks(template="high_dividend")

        >>> # Custom filters
        >>> bp.screen_stocks(market_cap_min=1000, pe_max=15)

        >>> # Combined
        >>> bp.screen_stocks(
        ...     sector="Bankacılık",
        ...     dividend_yield_min=3,
        ...     pe_max=10
        ... )
    """
    screener = Screener()

    # Set sector/index/recommendation
    if sector:
        screener.set_sector(sector)
    if index:
        screener.set_index(index)
    if recommendation:
        screener.set_recommendation(recommendation)

    # Add filters
    if market_cap_min is not None or market_cap_max is not None:
        screener.add_filter("market_cap", min=market_cap_min, max=market_cap_max)

    if pe_min is not None or pe_max is not None:
        screener.add_filter("pe", min=pe_min, max=pe_max)

    if pb_min is not None or pb_max is not None:
        screener.add_filter("pb", min=pb_min, max=pb_max)

    if dividend_yield_min is not None or dividend_yield_max is not None:
        screener.add_filter("dividend_yield", min=dividend_yield_min, max=dividend_yield_max)

    if upside_potential_min is not None or upside_potential_max is not None:
        screener.add_filter("upside_potential", min=upside_potential_min, max=upside_potential_max)

    if net_margin_min is not None or net_margin_max is not None:
        screener.add_filter("net_margin", min=net_margin_min, max=net_margin_max)

    if roe_min is not None or roe_max is not None:
        screener.add_filter("roe", min=roe_min, max=roe_max)

    return screener.run(template=template)


def screener_criteria() -> list[dict[str, Any]]:
    """
    Get list of available screening criteria.

    Returns:
        List of criteria with id, name, min, max values.

    Examples:
        >>> import borsapy as bp
        >>> bp.screener_criteria()
        [{'id': '7', 'name': 'Kapanış (TL)', 'min': '1.1', 'max': '14087.5'}, ...]
    """
    provider = get_screener_provider()
    return provider.get_criteria()


def sectors() -> list[str]:
    """
    Get list of available sectors for screening.

    Returns:
        List of sector names.

    Examples:
        >>> import borsapy as bp
        >>> bp.sectors()
        ['Bankacılık', 'Holding', 'Enerji', ...]
    """
    provider = get_screener_provider()
    data = provider.get_sectors()
    return [item["name"] for item in data if item.get("name")]


def stock_indices() -> list[str]:
    """
    Get list of available indices for screening.

    Returns:
        List of index names.

    Examples:
        >>> import borsapy as bp
        >>> bp.stock_indices()
        ['BIST30', 'BIST100', 'BIST BANKA', ...]
    """
    provider = get_screener_provider()
    data = provider.get_indices()
    return [item["name"] for item in data if item.get("name")]
