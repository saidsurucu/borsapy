"""Tests for fund management fees feature."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from borsapy._providers.tefas import TEFASProvider
from borsapy.fund import Fund, management_fees

# =============================================================================
# Unit Tests: _parse_turkish_decimal
# =============================================================================


class TestParseTurkishDecimal:
    """Tests for TEFASProvider._parse_turkish_decimal static method."""

    def test_normal_decimal(self):
        assert TEFASProvider._parse_turkish_decimal("2,2") == 2.2

    def test_multiple_decimals(self):
        assert TEFASProvider._parse_turkish_decimal("3,65") == 3.65

    def test_integer_string(self):
        assert TEFASProvider._parse_turkish_decimal("5") == 5.0

    def test_zero_string(self):
        assert TEFASProvider._parse_turkish_decimal("0") == 0.0

    def test_none_input(self):
        assert TEFASProvider._parse_turkish_decimal(None) is None

    def test_empty_string(self):
        assert TEFASProvider._parse_turkish_decimal("") is None

    def test_whitespace_string(self):
        assert TEFASProvider._parse_turkish_decimal("  ") is None

    def test_invalid_string(self):
        assert TEFASProvider._parse_turkish_decimal("abc") is None

    def test_numeric_input(self):
        """Numeric values get str()-converted and parsed."""
        assert TEFASProvider._parse_turkish_decimal(2.2) == 2.2

    def test_zero_integer(self):
        assert TEFASProvider._parse_turkish_decimal(0) == 0.0


# =============================================================================
# Unit Tests: get_management_fees (mocked)
# =============================================================================


# v2 envelope shape used by all /api/funds/* endpoints since 2026-04.
MOCK_API_RESPONSE = {
    "errorCode": None,
    "errorMessage": None,
    "resultList": [
        {
            "fonKodu": "AAK",
            "fonUnvan": "AK PORTFOY KISA VADELI BONO",
            "fonTurAciklama": "Kısa Vadeli Borçlanma",
            "kurucuKod": "AKP",
            "uygulananYu1Y": "1,0",
            "fonIcTuzukYu1G": "2,2",
            "fonTopGiderKesoran": "3,65",
            "yillikGetiri": 45.5,
        },
        {
            "fonKodu": "BS1",
            "fonUnvan": "AHLATCI PORTFOY BIRINCI SERBEST",
            "fonTurAciklama": "Serbest",
            "kurucuKod": "AHL",
            "uygulananYu1Y": "0",
            "fonIcTuzukYu1G": "2,2",
            "fonTopGiderKesoran": "3,65",
            "yillikGetiri": None,
        },
        {
            "fonKodu": "XYZ",
            "fonUnvan": "TEST FON",
            "fonTurAciklama": "Test",
            "kurucuKod": "TST",
            "uygulananYu1Y": None,
            "fonIcTuzukYu1G": None,
            "fonTopGiderKesoran": None,
            "yillikGetiri": None,
        },
    ],
}


class TestGetManagementFeesMocked:
    """Unit tests for TEFASProvider.get_management_fees with mocked API."""

    def _make_provider(self):
        import json as _json

        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_API_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json; charset=utf-8"}
        mock_response.content = _json.dumps(MOCK_API_RESPONSE).encode("utf-8")

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        provider = TEFASProvider.__new__(TEFASProvider)
        provider._client = mock_client
        provider._cache = {}
        return provider

    def test_returns_list(self):
        provider = self._make_provider()
        result = provider.get_management_fees()
        assert isinstance(result, list)
        assert len(result) == 3

    def test_field_mapping(self):
        provider = self._make_provider()
        result = provider.get_management_fees()
        first = result[0]

        assert first["fund_code"] == "AAK"
        assert first["name"] == "AK PORTFOY KISA VADELI BONO"
        assert first["fund_category"] == "Kısa Vadeli Borçlanma"
        assert first["founder_code"] == "AKP"
        assert first["applied_fee"] == 1.0
        assert first["prospectus_fee"] == 2.2
        assert first["max_expense_ratio"] == 3.65
        assert first["annual_return"] == 45.5

    def test_null_fees(self):
        provider = self._make_provider()
        result = provider.get_management_fees()
        null_fund = result[2]  # XYZ has all None

        assert null_fund["applied_fee"] is None
        assert null_fund["prospectus_fee"] is None
        assert null_fund["max_expense_ratio"] is None
        assert null_fund["annual_return"] is None

    def test_zero_fee(self):
        provider = self._make_provider()
        result = provider.get_management_fees()
        bs1 = result[1]  # BS1 has "0" for applied_fee

        assert bs1["applied_fee"] == 0.0


# =============================================================================
# Unit Tests: management_fees() DataFrame wrapper (mocked)
# =============================================================================


class TestManagementFeesFunctionMocked:
    """Unit tests for the management_fees() module-level function."""

    @patch("borsapy.fund.get_tefas_provider")
    def test_returns_dataframe(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.get_management_fees.return_value = [
            {
                "fund_code": "AAK",
                "name": "Test",
                "fund_category": "Cat",
                "founder_code": "AKP",
                "applied_fee": 1.0,
                "prospectus_fee": 2.2,
                "max_expense_ratio": 3.65,
                "annual_return": 45.5,
            }
        ]
        mock_get_provider.return_value = mock_provider

        df = management_fees()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert "fund_code" in df.columns
        assert "applied_fee" in df.columns

    @patch("borsapy.fund.get_tefas_provider")
    def test_empty_results(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.get_management_fees.return_value = []
        mock_get_provider.return_value = mock_provider

        df = management_fees()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert "fund_code" in df.columns
        assert "max_expense_ratio" in df.columns

    @patch("borsapy.fund.get_tefas_provider")
    def test_correct_columns(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.get_management_fees.return_value = [
            {
                "fund_code": "A",
                "name": "B",
                "fund_category": "C",
                "founder_code": "D",
                "applied_fee": 1.0,
                "prospectus_fee": 2.0,
                "max_expense_ratio": 3.0,
                "annual_return": 4.0,
            }
        ]
        mock_get_provider.return_value = mock_provider

        df = management_fees()
        expected = {
            "fund_code", "name", "fund_category", "founder_code",
            "applied_fee", "prospectus_fee", "max_expense_ratio", "annual_return",
        }
        assert set(df.columns) == expected


# =============================================================================
# Unit Tests: Fund.management_fee property (mocked)
# =============================================================================


class TestFundManagementFeePropertyMocked:
    """Unit tests for Fund.management_fee property."""

    @patch("borsapy.fund.get_tefas_provider")
    def test_returns_dict(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.get_management_fees.return_value = [
            {
                "fund_code": "AAK",
                "name": "Test",
                "fund_category": "Cat",
                "founder_code": "AKP",
                "applied_fee": 1.0,
                "prospectus_fee": 2.2,
                "max_expense_ratio": 3.65,
                "annual_return": 45.5,
            }
        ]
        mock_get_provider.return_value = mock_provider

        fund = Fund("AAK", fund_type="YAT")
        fee = fund.management_fee
        assert isinstance(fee, dict)
        assert fee["applied_fee"] == 1.0
        assert fee["prospectus_fee"] == 2.2
        assert fee["max_expense_ratio"] == 3.65
        assert fee["annual_return"] == 45.5

    @patch("borsapy.fund.get_tefas_provider")
    def test_correct_keys(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.get_management_fees.return_value = [
            {
                "fund_code": "AAK",
                "name": "Test",
                "fund_category": "Cat",
                "founder_code": "AKP",
                "applied_fee": 1.0,
                "prospectus_fee": 2.0,
                "max_expense_ratio": 3.0,
                "annual_return": 4.0,
            }
        ]
        mock_get_provider.return_value = mock_provider

        fund = Fund("AAK", fund_type="YAT")
        fee = fund.management_fee
        assert set(fee.keys()) == {"applied_fee", "prospectus_fee", "max_expense_ratio", "annual_return"}

    @patch("borsapy.fund.get_tefas_provider")
    def test_nonexistent_fund(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.get_management_fees.return_value = [
            {"fund_code": "OTHER", "applied_fee": 1.0, "prospectus_fee": 2.0, "max_expense_ratio": 3.0, "annual_return": 4.0}
        ]
        mock_get_provider.return_value = mock_provider

        fund = Fund("NONEXIST", fund_type="YAT")
        fee = fund.management_fee
        assert fee["applied_fee"] is None
        assert fee["prospectus_fee"] is None
        assert fee["max_expense_ratio"] is None
        assert fee["annual_return"] is None

    @patch("borsapy.fund.get_tefas_provider")
    def test_api_error_returns_empty(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.get_management_fees.side_effect = Exception("API error")
        mock_get_provider.return_value = mock_provider

        fund = Fund("AAK", fund_type="YAT")
        fee = fund.management_fee
        assert fee == {
            "applied_fee": None,
            "prospectus_fee": None,
            "max_expense_ratio": None,
            "annual_return": None,
        }


# =============================================================================
# Integration Tests (require network)
# =============================================================================


@pytest.mark.integration
class TestManagementFeesIntegration:
    """Integration tests requiring network connection."""

    def test_management_fees_yat(self):
        df = management_fees(fund_type="YAT")
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert "fund_code" in df.columns
        assert "applied_fee" in df.columns
        assert "prospectus_fee" in df.columns
        assert "max_expense_ratio" in df.columns

    def test_management_fees_emk(self):
        df = management_fees(fund_type="EMK")
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_management_fees_founder_filter(self):
        df = management_fees(founder="AKP")
        assert isinstance(df, pd.DataFrame)
        if len(df) > 0:
            assert (df["founder_code"] == "AKP").all()

    def test_management_fees_numeric_values(self):
        df = management_fees()
        # At least some funds should have numeric fee values
        non_null = df["applied_fee"].dropna()
        assert len(non_null) > 0
        assert non_null.dtype in ("float64", "object")

    def test_fund_management_fee_property(self):
        fund = Fund("AAK")
        fee = fund.management_fee
        assert isinstance(fee, dict)
        assert "applied_fee" in fee
        assert "prospectus_fee" in fee
        assert "max_expense_ratio" in fee
        assert "annual_return" in fee
