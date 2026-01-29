"""
Hacim Artışı Tarama Örneği (BIST 100)
=====================================

Bu örnek, BIST 100 hisselerinde hacim artışı gösteren hisseleri bulur:
- Son 3 günlük ortalama işlem adedi
- Son 7 günlük ortalama işlem adedini
- %20 veya daha fazla geçen hisseler

Kullanım:
    python examples/volume_breakout_xu100.py

    # Farklı parametrelerle
    python -c "from examples.volume_breakout_xu100 import screen_volume_breakout; screen_volume_breakout(threshold=30, index='XU030')"

Gereksinimler:
    pip install borsapy pandas
"""

import pandas as pd

import borsapy as bp


def calculate_volume_change(
    symbol: str,
    short_period: int = 3,
    long_period: int = 7,
) -> dict | None:
    """
    Hisse için kısa ve uzun dönem hacim ortalamalarını hesapla.

    Args:
        symbol: Hisse sembolü
        short_period: Kısa dönem gün sayısı (varsayılan: 3)
        long_period: Uzun dönem gün sayısı (varsayılan: 7)

    Returns:
        Hacim bilgileri dict veya None (veri yoksa)
    """
    try:
        ticker = bp.Ticker(symbol)
        # Yeterli veri için biraz fazla gün çek
        df = ticker.history(period="1mo")

        if df.empty or len(df) < long_period:
            return None

        # Son N günlük verileri al
        recent_data = df.tail(long_period)

        if len(recent_data) < long_period:
            return None

        # Ortalama hacimleri hesapla
        short_avg = recent_data["Volume"].tail(short_period).mean()
        long_avg = recent_data["Volume"].mean()

        if long_avg == 0:
            return None

        # Yüzde değişim
        change_pct = ((short_avg - long_avg) / long_avg) * 100

        # Son fiyat bilgisi
        last_close = df["Close"].iloc[-1]
        prev_close = df["Close"].iloc[-2] if len(df) > 1 else last_close
        price_change_pct = ((last_close - prev_close) / prev_close) * 100

        return {
            "symbol": symbol,
            "short_avg_volume": int(short_avg),
            "long_avg_volume": int(long_avg),
            "volume_change_pct": round(change_pct, 2),
            "last_price": round(last_close, 2),
            "price_change_pct": round(price_change_pct, 2),
        }

    except Exception:
        return None


def screen_volume_breakout(
    threshold: float = 20.0,
    short_period: int = 3,
    long_period: int = 7,
    index: str = "XU100",
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Hacim artışı gösteren hisseleri tara.

    Args:
        threshold: Minimum hacim artışı yüzdesi (varsayılan: 20)
        short_period: Kısa dönem gün sayısı (varsayılan: 3)
        long_period: Uzun dönem gün sayısı (varsayılan: 7)
        index: Endeks (varsayılan: "XU100")
        verbose: Detaylı çıktı göster

    Returns:
        Kriterlere uyan hisseler DataFrame'i
    """
    if verbose:
        print(f"📊 Tarama kriterleri:")
        print(f"   - Endeks: {index}")
        print(f"   - Son {short_period} gün ort. hacim > Son {long_period} gün ort. hacim + %{threshold}")
        print()

    # Endeks bileşenlerini al
    if verbose:
        print(f"🔍 {index} bileşenleri alınıyor...")

    try:
        idx = bp.Index(index)
        symbols = idx.component_symbols

        if not symbols:
            if verbose:
                print(f"❌ {index} bileşenleri alınamadı.")
            return pd.DataFrame()

        if verbose:
            print(f"✅ {len(symbols)} hisse bulundu")
            print()

    except Exception as e:
        if verbose:
            print(f"❌ Endeks verisi alınamadı: {e}")
        return pd.DataFrame()

    # Her hisse için hacim analizi yap
    results = []
    processed = 0

    if verbose:
        print("📈 Hacim analizi yapılıyor...")
        print("-" * 70)

    for symbol in symbols:
        processed += 1

        if verbose:
            print(f"\r   İşleniyor: {processed}/{len(symbols)} - {symbol:8}", end="", flush=True)

        data = calculate_volume_change(
            symbol=symbol,
            short_period=short_period,
            long_period=long_period,
        )

        if data is None:
            continue

        # Eşik değerini geçenler
        if data["volume_change_pct"] >= threshold:
            results.append(data)

    if verbose:
        print()  # Satır sonu
        print("-" * 70)
        print()

    if not results:
        if verbose:
            print(f"❌ %{threshold} hacim artışı gösteren hisse bulunamadı.")
        return pd.DataFrame()

    # DataFrame oluştur ve sırala
    df = pd.DataFrame(results)
    df = df.sort_values("volume_change_pct", ascending=False).reset_index(drop=True)

    # Sütun adlarını Türkçeleştir
    df = df.rename(
        columns={
            "symbol": "Sembol",
            "short_avg_volume": f"Ort.Hacim ({short_period}G)",
            "long_avg_volume": f"Ort.Hacim ({long_period}G)",
            "volume_change_pct": "Hacim Değişim %",
            "last_price": "Son Fiyat",
            "price_change_pct": "Fiyat Değişim %",
        }
    )

    if verbose:
        print(f"🎯 Toplam {len(df)} hisse kriterlere uyuyor:")
        print()
        print(df.to_string(index=False))

    return df


def main():
    """Ana fonksiyon."""
    print("=" * 70)
    print("borsapy - Hacim Artışı Taraması (BIST 100)")
    print("=" * 70)
    print()

    # Taramayı çalıştır
    results = screen_volume_breakout(
        threshold=20.0,      # %20 hacim artışı
        short_period=3,      # Son 3 gün
        long_period=7,       # Son 7 gün
        index="XU100",       # BIST 100
        verbose=True,
    )

    if not results.empty:
        # CSV'ye kaydet
        output_file = "volume_breakout_xu100_results.csv"
        results.to_csv(output_file, index=False)
        print()
        print(f"📁 Sonuçlar '{output_file}' dosyasına kaydedildi.")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
