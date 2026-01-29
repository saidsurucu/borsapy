"""
Risk Paritesi Portföyü
======================

Eşit risk katkısı prensibine göre portföy oluşturur.
Her varlık portföy riskine eşit katkıda bulunur.

Kullanım:
    python examples/risk_parity_portfolio.py
"""

import numpy as np
import pandas as pd

import borsapy as bp


def calculate_volatility(symbol: str, asset_type: str = "stock", period: str = "1y") -> float:
    """Varlık volatilitesini hesapla."""
    try:
        if asset_type == "stock":
            asset = bp.Ticker(symbol)
        elif asset_type == "index":
            asset = bp.Index(symbol)
        elif asset_type == "fx":
            asset = bp.FX(symbol)
        elif asset_type == "crypto":
            asset = bp.Crypto(symbol)
        else:
            return None

        df = asset.history(period=period)

        if df is None or len(df) < 20:
            return None

        # Günlük getiri
        returns = df['Close'].pct_change().dropna()

        # Yıllık volatilite
        volatility = returns.std() * np.sqrt(252) * 100

        return volatility

    except Exception:
        return None


def build_risk_parity_portfolio(
    assets: list[dict],
    total_capital: float = 100000,
    verbose: bool = True,
) -> dict:
    """Risk paritesi portföyü oluştur."""

    if verbose:
        print("📊 RİSK PARİTESİ PORTFÖYÜ")
        print("=" * 70)
        print()
        print(f"💰 Toplam Sermaye: {total_capital:,.0f} TL")
        print()

    # Volatilite hesapla
    if verbose:
        print("📈 VOLATİLİTE HESAPLAMA")
        print("-" * 50)

    asset_data = []

    for asset in assets:
        symbol = asset['symbol']
        asset_type = asset.get('type', 'stock')
        name = asset.get('name', symbol)

        vol = calculate_volatility(symbol, asset_type)

        if vol:
            asset_data.append({
                'symbol': symbol,
                'name': name,
                'type': asset_type,
                'volatility': vol,
            })

            if verbose:
                print(f"   {name:<20} Volatilite: %{vol:.1f}")
        else:
            if verbose:
                print(f"   {name:<20} ⚠️ Veri alınamadı")

    if len(asset_data) < 2:
        if verbose:
            print("❌ Yeterli varlık yok.")
        return {}

    # Risk paritesi ağırlıkları hesapla
    # Ağırlık = 1/volatilite (normalize edilmiş)
    total_inv_vol = sum(1 / a['volatility'] for a in asset_data)

    for asset in asset_data:
        # Ters volatilite ağırlığı
        weight = (1 / asset['volatility']) / total_inv_vol
        asset['weight'] = weight * 100
        asset['allocation'] = total_capital * weight

        # Risk katkısı (eşit olmalı)
        asset['risk_contribution'] = weight * asset['volatility']

    # Normalize risk katkısı
    total_risk = sum(a['risk_contribution'] for a in asset_data)
    for asset in asset_data:
        asset['risk_contribution_pct'] = (asset['risk_contribution'] / total_risk) * 100

    if verbose:
        print()
        print("📊 RİSK PARİTESİ DAĞILIMI")
        print("-" * 70)
        print(f"{'Varlık':<20} {'Ağırlık':>10} {'Tutar':>15} {'Volatilite':>12} {'Risk Katkısı':>12}")
        print("-" * 70)

        for asset in asset_data:
            print(f"{asset['name']:<20} %{asset['weight']:>9.1f} "
                  f"{asset['allocation']:>14,.0f} %{asset['volatility']:>11.1f} "
                  f"%{asset['risk_contribution_pct']:>11.1f}")

        print("-" * 70)
        total_weight = sum(a['weight'] for a in asset_data)
        total_alloc = sum(a['allocation'] for a in asset_data)
        print(f"{'TOPLAM':<20} %{total_weight:>9.1f} {total_alloc:>14,.0f}")

        print()
        print("💡 Risk Paritesi Prensibi:")
        print("   Her varlık portföy riskine eşit katkıda bulunur.")
        print("   Düşük volatiliteli varlıklara daha fazla ağırlık verilir.")

    return {
        'assets': asset_data,
        'total_capital': total_capital,
    }


def compare_with_equal_weight(
    assets: list[dict],
    total_capital: float = 100000,
    verbose: bool = True,
) -> dict:
    """Risk paritesi vs eşit ağırlık karşılaştırması."""

    if verbose:
        print()
        print("=" * 70)
        print("📊 RİSK PARİTESİ vs EŞİT AĞIRLIK KARŞILAŞTIRMASI")
        print("=" * 70)
        print()

    # Risk paritesi
    rp = build_risk_parity_portfolio(assets, total_capital, verbose=False)

    if not rp:
        return {}

    # Eşit ağırlık
    n = len(rp['assets'])
    equal_weight = 100 / n

    if verbose:
        print(f"{'Varlık':<20} {'Risk Paritesi':>15} {'Eşit Ağırlık':>15} {'Fark':>10}")
        print("-" * 65)

        for asset in rp['assets']:
            diff = asset['weight'] - equal_weight
            print(f"{asset['name']:<20} %{asset['weight']:>14.1f} "
                  f"%{equal_weight:>14.1f} %{diff:>+9.1f}")

        print()

        # Portföy volatilitesi karşılaştırma
        rp_vol = sum(a['weight'] / 100 * a['volatility'] for a in rp['assets'])
        eq_vol = sum(equal_weight / 100 * a['volatility'] for a in rp['assets'])

        print(f"📈 Tahmini Portföy Volatilitesi:")
        print(f"   Risk Paritesi: %{rp_vol:.1f}")
        print(f"   Eşit Ağırlık: %{eq_vol:.1f}")
        print(f"   Fark: %{rp_vol - eq_vol:+.1f}")

    return {
        'risk_parity': rp,
        'equal_weight': equal_weight,
    }


if __name__ == "__main__":
    # Örnek varlıklar
    assets = [
        {'symbol': 'THYAO', 'name': 'THY', 'type': 'stock'},
        {'symbol': 'GARAN', 'name': 'Garanti', 'type': 'stock'},
        {'symbol': 'gram-altin', 'name': 'Altın', 'type': 'fx'},
        {'symbol': 'USD', 'name': 'Dolar', 'type': 'fx'},
        {'symbol': 'XU100', 'name': 'BIST100 ETF', 'type': 'index'},
    ]

    # Risk paritesi portföyü oluştur
    portfolio = build_risk_parity_portfolio(assets, total_capital=100000)

    # Eşit ağırlık ile karşılaştır
    comparison = compare_with_equal_weight(assets)

    if portfolio.get('assets'):
        df = pd.DataFrame(portfolio['assets'])
        df.to_csv("risk_parity_portfolio.csv", index=False)
        print()
        print("📁 Portföy 'risk_parity_portfolio.csv' dosyasına kaydedildi.")
