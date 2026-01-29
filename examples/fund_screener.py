"""
Fon Tarama
==========

TEFAS fonlarını çeşitli kriterlere göre tarar.
En iyi performans gösteren fonları bulur.

Kullanım:
    python examples/fund_screener.py
"""

import pandas as pd

import borsapy as bp


def screen_top_funds(fund_type: str = "YAT", verbose: bool = True) -> pd.DataFrame:
    """Belirli tipteki en iyi fonları tara."""

    if verbose:
        type_names = {
            'YAT': 'Yatırım Fonları',
            'EMK': 'Emeklilik Fonları',
        }
        print(f"📊 FON TARAMA: {type_names.get(fund_type, fund_type)}")
        print("=" * 80)
        print()

    try:
        # Fon taraması
        results = bp.screen_funds(
            fund_type=fund_type,
            min_return_1y=0,  # Tüm fonlar
        )

        if results.empty:
            if verbose:
                print("❌ Fon bulunamadı.")
            return pd.DataFrame()

        # Getiriye göre sırala
        results = results.sort_values('return_1y', ascending=False)

        if verbose:
            print(f"🎯 {len(results)} Fon Bulundu")
            print()

            print("🏆 EN İYİ 1 YILLIK GETİRİ (İlk 20)")
            print("-" * 80)
            print(f"{'Kod':<8} {'Ad':<35} {'1Y':>10} {'YTD':>10} {'Risk':>8}")
            print("-" * 80)

            for _, row in results.head(20).iterrows():
                name = (row.get('name') or '')[:34]
                return_1y = row.get('return_1y') or 0
                return_ytd = row.get('return_ytd') or 0
                risk = row.get('risk_value') or 0

                print(f"{row['fund_code']:<8} {name:<35} "
                      f"%{return_1y:>9.1f} %{return_ytd:>9.1f} {risk:>7}/7")

        return results

    except Exception as e:
        if verbose:
            print(f"❌ Hata: {e}")
        return pd.DataFrame()


def find_low_risk_high_return(verbose: bool = True) -> pd.DataFrame:
    """Düşük riskli yüksek getirili fonları bul."""

    if verbose:
        print()
        print("=" * 80)
        print("🎯 DÜŞÜK RİSKLİ - YÜKSEK GETİRİLİ FONLAR")
        print("=" * 80)
        print()

    # Popüler fon kodları
    fund_codes = [
        # Hisse fonları
        'AAK', 'GAF', 'MAC', 'TTE', 'YAY', 'AFO',
        # Altın fonları
        'ALA', 'ALB', 'GLA',
        # Kısa vadeli
        'TKF', 'ZKB', 'ZBV',
    ]

    fund_data = []

    for code in fund_codes:
        try:
            fund = bp.Fund(code)
            info = fund.info

            # Risk metrikleri
            try:
                risk = fund.risk_metrics(period="1y")
                sharpe = risk.get('sharpe_ratio')
                volatility = risk.get('annualized_volatility')
                max_dd = risk.get('max_drawdown')
            except Exception:
                sharpe = None
                volatility = None
                max_dd = None

            fund_data.append({
                'code': code,
                'name': info.get('name', code)[:30],
                'return_1y': info.get('return_1y') or 0,
                'return_ytd': info.get('return_ytd') or 0,
                'risk_value': info.get('risk_value'),
                'sharpe': sharpe,
                'volatility': volatility,
                'max_drawdown': max_dd,
            })

        except Exception as e:
            if verbose:
                print(f"   ⚠️ {code}: {e}")

    df = pd.DataFrame(fund_data)

    if df.empty:
        return df

    # Sharpe'a göre sırala
    df = df.sort_values('sharpe', ascending=False, na_position='last')

    if verbose:
        print("📊 RİSK-GETİRİ ANALİZİ (Sharpe'a göre sıralı)")
        print("-" * 90)
        print(f"{'Kod':<8} {'Ad':<32} {'1Y':>8} {'Sharpe':>8} {'Volat.':>8} {'MDD':>8} {'Risk':>6}")
        print("-" * 90)

        for _, row in df.iterrows():
            sharpe_str = f"{row['sharpe']:.2f}" if pd.notna(row['sharpe']) else "N/A"
            vol_str = f"%{row['volatility']:.1f}" if pd.notna(row['volatility']) else "N/A"
            mdd_str = f"%{row['max_drawdown']:.1f}" if pd.notna(row['max_drawdown']) else "N/A"
            risk_str = f"{row['risk_value']}/7" if pd.notna(row['risk_value']) else "N/A"

            print(f"{row['code']:<8} {row['name']:<32} "
                  f"%{row['return_1y']:>7.1f} {sharpe_str:>8} {vol_str:>8} {mdd_str:>8} {risk_str:>6}")

        print()
        print("💡 YORUM:")
        print("   • Sharpe > 1: İyi risk-getiri dengesi")
        print("   • Sharpe > 2: Çok iyi risk-getiri dengesi")
        print("   • MDD (Max Drawdown): Düşük = daha az dalgalanma")

    return df


def compare_fund_categories(verbose: bool = True) -> dict:
    """Fon kategorilerini karşılaştır."""

    if verbose:
        print()
        print("=" * 80)
        print("📊 FON KATEGORİ KARŞILAŞTIRMASI")
        print("=" * 80)
        print()

    categories = {
        'Hisse': ['AAK', 'GAF', 'MAC'],
        'Yabancı Hisse': ['YAY', 'TTE', 'AFO'],
        'Altın': ['ALA', 'ALB', 'GLA'],
    }

    results = {}

    for category, codes in categories.items():
        returns = []

        for code in codes:
            try:
                fund = bp.Fund(code)
                info = fund.info
                return_1y = info.get('return_1y')
                if return_1y:
                    returns.append(return_1y)
            except Exception:
                pass

        if returns:
            avg_return = sum(returns) / len(returns)
            results[category] = {
                'avg_return': avg_return,
                'fund_count': len(returns),
                'best': max(returns),
                'worst': min(returns),
            }

            if verbose:
                print(f"📁 {category}:")
                print(f"   Ortalama 1Y Getiri: %{avg_return:.1f}")
                print(f"   En İyi: %{max(returns):.1f} | En Kötü: %{min(returns):.1f}")
                print()

    return results


if __name__ == "__main__":
    # Yatırım fonları tarama
    yat_funds = screen_top_funds("YAT")

    # Risk-getiri analizi
    risk_return = find_low_risk_high_return()

    # Kategori karşılaştırma
    categories = compare_fund_categories()

    if not risk_return.empty:
        risk_return.to_csv("fund_screener_results.csv", index=False)
        print()
        print("📁 Sonuçlar 'fund_screener_results.csv' dosyasına kaydedildi.")
