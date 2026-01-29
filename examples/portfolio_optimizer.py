"""
Portföy Optimizasyonu (Monte Carlo)
===================================

Modern Portföy Teorisi kullanarak Sharpe oranını maksimize eden
optimal portföy ağırlıklarını bulur.

Monte Carlo simülasyonu ile:
- 10,000 rastgele portföy oluşturur
- En yüksek Sharpe oranına sahip portföyü seçer
- Etkin sınır üzerindeki portföyleri gösterir

Kullanım:
    python examples/portfolio_optimizer.py
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

import borsapy as bp


def get_returns_matrix(symbols: list[str], period: str = "1y") -> pd.DataFrame | None:
    """
    Hisseler için günlük getiri matrisi oluştur.

    Returns:
        DataFrame (tarih x sembol) veya None
    """
    returns_dict = {}

    for symbol in symbols:
        try:
            ticker = bp.Ticker(symbol)
            df = ticker.history(period=period)

            if df.empty or len(df) < 50:
                continue

            # Günlük getiri
            returns = df['Close'].pct_change().dropna()
            returns_dict[symbol] = returns

        except Exception:
            continue

    if len(returns_dict) < 2:
        return None

    # DataFrame'e çevir ve ortak tarihleri al
    returns_df = pd.DataFrame(returns_dict)
    returns_df = returns_df.dropna()

    return returns_df


def monte_carlo_optimization(
    returns: pd.DataFrame,
    num_portfolios: int = 10000,
    risk_free_rate: float = 0.40,  # %40 yıllık
) -> dict:
    """
    Monte Carlo simülasyonu ile optimal portföy bul.

    Args:
        returns: Günlük getiri matrisi
        num_portfolios: Simüle edilecek portföy sayısı
        risk_free_rate: Risksiz faiz oranı (yıllık)

    Returns:
        Optimizasyon sonuçları
    """
    num_assets = len(returns.columns)
    symbols = returns.columns.tolist()

    # Yıllık getiri ve kovaryans
    mean_returns = returns.mean() * 252  # Yıllık
    cov_matrix = returns.cov() * 252

    # Simülasyon sonuçları
    results = np.zeros((4, num_portfolios))
    weights_record = []

    for i in range(num_portfolios):
        # Rastgele ağırlıklar
        weights = np.random.random(num_assets)
        weights = weights / np.sum(weights)
        weights_record.append(weights)

        # Portföy getirisi
        portfolio_return = np.sum(mean_returns * weights)

        # Portföy volatilitesi
        portfolio_std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

        # Sharpe oranı
        sharpe_ratio = (portfolio_return - risk_free_rate) / portfolio_std

        results[0, i] = portfolio_return
        results[1, i] = portfolio_std
        results[2, i] = sharpe_ratio
        results[3, i] = i

    # En iyi Sharpe
    max_sharpe_idx = np.argmax(results[2])
    max_sharpe_weights = weights_record[max_sharpe_idx]

    # Minimum volatilite
    min_vol_idx = np.argmin(results[1])
    min_vol_weights = weights_record[min_vol_idx]

    return {
        'symbols': symbols,
        'max_sharpe': {
            'weights': dict(zip(symbols, np.round(max_sharpe_weights * 100, 2))),
            'return': round(results[0, max_sharpe_idx] * 100, 2),
            'volatility': round(results[1, max_sharpe_idx] * 100, 2),
            'sharpe': round(results[2, max_sharpe_idx], 3),
        },
        'min_volatility': {
            'weights': dict(zip(symbols, np.round(min_vol_weights * 100, 2))),
            'return': round(results[0, min_vol_idx] * 100, 2),
            'volatility': round(results[1, min_vol_idx] * 100, 2),
            'sharpe': round(results[2, min_vol_idx], 3),
        },
        'all_portfolios': {
            'returns': results[0] * 100,
            'volatilities': results[1] * 100,
            'sharpes': results[2],
        },
        'individual_stats': {
            symbol: {
                'return': round(mean_returns[symbol] * 100, 2),
                'volatility': round(np.sqrt(cov_matrix.loc[symbol, symbol]) * 100, 2),
            }
            for symbol in symbols
        },
    }


def optimize_portfolio(
    symbols: list[str],
    period: str = "1y",
    num_simulations: int = 10000,
    verbose: bool = True,
) -> dict:
    """Portföy optimizasyonu çalıştır."""

    if verbose:
        print(f"📊 Portföy Optimizasyonu (Modern Portföy Teorisi)")
        print(f"   - Hisseler: {', '.join(symbols)}")
        print(f"   - Dönem: {period}")
        print(f"   - Simülasyon: {num_simulations:,} portföy")
        print()

    # Risksiz faiz oranını al
    try:
        rf_rate = bp.risk_free_rate() / 100
        if verbose:
            print(f"   - Risksiz Faiz: %{rf_rate*100:.1f} (10Y Tahvil)")
    except Exception:
        rf_rate = 0.40
        if verbose:
            print(f"   - Risksiz Faiz: %{rf_rate*100:.1f} (varsayılan)")

    print()

    # Getiri verilerini al
    if verbose:
        print("🔍 Fiyat verileri alınıyor...")

    returns = get_returns_matrix(symbols, period)

    if returns is None or len(returns.columns) < 2:
        if verbose:
            print("❌ Yeterli veri alınamadı.")
        return {}

    if verbose:
        print(f"✅ {len(returns.columns)} hisse, {len(returns)} gün veri")
        print()
        print("🎲 Monte Carlo simülasyonu çalıştırılıyor...")

    # Optimizasyon
    result = monte_carlo_optimization(returns, num_simulations, rf_rate)

    if verbose:
        print()
        print("=" * 70)
        print("📈 OPTİMİZASYON SONUÇLARI")
        print("=" * 70)
        print()

        # Bireysel hisse istatistikleri
        print("📊 Bireysel Hisse Performansı:")
        print(f"   {'Sembol':<10} {'Yıllık Getiri':>15} {'Volatilite':>15}")
        print("   " + "-" * 45)
        for sym, stats in result['individual_stats'].items():
            print(f"   {sym:<10} %{stats['return']:>13.1f} %{stats['volatility']:>13.1f}")

        print()
        print("-" * 70)

        # Maksimum Sharpe portföyü
        ms = result['max_sharpe']
        print()
        print("🏆 MAKSİMUM SHARPE PORTFÖYÜ (En İyi Risk/Getiri)")
        print(f"   Beklenen Getiri: %{ms['return']:.1f}")
        print(f"   Volatilite:      %{ms['volatility']:.1f}")
        print(f"   Sharpe Oranı:    {ms['sharpe']:.3f}")
        print()
        print("   Ağırlıklar:")
        for sym, weight in sorted(ms['weights'].items(), key=lambda x: -x[1]):
            if weight > 0.1:  # %0.1'den büyük olanları göster
                bar = "█" * int(weight / 5)
                print(f"   {sym:<10} %{weight:>6.1f} {bar}")

        # Minimum volatilite portföyü
        mv = result['min_volatility']
        print()
        print("🛡️  MİNİMUM VOLATİLİTE PORTFÖYÜ (En Düşük Risk)")
        print(f"   Beklenen Getiri: %{mv['return']:.1f}")
        print(f"   Volatilite:      %{mv['volatility']:.1f}")
        print(f"   Sharpe Oranı:    {mv['sharpe']:.3f}")
        print()
        print("   Ağırlıklar:")
        for sym, weight in sorted(mv['weights'].items(), key=lambda x: -x[1]):
            if weight > 0.1:
                bar = "█" * int(weight / 5)
                print(f"   {sym:<10} %{weight:>6.1f} {bar}")

    return result


def main():
    print("=" * 70)
    print("borsapy - Portföy Optimizasyonu")
    print("=" * 70)
    print()

    # Örnek portföy - farklı sektörlerden hisseler
    portfolio_symbols = [
        "THYAO",   # Havacılık
        "TUPRS",   # Enerji
        "BIMAS",   # Perakende
        "ASELS",   # Savunma
        "KCHOL",   # Holding
        "EREGL",   # Metal
        "TCELL",   # Telekomünikasyon
        "SISE",    # Cam
    ]

    result = optimize_portfolio(
        symbols=portfolio_symbols,
        period="1y",
        num_simulations=10000,
        verbose=True,
    )

    if result:
        # Sonuçları kaydet
        summary = {
            'type': ['Max Sharpe', 'Min Volatility'],
            'return': [result['max_sharpe']['return'], result['min_volatility']['return']],
            'volatility': [result['max_sharpe']['volatility'], result['min_volatility']['volatility']],
            'sharpe': [result['max_sharpe']['sharpe'], result['min_volatility']['sharpe']],
        }

        # Ağırlıkları ekle
        for sym in result['symbols']:
            summary[f'{sym}_weight'] = [
                result['max_sharpe']['weights'][sym],
                result['min_volatility']['weights'][sym],
            ]

        df = pd.DataFrame(summary)
        df.to_csv("portfolio_optimization_results.csv", index=False)

        print()
        print("📁 Sonuçlar 'portfolio_optimization_results.csv' dosyasına kaydedildi.")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
