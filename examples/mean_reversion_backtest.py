"""
Ortalamaya Dönüş (Mean Reversion) Backtest
==========================================

Bollinger Bands kullanarak ortalamaya dönüş stratejisini test eder.

Strateji:
- ALIM: Fiyat alt bandın altına düştüğünde (oversold)
- SATIM: Fiyat üst bandın üstüne çıktığında (overbought)

Kullanım:
    python examples/mean_reversion_backtest.py
"""

import pandas as pd

import borsapy as bp


def mean_reversion_strategy(candle: dict, position: str | None, indicators: dict) -> str:
    """
    Bollinger Bands Mean Reversion stratejisi.

    Args:
        candle: OHLCV verisi
        position: Mevcut pozisyon
        indicators: Gösterge değerleri (bb_upper, bb_middle, bb_lower)

    Returns:
        'BUY', 'SELL', veya 'HOLD'
    """
    close = candle.get('close', 0)
    bb_upper = indicators.get('bb_upper', 0)
    bb_lower = indicators.get('bb_lower', 0)
    bb_middle = indicators.get('bb_middle', 0)

    if not all([close, bb_upper, bb_lower, bb_middle]):
        return 'HOLD'

    # Pozisyon yoksa - Alım sinyali ara
    if position is None:
        # Fiyat alt bandın altında = Aşırı satım = ALIM
        if close < bb_lower:
            return 'BUY'

    # Pozisyon varsa - Satım sinyali ara
    elif position == 'long':
        # Fiyat üst bandın üstünde = Aşırı alım = SATIM
        if close > bb_upper:
            return 'SELL'
        # Veya orta banda dönünce kar al
        # if close > bb_middle:
        #     return 'SELL'

    return 'HOLD'


def run_mean_reversion_backtest(
    symbol: str,
    period: str = "2y",
    capital: float = 100000,
    verbose: bool = True,
) -> bp.BacktestResult | None:
    """Mean reversion backtesti çalıştır."""

    if verbose:
        print(f"📊 MEAN REVERSION BACKTEST: {symbol}")
        print("=" * 70)
        print()
        print("   Strateji: Bollinger Bands Mean Reversion")
        print("   ALIM: Fiyat < Alt Band (oversold)")
        print("   SATIM: Fiyat > Üst Band (overbought)")
        print(f"   Dönem: {period}")
        print(f"   Sermaye: {capital:,.0f} TL")
        print()

    try:
        result = bp.backtest(
            symbol=symbol,
            strategy=mean_reversion_strategy,
            period=period,
            capital=capital,
            commission=0.001,
            indicators=['bollinger'],
        )

        if verbose:
            print("📈 SONUÇLAR:")
            print("-" * 70)
            pnl_emoji = "📈" if result.net_profit >= 0 else "📉"
            print(f"   Net Kar/Zarar: {result.net_profit:+,.2f} TL ({pnl_emoji} %{result.net_profit_pct:+.2f})")
            print(f"   Son Portföy: {result.final_equity:,.2f} TL")
            print()

            print(f"   Toplam İşlem: {result.total_trades}")
            print(f"   Kazanan: {result.winning_trades} | Kaybeden: {result.losing_trades}")
            print(f"   Win Rate: %{result.win_rate:.1f}")

            avg = result.avg_trade if result.avg_trade == result.avg_trade else 0
            print(f"   Ortalama İşlem: {avg:+,.2f} TL")
            print()

            sharpe = result.sharpe_ratio if result.sharpe_ratio == result.sharpe_ratio else 0
            sortino = result.sortino_ratio if result.sortino_ratio == result.sortino_ratio else 0
            pf = result.profit_factor if result.profit_factor == result.profit_factor else 0

            print(f"   Max Drawdown: %{result.max_drawdown:.2f}")
            print(f"   Sharpe: {sharpe:.2f}")
            print(f"   Sortino: {sortino:.2f}")
            print(f"   Profit Factor: {pf:.2f}")
            print()

            print(f"   Buy & Hold: %{result.buy_hold_return:.2f}")
            bh_emoji = "✅" if result.vs_buy_hold > 0 else "❌"
            print(f"   Strateji vs B&H: %{result.vs_buy_hold:+.2f} {bh_emoji}")

        return result

    except Exception as e:
        if verbose:
            print(f"❌ Hata: {e}")
        return None


def compare_stocks(symbols: list[str], verbose: bool = True) -> pd.DataFrame:
    """Birden fazla hisse için stratejiyi karşılaştır."""

    if verbose:
        print()
        print("=" * 70)
        print("📊 ÇOKLU HİSSE KARŞILAŞTIRMASI")
        print("=" * 70)
        print()

    results = []

    for symbol in symbols:
        if verbose:
            print(f"🔄 {symbol} test ediliyor...", end=" ")

        try:
            result = bp.backtest(
                symbol=symbol,
                strategy=mean_reversion_strategy,
                period="2y",
                capital=100000,
                commission=0.001,
                indicators=['bollinger'],
            )

            results.append({
                'symbol': symbol,
                'net_profit_pct': result.net_profit_pct,
                'total_trades': result.total_trades,
                'win_rate': result.win_rate,
                'max_drawdown': result.max_drawdown,
                'sharpe': result.sharpe_ratio if result.sharpe_ratio == result.sharpe_ratio else 0,
                'buy_hold': result.buy_hold_return,
                'vs_buy_hold': result.vs_buy_hold,
            })

            if verbose:
                emoji = "✅" if result.vs_buy_hold > 0 else "❌"
                print(f"{emoji} Getiri: %{result.net_profit_pct:+.1f}")

        except Exception as e:
            if verbose:
                print(f"❌ Hata: {e}")

    df = pd.DataFrame(results)

    if not df.empty:
        df = df.sort_values('vs_buy_hold', ascending=False)

        if verbose:
            print()
            print("-" * 80)
            print(f"{'Sembol':<10} {'Getiri':>10} {'İşlem':>8} {'Win %':>8} {'MDD':>8} {'B&H':>10} {'vs B&H':>10}")
            print("-" * 80)

            for _, row in df.iterrows():
                print(f"{row['symbol']:<10} %{row['net_profit_pct']:>9.2f} "
                      f"{row['total_trades']:>8} %{row['win_rate']:>7.1f} "
                      f"%{row['max_drawdown']:>7.2f} %{row['buy_hold']:>9.2f} "
                      f"%{row['vs_buy_hold']:>+9.2f}")

            print()
            winners = len(df[df['vs_buy_hold'] > 0])
            print(f"📊 Strateji Buy & Hold'u yenen: {winners}/{len(df)} hisse")

    return df


if __name__ == "__main__":
    # Tek hisse backtest
    result = run_mean_reversion_backtest("THYAO", period="2y")

    # Çoklu hisse karşılaştırma
    symbols = ["THYAO", "GARAN", "ASELS", "BIMAS", "TUPRS", "TCELL"]
    comparison = compare_stocks(symbols)

    if not comparison.empty:
        comparison.to_csv("mean_reversion_backtest.csv", index=False)
        print()
        print("📁 Sonuçlar 'mean_reversion_backtest.csv' dosyasına kaydedildi.")
