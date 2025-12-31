"""Base provider class for all data providers."""

from typing import Any

import httpx

from borsapy.cache import Cache, get_cache


class BaseProvider:
    """Base class for all data providers."""

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    def __init__(
        self,
        timeout: float = 30.0,
        cache: Cache | None = None,
    ):
        """
        Initialize the provider.

        Args:
            timeout: HTTP request timeout in seconds.
            cache: Cache instance to use. If None, uses global cache.
        """
        self._client = httpx.Client(timeout=timeout, headers=self.DEFAULT_HEADERS)
        self._cache = cache or get_cache()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """
        Make a GET request.

        Args:
            url: Request URL.
            params: Query parameters.
            headers: Request headers.

        Returns:
            HTTP response.
        """
        response = self._client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response

    def _post(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """
        Make a POST request.

        Args:
            url: Request URL.
            data: Form data.
            json: JSON data.
            headers: Request headers.

        Returns:
            HTTP response.
        """
        response = self._client.post(url, data=data, json=json, headers=headers)
        response.raise_for_status()
        return response

    def _cache_get(self, key: str) -> Any | None:
        """Get a value from cache."""
        return self._cache.get(key)

    def _cache_set(self, key: str, value: Any, ttl: int) -> None:
        """Set a value in cache."""
        self._cache.set(key, value, ttl)
