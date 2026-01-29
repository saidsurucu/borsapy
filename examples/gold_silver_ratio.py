"""
Altın/Gümüş Oranı Analizi
=========================

Altın/Gümüş oranını takip eder ve tarihsel karşılaştırma yapar.
Yüksek oran = Gümüş ucuz | Düşük oran = Altın ucuz

Tarihsel ortalama: ~60-70
Oran > 80: Gümüş çok ucuz (gümüş al)
Oran < 50: Altın ucuz (altın al)

Kullanım:
    python examples/gold_silver_ratio.py
"""

import pandas as pd

import borsapy as bp


def analyze_gold_silver_ratio(period: str = "1y", verbose: bool = True) -> dict:
    """Altın/Gümüş oranını analiz et."""

    if verbose:
        print("📊 ALTIN/GÜMÜŞ ORANI ANALİZİ")
        print("=" * 70)
        print()

    # Veri çek
    gold = bp.FX("gram-altin")
    silver = bp.FX("gram-gumus")

    gold_current = gold.current
    silver_current = silver.current

    gold_price = gold_current.get('last', 0)
    silver_price = silver_current.get('last', 0)

    if not silver_price:
        if verbose:
            print("❌ Gümüş fiyatı alınamadı.")
        return {}

    current_ratio = gold_price / silver_price

    if verbose:
        print("💰 GÜNCEL FİYATLAR:")
        print(f"   🥇 Gram Altın: {gold_price:,.2f} TL")
        print(f"   🥈 Gram Gümüş: {silver_price:,.2f} TL")
        print()
        print(f"📏 GÜNCEL ALTIN/GÜMÜŞ ORANI: {current_ratio:.2f}")
        print()

    # Tarihsel veri
    try:
        gold_hist = gold.history(period=period)
        silver_hist = silver.history(period=period)

        if gold_hist is not None and silver_hist is not None:
            # İndeksleri hizala
            combined = pd.DataFrame({
                'gold': gold_hist['Close'],
                'silver': silver_hist['Close'],
            }).dropna()

            combined['ratio'] = combined['gold'] / combined['silver']

            # İstatistikler
            ratio_mean = combined['ratio'].mean()
            ratio_std = combined['ratio'].std()
            ratio_min = combined['ratio'].min()
            ratio_max = combined['ratio'].max()
            ratio_median = combined['ratio'].median()

            # Percentile
            percentile = (combined['ratio'] < current_ratio).mean() * 100

            if verbose:
                print(f"📈 TARİHSEL İSTATİSTİKLER ({period}):")
                print("-" * 40)
                print(f"   Ortalama: {ratio_mean:.2f}")
                print(f"   Medyan: {ratio_median:.2f}")
                print(f"   Min: {ratio_min:.2f}")
                print(f"   Max: {ratio_max:.2f}")
                print(f"   Std Sapma: {ratio_std:.2f}")
                print()
                print(f"   Güncel oran tarihsel verilerin %{percentile:.0f}'inde")
                print()

            # Değerleme
            if current_ratio > ratio_mean + ratio_std:
                recommendation = "GÜMÜŞ AL"
                emoji = "🥈"
                reason = f"Oran ({current_ratio:.1f}) ortalamanın ({ratio_mean:.1f}) üzerinde - gümüş görece ucuz"
            elif current_ratio < ratio_mean - ratio_std:
                recommendation = "ALTIN AL"
                emoji = "🥇"
                reason = f"Oran ({current_ratio:.1f}) ortalamanın ({ratio_mean:.1f}) altında - altın görece ucuz"
            else:
                recommendation = "NÖTR"
                emoji = "⚖️"
                reason = f"Oran ({current_ratio:.1f}) normal aralıkta"

            if verbose:
                print(f"🎯 DEĞERLENDİRME: {emoji} {recommendation}")
                print(f"   {reason}")
                print()
                print("=" * 70)
                print("💡 GENEL KURAL:")
                print("   • Oran > 80: Gümüş çok ucuz (tarihsel olarak)")
                print("   • Oran 60-80: Normal aralık")
                print("   • Oran < 60: Altın görece ucuz")

            return {
                'gold_price': gold_price,
                'silver_price': silver_price,
                'current_ratio': current_ratio,
                'ratio_mean': ratio_mean,
                'ratio_median': ratio_median,
                'ratio_std': ratio_std,
                'ratio_min': ratio_min,
                'ratio_max': ratio_max,
                'percentile': percentile,
                'recommendation': recommendation,
                'history': combined,
            }

    except Exception as e:
        if verbose:
            print(f"⚠️ Tarihsel veri hatası: {e}")

    return {
        'gold_price': gold_price,
        'silver_price': silver_price,
        'current_ratio': current_ratio,
    }


def compare_metal_performance(period: str = "1mo", verbose: bool = True) -> pd.DataFrame:
    """Metal performanslarını karşılaştır."""

    if verbose:
        print()
        print("=" * 70)
        print(f"📊 METAL PERFORMANS KARŞILAŞTIRMASI ({period})")
        print("=" * 70)
        print()

    metals = {
        'gram-altin': '🥇 Gram Altın',
        'ons-altin': '🥇 Ons Altın',
        'gram-gumus': '🥈 Gram Gümüş',
    }

    performance_data = []

    for symbol, name in metals.items():
        try:
            fx = bp.FX(symbol)
            df = fx.history(period=period)

            if df is not None and len(df) > 1:
                start = df['Close'].iloc[0]
                end = df['Close'].iloc[-1]
                change_pct = ((end - start) / start) * 100

                performance_data.append({
                    'symbol': symbol,
                    'name': name,
                    'start_price': start,
                    'end_price': end,
                    'change_pct': change_pct,
                })

        except Exception as e:
            if verbose:
                print(f"   ⚠️ {symbol}: {e}")

    df = pd.DataFrame(performance_data)

    if not df.empty:
        df = df.sort_values('change_pct', ascending=False)

        if verbose:
            print(f"{'Metal':<20} {'Başlangıç':>12} {'Son':>12} {'Değişim':>10}")
            print("-" * 60)

            for _, row in df.iterrows():
                change_emoji = "📈" if row['change_pct'] > 0 else "📉"
                print(f"{row['name']:<20} {row['start_price']:>12.2f} {row['end_price']:>12.2f} "
                      f"{change_emoji} %{row['change_pct']:>+7.2f}")

    return df


if __name__ == "__main__":
    # Oran analizi
    result = analyze_gold_silver_ratio("1y")

    # Performans karşılaştırma
    perf = compare_metal_performance("1mo")
