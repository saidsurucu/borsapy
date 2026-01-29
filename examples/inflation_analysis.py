"""
Enflasyon Analizi
=================

TCMB enflasyon verilerini analiz eder.
Aylık ve yıllık TÜFE değişimlerini takip eder.

Kullanım:
    python examples/inflation_analysis.py
"""

import pandas as pd

import borsapy as bp


def analyze_inflation(verbose: bool = True) -> dict:
    """Enflasyon analizi yap."""

    if verbose:
        print("📊 ENFLASYON ANALİZİ")
        print("=" * 70)
        print()

    try:
        inflation = bp.Inflation()

        # Güncel veriler
        current = inflation.latest()

        if verbose:
            print("📈 GÜNCEL ENFLASYON VERİLERİ")
            print("-" * 50)
            print(f"   Yıllık TÜFE: %{current.get('annual', 0):.2f}")
            print(f"   Aylık TÜFE: %{current.get('monthly', 0):.2f}")
            print(f"   Dönem: {current.get('year', 'N/A')}/{current.get('month', 'N/A')}")
            print()

        # Tarihsel veri
        history = inflation.tufe()  # DataFrame döndürür

        result = {
            'current': current,
            'history': history,
        }

        if history is not None and not history.empty:
            # İstatistikler - son 24 ay
            recent_history = history.tail(24)
            annual_col = 'yillik' if 'yillik' in recent_history.columns else 'annual'

            if annual_col in recent_history.columns:
                annual_mean = recent_history[annual_col].mean()
                annual_max = recent_history[annual_col].max()
                annual_min = recent_history[annual_col].min()

                if verbose:
                    print("📊 İSTATİSTİKLER (Son 2 Yıl)")
                    print("-" * 50)
                    print(f"   Ortalama Yıllık: %{annual_mean:.2f}")
                    print(f"   En Yüksek: %{annual_max:.2f}")
                    print(f"   En Düşük: %{annual_min:.2f}")
                    print()

                result['stats'] = {
                    'mean': annual_mean,
                    'max': annual_max,
                    'min': annual_min,
                }

            # Trend analizi
            if len(recent_history) >= 3 and annual_col in recent_history.columns:
                last_3 = recent_history[annual_col].tail(3)
                trend = "Düşüyor" if last_3.is_monotonic_decreasing else \
                        "Yükseliyor" if last_3.is_monotonic_increasing else "Dalgalı"

                if verbose:
                    trend_emoji = "📉" if trend == "Düşüyor" else "📈" if trend == "Yükseliyor" else "〰️"
                    print(f"   Trend: {trend_emoji} {trend}")

                result['trend'] = trend

        return result

    except Exception as e:
        if verbose:
            print(f"❌ Hata: {e}")
        return {}


def calculate_real_return(nominal_return: float, inflation_rate: float) -> float:
    """Reel getiri hesapla (Fisher denklemi)."""
    return ((1 + nominal_return / 100) / (1 + inflation_rate / 100) - 1) * 100


def compare_real_returns(verbose: bool = True) -> pd.DataFrame:
    """Varlıkların reel getirilerini karşılaştır."""

    if verbose:
        print()
        print("=" * 70)
        print("📊 REEL GETİRİ KARŞILAŞTIRMASI")
        print("=" * 70)
        print()

    # Enflasyon oranı
    try:
        inflation = bp.Inflation()
        inflation_rate = inflation.current.get('annual', 50)
    except Exception:
        inflation_rate = 50  # Varsayılan

    if verbose:
        print(f"📈 Yıllık Enflasyon: %{inflation_rate:.1f}")
        print()

    # Karşılaştırılacak varlıklar
    assets = [
        ('BIST100', 'index', 'XU100'),
        ('Altın', 'fx', 'gram-altin'),
        ('USD', 'fx', 'USD'),
        ('EUR', 'fx', 'EUR'),
    ]

    results = []

    for name, asset_type, symbol in assets:
        try:
            if asset_type == 'index':
                asset = bp.Index(symbol)
            else:
                asset = bp.FX(symbol)

            df = asset.history(period="1y")

            if df is not None and len(df) > 20:
                start = df['Close'].iloc[0]
                end = df['Close'].iloc[-1]
                nominal_return = ((end - start) / start) * 100
                real_return = calculate_real_return(nominal_return, inflation_rate)

                results.append({
                    'asset': name,
                    'nominal_return': nominal_return,
                    'real_return': real_return,
                    'beat_inflation': real_return > 0,
                })

        except Exception as e:
            if verbose:
                print(f"   ⚠️ {name}: {e}")

    # Mevduat tahmini
    try:
        tcmb = bp.TCMB()
        policy_rate = tcmb.policy_rate
        # Mevduat genelde politika faizinin biraz altında
        deposit_rate = policy_rate * 0.9
        real_deposit = calculate_real_return(deposit_rate, inflation_rate)

        results.append({
            'asset': 'Mevduat (tahmini)',
            'nominal_return': deposit_rate,
            'real_return': real_deposit,
            'beat_inflation': real_deposit > 0,
        })
    except Exception:
        pass

    df = pd.DataFrame(results)

    if not df.empty:
        df = df.sort_values('real_return', ascending=False)

        if verbose:
            print("-" * 60)
            print(f"{'Varlık':<20} {'Nominal':>12} {'Reel':>12} {'Enflasyonu':>12}")
            print("-" * 60)

            for _, row in df.iterrows():
                beat = "✅ Yendi" if row['beat_inflation'] else "❌ Yenemedi"
                print(f"{row['asset']:<20} %{row['nominal_return']:>11.1f} "
                      f"%{row['real_return']:>11.1f} {beat:>12}")

            print()
            print("💡 YORUM:")
            winners = df[df['beat_inflation']]['asset'].tolist()
            if winners:
                print(f"   ✅ Enflasyonu yenen: {', '.join(winners)}")
            else:
                print("   ❌ Hiçbir varlık enflasyonu yenemedi!")

    return df


def inflation_adjusted_portfolio(verbose: bool = True) -> dict:
    """Enflasyona karşı korumalı portföy önerisi."""

    if verbose:
        print()
        print("=" * 70)
        print("🛡️ ENFLASYONA KARŞI KORUMA STRATEJİLERİ")
        print("=" * 70)
        print()

    strategies = {
        'Konsantre Hisse': {
            'allocation': {'Hisse': 80, 'Altın': 20},
            'risk': 'Yüksek',
            'description': 'Yüksek büyüme potansiyeli, yüksek volatilite',
        },
        'Dengeli': {
            'allocation': {'Hisse': 40, 'Altın': 30, 'Döviz': 30},
            'risk': 'Orta',
            'description': 'Çeşitlendirilmiş, dengeli risk-getiri',
        },
        'Muhafazakar': {
            'allocation': {'Altın': 40, 'Döviz': 40, 'Hisse': 20},
            'risk': 'Düşük',
            'description': 'Sermaye koruma odaklı',
        },
    }

    if verbose:
        for name, strategy in strategies.items():
            print(f"📊 {name.upper()}")
            print(f"   Risk: {strategy['risk']}")
            print(f"   {strategy['description']}")
            print("   Dağılım:")
            for asset, weight in strategy['allocation'].items():
                print(f"      • {asset}: %{weight}")
            print()

    return strategies


if __name__ == "__main__":
    # Enflasyon analizi
    inflation_data = analyze_inflation()

    # Reel getiri karşılaştırma
    real_returns = compare_real_returns()

    # Portföy stratejileri
    strategies = inflation_adjusted_portfolio()

    if not real_returns.empty:
        real_returns.to_csv("inflation_analysis.csv", index=False)
        print()
        print("📁 Sonuçlar 'inflation_analysis.csv' dosyasına kaydedildi.")
