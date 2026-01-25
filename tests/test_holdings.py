"""Tests for Fund holdings functionality."""

import os
from unittest.mock import patch

import pandas as pd
import pytest

from borsapy._providers.kap_holdings import (
    Holding,
    KAPHoldingsProvider,
    get_kap_holdings_provider,
)

# Test API key (for integration tests)
TEST_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")


class TestHolding:
    """Tests for Holding dataclass."""

    def test_holding_creation(self):
        """Test creating a Holding instance."""
        holding = Holding(
            symbol="GOOGL",
            isin="US02079K3059",
            name="ALPHABET INC",
            weight=6.76,
            holding_type="stock",
            country="US",
            nominal_value=7154.00,
            market_value=82478088.00,
        )

        assert holding.symbol == "GOOGL"
        assert holding.isin == "US02079K3059"
        assert holding.name == "ALPHABET INC"
        assert holding.weight == 6.76
        assert holding.holding_type == "stock"
        assert holding.country == "US"
        assert holding.nominal_value == 7154.00
        assert holding.market_value == 82478088.00

    def test_holding_defaults(self):
        """Test Holding default values."""
        holding = Holding(
            symbol="TEST",
            isin=None,
            name="Test Fund",
            weight=1.0,
            holding_type="fund",
        )

        assert holding.country is None
        assert holding.nominal_value is None
        assert holding.market_value is None


class TestKAPHoldingsProvider:
    """Tests for KAPHoldingsProvider."""

    def test_singleton(self):
        """Test that get_kap_holdings_provider returns singleton."""
        provider1 = get_kap_holdings_provider()
        provider2 = get_kap_holdings_provider()
        assert provider1 is provider2

    def test_deduplicate_holdings_by_isin(self):
        """Test deduplication by ISIN."""
        provider = KAPHoldingsProvider()

        holdings = [
            Holding("GOOGL", "US02079K3059", "Alphabet", 6.76, "stock"),
            Holding("GOOG", "US02079K3059", "Alphabet", 6.76, "stock"),  # Same ISIN
            Holding("MSFT", "US5949181045", "Microsoft", 5.00, "stock"),
        ]

        result = provider._deduplicate_holdings(holdings)

        assert len(result) == 2
        assert result[0].symbol == "GOOGL"  # First one kept
        assert result[1].symbol == "MSFT"

    def test_deduplicate_holdings_by_symbol(self):
        """Test deduplication by symbol when no ISIN."""
        provider = KAPHoldingsProvider()

        holdings = [
            Holding("YAY", None, "YAY Fund 1", 1.0, "fund"),
            Holding("YAY", None, "YAY Fund 2", 1.0, "fund"),  # Same symbol
            Holding("AAK", None, "AAK Fund", 2.0, "fund"),
        ]

        result = provider._deduplicate_holdings(holdings)

        assert len(result) == 2
        assert result[0].symbol == "YAY"
        assert result[1].symbol == "AAK"

    def test_get_holdings_df_empty(self):
        """Test get_holdings_df with empty holdings."""
        provider = KAPHoldingsProvider()

        with patch.object(provider, "get_holdings", return_value=[]):
            df = provider.get_holdings_df("TEST", "fake-api-key")

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert list(df.columns) == [
            "symbol",
            "isin",
            "name",
            "weight",
            "type",
            "country",
            "value",
        ]

    def test_get_holdings_df_with_data(self):
        """Test get_holdings_df returns proper DataFrame."""
        provider = KAPHoldingsProvider()

        mock_holdings = [
            Holding("GOOGL", "US02079K3059", "Alphabet", 6.76, "stock", "US", 7154.0, 82478088.0),
            Holding("MSFT", "US5949181045", "Microsoft", 5.00, "stock", "US", 5000.0, 50000000.0),
        ]

        with patch.object(provider, "get_holdings", return_value=mock_holdings):
            df = provider.get_holdings_df("TEST", "fake-api-key")

        assert len(df) == 2
        # Should be sorted by weight descending
        assert df.iloc[0]["symbol"] == "GOOGL"
        assert df.iloc[0]["weight"] == 6.76
        assert df.iloc[1]["symbol"] == "MSFT"
        assert df.iloc[1]["weight"] == 5.00


class TestFundHoldings:
    """Tests for Fund.get_holdings integration."""

    def test_fund_get_holdings_method(self):
        """Test Fund.get_holdings() method with api_key."""
        from borsapy import Fund

        mock_df = pd.DataFrame({"symbol": ["TEST"], "weight": [1.0]})

        with patch(
            "borsapy._providers.kap_holdings.get_kap_holdings_provider"
        ) as mock_provider:
            mock_provider.return_value.get_holdings_df.return_value = mock_df

            fund = Fund("YAY")
            fund.get_holdings(api_key="test-api-key")

            mock_provider.return_value.get_holdings_df.assert_called_once_with(
                "YAY", "test-api-key", period=None
            )

    def test_fund_get_holdings_with_period(self):
        """Test Fund.get_holdings() method with period."""
        from borsapy import Fund

        mock_df = pd.DataFrame({"symbol": ["TEST"], "weight": [1.0]})

        with patch(
            "borsapy._providers.kap_holdings.get_kap_holdings_provider"
        ) as mock_provider:
            mock_provider.return_value.get_holdings_df.return_value = mock_df

            fund = Fund("YAY")
            fund.get_holdings(api_key="test-api-key", period="2025-01")

            mock_provider.return_value.get_holdings_df.assert_called_once_with(
                "YAY", "test-api-key", period="2025-01"
            )


@pytest.mark.integration
class TestHoldingsIntegration:
    """Integration tests for holdings (require network and API key)."""

    @pytest.mark.skipif(not TEST_API_KEY, reason="OPENROUTER_API_KEY not set")
    def test_fund_holdings_real(self):
        """Test fetching real fund holdings from KAP using LLM."""
        from borsapy import Fund

        fund = Fund("YAY")
        holdings = fund.get_holdings(api_key=TEST_API_KEY)

        # Basic checks
        assert isinstance(holdings, pd.DataFrame)
        assert len(holdings) > 0
        assert "symbol" in holdings.columns
        assert "weight" in holdings.columns
        assert "type" in holdings.columns

        # Weight should be reasonable (90-110% is normal due to LLM parsing)
        total_weight = holdings["weight"].sum()
        assert 90 < total_weight <= 110

        # Should have valid holding types
        valid_types = ["stock", "etf", "fund", "viop", "viop_cash", "term_deposit", "reverse_repo"]
        assert holdings["type"].isin(valid_types).all()

    @pytest.mark.skipif(not TEST_API_KEY, reason="OPENROUTER_API_KEY not set")
    def test_fund_get_holdings_with_period(self):
        """Test fetching holdings for a specific period."""
        from borsapy import Fund

        fund = Fund("YAY")
        holdings = fund.get_holdings(api_key=TEST_API_KEY, period="2024-12")

        # May be empty if no disclosure for that period
        assert isinstance(holdings, pd.DataFrame)

    def test_provider_get_disclosures(self):
        """Test fetching disclosures from KAP (no API key needed)."""
        provider = get_kap_holdings_provider()
        disclosures = provider.get_disclosures("YAY", days=365)

        assert len(disclosures) > 0
        assert "disclosure_id" in disclosures[0]
        assert "publish_date" in disclosures[0]

    def test_provider_get_fund_id(self):
        """Test fetching KAP fund ID (no API key needed)."""
        provider = get_kap_holdings_provider()
        fund_id = provider.get_fund_id("YAY")

        assert fund_id is not None
        assert len(fund_id) == 32  # KAP objId is 32 hex chars

    @pytest.mark.skipif(not TEST_API_KEY, reason="OPENROUTER_API_KEY not set")
    def test_multiple_fund_types(self):
        """Test parsing different fund types with LLM."""
        from borsapy import Fund

        fund_codes = ["YAY", "MAC", "GAF", "AAK", "TTE"]

        for code in fund_codes:
            try:
                fund = Fund(code)
                holdings = fund.get_holdings(api_key=TEST_API_KEY)

                assert isinstance(holdings, pd.DataFrame), f"{code}: Should return DataFrame"

                if len(holdings) > 0:
                    total_weight = holdings["weight"].sum()
                    print(f"{code}: {len(holdings)} holdings, {total_weight:.2f}% total weight")

                    # LLM should achieve high coverage
                    assert total_weight > 80, f"{code}: Weight too low ({total_weight:.2f}%)"

            except Exception as e:
                pytest.fail(f"{code}: Failed with error: {e}")
