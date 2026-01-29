"""
Golden Cross / Death Cross Tarama
=================================

Hareketli ortalama kesişimlerini tespit eder:
- Golden Cross: SMA50 > SMA200 (yukarı kesişim) - Güçlü alım sinyali
- Death Cross: SMA50 < SMA200 (aşağı kesişim) - Güçlü satım sinyali

Kullanım:
    python examples/golden_death_cross.py
"""

import pandas as pd

import borsapy as bp


def detect_cross(
    df: pd.DataFrame,
    fast_period: int = 50,
    slow_period: int = 200,
    lookback_days: int = 5,
) -> dict:
    """
    SMA kesişimlerini tespit et.

    Args:
        df: OHLCV DataFrame
        fast_period: Hızlı SMA periyodu (varsayılan: 50)
        slow_period: Yavaş SMA periyodu (varsayılan: 200)
        lookback_days: Kesişim aranacak gün sayısı

    Returns:
        {'golden_cross': bool, 'death_cross': bool, 'days_ago': int, 'sma_fast': float, 'sma_slow': float}
    """
    result = {
        'golden_cross': False,
        'death_cross': False,
        'days_ago': None,
        'sma_fast': None,
        'sma_slow': None,
    }

    if len(df) < slow_period + lookback_days:
        return result

    # SMA hesapla
    sma_fast = bp.calculate_sma(df, period=fast_period)
    sma_slow = bp.calculate_sma(df, period=slow_period)

    result['sma_fast'] = round(sma_fast.iloc[-1], 2)
    result['sma_slow'] = round(sma_slow.iloc[-1], 2)

    # Son N gün içinde kesişim var mı?
    for i in range(1, lookback_days + 1):
        idx = -i
        prev_idx = -i - 1

        if abs(prev_idx) >= len(sma_fast):
            break

        fast_now = sma_fast.iloc[idx]
        fast_prev = sma_fast.iloc[prev_idx]
        slow_now = sma_slow.iloc[idx]
        slow_prev = sma_slow.iloc[prev_idx]

        # Golden Cross: fast önceden slow'un altındaydı, şimdi üstünde
        if fast_prev <= slow_prev and fast_now > slow_now:
            result['golden_cross'] = True
            result['days_ago'] = i
            break

        # Death Cross: fast önceden slow'un üstündeydi, şimdi altında
        if fast_prev >= slow_prev and fast_now < slow_now:
            result['death_cross'] = True
            result['days_ago'] = i
            break

    return result


def scan_ma_crossover(
    index: str = "XU100",
    fast_period: int = 50,
    slow_period: int = 200,
    lookback_days: int = 5,
    verbose: bool = True,
) -> pd.DataFrame:
    """Golden/Death Cross taraması."""

    if verbose:
        print(f"📊 Golden/Death Cross Tarama")
        print(f"   - Endeks: {index}")
        print(f"   - Hızlı SMA: {fast_period} gün")
        print(f"   - Yavaş SMA: {slow_period} gün")
        print(f"   - Lookback: Son {lookback_days} gün")
        print()

    # Endeks bileşenlerini al
    idx = bp.Index(index)
    symbols = idx.component_symbols

    if verbose:
        print(f"🔍 {len(symbols)} hisse taranıyor...")
        print("-" * 70)

    golden_crosses = []
    death_crosses = []
    above_sma = []  # SMA50 > SMA200 olanlar (trend yukarı)

    for i, symbol in enumerate(symbols):
        if verbose:
            print(f"\r   İşleniyor: {i+1}/{len(symbols)} - {symbol:8}", end="", flush=True)

        try:
            ticker = bp.Ticker(symbol)
            df = ticker.history(period="1y")

            if df.empty or len(df) < slow_period + lookback_days:
                continue

            cross = detect_cross(df, fast_period, slow_period, lookback_days)

            last_price = round(df['Close'].iloc[-1], 2)

            if cross['golden_cross']:
                golden_crosses.append({
                    'symbol': symbol,
                    'type': 'GOLDEN CROSS',
                    'days_ago': cross['days_ago'],
                    'price': last_price,
                    'sma_fast': cross['sma_fast'],
                    'sma_slow': cross['sma_slow'],
                })
            elif cross['death_cross']:
                death_crosses.append({
                    'symbol': symbol,
                    'type': 'DEATH CROSS',
                    'days_ago': cross['days_ago'],
                    'price': last_price,
                    'sma_fast': cross['sma_fast'],
                    'sma_slow': cross['sma_slow'],
                })
            elif cross['sma_fast'] and cross['sma_slow']:
                # Kesişim yok ama trend yukarı mı?
                if cross['sma_fast'] > cross['sma_slow']:
                    above_sma.append(symbol)

        except Exception:
            continue

    if verbose:
        print()
        print("-" * 70)
        print()

    # Sonuçlar
    all_results = golden_crosses + death_crosses

    if verbose:
        print(f"🟢 GOLDEN CROSS ({len(golden_crosses)} hisse) - ALIM Sinyali:")
        if golden_crosses:
            for r in golden_crosses:
                print(f"   ✅ {r['symbol']:8} {r['days_ago']} gün önce | "
                      f"Fiyat: {r['price']:>8} | SMA50: {r['sma_fast']:>8} > SMA200: {r['sma_slow']:>8}")
        else:
            print("   Son 5 günde golden cross yok")

        print()
        print(f"🔴 DEATH CROSS ({len(death_crosses)} hisse) - SATIM Sinyali:")
        if death_crosses:
            for r in death_crosses:
                print(f"   ⚠️  {r['symbol']:8} {r['days_ago']} gün önce | "
                      f"Fiyat: {r['price']:>8} | SMA50: {r['sma_fast']:>8} < SMA200: {r['sma_slow']:>8}")
        else:
            print("   Son 5 günde death cross yok")

        print()
        print(f"📈 Yükseliş Trendinde ({len(above_sma)} hisse): SMA50 > SMA200")
        print(f"   {', '.join(above_sma[:20])}{'...' if len(above_sma) > 20 else ''}")

    if not all_results:
        return pd.DataFrame()

    return pd.DataFrame(all_results)


def main():
    print("=" * 70)
    print("borsapy - Golden Cross / Death Cross Tarama")
    print("=" * 70)
    print()

    results = scan_ma_crossover(
        index="XU100",
        fast_period=50,
        slow_period=200,
        lookback_days=5,
        verbose=True,
    )

    if not results.empty:
        results.to_csv("golden_death_cross_results.csv", index=False)
        print()
        print("📁 Sonuçlar 'golden_death_cross_results.csv' dosyasına kaydedildi.")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
