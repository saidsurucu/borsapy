"""
RSI Divergence (Uyumsuzluk) Tarama
==================================

Fiyat ve RSI arasında uyumsuzluk gösteren hisseleri bulur:
- Bullish Divergence: Fiyat yeni dip yaparken RSI yapmıyor (alım sinyali)
- Bearish Divergence: Fiyat yeni zirve yaparken RSI yapmıyor (satım sinyali)

Kullanım:
    python examples/rsi_divergence.py
"""

import pandas as pd
import numpy as np

import borsapy as bp


def find_local_extremes(series: pd.Series, window: int = 5) -> tuple[list, list]:
    """Yerel tepe ve dipleri bul."""
    highs = []
    lows = []

    for i in range(window, len(series) - window):
        # Yerel tepe
        if series.iloc[i] == series.iloc[i-window:i+window+1].max():
            highs.append(i)
        # Yerel dip
        if series.iloc[i] == series.iloc[i-window:i+window+1].min():
            lows.append(i)

    return highs, lows


def detect_divergence(
    price: pd.Series,
    rsi: pd.Series,
    lookback: int = 20,
    window: int = 5,
) -> dict:
    """
    RSI divergence tespit et.

    Returns:
        {'bullish': bool, 'bearish': bool, 'details': str}
    """
    result = {'bullish': False, 'bearish': False, 'details': ''}

    if len(price) < lookback + window * 2:
        return result

    # Son N günlük veriyi al
    price_recent = price.tail(lookback)
    rsi_recent = rsi.tail(lookback)

    # Yerel ekstremumları bul
    price_highs, price_lows = find_local_extremes(price_recent, window)
    rsi_highs, rsi_lows = find_local_extremes(rsi_recent, window)

    # Bullish Divergence: Fiyat düşük dip, RSI yüksek dip
    if len(price_lows) >= 2 and len(rsi_lows) >= 2:
        last_price_low = price_recent.iloc[price_lows[-1]]
        prev_price_low = price_recent.iloc[price_lows[-2]]
        last_rsi_low = rsi_recent.iloc[rsi_lows[-1]]
        prev_rsi_low = rsi_recent.iloc[rsi_lows[-2]]

        if last_price_low < prev_price_low and last_rsi_low > prev_rsi_low:
            result['bullish'] = True
            result['details'] = f"Fiyat: {prev_price_low:.2f}→{last_price_low:.2f} (↓), RSI: {prev_rsi_low:.1f}→{last_rsi_low:.1f} (↑)"

    # Bearish Divergence: Fiyat yüksek tepe, RSI düşük tepe
    if len(price_highs) >= 2 and len(rsi_highs) >= 2:
        last_price_high = price_recent.iloc[price_highs[-1]]
        prev_price_high = price_recent.iloc[price_highs[-2]]
        last_rsi_high = rsi_recent.iloc[rsi_highs[-1]]
        prev_rsi_high = rsi_recent.iloc[rsi_highs[-2]]

        if last_price_high > prev_price_high and last_rsi_high < prev_rsi_high:
            result['bearish'] = True
            result['details'] = f"Fiyat: {prev_price_high:.2f}→{last_price_high:.2f} (↑), RSI: {prev_rsi_high:.1f}→{last_rsi_high:.1f} (↓)"

    return result


def scan_rsi_divergence(
    index: str = "XU100",
    rsi_period: int = 14,
    lookback: int = 20,
    verbose: bool = True,
) -> pd.DataFrame:
    """RSI divergence taraması yap."""

    if verbose:
        print(f"📊 RSI Divergence Tarama")
        print(f"   - Endeks: {index}")
        print(f"   - RSI Period: {rsi_period}")
        print(f"   - Lookback: {lookback} gün")
        print()

    # Endeks bileşenlerini al
    idx = bp.Index(index)
    symbols = idx.component_symbols

    if verbose:
        print(f"🔍 {len(symbols)} hisse taranıyor...")
        print("-" * 60)

    bullish_results = []
    bearish_results = []

    for i, symbol in enumerate(symbols):
        if verbose:
            print(f"\r   İşleniyor: {i+1}/{len(symbols)} - {symbol:8}", end="", flush=True)

        try:
            ticker = bp.Ticker(symbol)
            df = ticker.history(period="3mo")

            if df.empty or len(df) < 50:
                continue

            # RSI hesapla
            rsi = bp.calculate_rsi(df, period=rsi_period)

            # Divergence tespit
            div = detect_divergence(df['Close'], rsi, lookback=lookback)

            if div['bullish']:
                bullish_results.append({
                    'symbol': symbol,
                    'type': 'BULLISH',
                    'rsi': round(rsi.iloc[-1], 1),
                    'price': round(df['Close'].iloc[-1], 2),
                    'details': div['details'],
                })

            if div['bearish']:
                bearish_results.append({
                    'symbol': symbol,
                    'type': 'BEARISH',
                    'rsi': round(rsi.iloc[-1], 1),
                    'price': round(df['Close'].iloc[-1], 2),
                    'details': div['details'],
                })

        except Exception:
            continue

    if verbose:
        print()
        print("-" * 60)
        print()

    # Sonuçları birleştir
    all_results = bullish_results + bearish_results

    if not all_results:
        if verbose:
            print("❌ Divergence tespit edilemedi.")
        return pd.DataFrame()

    df = pd.DataFrame(all_results)

    if verbose:
        print(f"🟢 BULLISH Divergence ({len(bullish_results)} hisse) - Potansiyel ALIM:")
        if bullish_results:
            for r in bullish_results:
                print(f"   ✅ {r['symbol']:8} RSI: {r['rsi']:5.1f} | {r['details']}")
        else:
            print("   Yok")

        print()
        print(f"🔴 BEARISH Divergence ({len(bearish_results)} hisse) - Potansiyel SATIM:")
        if bearish_results:
            for r in bearish_results:
                print(f"   ⚠️  {r['symbol']:8} RSI: {r['rsi']:5.1f} | {r['details']}")
        else:
            print("   Yok")

    return df


def main():
    print("=" * 60)
    print("borsapy - RSI Divergence Tarama")
    print("=" * 60)
    print()

    results = scan_rsi_divergence(
        index="XU100",
        rsi_period=14,
        lookback=20,
        verbose=True,
    )

    if not results.empty:
        results.to_csv("rsi_divergence_results.csv", index=False)
        print()
        print("📁 Sonuçlar 'rsi_divergence_results.csv' dosyasına kaydedildi.")

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
