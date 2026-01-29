"""
Bollinger Band Squeeze Tarama
=============================

Bollinger bantlarının daraldığı (squeeze) hisseleri bulur.
Squeeze, düşük volatilite dönemini gösterir ve genellikle büyük
bir fiyat hareketinin habercisidir.

Squeeze Ölçütü: Bant Genişliği = (Üst Bant - Alt Bant) / Orta Bant
Squeeze = Bant genişliği son 6 ayın en düşük seviyesine yakın

Kullanım:
    python examples/bollinger_squeeze.py
"""

import pandas as pd
import numpy as np

import borsapy as bp


def calculate_bandwidth(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> pd.Series:
    """
    Bollinger Bant Genişliği hesapla.

    Bandwidth = (Upper - Lower) / Middle * 100
    """
    bb = bp.calculate_bollinger_bands(df, period=period, std=std)

    bandwidth = (bb['BB_Upper'] - bb['BB_Lower']) / bb['BB_Middle'] * 100
    return bandwidth


def detect_squeeze(
    df: pd.DataFrame,
    lookback_days: int = 120,
    squeeze_percentile: float = 10,
) -> dict:
    """
    Bollinger Squeeze tespit et.

    Args:
        df: OHLCV DataFrame
        lookback_days: Karşılaştırma periyodu
        squeeze_percentile: Squeeze eşiği (yüzdelik dilim)

    Returns:
        {'is_squeeze': bool, 'bandwidth': float, 'percentile': float, 'min_bandwidth': float}
    """
    result = {
        'is_squeeze': False,
        'bandwidth': None,
        'percentile': None,
        'min_bandwidth': None,
        'bb_position': None,  # Fiyatın bant içindeki konumu
    }

    if len(df) < lookback_days:
        return result

    bandwidth = calculate_bandwidth(df)

    if bandwidth.empty or bandwidth.isna().all():
        return result

    current_bw = bandwidth.iloc[-1]
    historical_bw = bandwidth.tail(lookback_days)

    # Yüzdelik dilim hesapla
    percentile = (historical_bw < current_bw).sum() / len(historical_bw) * 100

    result['bandwidth'] = round(current_bw, 2)
    result['percentile'] = round(percentile, 1)
    result['min_bandwidth'] = round(historical_bw.min(), 2)

    # Fiyatın bant içindeki konumu (0 = alt bant, 100 = üst bant)
    bb = bp.calculate_bollinger_bands(df)
    last_close = df['Close'].iloc[-1]
    bb_upper = bb['BB_Upper'].iloc[-1]
    bb_lower = bb['BB_Lower'].iloc[-1]

    if bb_upper != bb_lower:
        bb_position = (last_close - bb_lower) / (bb_upper - bb_lower) * 100
        result['bb_position'] = round(bb_position, 1)

    # Squeeze kontrolü
    if percentile <= squeeze_percentile:
        result['is_squeeze'] = True

    return result


def scan_bollinger_squeeze(
    index: str = "XU100",
    lookback_days: int = 120,
    squeeze_percentile: float = 10,
    verbose: bool = True,
) -> pd.DataFrame:
    """Bollinger Squeeze taraması."""

    if verbose:
        print(f"📊 Bollinger Band Squeeze Tarama")
        print(f"   - Endeks: {index}")
        print(f"   - Lookback: {lookback_days} gün")
        print(f"   - Squeeze Eşiği: En düşük %{squeeze_percentile} bant genişliği")
        print()

    idx = bp.Index(index)
    symbols = idx.component_symbols

    if verbose:
        print(f"🔍 {len(symbols)} hisse taranıyor...")
        print("-" * 70)

    squeeze_results = []

    for i, symbol in enumerate(symbols):
        if verbose:
            print(f"\r   İşleniyor: {i+1}/{len(symbols)} - {symbol:8}", end="", flush=True)

        try:
            ticker = bp.Ticker(symbol)
            df = ticker.history(period="1y")

            if df.empty or len(df) < lookback_days:
                continue

            squeeze = detect_squeeze(df, lookback_days, squeeze_percentile)

            if squeeze['is_squeeze']:
                last_price = round(df['Close'].iloc[-1], 2)

                # Trend yönü (son 20 günlük SMA ile karşılaştır)
                sma20 = df['Close'].tail(20).mean()
                trend = "↑" if last_price > sma20 else "↓"

                squeeze_results.append({
                    'symbol': symbol,
                    'price': last_price,
                    'bandwidth': squeeze['bandwidth'],
                    'percentile': squeeze['percentile'],
                    'bb_position': squeeze['bb_position'],
                    'trend': trend,
                })

        except Exception:
            continue

    if verbose:
        print()
        print("-" * 70)
        print()

    if not squeeze_results:
        if verbose:
            print("❌ Squeeze durumunda hisse bulunamadı.")
        return pd.DataFrame()

    # Bant genişliğine göre sırala (en dar önce)
    df = pd.DataFrame(squeeze_results)
    df = df.sort_values('bandwidth').reset_index(drop=True)

    if verbose:
        print(f"🎯 SQUEEZE Durumunda {len(df)} Hisse (Volatilite Patlaması Bekleniyor):")
        print()
        print(f"{'Sembol':<8} {'Fiyat':>10} {'Bant Gen.':>10} {'Yüzdelik':>10} {'BB Poz.':>10} {'Trend':>6}")
        print("-" * 60)

        for _, row in df.iterrows():
            print(f"{row['symbol']:<8} {row['price']:>10.2f} {row['bandwidth']:>10.2f} "
                  f"{row['percentile']:>9.1f}% {row['bb_position']:>9.1f}% {row['trend']:>6}")

        print()
        print("💡 BB Pozisyon: 0% = Alt bant, 50% = Orta, 100% = Üst bant")
        print("💡 Düşük bant genişliği + üst banda yakın fiyat = Yukarı breakout olasılığı yüksek")

    return df


def main():
    print("=" * 70)
    print("borsapy - Bollinger Band Squeeze Tarama")
    print("=" * 70)
    print()

    results = scan_bollinger_squeeze(
        index="XU100",
        lookback_days=120,
        squeeze_percentile=10,
        verbose=True,
    )

    if not results.empty:
        results.to_csv("bollinger_squeeze_results.csv", index=False)
        print()
        print("📁 Sonuçlar 'bollinger_squeeze_results.csv' dosyasına kaydedildi.")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
