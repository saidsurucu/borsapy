"""
Supertrend Sinyal Değişimi Tarama
=================================

Supertrend göstergesinin yön değiştirdiği hisseleri bulur:
- Bullish: Direction -1 → +1 (satıştan alıma dönüş)
- Bearish: Direction +1 → -1 (alımdan satışa dönüş)

Supertrend, trend takip eden ATR-tabanlı bir göstergedir.

Kullanım:
    python examples/supertrend_signals.py
"""

import pandas as pd

import borsapy as bp


def detect_supertrend_signal(
    df: pd.DataFrame,
    atr_period: int = 10,
    multiplier: float = 3.0,
    lookback_days: int = 3,
) -> dict:
    """
    Supertrend sinyal değişimi tespit et.

    Returns:
        {'signal': str, 'days_ago': int, 'supertrend': float, 'direction': int}
    """
    result = {
        'signal': None,
        'days_ago': None,
        'supertrend': None,
        'direction': None,
        'distance_pct': None,
    }

    if len(df) < atr_period + lookback_days + 10:
        return result

    # Supertrend hesapla
    st = bp.calculate_supertrend(df, atr_period=atr_period, multiplier=multiplier)

    if st.empty:
        return result

    current_direction = st['Direction'].iloc[-1]
    current_st = st['Supertrend'].iloc[-1]
    current_price = df['Close'].iloc[-1]

    result['supertrend'] = round(current_st, 2)
    result['direction'] = int(current_direction)

    # Fiyatın Supertrend'e uzaklığı
    distance_pct = (current_price - current_st) / current_st * 100
    result['distance_pct'] = round(distance_pct, 2)

    # Son N gün içinde sinyal değişimi var mı?
    for i in range(1, lookback_days + 1):
        idx = -i
        prev_idx = -i - 1

        if abs(prev_idx) >= len(st):
            break

        dir_now = st['Direction'].iloc[idx]
        dir_prev = st['Direction'].iloc[prev_idx]

        # Bullish sinyal: -1 → +1
        if dir_prev == -1 and dir_now == 1:
            result['signal'] = 'BULLISH'
            result['days_ago'] = i
            break

        # Bearish sinyal: +1 → -1
        if dir_prev == 1 and dir_now == -1:
            result['signal'] = 'BEARISH'
            result['days_ago'] = i
            break

    return result


def scan_supertrend_signals(
    index: str = "XU100",
    atr_period: int = 10,
    multiplier: float = 3.0,
    lookback_days: int = 3,
    verbose: bool = True,
) -> pd.DataFrame:
    """Supertrend sinyal taraması."""

    if verbose:
        print(f"📊 Supertrend Sinyal Tarama")
        print(f"   - Endeks: {index}")
        print(f"   - ATR Period: {atr_period}")
        print(f"   - Multiplier: {multiplier}")
        print(f"   - Sinyal Lookback: Son {lookback_days} gün")
        print()

    idx = bp.Index(index)
    symbols = idx.component_symbols

    if verbose:
        print(f"🔍 {len(symbols)} hisse taranıyor...")
        print("-" * 70)

    bullish_signals = []
    bearish_signals = []
    bullish_trend = []  # Zaten bullish olanlar
    bearish_trend = []  # Zaten bearish olanlar

    for i, symbol in enumerate(symbols):
        if verbose:
            print(f"\r   İşleniyor: {i+1}/{len(symbols)} - {symbol:8}", end="", flush=True)

        try:
            ticker = bp.Ticker(symbol)
            df = ticker.history(period="6mo")

            if df.empty or len(df) < 50:
                continue

            signal = detect_supertrend_signal(df, atr_period, multiplier, lookback_days)

            last_price = round(df['Close'].iloc[-1], 2)

            entry = {
                'symbol': symbol,
                'price': last_price,
                'supertrend': signal['supertrend'],
                'distance_pct': signal['distance_pct'],
                'days_ago': signal['days_ago'],
            }

            if signal['signal'] == 'BULLISH':
                bullish_signals.append(entry)
            elif signal['signal'] == 'BEARISH':
                bearish_signals.append(entry)
            elif signal['direction'] == 1:
                bullish_trend.append(symbol)
            elif signal['direction'] == -1:
                bearish_trend.append(symbol)

        except Exception:
            continue

    if verbose:
        print()
        print("-" * 70)
        print()

    # Sonuçları göster
    if verbose:
        print(f"🟢 BULLISH Sinyal ({len(bullish_signals)} hisse) - YENİ ALIM:")
        if bullish_signals:
            print(f"   {'Sembol':<8} {'Fiyat':>10} {'Supertrend':>12} {'Uzaklık':>10} {'Gün Önce':>10}")
            print("   " + "-" * 55)
            for r in bullish_signals:
                print(f"   {r['symbol']:<8} {r['price']:>10.2f} {r['supertrend']:>12.2f} "
                      f"{r['distance_pct']:>9.1f}% {r['days_ago']:>10}")
        else:
            print("   Son 3 günde bullish sinyal yok")

        print()
        print(f"🔴 BEARISH Sinyal ({len(bearish_signals)} hisse) - YENİ SATIM:")
        if bearish_signals:
            print(f"   {'Sembol':<8} {'Fiyat':>10} {'Supertrend':>12} {'Uzaklık':>10} {'Gün Önce':>10}")
            print("   " + "-" * 55)
            for r in bearish_signals:
                print(f"   {r['symbol']:<8} {r['price']:>10.2f} {r['supertrend']:>12.2f} "
                      f"{r['distance_pct']:>9.1f}% {r['days_ago']:>10}")
        else:
            print("   Son 3 günde bearish sinyal yok")

        print()
        print(f"📈 Bullish Trend ({len(bullish_trend)} hisse): {', '.join(bullish_trend[:15])}{'...' if len(bullish_trend) > 15 else ''}")
        print(f"📉 Bearish Trend ({len(bearish_trend)} hisse): {', '.join(bearish_trend[:15])}{'...' if len(bearish_trend) > 15 else ''}")

    # DataFrame oluştur
    all_signals = []
    for s in bullish_signals:
        s['signal'] = 'BULLISH'
        all_signals.append(s)
    for s in bearish_signals:
        s['signal'] = 'BEARISH'
        all_signals.append(s)

    if not all_signals:
        return pd.DataFrame()

    return pd.DataFrame(all_signals)


def main():
    print("=" * 70)
    print("borsapy - Supertrend Sinyal Tarama")
    print("=" * 70)
    print()

    results = scan_supertrend_signals(
        index="XU100",
        atr_period=10,
        multiplier=3.0,
        lookback_days=3,
        verbose=True,
    )

    if not results.empty:
        results.to_csv("supertrend_signals_results.csv", index=False)
        print()
        print("📁 Sonuçlar 'supertrend_signals_results.csv' dosyasına kaydedildi.")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
