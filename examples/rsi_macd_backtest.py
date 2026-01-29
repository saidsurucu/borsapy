"""
RSI + MACD Strateji Backtesti
=============================

İki göstergenin kombinasyonuyla al-sat stratejisi test eder.

Strateji Kuralları:
- ALIM: RSI < 30 (oversold) VE MACD > Signal (bullish cross)
- SATIM: RSI > 70 (overbought) VEYA MACD < Signal (bearish cross)

borsapy'nin backtest modülünü kullanır.

Kullanım:
    python examples/rsi_macd_backtest.py
"""

import pandas as pd

import borsapy as bp


def rsi_macd_strategy(candle: dict, position: str | None, indicators: dict) -> str:
    """
    RSI + MACD kombinasyon stratejisi.

    Args:
        candle: OHLCV verisi
        position: Mevcut pozisyon ('long', 'short', None)
        indicators: Gösterge değerleri

    Returns:
        'BUY', 'SELL', veya 'HOLD'
    """
    rsi = indicators.get('rsi', 50)
    macd = indicators.get('macd', 0)
    signal = indicators.get('signal', 0)

    # ALIM koşulları
    rsi_oversold = rsi < 30
    macd_bullish = macd > signal

    # SATIM koşulları
    rsi_overbought = rsi > 70
    macd_bearish = macd < signal

    # Pozisyon yoksa alım sinyali ara
    if position is None:
        if rsi_oversold and macd_bullish:
            return 'BUY'

    # Pozisyon varsa satım sinyali ara
    elif position == 'long':
        if rsi_overbought or macd_bearish:
            return 'SELL'

    return 'HOLD'


def run_backtest(
    symbol: str,
    period: str = "1y",
    capital: float = 100000,
    commission: float = 0.001,
    verbose: bool = True,
) -> bp.BacktestResult | None:
    """Backtesti çalıştır."""

    if verbose:
        print(f"📊 RSI + MACD Strateji Backtesti")
        print("=" * 70)
        print()
        print(f"   Sembol: {symbol}")
        print(f"   Dönem: {period}")
        print(f"   Başlangıç Sermayesi: {capital:,.0f} TL")
        print(f"   Komisyon: %{commission * 100:.2f}")
        print()
        print("   Strateji Kuralları:")
        print("   - ALIM: RSI < 30 VE MACD > Signal")
        print("   - SATIM: RSI > 70 VEYA MACD < Signal")
        print()

    try:
        result = bp.backtest(
            symbol=symbol,
            strategy=rsi_macd_strategy,
            period=period,
            capital=capital,
            commission=commission,
            indicators=['rsi', 'macd'],
        )

        if verbose:
            print("📈 BACKTEST SONUÇLARI")
            print("-" * 70)
            print()

            # Performans
            print("💰 PERFORMANS:")
            pnl_emoji = "📈" if result.net_profit >= 0 else "📉"
            print(f"   Net Kar/Zarar: {result.net_profit:+,.2f} TL ({pnl_emoji} %{result.net_profit_pct:+.2f})")
            print(f"   Son Portföy Değeri: {result.final_equity:,.2f} TL")
            print()

            # İşlem istatistikleri
            print("📊 İŞLEM İSTATİSTİKLERİ:")
            print(f"   Toplam İşlem: {result.total_trades}")
            print(f"   Kazanan İşlem: {result.winning_trades} (%{result.win_rate:.1f})")
            print(f"   Kaybeden İşlem: {result.losing_trades}")
            avg_trade = result.avg_trade if result.avg_trade == result.avg_trade else 0
            print(f"   Ortalama İşlem K/Z: {avg_trade:+,.2f} TL")
            print()

            # Risk metrikleri
            import math
            print("📉 RİSK METRİKLERİ:")
            print(f"   Max Drawdown: %{result.max_drawdown:.2f}")
            sharpe = result.sharpe_ratio if result.sharpe_ratio == result.sharpe_ratio else 0
            sortino = result.sortino_ratio if result.sortino_ratio == result.sortino_ratio else 0
            pf = result.profit_factor if result.profit_factor == result.profit_factor else 0
            print(f"   Sharpe Oranı: {sharpe:.2f}")
            print(f"   Sortino Oranı: {sortino:.2f}")
            print(f"   Profit Factor: {pf:.2f}")
            print()

            # Buy & Hold karşılaştırma
            print("⚖️  BUY & HOLD KARŞILAŞTIRMA:")
            print(f"   Buy & Hold Getiri: %{result.buy_hold_return:.2f}")
            print(f"   Strateji vs B&H: %{result.vs_buy_hold:+.2f}")

            bh_emoji = "✅" if result.vs_buy_hold > 0 else "❌"
            if result.vs_buy_hold > 0:
                print(f"   {bh_emoji} Strateji Buy & Hold'u yendi!")
            else:
                print(f"   {bh_emoji} Buy & Hold daha iyi performans gösterdi.")

            print()

            # İşlem listesi
            if result.trades_df is not None and not result.trades_df.empty:
                print("📋 SON 10 İŞLEM:")
                print("-" * 70)
                trades = result.trades_df.tail(10)
                print(trades.to_string(index=False))

        return result

    except Exception as e:
        if verbose:
            print(f"❌ Backtest hatası: {e}")
        return None


def compare_strategies(symbols: list[str], period: str = "1y", verbose: bool = True) -> pd.DataFrame:
    """Birden fazla hisse için stratejiyi karşılaştır."""

    if verbose:
        print("📊 ÇOKLU HİSSE BACKTEST KARŞILAŞTIRMASI")
        print("=" * 70)
        print()

    results = []

    for symbol in symbols:
        if verbose:
            print(f"🔄 {symbol} test ediliyor...", end=" ")

        try:
            result = bp.backtest(
                symbol=symbol,
                strategy=rsi_macd_strategy,
                period=period,
                capital=100000,
                commission=0.001,
                indicators=['rsi', 'macd'],
            )

            results.append({
                'symbol': symbol,
                'net_profit_pct': result.net_profit_pct,
                'total_trades': result.total_trades,
                'win_rate': result.win_rate,
                'max_drawdown': result.max_drawdown,
                'sharpe_ratio': result.sharpe_ratio,
                'buy_hold_return': result.buy_hold_return,
                'vs_buy_hold': result.vs_buy_hold,
            })

            if verbose:
                emoji = "✅" if result.vs_buy_hold > 0 else "❌"
                print(f"{emoji} Getiri: %{result.net_profit_pct:+.1f}, B&H: %{result.buy_hold_return:+.1f}")

        except Exception as e:
            if verbose:
                print(f"❌ Hata: {e}")

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df = df.sort_values('net_profit_pct', ascending=False).reset_index(drop=True)

    if verbose:
        print()
        print("-" * 70)
        print()
        print("📈 ÖZET (Getiriye göre sıralı):")
        print(df.to_string(index=False))

        # İstatistikler
        winners = len(df[df['vs_buy_hold'] > 0])
        print()
        print(f"📊 Strateji Buy & Hold'u yenen hisse: {winners}/{len(df)}")
        print(f"   Ortalama Getiri: %{df['net_profit_pct'].mean():.2f}")
        print(f"   Ortalama Win Rate: %{df['win_rate'].mean():.1f}")

    return df


def main():
    print("=" * 70)
    print("borsapy - RSI + MACD Strateji Backtesti")
    print("=" * 70)
    print()

    # Tek hisse detaylı backtest
    result = run_backtest(
        symbol="THYAO",
        period="1y",
        capital=100000,
        verbose=True,
    )

    print()
    print("=" * 70)
    print()

    # Çoklu hisse karşılaştırma
    symbols = ["THYAO", "ASELS", "TUPRS", "BIMAS", "EREGL", "TCELL"]

    comparison = compare_strategies(
        symbols=symbols,
        period="1y",
        verbose=True,
    )

    if not comparison.empty:
        comparison.to_csv("rsi_macd_backtest_results.csv", index=False)
        print()
        print("📁 Sonuçlar 'rsi_macd_backtest_results.csv' dosyasına kaydedildi.")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
