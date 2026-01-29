"""
Kazanç Takvimi
==============

Yaklaşan finansal tablo açıklama tarihlerini takip eder.
KAP bildirimlerinden beklenen açıklama tarihlerini alır.

Kullanım:
    python examples/earnings_calendar.py
"""

from datetime import datetime, timedelta

import pandas as pd

import borsapy as bp


def get_earnings_calendar(index_name: str = "XU030", verbose: bool = True) -> pd.DataFrame:
    """Yaklaşan kazanç açıklamalarını listele."""

    if verbose:
        print("📅 KAZANÇ TAKVİMİ")
        print("=" * 70)
        print()

    index = bp.Index(index_name)
    symbols = index.component_symbols[:15]  # İlk 15 hisse (hız için)

    if verbose:
        print(f"🔍 {index_name} endeksindeki {len(symbols)} hisse taranıyor...")
        print()

    calendar_data = []

    for symbol in symbols:
        try:
            stock = bp.Ticker(symbol)

            # Beklenen açıklama tarihleri
            calendar = stock.calendar

            if calendar is not None and not calendar.empty:
                for _, event in calendar.iterrows():
                    # KAP takvimi EndDate (son tarih) kullanır
                    date = event.get('EndDate') or event.get('StartDate')
                    event_type = event.get('Subject', 'N/A')
                    period = event.get('Period', '')
                    year = event.get('Year', '')

                    if date:
                        calendar_data.append({
                            'symbol': symbol,
                            'date': date,
                            'type': event_type,
                            'period': f"{period} {year}".strip(),
                        })

        except Exception:
            pass

    if not calendar_data:
        if verbose:
            print("❌ Yaklaşan kazanç açıklaması bulunamadı.")
        return pd.DataFrame()

    df = pd.DataFrame(calendar_data)

    # Tarihe göre sırala
    df['date'] = pd.to_datetime(df['date'], format='%d.%m.%Y', errors='coerce')
    df = df.dropna(subset=['date'])
    df = df.sort_values('date')

    # Sadece gelecek tarihleri al
    today = datetime.now()
    df = df[df['date'] >= today]

    if verbose and not df.empty:
        print("📋 YAKLAŞAN AÇIKLAMALAR (Önümüzdeki 60 Gün)")
        print("-" * 70)
        print(f"{'Tarih':<12} {'Sembol':<10} {'Tip':<30} {'Dönem':<15}")
        print("-" * 70)

        # Önümüzdeki 60 gün
        cutoff = today + timedelta(days=60)
        upcoming = df[df['date'] <= cutoff]

        for _, row in upcoming.iterrows():
            date_str = row['date'].strftime('%d.%m.%Y')
            event_type = str(row['type'])[:29]
            period = str(row['period'])[:14]
            print(f"{date_str:<12} {row['symbol']:<10} {event_type:<30} {period:<15}")

        print()
        print(f"📊 Toplam {len(upcoming)} açıklama bekleniyor (60 gün içinde)")

    return df


def analyze_post_earnings(symbol: str, verbose: bool = True) -> dict:
    """Geçmiş kazanç açıklamalarından sonraki fiyat hareketini analiz et."""

    if verbose:
        print()
        print("=" * 70)
        print(f"📊 KAZANÇ SONRASI FİYAT HAREKETİ: {symbol}")
        print("=" * 70)
        print()

    stock = bp.Ticker(symbol)

    # Geçmiş bildirimler
    try:
        news = stock.news

        if news is None or news.empty:
            if verbose:
                print("❌ Geçmiş bildirim bulunamadı.")
            return {}

        # Sütun adlarını normalize et (büyük/küçük harf farkı)
        news.columns = [c.lower() for c in news.columns]

        # Finansal tablo bildirimleri
        if 'title' not in news.columns:
            if verbose:
                print("❌ Bildirim başlığı bulunamadı.")
            return {}

        financial_news = news[news['title'].str.contains('Finansal|Mali|Bilanço', case=False, na=False)]

        if financial_news.empty:
            if verbose:
                print("❌ Finansal tablo bildirimi bulunamadı.")
            return {}

        # Fiyat verileri
        df = stock.history(period="1y")

        if df is None or df.empty:
            if verbose:
                print("❌ Fiyat verisi bulunamadı.")
            return {}

        results = []

        for _, news_item in financial_news.head(4).iterrows():
            news_date = pd.to_datetime(news_item.get('date'), dayfirst=True, errors='coerce')

            if pd.isna(news_date):
                continue

            # Timezone-naive yap
            news_date = news_date.replace(tzinfo=None)

            # Açıklama tarihinden sonraki 5 iş günü
            try:
                # En yakın işlem gününü bul
                df_after = df[df.index >= news_date].head(6)

                if len(df_after) >= 2:
                    price_before = df_after['Close'].iloc[0]
                    price_after = df_after['Close'].iloc[-1]
                    change = ((price_after - price_before) / price_before) * 100

                    results.append({
                        'date': news_date,
                        'title': news_item.get('title', '')[:40],
                        'price_before': price_before,
                        'price_after': price_after,
                        'change_5d': change,
                    })

            except Exception:
                pass

        if results:
            if verbose:
                print("📈 GEÇMİŞ AÇIKLAMA SONRASI PERFORMANS (5 Gün)")
                print("-" * 70)
                print(f"{'Tarih':<12} {'Açıklama Öncesi':>15} {'5 Gün Sonra':>15} {'Değişim':>10}")
                print("-" * 70)

                for r in results:
                    date_str = r['date'].strftime('%d.%m.%Y')
                    emoji = "📈" if r['change_5d'] > 0 else "📉"
                    print(f"{date_str:<12} {r['price_before']:>15.2f} "
                          f"{r['price_after']:>15.2f} {emoji} %{r['change_5d']:>+7.2f}")

                # Ortalama
                avg_change = sum(r['change_5d'] for r in results) / len(results)
                print()
                print(f"📊 Ortalama 5 günlük hareket: %{avg_change:+.2f}")

            return {
                'symbol': symbol,
                'earnings_reactions': results,
                'avg_reaction': avg_change if results else 0,
            }

    except Exception as e:
        if verbose:
            print(f"❌ Hata: {e}")

    return {}


if __name__ == "__main__":
    # Kazanç takvimi
    calendar = get_earnings_calendar("XU030")

    # Örnek hisse için kazanç sonrası analiz
    analyze_post_earnings("THYAO")

    if not calendar.empty:
        calendar.to_csv("earnings_calendar.csv", index=False)
        print()
        print("📁 Takvim 'earnings_calendar.csv' dosyasına kaydedildi.")
