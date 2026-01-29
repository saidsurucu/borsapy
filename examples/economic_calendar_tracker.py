"""
Ekonomik Takvim Takipçisi
=========================

Bu hafta ve gelecek haftanın önemli ekonomik olaylarını
takip eder ve filtreler.

Özellikler:
- Türkiye ve dünya ekonomik olayları
- Önem derecesine göre filtreleme
- Tarih aralığı seçimi

Kullanım:
    python examples/economic_calendar_tracker.py
"""

import pandas as pd
from datetime import datetime, timedelta

import borsapy as bp


def get_importance_emoji(importance: str) -> str:
    """Önem derecesi için emoji."""
    if importance == 'high':
        return "🔴"
    elif importance == 'medium':
        return "🟡"
    else:
        return "🟢"


def format_event(event: dict) -> str:
    """Olayı formatla."""
    # API capitalized column names döndürüyor
    importance = event.get('Importance', event.get('importance', 'low'))
    emoji = get_importance_emoji(importance)
    time_str = event.get('Time', event.get('time', 'N/A'))
    name = event.get('Event', event.get('event', 'N/A'))
    country = event.get('Country', event.get('country', ''))

    # Beklenti ve önceki değer
    forecast = event.get('Forecast', event.get('forecast', ''))
    previous = event.get('Previous', event.get('previous', ''))

    extra = ""
    if forecast:
        extra += f" | Beklenti: {forecast}"
    if previous:
        extra += f" | Önceki: {previous}"

    return f"{emoji} [{time_str}] [{country}] {name}{extra}"


def show_economic_calendar(
    period: str = "1w",
    country: str | None = None,
    importance: str | None = None,
    verbose: bool = True,
) -> pd.DataFrame:
    """Ekonomik takvimi göster."""

    if verbose:
        print("📅 EKONOMİK TAKVİM")
        print("=" * 80)
        print()

        filters = []
        if period:
            filters.append(f"Dönem: {period}")
        if country:
            filters.append(f"Ülke: {country}")
        if importance:
            filters.append(f"Önem: {importance}")

        if filters:
            print(f"   Filtreler: {', '.join(filters)}")
            print()

    try:
        calendar = bp.EconomicCalendar()
        events = calendar.events(
            period=period,
            country=country,
            importance=importance,
        )

        if events.empty:
            if verbose:
                print("❌ Bu kriterlere uygun olay bulunamadı.")
            return pd.DataFrame()

        if verbose:
            # Tarihe göre grupla (API 'Date' ile döndürüyor)
            date_col = 'Date' if 'Date' in events.columns else 'date'
            events['date_only'] = pd.to_datetime(events[date_col]).dt.date

            for date, group in events.groupby('date_only'):
                # Tarih başlığı
                day_name = pd.Timestamp(date).strftime('%A')
                date_str = pd.Timestamp(date).strftime('%d %B %Y')
                print(f"📆 {date_str} ({day_name})")
                print("-" * 70)

                for _, event in group.iterrows():
                    print(f"   {format_event(event.to_dict())}")

                print()

            # Özet
            print("=" * 80)
            print("📊 ÖZET:")
            print(f"   Toplam olay: {len(events)}")

            imp_col = 'Importance' if 'Importance' in events.columns else 'importance'
            importance_counts = events[imp_col].value_counts()
            for imp, count in importance_counts.items():
                emoji = get_importance_emoji(imp)
                print(f"   {emoji} {imp.title()}: {count}")

            if country is None:
                country_col = 'Country' if 'Country' in events.columns else 'country'
                country_counts = events[country_col].value_counts()
                print()
                print("   Ülke dağılımı:")
                for c, count in country_counts.head(5).items():
                    print(f"      {c}: {count}")

        return events

    except Exception as e:
        if verbose:
            print(f"❌ Hata: {e}")
        return pd.DataFrame()


def show_turkey_events(verbose: bool = True) -> pd.DataFrame:
    """Sadece Türkiye olaylarını göster."""

    if verbose:
        print("🇹🇷 TÜRKİYE EKONOMİK TAKVİMİ")
        print("=" * 80)
        print()

    return show_economic_calendar(
        period="1mo",
        country="TR",
        importance=None,
        verbose=verbose,
    )


def show_high_impact_events(verbose: bool = True) -> pd.DataFrame:
    """Yüksek önemli olayları göster."""

    if verbose:
        print("🔴 YÜKSEK ÖNEMLİ OLAYLAR")
        print("=" * 80)
        print()

    return show_economic_calendar(
        period="1w",
        country=None,
        importance="high",
        verbose=verbose,
    )


def main():
    print("=" * 80)
    print("borsapy - Ekonomik Takvim Takipçisi")
    print("=" * 80)
    print()

    # Bu hafta tüm olaylar
    all_events = show_economic_calendar(
        period="1w",
        verbose=True,
    )

    print()
    print("=" * 80)
    print()

    # Sadece Türkiye
    tr_events = show_turkey_events(verbose=True)

    if not all_events.empty:
        all_events.to_csv("economic_calendar.csv", index=False)
        print()
        print("📁 Takvim 'economic_calendar.csv' dosyasına kaydedildi.")

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
