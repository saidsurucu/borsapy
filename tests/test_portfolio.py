"""Tests for Portfolio management."""

from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from borsapy.portfolio import (
    FX_COMMODITIES,
    FX_CURRENCIES,
    FX_METALS,
    Holding,
    Portfolio,
    _detect_asset_type,
    _get_asset,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def empty_portfolio():
    """Empty portfolio for basic tests."""
    return Portfolio()


@pytest.fixture
def sample_portfolio():
    """Portfolio with sample holdings for testing."""
    p = Portfolio()
    # Add with explicit costs to avoid API calls
    p._holdings["THYAO"] = Holding("THYAO", 100, 280.0, "stock")
    p._holdings["GARAN"] = Holding("GARAN", 200, 50.0, "stock")
    return p


# =============================================================================
# Asset Type Detection Tests
# =============================================================================


class TestAssetTypeDetection:
    """Tests for automatic asset type detection."""

    def test_detect_major_currencies(self):
        """Test detection of major currencies."""
        assert _detect_asset_type("USD") == "fx"
        assert _detect_asset_type("EUR") == "fx"
        assert _detect_asset_type("GBP") == "fx"
        assert _detect_asset_type("JPY") == "fx"
        assert _detect_asset_type("CHF") == "fx"

    def test_detect_all_65_currencies(self):
        """Test all 65 supported currencies are detected as fx."""
        for currency in FX_CURRENCIES:
            assert _detect_asset_type(currency) == "fx", f"Failed for {currency}"

    def test_detect_metals(self):
        """Test detection of precious metals."""
        for metal in FX_METALS:
            assert _detect_asset_type(metal) == "fx", f"Failed for {metal}"

    def test_detect_commodities(self):
        """Test detection of commodities."""
        for commodity in FX_COMMODITIES:
            assert _detect_asset_type(commodity) == "fx", f"Failed for {commodity}"

    def test_detect_crypto(self):
        """Test detection of crypto pairs."""
        assert _detect_asset_type("BTCTRY") == "crypto"
        assert _detect_asset_type("ETHTRY") == "crypto"
        assert _detect_asset_type("AVAXTRY") == "crypto"  # 7+ chars ending in TRY

    def test_detect_stock_default(self):
        """Test that unknown symbols default to stock."""
        assert _detect_asset_type("THYAO") == "stock"
        assert _detect_asset_type("GARAN") == "stock"
        assert _detect_asset_type("ASELS") == "stock"

    def test_fund_not_auto_detected(self):
        """Test that fund codes are detected as stock (need manual override)."""
        # Funds like AAK, YAY are 3 letters - could be stocks
        # User must specify asset_type="fund"
        assert _detect_asset_type("AAK") == "stock"
        assert _detect_asset_type("YAY") == "stock"

    def test_case_insensitivity(self):
        """Test case insensitive detection for currencies."""
        assert _detect_asset_type("usd") == "fx"
        assert _detect_asset_type("Eur") == "fx"


# =============================================================================
# Portfolio Basic Operations Tests
# =============================================================================


class TestPortfolioBasic:
    """Tests for basic portfolio operations."""

    def test_init_empty(self, empty_portfolio):
        """Test empty portfolio initialization."""
        assert len(empty_portfolio) == 0
        assert empty_portfolio.symbols == []
        assert empty_portfolio._benchmark == "XU100"

    def test_init_custom_benchmark(self):
        """Test portfolio with custom benchmark."""
        p = Portfolio(benchmark="XU030")
        assert p._benchmark == "XU030"

    def test_add_holding_with_cost(self, empty_portfolio):
        """Test adding holding with explicit cost."""
        empty_portfolio.add("THYAO", shares=100, cost=280.0)
        assert len(empty_portfolio) == 1
        assert "THYAO" in empty_portfolio.symbols
        h = empty_portfolio._holdings["THYAO"]
        assert h.shares == 100
        assert h.cost_per_share == 280.0
        assert h.asset_type == "stock"

    def test_add_fx_explicit(self, empty_portfolio):
        """Test adding FX asset with explicit type."""
        empty_portfolio.add("gram-altin", shares=5, cost=3500.0, asset_type="fx")
        assert len(empty_portfolio) == 1
        h = empty_portfolio._holdings["gram-altin"]
        assert h.asset_type == "fx"

    def test_add_fund_explicit(self, empty_portfolio):
        """Test adding fund with explicit type."""
        empty_portfolio.add("YAY", shares=1000, cost=1.5, asset_type="fund")
        assert len(empty_portfolio) == 1
        h = empty_portfolio._holdings["YAY"]
        assert h.asset_type == "fund"

    def test_add_crypto_auto_detect(self, empty_portfolio):
        """Test crypto auto-detection."""
        empty_portfolio.add("BTCTRY", shares=0.5, cost=2000000.0)
        h = empty_portfolio._holdings["BTCTRY"]
        assert h.asset_type == "crypto"

    def test_remove_holding(self, sample_portfolio):
        """Test removing a holding."""
        assert len(sample_portfolio) == 2
        sample_portfolio.remove("THYAO")
        assert len(sample_portfolio) == 1
        assert "THYAO" not in sample_portfolio.symbols

    def test_remove_nonexistent(self, sample_portfolio):
        """Test removing non-existent holding (should not raise)."""
        sample_portfolio.remove("NONEXISTENT")
        assert len(sample_portfolio) == 2  # No change

    def test_update_holding(self, sample_portfolio):
        """Test updating holding shares and cost."""
        sample_portfolio.update("THYAO", shares=150, cost=290.0)
        h = sample_portfolio._holdings["THYAO"]
        assert h.shares == 150
        assert h.cost_per_share == 290.0

    def test_update_partial(self, sample_portfolio):
        """Test updating only shares."""
        original_cost = sample_portfolio._holdings["THYAO"].cost_per_share
        sample_portfolio.update("THYAO", shares=150)
        h = sample_portfolio._holdings["THYAO"]
        assert h.shares == 150
        assert h.cost_per_share == original_cost

    def test_update_nonexistent(self, sample_portfolio):
        """Test updating non-existent holding raises error."""
        with pytest.raises(KeyError):
            sample_portfolio.update("NONEXISTENT", shares=100)

    def test_clear_portfolio(self, sample_portfolio):
        """Test clearing all holdings."""
        assert len(sample_portfolio) > 0
        sample_portfolio.clear()
        assert len(sample_portfolio) == 0
        assert sample_portfolio.symbols == []

    def test_set_benchmark(self, empty_portfolio):
        """Test setting benchmark."""
        empty_portfolio.set_benchmark("XU030")
        assert empty_portfolio._benchmark == "XU030"

    def test_method_chaining(self, empty_portfolio):
        """Test method chaining works."""
        result = (
            empty_portfolio
            .add("THYAO", shares=100, cost=280.0)
            .add("GARAN", shares=200, cost=50.0)
            .set_benchmark("XU030")
        )
        assert result is empty_portfolio
        assert len(empty_portfolio) == 2


# =============================================================================
# Portfolio Properties Tests
# =============================================================================


class TestPortfolioProperties:
    """Tests for portfolio properties."""

    def test_symbols(self, sample_portfolio):
        """Test symbols property."""
        symbols = sample_portfolio.symbols
        assert "THYAO" in symbols
        assert "GARAN" in symbols
        assert len(symbols) == 2

    def test_cost_calculation(self, sample_portfolio):
        """Test total cost calculation."""
        # THYAO: 100 * 280 = 28000
        # GARAN: 200 * 50 = 10000
        # Total: 38000
        expected_cost = 100 * 280 + 200 * 50
        assert sample_portfolio.cost == expected_cost

    def test_cost_empty_portfolio(self, empty_portfolio):
        """Test cost of empty portfolio."""
        assert empty_portfolio.cost == 0

    def test_holdings_dataframe_empty(self, empty_portfolio):
        """Test holdings DataFrame for empty portfolio."""
        df = empty_portfolio.holdings
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert "symbol" in df.columns

    def test_weights_empty(self, empty_portfolio):
        """Test weights for empty portfolio."""
        assert empty_portfolio.weights == {}

    def test_pnl_pct_zero_cost(self, empty_portfolio):
        """Test pnl_pct with zero cost."""
        assert empty_portfolio.pnl_pct == 0.0


# =============================================================================
# Import/Export Tests
# =============================================================================


class TestPortfolioExport:
    """Tests for portfolio import/export."""

    def test_to_dict(self, sample_portfolio):
        """Test export to dictionary."""
        data = sample_portfolio.to_dict()
        assert "benchmark" in data
        assert "holdings" in data
        assert data["benchmark"] == "XU100"
        assert len(data["holdings"]) == 2

    def test_to_dict_structure(self, sample_portfolio):
        """Test exported dictionary structure."""
        data = sample_portfolio.to_dict()
        holding = data["holdings"][0]
        assert "symbol" in holding
        assert "shares" in holding
        assert "cost_per_share" in holding
        assert "asset_type" in holding

    def test_from_dict(self):
        """Test import from dictionary."""
        data = {
            "benchmark": "XU030",
            "holdings": [
                {"symbol": "THYAO", "shares": 100, "cost_per_share": 280, "asset_type": "stock"},
                {"symbol": "USD", "shares": 1000, "cost_per_share": 35, "asset_type": "fx"},
            ],
        }
        p = Portfolio.from_dict(data)
        assert p._benchmark == "XU030"
        assert len(p) == 2
        assert "THYAO" in p.symbols

    def test_roundtrip(self, sample_portfolio):
        """Test export and re-import produces equivalent portfolio."""
        data = sample_portfolio.to_dict()
        restored = Portfolio.from_dict(data)
        assert len(restored) == len(sample_portfolio)
        assert restored._benchmark == sample_portfolio._benchmark
        assert set(restored.symbols) == set(sample_portfolio.symbols)


# =============================================================================
# Holding Dataclass Tests
# =============================================================================


class TestHolding:
    """Tests for Holding dataclass."""

    def test_holding_creation(self):
        """Test creating a Holding."""
        h = Holding("THYAO", 100, 280.0, "stock")
        assert h.symbol == "THYAO"
        assert h.shares == 100
        assert h.cost_per_share == 280.0
        assert h.asset_type == "stock"

    def test_holding_none_cost(self):
        """Test Holding with None cost."""
        h = Holding("THYAO", 100, None, "stock")
        assert h.cost_per_share is None

    def test_holding_with_purchase_date(self):
        """Test Holding with purchase_date."""
        h = Holding("THYAO", 100, 280.0, "stock", purchase_date=date(2024, 1, 15))
        assert h.purchase_date == date(2024, 1, 15)

    def test_holding_default_purchase_date_none(self):
        """Test Holding default purchase_date is None."""
        h = Holding("THYAO", 100, 280.0, "stock")
        assert h.purchase_date is None


# =============================================================================
# Purchase Date Tests
# =============================================================================


class TestPurchaseDate:
    """Tests for purchase_date feature."""

    def test_add_with_date_string(self, empty_portfolio):
        """Test adding holding with date as string."""
        empty_portfolio.add("THYAO", shares=100, cost=280.0, purchase_date="2024-01-15")
        h = empty_portfolio._holdings["THYAO"]
        assert h.purchase_date == date(2024, 1, 15)

    def test_add_with_date_object(self, empty_portfolio):
        """Test adding holding with date as date object."""
        empty_portfolio.add("THYAO", shares=100, cost=280.0, purchase_date=date(2024, 6, 1))
        h = empty_portfolio._holdings["THYAO"]
        assert h.purchase_date == date(2024, 6, 1)

    def test_add_with_datetime_object(self, empty_portfolio):
        """Test adding holding with date as datetime object."""
        dt = datetime(2024, 3, 15, 10, 30, 0)
        empty_portfolio.add("THYAO", shares=100, cost=280.0, purchase_date=dt)
        h = empty_portfolio._holdings["THYAO"]
        assert h.purchase_date == date(2024, 3, 15)

    def test_add_without_date_defaults_to_today(self, empty_portfolio):
        """Test adding holding without date defaults to today."""
        empty_portfolio.add("THYAO", shares=100, cost=280.0)
        h = empty_portfolio._holdings["THYAO"]
        assert h.purchase_date == date.today()

    def test_holdings_has_purchase_date_column(self, empty_portfolio):
        """Test holdings DataFrame has purchase_date column."""
        empty_portfolio.add("THYAO", shares=100, cost=280.0, purchase_date="2024-01-15")
        df = empty_portfolio.holdings
        assert "purchase_date" in df.columns
        assert df.iloc[0]["purchase_date"] == date(2024, 1, 15)

    def test_holdings_has_holding_days_column(self, empty_portfolio):
        """Test holdings DataFrame has holding_days column."""
        # Set purchase date to 30 days ago
        purchase = date.today() - timedelta(days=30)
        empty_portfolio.add("THYAO", shares=100, cost=280.0, purchase_date=purchase)
        df = empty_portfolio.holdings
        assert "holding_days" in df.columns
        assert df.iloc[0]["holding_days"] == 30

    def test_holdings_columns_empty_portfolio(self, empty_portfolio):
        """Test empty portfolio has purchase_date and holding_days columns."""
        df = empty_portfolio.holdings
        assert "purchase_date" in df.columns
        assert "holding_days" in df.columns

    def test_to_dict_includes_purchase_date(self, empty_portfolio):
        """Test to_dict() includes purchase_date."""
        empty_portfolio.add("THYAO", shares=100, cost=280.0, purchase_date="2024-01-15")
        data = empty_portfolio.to_dict()
        assert data["holdings"][0]["purchase_date"] == "2024-01-15"

    def test_to_dict_null_purchase_date(self):
        """Test to_dict() handles None purchase_date (legacy holdings)."""
        p = Portfolio()
        # Manually create holding without purchase_date
        p._holdings["THYAO"] = Holding("THYAO", 100, 280.0, "stock", purchase_date=None)
        data = p.to_dict()
        assert data["holdings"][0]["purchase_date"] is None

    def test_from_dict_restores_purchase_date(self):
        """Test from_dict() restores purchase_date."""
        data = {
            "benchmark": "XU100",
            "holdings": [
                {
                    "symbol": "THYAO",
                    "shares": 100,
                    "cost_per_share": 280.0,
                    "asset_type": "stock",
                    "purchase_date": "2024-01-15",
                }
            ],
        }
        p = Portfolio.from_dict(data)
        h = p._holdings["THYAO"]
        assert h.purchase_date == date(2024, 1, 15)

    def test_from_dict_handles_missing_purchase_date(self):
        """Test from_dict() handles legacy data without purchase_date."""
        data = {
            "benchmark": "XU100",
            "holdings": [
                {
                    "symbol": "THYAO",
                    "shares": 100,
                    "cost_per_share": 280.0,
                    "asset_type": "stock",
                }
            ],
        }
        p = Portfolio.from_dict(data)
        h = p._holdings["THYAO"]
        # Should default to today when not specified
        assert h.purchase_date == date.today()

    def test_from_dict_handles_null_purchase_date(self):
        """Test from_dict() handles explicit null purchase_date."""
        data = {
            "benchmark": "XU100",
            "holdings": [
                {
                    "symbol": "THYAO",
                    "shares": 100,
                    "cost_per_share": 280.0,
                    "asset_type": "stock",
                    "purchase_date": None,
                }
            ],
        }
        p = Portfolio.from_dict(data)
        h = p._holdings["THYAO"]
        # Should be today when explicitly None
        assert h.purchase_date == date.today()

    def test_roundtrip_with_purchase_date(self, empty_portfolio):
        """Test export and re-import preserves purchase_date."""
        empty_portfolio.add("THYAO", shares=100, cost=280.0, purchase_date="2024-01-15")
        empty_portfolio.add("GARAN", shares=200, cost=50.0, purchase_date="2024-06-01")

        data = empty_portfolio.to_dict()
        restored = Portfolio.from_dict(data)

        assert restored._holdings["THYAO"].purchase_date == date(2024, 1, 15)
        assert restored._holdings["GARAN"].purchase_date == date(2024, 6, 1)

    def test_multiple_holdings_different_dates(self, empty_portfolio):
        """Test portfolio with holdings from different dates."""
        empty_portfolio.add("THYAO", shares=100, cost=280.0, purchase_date="2024-01-15")
        empty_portfolio.add("GARAN", shares=200, cost=50.0, purchase_date="2024-06-01")
        empty_portfolio.add("ASELS", shares=50, cost=120.0)  # Today

        df = empty_portfolio.holdings
        assert len(df) == 3

        thyao_row = df[df["symbol"] == "THYAO"].iloc[0]
        garan_row = df[df["symbol"] == "GARAN"].iloc[0]
        asels_row = df[df["symbol"] == "ASELS"].iloc[0]

        assert thyao_row["purchase_date"] == date(2024, 1, 15)
        assert garan_row["purchase_date"] == date(2024, 6, 1)
        assert asels_row["purchase_date"] == date.today()


# =============================================================================
# Currency/Metal/Commodity Constants Tests
# =============================================================================


class TestConstants:
    """Tests for currency/metal/commodity constants."""

    def test_fx_currencies_count(self):
        """Test we have 65 currencies."""
        assert len(FX_CURRENCIES) >= 60  # Allow some flexibility

    def test_major_currencies_present(self):
        """Test major currencies are in the list."""
        majors = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD"]
        for m in majors:
            assert m in FX_CURRENCIES

    def test_metals_present(self):
        """Test gold/silver variants present."""
        assert "gram-altin" in FX_METALS
        assert "ceyrek-altin" in FX_METALS
        assert "gram-gumus" in FX_METALS

    def test_commodities_present(self):
        """Test commodities present."""
        assert "BRENT" in FX_COMMODITIES


# =============================================================================
# Get Asset Function Tests
# =============================================================================


class TestGetAsset:
    """Tests for _get_asset helper function."""

    def test_get_stock(self):
        """Test getting stock asset."""
        from borsapy.ticker import Ticker
        asset = _get_asset("THYAO", "stock")
        assert isinstance(asset, Ticker)

    def test_get_fx(self):
        """Test getting FX asset."""
        from borsapy.fx import FX
        asset = _get_asset("USD", "fx")
        assert isinstance(asset, FX)

    def test_get_crypto(self):
        """Test getting crypto asset."""
        from borsapy.crypto import Crypto
        asset = _get_asset("BTCTRY", "crypto")
        assert isinstance(asset, Crypto)

    def test_get_fund(self):
        """Test getting fund asset."""
        from borsapy.fund import Fund
        asset = _get_asset("AAK", "fund")
        assert isinstance(asset, Fund)


# =============================================================================
# Repr Tests
# =============================================================================


class TestRepr:
    """Tests for string representation."""

    def test_repr_empty(self, empty_portfolio):
        """Test repr of empty portfolio."""
        repr_str = repr(empty_portfolio)
        assert "Portfolio" in repr_str
        assert "0 holdings" in repr_str

    def test_repr_with_holdings(self, sample_portfolio):
        """Test repr of portfolio with holdings."""
        repr_str = repr(sample_portfolio)
        assert "Portfolio" in repr_str
        assert "2 holdings" in repr_str
        assert "TL" in repr_str


# =============================================================================
# Integration Tests (require network)
# =============================================================================


@pytest.mark.integration
class TestIntegration:
    """Integration tests with live API (marked for optional execution)."""

    def test_add_stock_live(self):
        """Test adding stock with live price lookup."""
        p = Portfolio()
        p.add("THYAO", shares=100)  # No cost - uses live price
        assert len(p) == 1
        assert p._holdings["THYAO"].cost_per_share is not None
        assert p._holdings["THYAO"].cost_per_share > 0

    def test_portfolio_value_live(self):
        """Test portfolio value calculation with live prices."""
        p = Portfolio()
        p.add("THYAO", shares=100, cost=280.0)
        value = p.value
        assert value > 0

    def test_holdings_dataframe_live(self):
        """Test holdings DataFrame with live prices."""
        p = Portfolio()
        p.add("THYAO", shares=100, cost=280.0)
        df = p.holdings
        assert len(df) == 1
        assert df.iloc[0]["current_price"] > 0
        assert df.iloc[0]["value"] > 0

    def test_portfolio_history_live(self):
        """Test portfolio history with live data."""
        p = Portfolio()
        p.add("THYAO", shares=100, cost=280.0)
        hist = p.history(period="1mo")
        assert not hist.empty
        assert "Value" in hist.columns
        assert "Daily_Return" in hist.columns

    def test_risk_metrics_live(self):
        """Test risk metrics calculation."""
        p = Portfolio()
        p.add("THYAO", shares=100, cost=280.0)
        p.add("GARAN", shares=200, cost=50.0)
        metrics = p.risk_metrics(period="3mo")
        assert "sharpe_ratio" in metrics
        assert "beta" in metrics
        assert metrics["trading_days"] > 0

    def test_correlation_matrix_live(self):
        """Test correlation matrix calculation."""
        p = Portfolio()
        p.add("THYAO", shares=100, cost=280.0)
        p.add("GARAN", shares=200, cost=50.0)
        corr = p.correlation_matrix(period="3mo")
        assert not corr.empty
        assert "THYAO" in corr.columns
        assert "GARAN" in corr.columns

    def test_mixed_assets_live(self):
        """Test portfolio with mixed asset types."""
        p = Portfolio()
        p.add("THYAO", shares=100, cost=280.0)  # Stock
        p.add("USD", shares=1000, cost=35.0, asset_type="fx")  # Currency
        assert len(p) == 2
        assert p.value > 0

    def test_fund_in_portfolio(self):
        """Test adding fund to portfolio."""
        p = Portfolio()
        p.add("YAY", shares=1000, cost=1.5, asset_type="fund")
        assert len(p) == 1
        h = p._holdings["YAY"]
        assert h.asset_type == "fund"

    def test_benchmark_beta(self):
        """Test beta calculation with different benchmarks."""
        p = Portfolio()
        p.add("THYAO", shares=100, cost=280.0)
        p.add("GARAN", shares=200, cost=50.0)

        # Test with default benchmark (XU100)
        beta_xu100 = p.beta(period="3mo")

        # Test with different benchmark
        beta_xu030 = p.beta(benchmark="XU030", period="3mo")

        # Both should be numeric (may be NaN if insufficient data)
        assert isinstance(beta_xu100, (float, np.floating))
        assert isinstance(beta_xu030, (float, np.floating))
