"""Doviz.com Economic Calendar provider for borsapy."""

import re
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup

from borsapy._providers.base import BaseProvider
from borsapy.cache import TTL
from borsapy.exceptions import APIError


class DovizcomCalendarProvider(BaseProvider):
    """
    Provider for economic calendar data from doviz.com.

    API: https://www.doviz.com/calendar/getCalendarEvents
    """

    BASE_URL = "https://www.doviz.com/calendar/getCalendarEvents"
    BEARER_TOKEN = "d00c1214cbca6a7a1b4728a8cc78cd69ba99e0d2ddb6d0687d2ed34f6a547b48"

    # Country code mapping
    COUNTRY_MAP = {
        "TR": "Türkiye",
        "US": "ABD",
        "EU": "Euro Bölgesi",
        "DE": "Almanya",
        "GB": "Birleşik Krallık",
        "JP": "Japonya",
        "CN": "Çin",
        "FR": "Fransa",
        "IT": "İtalya",
        "CA": "Kanada",
        "AU": "Avustralya",
        "CH": "İsviçre",
        "KR": "Güney Kore",
        "BR": "Brezilya",
        "IN": "Hindistan",
        "RU": "Rusya",
    }

    # Turkish month names
    TURKISH_MONTHS = {
        "Ocak": 1,
        "Şubat": 2,
        "Mart": 3,
        "Nisan": 4,
        "Mayıs": 5,
        "Haziran": 6,
        "Temmuz": 7,
        "Ağustos": 8,
        "Eylül": 9,
        "Ekim": 10,
        "Kasım": 11,
        "Aralık": 12,
    }

    def _get_auth_headers(self) -> dict[str, str]:
        """Get headers with Bearer token for doviz.com API."""
        return {
            **self.DEFAULT_HEADERS,
            "Authorization": f"Bearer {self.BEARER_TOKEN}",
            "Accept": "application/json",
        }

    def _parse_turkish_date(self, date_str: str) -> datetime | None:
        """Parse Turkish date format like '30 Haziran 2025'."""
        try:
            parts = date_str.strip().split()
            if len(parts) == 3:
                day = int(parts[0])
                month = self.TURKISH_MONTHS.get(parts[1])
                year = int(parts[2])
                if month:
                    return datetime(year, month, day)
        except (ValueError, IndexError):
            pass
        return None

    def _parse_time(self, time_str: str) -> str | None:
        """Parse time string like '10:00'."""
        if not time_str:
            return None
        time_str = time_str.strip()
        if re.match(r"^\d{1,2}:\d{2}$", time_str):
            return time_str
        return None

    def _extract_period(self, event_name: str) -> str:
        """Extract period from event name like 'Enflasyon (Haziran)'."""
        match = re.search(r"\(([^)]+)\)$", event_name)
        if match:
            return match.group(1)
        return ""

    def _parse_html(
        self, html_content: str, country_code: str
    ) -> list[dict[str, Any]]:
        """Parse HTML content and extract economic events."""
        soup = BeautifulSoup(html_content, "html.parser")
        events = []
        current_date = None

        # Find content containers
        content_divs = soup.find_all(
            "div", id=lambda x: x and "calendar-content-" in x
        )

        for content_div in content_divs:
            # Find date header
            date_header = content_div.find(
                "div", class_="text-center mt-8 mb-8 text-bold"
            )
            if date_header:
                date_text = date_header.get_text(strip=True)
                current_date = self._parse_turkish_date(date_text)

            # Find event rows
            rows = content_div.find_all("tr")

            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 7:
                    try:
                        time_cell = cells[0]
                        importance_cell = cells[2]
                        event_cell = cells[3]
                        actual_cell = cells[4]
                        expected_cell = cells[5]
                        previous_cell = cells[6]

                        # Parse data
                        event_time = self._parse_time(time_cell.get_text(strip=True))
                        event_name = event_cell.get_text(strip=True)

                        # Parse importance
                        importance = "low"
                        importance_span = importance_cell.find(
                            "span", class_=lambda x: x and "importance" in str(x)
                        )
                        if importance_span:
                            classes = importance_span.get("class", [])
                            for cls in classes:
                                if cls in ["low", "mid", "high"]:
                                    importance = cls
                                    break

                        actual = actual_cell.get_text(strip=True) or None
                        expected = expected_cell.get_text(strip=True) or None
                        previous = previous_cell.get_text(strip=True) or None

                        if event_name and current_date:
                            events.append(
                                {
                                    "date": current_date,
                                    "time": event_time,
                                    "country_code": country_code,
                                    "country": self.COUNTRY_MAP.get(
                                        country_code, country_code
                                    ),
                                    "event": event_name,
                                    "importance": importance,
                                    "period": self._extract_period(event_name),
                                    "actual": actual,
                                    "forecast": expected,
                                    "previous": previous,
                                }
                            )
                    except Exception:
                        continue

        return events

    def get_economic_calendar(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        countries: list[str] | None = None,
        importance: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get economic calendar events.

        Args:
            start: Start date. Defaults to today.
            end: End date. Defaults to start + 7 days.
            countries: List of country codes (TR, US, EU, etc.). Defaults to ['TR', 'US'].
            importance: Filter by importance level ('low', 'mid', 'high').

        Returns:
            List of economic events with date, time, country, event, importance, etc.
        """
        from datetime import timedelta

        # Defaults
        if start is None:
            start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if end is None:
            end = start + timedelta(days=7)
        if countries is None:
            countries = ["TR", "US"]

        # Build cache key
        cache_key = f"dovizcom:calendar:{start.date()}:{end.date()}:{','.join(countries)}:{importance or 'all'}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        all_events = []

        for country_code in countries:
            try:
                # Build params
                importance_param = "3,2,1"  # 3=high, 2=mid, 1=low
                if importance == "high":
                    importance_param = "3"
                elif importance == "mid":
                    importance_param = "3,2"

                params = {
                    "country": country_code,
                    "importance": importance_param,
                }

                response = self._get(
                    self.BASE_URL,
                    params=params,
                    headers=self._get_auth_headers(),
                )

                data = response.json()

                if "calendarHTML" not in data:
                    continue

                # Parse HTML
                events = self._parse_html(data["calendarHTML"], country_code)

                # Filter by date range
                for event in events:
                    event_date = event["date"]
                    if start.date() <= event_date.date() <= end.date():
                        # Filter by importance if specified
                        if importance and event["importance"] != importance:
                            continue
                        all_events.append(event)

            except Exception as e:
                raise APIError(f"Failed to fetch calendar for {country_code}: {e}") from e

        # Sort by date and time
        all_events.sort(
            key=lambda x: (
                x["date"],
                x["time"] or "99:99",
            )
        )

        # Cache result
        self._cache_set(cache_key, all_events, TTL.OHLCV_HISTORY)

        return all_events


# Singleton instance
_provider: DovizcomCalendarProvider | None = None


def get_calendar_provider() -> DovizcomCalendarProvider:
    """Get the singleton calendar provider instance."""
    global _provider
    if _provider is None:
        _provider = DovizcomCalendarProvider()
    return _provider
