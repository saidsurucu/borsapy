"""
En İyi Fon Karşılaştırma
========================

TEFAS fonlarını karşılaştırır ve performans analizi yapar.

borsapy'nin compare_funds() fonksiyonunu kullanır.

Kullanım:
    python examples/best_funds_comparison.py
"""

import pandas as pd

import borsapy as bp


def get_fund_metrics(fund_code: str) -> dict | None:
    """Fon metriklerini al."""
    try:
        fund = bp.Fund(fund_code)
        info = fund.info

        # Risk metrikleri (1 yıllık)
        try:
            risk = fund.risk_metrics(period="1y")
        except Exception:
            risk = {}

        return {
            'code': fund_code,
            'name': info.get('name', fund_code),
            'type': info.get('fund_type', 'N/A'),
            'return_1m': info.get('return_1m', 0),
            'return_3m': info.get('return_3m', 0),
            'return_6m': info.get('return_6m', 0),
            'return_1y': info.get('return_1y', 0),
            'return_ytd': info.get('return_ytd', 0),
            'price': info.get('price', 0),
            'fund_size': info.get('fund_size', 0),
            'sharpe_ratio': risk.get('sharpe_ratio'),
            'volatility': risk.get('annualized_volatility'),
            'max_drawdown': risk.get('max_drawdown'),
        }
    except Exception as e:
        print(f"   ⚠️ {fund_code}: {e}")
        return None


def compare_fund_group(
    fund_codes: list[str],
    group_name: str = "Fonlar",
    verbose: bool = True,
) -> pd.DataFrame:
    """Fon grubunu karşılaştır."""

    if verbose:
        print(f"📊 {group_name} Karşılaştırması")
        print("=" * 80)
        print()

    # compare_funds API'sini kullan
    if verbose:
        print("🔍 Fon verileri alınıyor...")

    try:
        comparison = bp.compare_funds(fund_codes)

        if not comparison or 'funds' not in comparison:
            if verbose:
                print("❌ Fon verisi alınamadı.")
            return pd.DataFrame()

        funds_data = comparison['funds']
        rankings = comparison.get('rankings', {})
        summary = comparison.get('summary', {})

        if verbose:
            print(f"✅ {len(funds_data)} fon karşılaştırıldı")
            print()

            # Özet bilgi
            print("📈 ÖZET:")
            print("-" * 60)
            print(f"   Fon Sayısı: {summary.get('fund_count', len(funds_data))}")
            print(f"   Ortalama 1Y Getiri: %{summary.get('avg_return_1y', 0):.1f}")
            print(f"   En İyi 1Y Getiri: %{summary.get('best_return_1y', 0):.1f}")
            print(f"   En Kötü 1Y Getiri: %{summary.get('worst_return_1y', 0):.1f}")
            print(f"   Toplam Fon Büyüklüğü: {summary.get('total_size', 0):,.0f} TL")
            print()

            # Sıralamalar
            print("🏆 SIRALAMALAR:")
            print("-" * 60)
            if 'by_return_1y' in rankings:
                print(f"   1Y Getiriye Göre: {', '.join(rankings['by_return_1y'][:5])}")
            if 'by_return_ytd' in rankings:
                print(f"   YTD Getiriye Göre: {', '.join(rankings['by_return_ytd'][:5])}")
            if 'by_size' in rankings:
                print(f"   Büyüklüğe Göre: {', '.join(rankings['by_size'][:5])}")
            print()

            # Detaylı tablo
            print("📋 DETAYLI KARŞILAŞTIRMA:")
            print("-" * 80)
            print(f"{'Kod':<8} {'Ad':<30} {'1Y':>10} {'YTD':>10} {'Büyüklük':>15}")
            print("-" * 80)

            for fund in funds_data:
                if fund is None:
                    continue
                name = (fund.get('name') or 'N/A')[:29]
                return_1y = fund.get('return_1y') or 0
                return_ytd = fund.get('return_ytd') or 0
                fund_size = fund.get('fund_size') or 0

                print(f"{fund.get('fund_code', 'N/A'):<8} {name:<30} "
                      f"%{return_1y:>8.1f} %{return_ytd:>8.1f} "
                      f"{fund_size:>14,.0f}")

        # DataFrame oluştur
        df = pd.DataFrame(funds_data)
        return df

    except Exception as e:
        if verbose:
            print(f"❌ Hata: {e}")
        return pd.DataFrame()


def analyze_popular_funds(verbose: bool = True) -> dict:
    """Popüler fon kategorilerini analiz et."""

    # Popüler fon grupları
    fund_groups = {
        'Teknoloji Fonları': ['YAY', 'TTE', 'AFO', 'IPY', 'IYT'],
        'Hisse Fonları': ['AAK', 'GAF', 'MAC', 'ZHF', 'AFS'],
        'Altın Fonları': ['ALA', 'ALB', 'GLA', 'GLF', 'GLY'],
        'Döviz Fonları': ['DAH', 'EUR', 'GDS', 'DFL', 'DLF'],
    }

    if verbose:
        print("📊 POPÜLER FON KATEGORİLERİ ANALİZİ")
        print("=" * 80)
        print()

    results = {}

    for group_name, codes in fund_groups.items():
        if verbose:
            print(f"🔍 {group_name} analiz ediliyor...")

        try:
            df = compare_fund_group(codes, group_name, verbose=False)

            if not df.empty:
                results[group_name] = df

                # Grup özeti
                if verbose:
                    avg_return = df['return_1y'].mean() if 'return_1y' in df.columns else 0
                    best_fund = df.iloc[0]['fund_code'] if 'fund_code' in df.columns else 'N/A'
                    print(f"   ✅ {len(df)} fon, Ort. 1Y Getiri: %{avg_return:.1f}, En İyi: {best_fund}")
        except Exception as e:
            if verbose:
                print(f"   ❌ Hata: {e}")

    return results


def main():
    print("=" * 80)
    print("borsapy - En İyi Fon Karşılaştırma")
    print("=" * 80)
    print()

    # Popüler fonları analiz et
    results = analyze_popular_funds(verbose=True)

    print()
    print("=" * 80)
    print()

    # Örnek detaylı karşılaştırma - Teknoloji fonları
    tech_funds = ['YAY', 'TTE', 'AFO', 'IPY', 'IYT']
    tech_df = compare_fund_group(tech_funds, "Teknoloji/Yabancı Hisse Fonları", verbose=True)

    if not tech_df.empty:
        tech_df.to_csv("best_funds_comparison.csv", index=False)
        print()
        print("📁 Sonuçlar 'best_funds_comparison.csv' dosyasına kaydedildi.")

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
