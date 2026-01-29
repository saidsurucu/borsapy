"""
Sektör Rotasyonu Analizi
========================

Sektörlerin göreli performansını analiz eder.
Hangi sektörlere para akışı var, hangilerinden çıkış var?

Kullanım:
    python examples/sector_rotation.py
"""

import pandas as pd

import borsapy as bp


def analyze_sector_rotation(period: str = "1mo", verbose: bool = True) -> pd.DataFrame:
    """Sektör rotasyonu analizi yap."""

    if verbose:
        print(f"📊 Sektör Rotasyonu Analizi ({period})")
        print("=" * 70)
        print()

    # Ana endeksler (TradingView'da mevcut olanlar)
    sector_indices = {
        'XU100': 'BIST 100',
        'XU030': 'BIST 30',
        'XBANK': 'Bankacılık',
        'XUTEK': 'Teknoloji',
        'XKTUM': 'Katılım Tüm',
    }

    sector_data = []

    for symbol, name in sector_indices.items():
        try:
            index = bp.Index(symbol)
            df = index.history(period=period)

            if df is None or len(df) < 5:
                continue

            # Getiri hesapla
            start_price = df['Close'].iloc[0]
            end_price = df['Close'].iloc[-1]
            period_return = ((end_price - start_price) / start_price) * 100

            # Hacim değişimi
            avg_vol_start = df['Volume'].head(5).mean()
            avg_vol_end = df['Volume'].tail(5).mean()
            vol_change = ((avg_vol_end - avg_vol_start) / avg_vol_start) * 100 if avg_vol_start > 0 else 0

            # RSI (momentum)
            try:
                rsi = index.rsi()
            except Exception:
                rsi = None

            sector_data.append({
                'symbol': symbol,
                'sector': name,
                'return_pct': period_return,
                'vol_change_pct': vol_change,
                'rsi': rsi,
                'current_price': end_price,
            })

        except Exception as e:
            if verbose:
                print(f"   ⚠️ {symbol}: {e}")

    # DataFrame oluştur ve sırala
    df = pd.DataFrame(sector_data)
    df = df.sort_values('return_pct', ascending=False)

    if verbose:
        print("📈 SEKTÖR PERFORMANSI (Getiriye Göre Sıralı)")
        print("-" * 70)
        print(f"{'Sektör':<15} {'Getiri':>10} {'Hacim Değ.':>12} {'RSI':>8} {'Trend':>10}")
        print("-" * 70)

        for _, row in df.iterrows():
            # Trend belirleme
            if row['return_pct'] > 5 and row['vol_change_pct'] > 0:
                trend = "🔥 GÜÇLÜ"
            elif row['return_pct'] > 0:
                trend = "📈 Pozitif"
            elif row['return_pct'] > -5:
                trend = "➡️ Nötr"
            else:
                trend = "📉 Negatif"

            rsi_str = f"{row['rsi']:.1f}" if row['rsi'] else "N/A"
            print(f"{row['sector']:<15} %{row['return_pct']:>9.2f} %{row['vol_change_pct']:>11.1f} "
                  f"{rsi_str:>8} {trend:>10}")

        print()
        print("=" * 70)
        print("📊 SEKTÖR ROTASYONU ÖZETİ:")
        print()

        # En iyi 3 sektör
        top_3 = df.head(3)
        print("🏆 PARA GİRİŞİ (En İyi 3 Sektör):")
        for _, row in top_3.iterrows():
            print(f"   • {row['sector']}: %{row['return_pct']:.2f}")

        # En kötü 3 sektör
        bottom_3 = df.tail(3)
        print()
        print("⚠️ PARA ÇIKIŞI (En Kötü 3 Sektör):")
        for _, row in bottom_3.iterrows():
            print(f"   • {row['sector']}: %{row['return_pct']:.2f}")

    return df


def compare_periods(verbose: bool = True) -> dict:
    """Farklı dönemlerde sektör performansını karşılaştır."""

    if verbose:
        print()
        print("=" * 70)
        print("📊 DÖNEMSEL SEKTÖR KARŞILAŞTIRMASI")
        print("=" * 70)
        print()

    periods = ['1w', '1mo', '3mo']
    results = {}

    for period in periods:
        if verbose:
            print(f"📅 {period.upper()} Dönemi:")
        df = analyze_sector_rotation(period, verbose=False)

        if not df.empty:
            top = df.head(1).iloc[0]
            bottom = df.tail(1).iloc[0]
            if verbose:
                print(f"   🏆 En iyi: {top['sector']} (%{top['return_pct']:.2f})")
                print(f"   📉 En kötü: {bottom['sector']} (%{bottom['return_pct']:.2f})")
                print()

            results[period] = df

    return results


if __name__ == "__main__":
    # Ana analiz
    df = analyze_sector_rotation("1mo")

    # Dönemsel karşılaştırma
    compare_periods()
