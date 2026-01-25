"""KAP Holdings provider for fund portfolio holdings from disclosure PDFs.

This module extracts detailed portfolio holdings (individual stocks, ETFs, etc.)
from KAP "Portföy Dağılım Raporu" (Portfolio Distribution Report) disclosures.

Uses pymupdf4llm for PDF to markdown conversion and OpenRouter LLM for parsing.
"""

import io
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from borsapy._providers.base import BaseProvider
from borsapy.exceptions import APIError, DataNotAvailableError

# Portfolio Distribution Report disclosure type ID
PORTFOLIO_REPORT_DISCLOSURE_TYPE = "8aca490d502e34b801502e380044002b"

# Cache duration
CACHE_DURATION = 3600  # 1 hour

# OpenRouter default model
OPENROUTER_MODEL = "google/gemini-3-flash-preview"


@dataclass
class Holding:
    """Represents a single holding in a fund portfolio."""

    symbol: str
    isin: str | None
    name: str
    weight: float
    holding_type: str  # 'stock', 'etf', 'fund', 'viop', 'viop_cash', 'reverse_repo', 'term_deposit'
    country: str | None = None
    nominal_value: float | None = None
    market_value: float | None = None


class KAPHoldingsProvider(BaseProvider):
    """
    Provider for extracting fund portfolio holdings from KAP disclosures.

    Uses OpenRouter LLM to parse portfolio distribution PDFs.

    Example:
        >>> provider = KAPHoldingsProvider()
        >>> holdings = provider.get_holdings("YAY", api_key="sk-or-v1-...")
        >>> for h in holdings:
        ...     print(f"{h.symbol}: {h.weight:.2f}%")
    """

    # KAP API endpoints
    DISCLOSURE_FILTER_URL = "https://kap.org.tr/tr/api/disclosure/filter/FILTERYFBF"
    DISCLOSURE_PAGE_URL = "https://kap.org.tr/tr/Bildirim"
    FILE_DOWNLOAD_URL = "https://kap.org.tr/tr/api/file/download"
    FUND_INFO_URL = "https://www.kap.org.tr/tr/fon-bilgileri/genel"

    def __init__(self):
        super().__init__()
        self._fund_id_cache: dict[str, str] = {}
        self._holdings_cache: dict[str, tuple[list[Holding], datetime]] = {}
        self._holdings_cache_time: dict[str, float] = {}

    def get_fund_id(self, fund_code: str) -> str | None:
        """
        Get KAP fund ID for a fund code.

        Uses the KAP fund info page linked from TEFAS to extract the fund's objId.

        Args:
            fund_code: TEFAS fund code (e.g., "YAY", "AAK")

        Returns:
            KAP fund ID or None if not found.
        """
        fund_code = fund_code.upper()

        # Check cache
        if fund_code in self._fund_id_cache:
            return self._fund_id_cache[fund_code]

        try:
            # Get fund info from TEFAS which includes KAP link
            from borsapy._providers.tefas import get_tefas_provider

            tefas = get_tefas_provider()
            info = tefas.get_fund_detail(fund_code)

            kap_link = info.get("kap_link")
            if not kap_link:
                return None

            # Fetch KAP fund info page
            response = self._client.get(kap_link, timeout=30)
            response.raise_for_status()

            # Extract objId from page data
            # Pattern: objId\":\"33E5FED7E50300EAE0530A4A622B2AEA\" (escaped quotes in Next.js)
            match = re.search(r'objId[\\"\':]+([A-F0-9]{32})', response.text)
            if match:
                fund_id = match.group(1)
                self._fund_id_cache[fund_code] = fund_id
                return fund_id

            return None

        except Exception:
            return None

    def get_disclosures(
        self,
        fund_code: str,
        days: int = 365,
    ) -> list[dict[str, Any]]:
        """
        Get portfolio distribution report disclosures for a fund.

        Args:
            fund_code: TEFAS fund code (e.g., "YAY")
            days: Number of days to look back (default: 365)

        Returns:
            List of disclosures with disclosure_id, disclosure_index, publish_date, etc.
        """
        fund_id = self.get_fund_id(fund_code)
        if not fund_id:
            raise DataNotAvailableError(f"Fund not found in KAP: {fund_code}")

        url = f"{self.DISCLOSURE_FILTER_URL}/{fund_id}/{PORTFOLIO_REPORT_DISCLOSURE_TYPE}/{days}"

        try:
            response = self._client.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            disclosures = []
            for item in data:
                basic = item.get("disclosureBasic", {})
                disclosures.append({
                    "disclosure_id": basic.get("disclosureId"),
                    "disclosure_index": basic.get("disclosureIndex"),
                    "publish_date": basic.get("publishDate"),
                    "title": basic.get("title"),
                    "summary": basic.get("summary"),
                    "year": basic.get("year"),
                    "period": basic.get("donem"),  # Month number
                    "attachment_count": basic.get("attachmentCount", 0),
                })

            return disclosures

        except Exception as e:
            raise APIError(f"Failed to fetch disclosures for {fund_code}: {e}") from e

    def get_latest_disclosure(self, fund_code: str) -> dict[str, Any] | None:
        """Get the most recent portfolio distribution report disclosure."""
        disclosures = self.get_disclosures(fund_code, days=365)
        if disclosures:
            return disclosures[0]  # Most recent first
        return None

    def _get_file_id(self, disclosure_index: int) -> str | None:
        """
        Extract file ID from disclosure page HTML.

        Args:
            disclosure_index: KAP disclosure index number

        Returns:
            File ID (32 hex chars) or None if not found.
        """
        url = f"{self.DISCLOSURE_PAGE_URL}/{disclosure_index}"

        try:
            response = self._client.get(url, timeout=30)
            response.raise_for_status()

            # Find file download link: file/download/{32-char-hex-id}
            match = re.search(r'file/download/([a-f0-9]{32})', response.text)
            if match:
                return match.group(1)

            return None

        except Exception:
            return None

    def _download_pdf(self, file_id: str) -> bytes | None:
        """
        Download and extract PDF from Java-serialized wrapper.

        KAP file downloads return data wrapped in Java serialization format.
        The actual PDF starts at byte offset ~27 with the %PDF- marker.

        Args:
            file_id: KAP file ID (32 hex chars)

        Returns:
            Raw PDF bytes or None if failed.
        """
        url = f"{self.FILE_DOWNLOAD_URL}/{file_id}"

        try:
            response = self._client.get(url, timeout=60)
            response.raise_for_status()

            data = response.content

            # Find %PDF- marker and extract PDF
            pdf_start = data.find(b"%PDF-")
            if pdf_start != -1:
                return data[pdf_start:]

            return None

        except Exception:
            return None

    def _parse_holdings_with_llm(self, pdf_data: bytes, api_key: str) -> list[Holding]:
        """
        Parse holdings from PDF using OpenRouter LLM.

        Args:
            pdf_data: Raw PDF bytes
            api_key: OpenRouter API key

        Returns:
            List of Holding objects.
        """
        try:
            import pymupdf
            import pymupdf4llm
        except ImportError:
            raise ImportError(
                "pymupdf4llm is required for PDF parsing. "
                "Install with: pip install pymupdf4llm"
            ) from None

        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai package is required for OpenRouter API. "
                "Install with: pip install openai"
            ) from None

        # Convert PDF to markdown using pymupdf4llm (better table handling)
        doc = pymupdf.open(stream=pdf_data, filetype="pdf")
        md_text = pymupdf4llm.to_markdown(doc)

        # Truncate if too long (balance between completeness and speed)
        MAX_CHARS = 80000  # ~20K tokens - enough for most fund portfolios
        if len(md_text) > MAX_CHARS:
            md_text = md_text[:MAX_CHARS]

        # Prepare OpenRouter client
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

        # Simplified prompt focusing on key columns
        prompt = '''Extract stock holdings from this Turkish investment fund portfolio report.

For each stock row, extract:
- symbol: BIST stock ticker (4-5 letters like "ASELS", "THYAO", "GARAN") - NOT the ISIN code!
- name: Company name
- weight: Portfolio weight percentage from "Toplam%" or "Fon Toplam Değerine Oranı %" column (e.g. 5.25)
- type: "stock"
- market_value: Value in TL (number)

IMPORTANT:
- symbol must be BIST ticker (ASELS, THYAO), NOT ISIN (TRAASELS...)
- weight is percentage (usually between 0.01 and 10)
- Turkish number format: "5,25" means 5.25

Return JSON array only:
[{"symbol": "ASELS", "name": "ASELSAN", "weight": 5.25, "type": "stock", "market_value": 228500000}]

DATA:
'''

        try:
            completion = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=[{"role": "user", "content": prompt + md_text}],
            )

            response_text = completion.choices[0].message.content

            # Extract JSON from response (handle markdown code blocks)
            json_text = response_text
            if "```json" in response_text:
                json_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_text = response_text.split("```")[1].split("```")[0]

            # Try to find JSON array in response
            json_text = json_text.strip()

            # Find the start of JSON array
            start_idx = json_text.find("[")
            if start_idx == -1:
                raise APIError("No JSON array found in LLM response")

            # Find matching end bracket
            bracket_count = 0
            end_idx = -1
            for i, char in enumerate(json_text[start_idx:], start_idx):
                if char == "[":
                    bracket_count += 1
                elif char == "]":
                    bracket_count -= 1
                    if bracket_count == 0:
                        end_idx = i + 1
                        break

            if end_idx == -1:
                # Try to find any closing bracket
                end_idx = json_text.rfind("]") + 1

            if end_idx <= start_idx:
                raise APIError("Could not find valid JSON array bounds")

            json_text = json_text[start_idx:end_idx]

            # Parse JSON
            data = json.loads(json_text)

            # Convert to Holding objects
            holdings = []
            for item in data:
                if not item or not isinstance(item, dict):
                    continue

                # Clean symbol (remove .E suffix if present)
                raw_symbol = item.get("symbol")
                if not raw_symbol:
                    continue
                symbol = str(raw_symbol).replace(".E", "")

                # Parse weight (handle string or number)
                weight = item.get("weight")
                if weight is None:
                    weight = 0.0
                elif isinstance(weight, str):
                    weight = float(weight.replace(",", ".").replace("%", ""))

                # Sanity check: weight should be 0-100%
                # If weight > 100, it's likely market_value was used by mistake
                if weight and weight > 100:
                    continue

                # Parse market_value
                market_value = item.get("market_value")
                if isinstance(market_value, str):
                    market_value = float(market_value.replace(".", "").replace(",", "."))

                holdings.append(Holding(
                    symbol=symbol,
                    isin=item.get("isin"),
                    name=item.get("name", symbol),
                    weight=weight,
                    holding_type=item.get("type", "stock"),
                    country=item.get("country"),
                    market_value=market_value,
                ))

            return self._deduplicate_holdings(holdings)

        except json.JSONDecodeError as e:
            raise APIError(f"Failed to parse LLM response as JSON: {e}") from e
        except Exception as e:
            raise APIError(f"LLM parsing failed: {e}") from e

    def _deduplicate_holdings(self, holdings: list[Holding]) -> list[Holding]:
        """Remove duplicate holdings based on ISIN or symbol."""
        seen = set()
        unique = []

        for h in holdings:
            # Use ISIN as primary key, fall back to symbol
            key = h.isin if h.isin else h.symbol
            if key not in seen:
                seen.add(key)
                unique.append(h)

        return unique

    def get_holdings(
        self,
        fund_code: str,
        api_key: str,
        period: str | None = None,
    ) -> list[Holding]:
        """
        Get detailed portfolio holdings for a fund.

        Args:
            fund_code: TEFAS fund code (e.g., "YAY", "AAK")
            api_key: OpenRouter API key for LLM parsing
            period: Optional period in format "YYYY-MM" (e.g., "2025-12")
                   If None, returns the most recent holdings.

        Returns:
            List of Holding objects with symbol, weight, type, etc.

        Raises:
            DataNotAvailableError: If fund or holdings not found.
            APIError: If API request fails.

        Example:
            >>> provider = KAPHoldingsProvider()
            >>> holdings = provider.get_holdings("YAY", api_key="sk-or-v1-...")
            >>> for h in holdings:
            ...     print(f"{h.symbol}: {h.weight:.2f}% ({h.holding_type})")
            GOOGL: 6.76% (stock)
            AVGO: 5.11% (stock)
            ...
        """
        fund_code = fund_code.upper()
        cache_key = f"{fund_code}:{period or 'latest'}"
        current_time = time.time()

        # Check cache
        if cache_key in self._holdings_cache:
            cache_time = self._holdings_cache_time.get(cache_key, 0)
            if (current_time - cache_time) < CACHE_DURATION:
                return self._holdings_cache[cache_key][0]

        # Get disclosures
        disclosures = self.get_disclosures(fund_code)
        if not disclosures:
            raise DataNotAvailableError(
                f"No portfolio distribution reports found for {fund_code}"
            )

        # Find matching disclosure
        disclosure = None
        if period:
            # Parse period (YYYY-MM)
            match = re.match(r'(\d{4})-(\d{2})', period)
            if match:
                year = int(match.group(1))
                month = int(match.group(2))
                for d in disclosures:
                    if d.get("year") == year and d.get("period") == month:
                        disclosure = d
                        break

        if disclosure is None:
            disclosure = disclosures[0]  # Most recent

        # Get file ID from disclosure page
        disclosure_index = disclosure.get("disclosure_index")
        if not disclosure_index:
            raise DataNotAvailableError("Disclosure has no index")

        file_id = self._get_file_id(disclosure_index)
        if not file_id:
            raise DataNotAvailableError(
                f"Could not find PDF attachment for disclosure {disclosure_index}"
            )

        # Download and parse PDF
        pdf_data = self._download_pdf(file_id)
        if not pdf_data:
            raise DataNotAvailableError(
                f"Failed to download PDF for file {file_id}"
            )

        # Parse with LLM
        holdings = self._parse_holdings_with_llm(pdf_data, api_key)

        # Get report date from disclosure
        report_date = None
        if disclosure.get("year") and disclosure.get("period"):
            try:
                report_date = datetime(
                    disclosure["year"],
                    disclosure["period"],
                    1
                )
            except ValueError:
                pass

        # Cache result
        self._holdings_cache[cache_key] = (holdings, report_date)
        self._holdings_cache_time[cache_key] = current_time

        return holdings

    def get_holdings_df(
        self,
        fund_code: str,
        api_key: str,
        period: str | None = None,
    ) -> pd.DataFrame:
        """
        Get holdings as a pandas DataFrame.

        Args:
            fund_code: TEFAS fund code
            api_key: OpenRouter API key for LLM parsing
            period: Optional period in format "YYYY-MM"

        Returns:
            DataFrame with columns: symbol, isin, name, weight, type, country, value
        """
        holdings = self.get_holdings(fund_code, api_key, period)

        if not holdings:
            return pd.DataFrame(columns=[
                'symbol', 'isin', 'name', 'weight', 'type', 'country', 'value'
            ])

        records = []
        for h in holdings:
            records.append({
                'symbol': h.symbol,
                'isin': h.isin,
                'name': h.name,
                'weight': h.weight,
                'type': h.holding_type,
                'country': h.country,
                'value': h.market_value,
            })

        df = pd.DataFrame(records)
        df = df.sort_values('weight', ascending=False).reset_index(drop=True)
        return df


# Singleton
_provider: KAPHoldingsProvider | None = None


def get_kap_holdings_provider() -> KAPHoldingsProvider:
    """Get singleton provider instance."""
    global _provider
    if _provider is None:
        _provider = KAPHoldingsProvider()
    return _provider
