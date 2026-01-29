"""
Hareketli Ortalama Backtest
===========================

SMA crossover stratejisini test eder.
Golden Cross: SMA20 > SMA50 → ALIM
Death Cross: SMA20 < SMA50 → SATIM

Kullanım:
    python examples/moving_average_backtest.py
"""

import pandas as pd

import borsapy as bp


def sma_crossover_strategy(candle: dict, position: str | None, indicators: dict) -> str:
    """
    SMA Crossover stratejisi.

    Args:
        candle: OHLCV verisi
        position: Mevcut pozisyon ('long', 'short', None)
        indicators: Gösterge değerleri (sma_20, sma_50)

    Returns:
        'BUY', 'SELL', veya 'HOLD'
    """
    sma_20 = indicators.get('sma_20', 0)
    sma_50 = indicators.get('sma_50', 0)

    if not sma_20 or not sma_50:
        return 'HOLD'

    # Golden Cross - Alım
    if position is None and sma_20 > sma_50:
        return 'BUY'

    # Death Cross - Satım
    if position == 'long' and sma_20 < sma_50:
        return 'SELL'

    return 'HOLD'


def run_sma_backtest(
    symbol: str,
    period: str = "2y",
    capital: float = 100000,
    verbose: bool = True,
) -> bp.BacktestResult | None:
    """SMA crossover backtesti çalıştır."""

    if verbose:
        print(f"📊 SMA CROSSOVER BACKTEST: {symbol}")
        print("=" * 70)
        print()
        print(f"   Strateji: SMA20/SMA50 Crossover")
        print(f"   Dönem: {period}")
        print(f"   Sermaye: {capital:,.0f} TL")
        print()

    try:
        result = bp.backtest(
            symbol=symbol,
            strategy=sma_crossover_strategy,
            period=period,
            capital=capital,
            commission=0.001,
            indicators=['sma_20', 'sma_50'],
        )

        if verbose:
            print("📈 SONUÇLAR:")
            print("-" * 70)
            pnl_emoji = "📈" if result.net_profit >= 0 else "📉"
            print(f"   Net Kar/Zarar: {result.net_profit:+,.2f} TL ({pnl_emoji} %{result.net_profit_pct:+.2f})")
            print(f"   Toplam İşlem: {result.total_trades}")
            print(f"   Kazanan: {result.winning_trades} | Kaybeden: {result.losing_trades}")
            print(f"   Win Rate: %{result.win_rate:.1f}")
            print()

            # Risk metrikleri
            sharpe = result.sharpe_ratio if result.sharpe_ratio == result.sharpe_ratio else 0
            sortino = result.sortino_ratio if result.sortino_ratio == result.sortino_ratio else 0
            print(f"   Max Drawdown: %{result.max_drawdown:.2f}")
            print(f"   Sharpe: {sharpe:.2f} | Sortino: {sortino:.2f}")
            print()

            # Buy & Hold
            print(f"   Buy & Hold: %{result.buy_hold_return:.2f}")
            vs_bh = result.vs_buy_hold
            bh_emoji = "✅" if vs_bh > 0 else "❌"
            print(f"   Strateji vs B&H: %{vs_bh:+.2f} {bh_emoji}")

        return result

    except Exception as e:
        if verbose:
            print(f"❌ Hata: {e}")
        return None


def compare_sma_periods(symbol: str, verbose: bool = True) -> pd.DataFrame:
    """Farklı SMA periyotlarını karşılaştır."""

    if verbose:
        print()
        print("=" * 70)
        print(f"📊 SMA PERİYOT KARŞILAŞTIRMASI: {symbol}")
        print("=" * 70)
        print()

    # Farklı SMA kombinasyonları
    combinations = [
        (10, 20, 'Kısa Vade'),
        (20, 50, 'Orta Vade'),
        (50, 100, 'Orta-Uzun'),
        (50, 200, 'Uzun Vade'),
    ]

    results = []

    for fast, slow, label in combinations:
        if verbose:
            print(f"🔄 Test ediliyor: SMA{fast}/SMA{slow} ({label})...")

        def make_strategy(fast_period, slow_period):
            def strategy(candle, position, indicators):
                fast_sma = indicators.get(f'sma_{fast_period}', 0)
                slow_sma = indicators.get(f'sma_{slow_period}', 0)

                if not fast_sma or not slow_sma:
                    return 'HOLD'

                if position is None and fast_sma > slow_sma:
                    return 'BUY'
                if position == 'long' and fast_sma < slow_sma:
                    return 'SELL'
                return 'HOLD'

            return strategy

        try:
            result = bp.backtest(
                symbol=symbol,
                strategy=make_strategy(fast, slow),
                period="2y",
                capital=100000,
                commission=0.001,
                indicators=[f'sma_{fast}', f'sma_{slow}'],
            )

            results.append({
                'combination': f'SMA{fast}/SMA{slow}',
                'label': label,
                'net_profit_pct': result.net_profit_pct,
                'total_trades': result.total_trades,
                'win_rate': result.win_rate,
                'max_drawdown': result.max_drawdown,
                'sharpe': result.sharpe_ratio if result.sharpe_ratio == result.sharpe_ratio else 0,
                'vs_buy_hold': result.vs_buy_hold,
            })

        except Exception as e:
            if verbose:
                print(f"   ⚠️ SMA{fast}/SMA{slow}: {e}")

    df = pd.DataFrame(results)

    if not df.empty and verbose:
        print()
        print("📋 KARŞILAŞTIRMA TABLOSU:")
        print("-" * 80)
        print(f"{'Kombinasyon':<15} {'Getiri':>10} {'İşlem':>8} {'Win %':>8} {'MDD':>8} {'Sharpe':>8} {'vs B&H':>10}")
        print("-" * 80)

        df = df.sort_values('vs_buy_hold', ascending=False)

        for _, row in df.iterrows():
            print(f"{row['combination']:<15} %{row['net_profit_pct']:>9.2f} "
                  f"{row['total_trades']:>8} %{row['win_rate']:>7.1f} "
                  f"%{row['max_drawdown']:>7.2f} {row['sharpe']:>8.2f} "
                  f"%{row['vs_buy_hold']:>+9.2f}")

        # En iyi strateji
        best = df.iloc[0]
        print()
        print(f"🏆 EN İYİ: {best['combination']} ({best['label']})")

    return df


if __name__ == "__main__":
    # Tek backtest
    result = run_sma_backtest("THYAO", period="2y")

    # SMA periyot karşılaştırma
    comparison = compare_sma_periods("THYAO")

    if not comparison.empty:
        comparison.to_csv("sma_backtest_comparison.csv", index=False)
        print()
        print("📁 Sonuçlar 'sma_backtest_comparison.csv' dosyasına kaydedildi.")
