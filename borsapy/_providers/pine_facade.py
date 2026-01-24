"""TradingView Pine Facade API provider for indicator metadata."""

from __future__ import annotations

from typing import Any

from borsapy._providers.base import BaseProvider
from borsapy._providers.tradingview import get_tradingview_auth
from borsapy.exceptions import AuthenticationError, DataNotAvailableError

# Standard TradingView indicators
STANDARD_INDICATORS = {
    "RSI": "STD;RSI",
    "MACD": "STD;MACD",
    "BB": "STD;BB",
    "BOLLINGER": "STD;BB",
    "EMA": "STD;EMA",
    "SMA": "STD;SMA",
    "STOCHASTIC": "STD;Stochastic",
    "STOCH": "STD;Stochastic",
    "ATR": "STD;ATR",
    "ADX": "STD;ADX",
    "OBV": "STD;OBV",
    "VWAP": "STD;VWAP",
    "ICHIMOKU": "STD;Ichimoku%Cloud",
    "SUPERTREND": "STD;Supertrend",
    "PSAR": "STD;Parabolic%SAR",
    "CCI": "STD;CCI",
    "MFI": "STD;MFI",
    "ROC": "STD;ROC",
    "WILLIAMS": "STD;Williams%25R",
    "CMF": "STD;CMF",
    "VOLUME": "STD;Volume",
}

# Output field mappings for each indicator type
INDICATOR_OUTPUTS = {
    "STD;RSI": {"plot_0": "value"},
    "STD;MACD": {"plot_0": "macd", "plot_1": "signal", "plot_2": "histogram"},
    "STD;BB": {"plot_0": "middle", "plot_1": "upper", "plot_2": "lower"},
    "STD;EMA": {"plot_0": "value"},
    "STD;SMA": {"plot_0": "value"},
    "STD;Stochastic": {"plot_0": "k", "plot_1": "d"},
    "STD;ATR": {"plot_0": "value"},
    "STD;ADX": {"plot_0": "adx", "plot_1": "plus_di", "plot_2": "minus_di"},
    "STD;OBV": {"plot_0": "value"},
    "STD;VWAP": {"plot_0": "value"},
    "STD;CCI": {"plot_0": "value"},
    "STD;MFI": {"plot_0": "value"},
    "STD;ROC": {"plot_0": "value"},
    "STD;CMF": {"plot_0": "value"},
}

# Module-level cache for indicator metadata
_indicator_cache: dict[tuple[str, str, str, str], dict[str, Any]] = {}


class PineFacadeProvider(BaseProvider):
    """
    TradingView Pine Facade API provider for indicator metadata.

    This provider fetches indicator definitions, inputs, and plot information
    from the TradingView Pine Facade API.

    Standard indicators (STD;*) don't require authentication.
    Custom indicators (PUB;*, USER;*) require TradingView authentication.
    """

    BASE_URL = "https://pine-facade.tradingview.com/pine-facade"

    def __init__(self):
        super().__init__(timeout=15.0)

    def get_indicator(
        self,
        indicator_id: str,
        version: str = "last",
        session: str | None = None,
        signature: str | None = None,
    ) -> dict[str, Any]:
        """
        Fetch indicator metadata from Pine Facade API.

        Args:
            indicator_id: Indicator identifier. Can be:
                - Short name: "RSI", "MACD", "BB" (mapped to STD;*)
                - Full TradingView ID: "STD;RSI", "PUB;abc123", "USER;xyz789"
            version: Version to fetch ("last" for latest)
            session: TradingView sessionid cookie (for custom indicators)
            signature: TradingView sessionid_sign cookie

        Returns:
            Dict with indicator metadata:
            - pineId: Indicator ID (e.g., "STD;RSI")
            - pineVersion: Version string
            - inputs: Dict of input parameters
            - plots: Dict of output plots
            - defaults: Default input values

        Raises:
            AuthenticationError: If custom indicator requires auth but none provided
            DataNotAvailableError: If indicator not found or access denied

        Examples:
            >>> provider = get_pine_facade_provider()
            >>> # Standard indicator (no auth)
            >>> rsi = provider.get_indicator("RSI")
            >>> print(rsi["inputs"])
            >>> # Custom indicator (requires auth)
            >>> bp.set_tradingview_auth(session="...", signature="...")
            >>> custom = provider.get_indicator("PUB;abc123")
        """
        # Normalize indicator ID
        normalized_id = self._normalize_indicator_id(indicator_id)

        # Get auth cookies
        auth_cookies = self._get_auth_cookies(session, signature)

        # Check if auth is needed
        if self._needs_auth(normalized_id) and not auth_cookies.get("sessionid"):
            raise AuthenticationError(
                f"Custom indicator '{indicator_id}' requires TradingView authentication. "
                "Use bp.set_tradingview_auth() first."
            )

        # Fetch indicator metadata (cached)
        session_str = auth_cookies.get("sessionid", "")
        signature_str = auth_cookies.get("sessionid_sign", "")

        return self._fetch_indicator(
            normalized_id,
            version,
            session_str,
            signature_str,
        )

    def _normalize_indicator_id(self, indicator_id: str) -> str:
        """
        Normalize indicator ID to TradingView format.

        Args:
            indicator_id: Short name or full ID

        Returns:
            Full TradingView indicator ID (e.g., "STD;RSI")
        """
        # Check if it's a short name
        upper_id = indicator_id.upper()
        if upper_id in STANDARD_INDICATORS:
            return STANDARD_INDICATORS[upper_id]

        # Already full ID format
        if ";" in indicator_id:
            return indicator_id

        # Try as standard indicator
        return f"STD;{indicator_id}"

    def _get_auth_cookies(
        self,
        session: str | None = None,
        signature: str | None = None,
    ) -> dict[str, str]:
        """
        Get authentication cookies from params or global auth.

        Args:
            session: Optional explicit session cookie
            signature: Optional explicit signature cookie

        Returns:
            Dict with sessionid and sessionid_sign
        """
        if session and signature:
            return {"sessionid": session, "sessionid_sign": signature}

        if session:
            return {"sessionid": session, "sessionid_sign": ""}

        # Try global auth
        creds = get_tradingview_auth()
        if creds:
            return {
                "sessionid": creds.get("session", ""),
                "sessionid_sign": creds.get("session_sign", ""),
            }

        return {"sessionid": "", "sessionid_sign": ""}

    def _needs_auth(self, indicator_id: str) -> bool:
        """
        Check if indicator requires authentication.

        Standard indicators (STD;*) don't require auth.
        Custom indicators (PUB;*, USER;*) require auth.

        Args:
            indicator_id: Full TradingView indicator ID

        Returns:
            True if authentication is required
        """
        return indicator_id.startswith(("USER;", "PUB;"))

    def _fetch_indicator(
        self,
        indicator_id: str,
        version: str,
        session: str = "",
        signature: str = "",
    ) -> dict[str, Any]:
        """
        Fetch indicator metadata from Pine Facade API (cached).

        Args:
            indicator_id: Full TradingView indicator ID
            version: Version to fetch
            session: Session cookie (for cache key)
            signature: Signature cookie (for cache key)

        Returns:
            Indicator metadata dict
        """
        # Check module-level cache
        cache_key = (indicator_id, version, session, signature)
        if cache_key in _indicator_cache:
            return _indicator_cache[cache_key]

        # Build URL - URL encode the indicator ID
        import urllib.parse
        encoded_id = urllib.parse.quote(indicator_id, safe="")
        url = f"{self.BASE_URL}/translate/{encoded_id}/{version}"

        # Build headers
        headers = {
            "User-Agent": self.DEFAULT_HEADERS["User-Agent"],
            "Origin": "https://www.tradingview.com",
            "Referer": "https://www.tradingview.com/",
        }

        # Add auth cookies if provided
        if session:
            cookies = f"sessionid={session}"
            if signature:
                cookies += f"; sessionid_sign={signature}"
            headers["Cookie"] = cookies

        try:
            response = self._client.get(url, headers=headers)
            response.raise_for_status()
        except Exception as e:
            if "401" in str(e) or "403" in str(e):
                raise AuthenticationError(
                    f"Access denied for indicator '{indicator_id}'. "
                    "Check your authentication or indicator permissions."
                ) from e
            if "404" in str(e):
                raise DataNotAvailableError(
                    f"Indicator '{indicator_id}' not found."
                ) from e
            raise DataNotAvailableError(
                f"Failed to fetch indicator '{indicator_id}': {e}"
            ) from e

        data = response.json()

        # Parse and normalize the response
        result = self._parse_indicator_response(indicator_id, data)

        # Store in module-level cache (limit size to 100)
        if len(_indicator_cache) >= 100:
            # Remove oldest entry (first key)
            oldest_key = next(iter(_indicator_cache))
            del _indicator_cache[oldest_key]
        _indicator_cache[cache_key] = result

        return result

    def _parse_indicator_response(
        self,
        indicator_id: str,
        data: dict,
    ) -> dict[str, Any]:
        """
        Parse and normalize Pine Facade API response.

        Args:
            indicator_id: Indicator ID for reference
            data: Raw API response

        Returns:
            Normalized indicator metadata
        """
        result = {
            "pineId": indicator_id,
            "pineVersion": data.get("version", "last"),
            "inputs": {},
            "plots": {},
            "defaults": {},
        }

        # Parse inputs
        inputs = data.get("inputs", [])
        if isinstance(inputs, list):
            for i, inp in enumerate(inputs):
                if isinstance(inp, dict):
                    name = inp.get("name", f"in_{i}")
                    result["inputs"][name] = {
                        "name": name,
                        "type": inp.get("type", "integer"),
                        "defval": inp.get("defval"),
                        "min": inp.get("min"),
                        "max": inp.get("max"),
                        "options": inp.get("options"),
                        "tooltip": inp.get("tooltip"),
                    }
                    if inp.get("defval") is not None:
                        result["defaults"][name] = inp["defval"]

        # Parse plots (outputs)
        plots = data.get("plots", [])
        if isinstance(plots, list):
            for i, plot in enumerate(plots):
                if isinstance(plot, dict):
                    plot_id = plot.get("id", f"plot_{i}")
                    result["plots"][plot_id] = {
                        "id": plot_id,
                        "type": plot.get("type", "line"),
                        "title": plot.get("title"),
                    }

        # Add output field mappings if known
        if indicator_id in INDICATOR_OUTPUTS:
            result["output_mapping"] = INDICATOR_OUTPUTS[indicator_id]

        return result

    def get_output_mapping(self, indicator_id: str) -> dict[str, str]:
        """
        Get output field name mapping for an indicator.

        Args:
            indicator_id: Indicator ID

        Returns:
            Dict mapping plot_N to friendly names
        """
        normalized = self._normalize_indicator_id(indicator_id)
        return INDICATOR_OUTPUTS.get(normalized, {})


def clear_indicator_cache() -> None:
    """Clear the module-level indicator cache."""
    _indicator_cache.clear()


# Singleton instance
_provider: PineFacadeProvider | None = None


def get_pine_facade_provider() -> PineFacadeProvider:
    """Get singleton Pine Facade provider instance."""
    global _provider
    if _provider is None:
        _provider = PineFacadeProvider()
    return _provider
