"""
Canlı Fiyat Monitörü
====================

TradingView WebSocket ile birden fazla hisseyi
gerçek zamanlı takip eden terminal uygulaması.

Özellikler:
- Anlık fiyat güncellemeleri
- Değişim yüzdesi ve yönü
- Hacim takibi
- Özelleştirilebilir watchlist

Kullanım:
    python examples/realtime_price_monitor.py

Not: Ctrl+C ile durdurun.
"""

import time
from datetime import datetime

import borsapy as bp


def format_change(change_pct: float) -> str:
    """Değişim yüzdesini formatla."""
    if change_pct is None:
        return "   N/A"

    if change_pct > 0:
        return f"  ↑ +{change_pct:.2f}%"
    elif change_pct < 0:
        return f"  ↓ {change_pct:.2f}%"
    else:
        return f"  → {change_pct:.2f}%"


def format_volume(volume: int) -> str:
    """Hacmi formatla."""
    if volume is None:
        return "N/A"
    if volume >= 1_000_000_000:
        return f"{volume/1_000_000_000:.1f}B"
    if volume >= 1_000_000:
        return f"{volume/1_000_000:.1f}M"
    if volume >= 1_000:
        return f"{volume/1_000:.0f}K"
    return str(volume)


def clear_screen():
    """Terminal ekranını temizle."""
    print("\033[H\033[J", end="")


def run_monitor(
    symbols: list[str],
    refresh_rate: float = 1.0,
    duration: int = 60,
):
    """
    Canlı fiyat monitörü çalıştır.

    Args:
        symbols: Takip edilecek semboller
        refresh_rate: Yenileme hızı (saniye)
        duration: Çalışma süresi (saniye, 0=sonsuz)
    """
    print("🚀 TradingView Stream'e bağlanılıyor...")

    stream = bp.TradingViewStream()
    stream.connect()

    # Sembollere abone ol
    for symbol in symbols:
        stream.subscribe(symbol)

    print(f"✅ {len(symbols)} sembole abone olundu")
    print()
    print("⏳ İlk veriler bekleniyor...")
    time.sleep(2)  # İlk verilerin gelmesini bekle

    start_time = time.time()
    iteration = 0

    try:
        while True:
            iteration += 1
            elapsed = time.time() - start_time

            # Süre kontrolü
            if duration > 0 and elapsed > duration:
                break

            clear_screen()

            # Header
            now = datetime.now().strftime("%H:%M:%S")
            print("=" * 75)
            print(f"📈 CANLI FİYAT MONİTÖRÜ | {now} | Güncelleme #{iteration}")
            print("=" * 75)
            print()
            print(f"{'Sembol':<10} {'Fiyat':>12} {'Değişim':>15} {'Hacim':>12} {'Bid':>10} {'Ask':>10}")
            print("-" * 75)

            for symbol in symbols:
                quote = stream.get_quote(symbol)

                if quote is None:
                    print(f"{symbol:<10} {'Bekleniyor...':<50}")
                    continue

                last = quote.get('last', 0)
                change_pct = quote.get('change_percent', 0)
                volume = quote.get('volume', 0)
                bid = quote.get('bid', 0)
                ask = quote.get('ask', 0)

                change_str = format_change(change_pct)
                volume_str = format_volume(volume)

                # Renk göstergesi
                if change_pct and change_pct > 0:
                    indicator = "🟢"
                elif change_pct and change_pct < 0:
                    indicator = "🔴"
                else:
                    indicator = "⚪"

                print(f"{indicator} {symbol:<8} {last:>11.2f} {change_str:>15} "
                      f"{volume_str:>12} {bid:>10.2f} {ask:>10.2f}")

            print("-" * 75)
            print()
            print(f"⏱️  Çalışma süresi: {int(elapsed)}s | Yenileme: {refresh_rate}s")
            print("📌 Durdurmak için Ctrl+C")

            if duration > 0:
                remaining = duration - int(elapsed)
                print(f"⏳ Kalan süre: {remaining}s")

            time.sleep(refresh_rate)

    except KeyboardInterrupt:
        print()
        print("🛑 Monitör durduruldu.")

    finally:
        stream.disconnect()
        print("✅ Bağlantı kapatıldı.")


def main():
    print("=" * 75)
    print("borsapy - Canlı Fiyat Monitörü")
    print("=" * 75)
    print()

    # Takip edilecek hisseler
    watchlist = [
        "THYAO",
        "GARAN",
        "ASELS",
        "TUPRS",
        "KCHOL",
        "EREGL",
        "BIMAS",
        "AKBNK",
    ]

    print(f"📋 Watchlist: {', '.join(watchlist)}")
    print()
    print("⚠️  Not: TradingView free tier ~15 dakika gecikmeli veri sağlar.")
    print("    Gerçek zamanlı veri için TradingView Pro hesabı gereklidir.")
    print()

    # Monitörü çalıştır (60 saniye demo)
    run_monitor(
        symbols=watchlist,
        refresh_rate=2.0,
        duration=60,  # 60 saniye sonra otomatik dur (0=sonsuz)
    )

    print()
    print("=" * 75)


if __name__ == "__main__":
    main()
