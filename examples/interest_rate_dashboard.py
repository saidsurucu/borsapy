"""
Faiz Oranları Dashboard
=======================

TCMB faiz oranları, tahvil getirileri ve spread analizini
tek bir dashboard'da gösterir.

İçerik:
- TCMB politika faizi ve koridor
- Devlet tahvili getirileri (2Y, 5Y, 10Y)
- Eurobond getirileri
- Spread analizi

Kullanım:
    python examples/interest_rate_dashboard.py
"""

import pandas as pd
from datetime import datetime

import borsapy as bp


def get_tcmb_rates() -> dict:
    """TCMB faiz oranlarını al."""
    try:
        tcmb = bp.TCMB()
        return {
            'policy_rate': tcmb.policy_rate,
            'overnight': tcmb.overnight,
            'late_liquidity': tcmb.late_liquidity,
        }
    except Exception as e:
        return {'error': str(e)}


def get_bond_yields() -> dict:
    """Devlet tahvili getirilerini al."""
    try:
        bonds_df = bp.bonds()

        if bonds_df.empty:
            return {}

        yields = {}
        for _, row in bonds_df.iterrows():
            maturity = row.get('maturity', 'N/A')
            yield_rate = row.get('yield', 0)
            yields[maturity] = yield_rate

        return yields

    except Exception as e:
        return {'error': str(e)}


def get_eurobond_yields() -> list:
    """Eurobond getirilerini al."""
    try:
        eurobonds = bp.eurobonds(currency="USD")

        if eurobonds.empty:
            return []

        # Vadeye göre sırala ve ilk 5
        eurobonds = eurobonds.sort_values('maturity').head(5)

        result = []
        for _, row in eurobonds.iterrows():
            result.append({
                'isin': row.get('isin', 'N/A'),
                'maturity': row.get('maturity'),
                'bid_yield': row.get('bid_yield', 0),
                'ask_yield': row.get('ask_yield', 0),
            })

        return result

    except Exception as e:
        return [{'error': str(e)}]


def calculate_spreads(tcmb_rate: float, bond_yields: dict) -> dict:
    """Spread hesapla."""
    spreads = {}

    # Risk free rate
    rf_rate = bond_yields.get('10Y', 0)

    if rf_rate:
        spreads['policy_vs_10y'] = round(tcmb_rate - rf_rate, 2)

    if '2Y' in bond_yields and '10Y' in bond_yields:
        spreads['2y_10y_spread'] = round(bond_yields['10Y'] - bond_yields['2Y'], 2)

    if '5Y' in bond_yields and '10Y' in bond_yields:
        spreads['5y_10y_spread'] = round(bond_yields['10Y'] - bond_yields['5Y'], 2)

    return spreads


def show_dashboard(verbose: bool = True):
    """Faiz dashboard'unu göster."""

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    print("=" * 70)
    print(f"💹 FAİZ ORANLARI DASHBOARD | {now}")
    print("=" * 70)
    print()

    # TCMB Faizleri
    print("🏦 TCMB FAİZ ORANLARI")
    print("-" * 50)

    tcmb = get_tcmb_rates()

    if 'error' not in tcmb:
        print(f"   📌 Politika Faizi (1 Hafta Repo): %{tcmb['policy_rate']:.2f}")
        print()
        print("   Gecelik Faiz Koridoru:")
        overnight = tcmb.get('overnight', {})
        print(f"      Borç Alma:  %{overnight.get('borrowing', 0):.2f}")
        print(f"      Borç Verme: %{overnight.get('lending', 0):.2f}")
        print()
        print("   Geç Likidite Penceresi:")
        late = tcmb.get('late_liquidity', {})
        print(f"      Borç Alma:  %{late.get('borrowing', 0):.2f}")
        print(f"      Borç Verme: %{late.get('lending', 0):.2f}")
    else:
        print(f"   ❌ Veri alınamadı: {tcmb['error']}")

    print()

    # Devlet Tahvilleri
    print("📈 DEVLET TAHVİLİ GETİRİLERİ")
    print("-" * 50)

    bonds = get_bond_yields()

    if 'error' not in bonds and bonds:
        for maturity, yield_rate in sorted(bonds.items()):
            bar = "█" * int(yield_rate / 3)
            print(f"   {maturity:<10} %{yield_rate:>6.2f} {bar}")
    else:
        print("   ❌ Tahvil verisi alınamadı.")

    print()

    # Eurobondlar
    print("🌍 EUROBOND GETİRİLERİ (USD)")
    print("-" * 50)

    eurobonds = get_eurobond_yields()

    if eurobonds and 'error' not in eurobonds[0]:
        print(f"   {'Vade':<12} {'Bid':>10} {'Ask':>10}")
        print("   " + "-" * 35)
        for eb in eurobonds:
            maturity_str = eb['maturity'].strftime('%Y-%m') if eb.get('maturity') else 'N/A'
            print(f"   {maturity_str:<12} %{eb['bid_yield']:>8.2f} %{eb['ask_yield']:>8.2f}")
    else:
        print("   ❌ Eurobond verisi alınamadı.")

    print()

    # Spread Analizi
    print("📊 SPREAD ANALİZİ")
    print("-" * 50)

    if 'error' not in tcmb and bonds:
        spreads = calculate_spreads(tcmb.get('policy_rate', 0), bonds)

        if spreads:
            if 'policy_vs_10y' in spreads:
                spread = spreads['policy_vs_10y']
                indicator = "↑" if spread > 0 else "↓"
                print(f"   Politika Faizi - 10Y Tahvil: {spread:+.2f}% {indicator}")

            if '2y_10y_spread' in spreads:
                spread = spreads['2y_10y_spread']
                curve = "Normal (Eğim +)" if spread > 0 else "Ters (Eğim -)"
                print(f"   10Y - 2Y Spread (Getiri Eğrisi): {spread:+.2f}% ({curve})")

            if '5y_10y_spread' in spreads:
                spread = spreads['5y_10y_spread']
                print(f"   10Y - 5Y Spread: {spread:+.2f}%")

    print()

    # Yorum
    print("💡 YORUM:")
    print("-" * 50)

    if 'error' not in tcmb and bonds:
        policy = tcmb.get('policy_rate', 0)
        y10 = bonds.get('10Y', 0)

        if policy > y10 + 5:
            print("   ⚠️  Politika faizi tahvil getirilerinin oldukça üzerinde.")
            print("      Sıkı para politikası devam ediyor.")
        elif policy > y10:
            print("   📊 Politika faizi tahvil getirilerinin üzerinde.")
            print("      Piyasa faiz indirim beklentisi içinde olabilir.")
        else:
            print("   📈 Tahvil getirileri politika faizinin üzerinde.")
            print("      Piyasa faiz artışı beklentisi içinde olabilir.")

    print()
    print("=" * 70)


def main():
    show_dashboard(verbose=True)


if __name__ == "__main__":
    main()
