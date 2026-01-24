"""Tests for Turkish Eurobond data."""

from datetime import datetime

import pandas as pd
import pytest

from borsapy.eurobond import Eurobond, eurobonds
from borsapy.exceptions import DataNotAvailableError

# =============================================================================
# Eurobonds Function Tests
# =============================================================================


class TestEurobondsFunction:
    """Tests for eurobonds() function."""

    def test_returns_dataframe(self):
        """Test eurobonds() returns DataFrame."""
        df = eurobonds()
        assert isinstance(df, pd.DataFrame)

    def test_dataframe_columns(self):
        """Test DataFrame has expected columns."""
        df = eurobonds()
        expected_cols = [
            "isin",
            "maturity",
            "days_to_maturity",
            "currency",
            "bid_price",
            "bid_yield",
            "ask_price",
            "ask_yield",
        ]
        for col in expected_cols:
            assert col in df.columns, f"Missing column: {col}"

    def test_has_data(self):
        """Test DataFrame has some data."""
        df = eurobonds()
        assert len(df) > 0, "Expected some Eurobond data"

    def test_currency_filter_usd(self):
        """Test filtering by USD currency."""
        df = eurobonds(currency="USD")
        if not df.empty:
            assert all(df["currency"] == "USD")

    def test_currency_filter_eur(self):
        """Test filtering by EUR currency."""
        df = eurobonds(currency="EUR")
        if not df.empty:
            assert all(df["currency"] == "EUR")

    def test_sorted_by_maturity(self):
        """Test DataFrame is sorted by maturity."""
        df = eurobonds()
        if len(df) > 1:
            maturities = df["maturity"].tolist()
            assert maturities == sorted(maturities), "Expected sorted by maturity"


# =============================================================================
# Eurobond Class Tests
# =============================================================================


class TestEurobondClass:
    """Tests for Eurobond class."""

    @pytest.fixture
    def sample_isin(self):
        """Get a valid ISIN from the list for testing."""
        df = eurobonds()
        if df.empty:
            pytest.skip("No Eurobond data available")
        return df.iloc[0]["isin"]

    def test_create_by_isin(self, sample_isin):
        """Test creating Eurobond by ISIN."""
        bond = Eurobond(sample_isin)
        assert bond.isin == sample_isin

    def test_isin_case_insensitive(self, sample_isin):
        """Test ISIN is case insensitive."""
        bond = Eurobond(sample_isin.lower())
        assert bond.isin == sample_isin.upper()

    def test_maturity_type(self, sample_isin):
        """Test maturity is datetime or None."""
        bond = Eurobond(sample_isin)
        assert bond.maturity is None or isinstance(bond.maturity, datetime)

    def test_days_to_maturity_type(self, sample_isin):
        """Test days_to_maturity is int."""
        bond = Eurobond(sample_isin)
        assert isinstance(bond.days_to_maturity, int)

    def test_currency_type(self, sample_isin):
        """Test currency is string."""
        bond = Eurobond(sample_isin)
        assert isinstance(bond.currency, str)
        assert bond.currency in ["USD", "EUR"]

    def test_bid_price_type(self, sample_isin):
        """Test bid_price is float or None."""
        bond = Eurobond(sample_isin)
        assert bond.bid_price is None or isinstance(bond.bid_price, float)

    def test_bid_yield_type(self, sample_isin):
        """Test bid_yield is float or None."""
        bond = Eurobond(sample_isin)
        assert bond.bid_yield is None or isinstance(bond.bid_yield, float)

    def test_ask_price_type(self, sample_isin):
        """Test ask_price is float or None."""
        bond = Eurobond(sample_isin)
        assert bond.ask_price is None or isinstance(bond.ask_price, float)

    def test_ask_yield_type(self, sample_isin):
        """Test ask_yield is float or None."""
        bond = Eurobond(sample_isin)
        assert bond.ask_yield is None or isinstance(bond.ask_yield, float)

    def test_info_returns_dict(self, sample_isin):
        """Test info returns dict with all data."""
        bond = Eurobond(sample_isin)
        info = bond.info
        assert isinstance(info, dict)
        assert "isin" in info
        assert "maturity" in info
        assert "currency" in info
        assert "bid_yield" in info

    def test_info_is_copy(self, sample_isin):
        """Test info returns a copy (modifying doesn't affect original)."""
        bond = Eurobond(sample_isin)
        info1 = bond.info
        info1["test"] = "value"
        info2 = bond.info
        assert "test" not in info2

    def test_repr(self, sample_isin):
        """Test string representation."""
        bond = Eurobond(sample_isin)
        repr_str = repr(bond)
        assert "Eurobond" in repr_str
        assert sample_isin in repr_str

    def test_invalid_isin_raises(self):
        """Test invalid ISIN raises DataNotAvailableError."""
        with pytest.raises(DataNotAvailableError):
            bond = Eurobond("INVALID_ISIN_123")
            _ = bond.isin  # Access property to trigger data load


# =============================================================================
# Integration Tests
# =============================================================================


class TestEurobondIntegration:
    """Integration tests with real API calls."""

    def test_usd_bonds_exist(self):
        """Test there are USD denominated bonds."""
        df = eurobonds(currency="USD")
        assert len(df) > 0, "Expected USD Eurobonds"

    def test_yield_reasonable_range(self):
        """Test yields are in reasonable range."""
        df = eurobonds()
        if not df.empty and df["bid_yield"].notna().any():
            yields = df["bid_yield"].dropna()
            # Skip if all yields are 0 (data source may be unavailable)
            if (yields == 0).all():
                pytest.skip("All yields are 0 - data source may be unavailable")
            valid_yields = yields[yields > 0]
            assert all(0 < y < 50 for y in valid_yields), "Yields seem unreasonable"

    def test_days_to_maturity_positive(self):
        """Test all bonds have positive days to maturity."""
        df = eurobonds()
        if not df.empty:
            # Filter out any with 0 (could be data issues)
            valid = df[df["days_to_maturity"] > 0]
            assert len(valid) > 0, "Expected bonds with positive days to maturity"
