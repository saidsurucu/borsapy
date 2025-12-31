"""Market-level functions for BIST data."""

import pandas as pd

from borsapy._providers.kap import get_kap_provider


def companies() -> pd.DataFrame:
    """
    Get list of all BIST companies.

    Returns:
        DataFrame with columns:
        - ticker: Stock ticker code (e.g., "THYAO", "GARAN")
        - name: Company name
        - city: Company headquarters city

    Examples:
        >>> import borsapy as bp
        >>> bp.companies()
              ticker                                    name        city
        0      ACSEL            ACIPAYAM SELULOZ SANAYI A.S.     DENIZLI
        1      ADEL                  ADEL KALEMCILIK A.S.    ISTANBUL
        ...
    """
    provider = get_kap_provider()
    return provider.get_companies()


def search_companies(query: str) -> pd.DataFrame:
    """
    Search BIST companies by name or ticker.

    Args:
        query: Search query (ticker code or company name)

    Returns:
        DataFrame with matching companies, sorted by relevance.

    Examples:
        >>> import borsapy as bp
        >>> bp.search_companies("THYAO")
              ticker                                    name        city
        0      THYAO          TURK HAVA YOLLARI A.O.    ISTANBUL

        >>> bp.search_companies("banka")
              ticker                                    name        city
        0      GARAN              TURKIYE GARANTI BANKASI A.S.  ISTANBUL
        1      AKBNK              AKBANK T.A.S.               ISTANBUL
        ...
    """
    provider = get_kap_provider()
    return provider.search(query)
