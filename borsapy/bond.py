"""Bond class for Turkish government bond yields - yfinance-like API."""

from typing import Any

import pandas as pd

from borsapy._providers.dovizcom_tahvil import get_tahvil_provider


class Bond:
    """
    A yfinance-like interface for Turkish government bond data.

    Data source: doviz.com/tahvil

    Examples:
        >>> import borsapy as bp
        >>> bond = bp.Bond("10Y")
        >>> bond.yield_rate  # Current yield (e.g., 28.03)
        28.03
        >>> bond.yield_decimal  # As decimal (e.g., 0.2803)
        0.2803
        >>> bond.change_pct  # Daily change percentage
        1.5

        >>> bp.bonds()  # Get all bond yields
                  name maturity   yield  change  change_pct
        0  2 Yıllık Tahvil       2Y   26.42    0.40        1.54
        1  5 Yıllık Tahvil       5Y   27.15    0.35        1.31
        2 10 Yıllık Tahvil      10Y   28.03    0.42        1.52
    """

    # Valid maturities
    MATURITIES = ["2Y", "5Y", "10Y"]

    def __init__(self, maturity: str):
        """
        Initialize a Bond object.

        Args:
            maturity: Bond maturity (2Y, 5Y, 10Y).
        """
        self._maturity = maturity.upper()
        self._provider = get_tahvil_provider()
        self._data_cache: dict[str, Any] | None = None

    @property
    def maturity(self) -> str:
        """Return the bond maturity."""
        return self._maturity

    @property
    def _data(self) -> dict[str, Any]:
        """Get bond data (cached)."""
        if self._data_cache is None:
            self._data_cache = self._provider.get_bond(self._maturity)
        return self._data_cache

    @property
    def name(self) -> str:
        """Return the bond name."""
        return self._data.get("name", "")

    @property
    def yield_rate(self) -> float | None:
        """
        Return the current yield as percentage.

        Returns:
            Yield rate as percentage (e.g., 28.03 for 28.03%).
        """
        return self._data.get("yield")

    @property
    def yield_decimal(self) -> float | None:
        """
        Return the current yield as decimal.

        Returns:
            Yield rate as decimal (e.g., 0.2803 for 28.03%).
            Useful for financial calculations.
        """
        return self._data.get("yield_decimal")

    @property
    def change(self) -> float | None:
        """Return the absolute change in yield."""
        return self._data.get("change")

    @property
    def change_pct(self) -> float | None:
        """Return the percentage change in yield."""
        return self._data.get("change_pct")

    @property
    def info(self) -> dict[str, Any]:
        """
        Return all bond information.

        Returns:
            Dictionary with name, maturity, yield, change, etc.
        """
        return self._data.copy()

    def __repr__(self) -> str:
        return f"Bond('{self._maturity}')"


def bonds() -> pd.DataFrame:
    """
    Get all Turkish government bond yields.

    Returns:
        DataFrame with columns: name, maturity, yield, change, change_pct.

    Examples:
        >>> import borsapy as bp
        >>> bp.bonds()
                      name maturity   yield  change  change_pct
        0  2 Yıllık Tahvil       2Y   26.42    0.40        1.54
        1  5 Yıllık Tahvil       5Y   27.15    0.35        1.31
        2 10 Yıllık Tahvil      10Y   28.03    0.42        1.52
    """
    provider = get_tahvil_provider()
    data = provider.get_bond_yields()

    if not data:
        return pd.DataFrame(columns=["name", "maturity", "yield", "change", "change_pct"])

    df = pd.DataFrame(data)

    # Select and rename columns
    columns = {
        "name": "name",
        "maturity": "maturity",
        "yield": "yield",
        "change": "change",
        "change_pct": "change_pct",
    }

    df = df[[c for c in columns.keys() if c in df.columns]]
    df = df.rename(columns=columns)

    return df


def risk_free_rate() -> float | None:
    """
    Get the risk-free rate for Turkish market (10Y bond yield).

    Returns:
        10-year government bond yield as decimal.
        Useful for CAPM and DCF calculations.

    Examples:
        >>> import borsapy as bp
        >>> rfr = bp.risk_free_rate()
        >>> rfr
        0.2803
    """
    provider = get_tahvil_provider()
    return provider.get_10y_yield()
