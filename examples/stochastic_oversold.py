"""
Stochastic Aşırı Satım Tarayıcı
===============================

Stochastic osilatörü ile aşırı satım bölgesindeki hisseleri bulur.

Kriterler:
- %K < 20 (aşırı satım)
- %K > %D (yukarı kesişim = alım sinyali)

Kullanım:
    python examples/stochastic_oversold.py
"""

import borsapy as bp


def find_stochastic_oversold(
    index_name: str = "XU030",
    oversold_level: float = 20,
    verbose: bool = True,
) -> list:
    """Stochastic aşırı satım bölgesindeki hisseleri bul."""

    if verbose:
        print(f"📊 Stochastic Aşırı Satım Tarayıcı")
        print("=" * 60)
        print(f"   Aşırı satım seviyesi: %K < {oversold_level}")
        print()

    # Endeks bileşenlerini al
    index = bp.Index(index_name)
    symbols = index.component_symbols

    if verbose:
        print(f"🔍 {index_name} endeksindeki {len(symbols)} hisse taranıyor...")
        print()

    oversold_stocks = []

    for symbol in symbols:
        try:
            stock = bp.Ticker(symbol)
            stoch = stock.stochastic()

            if stoch is None:
                continue

            k_value = stoch['k']
            d_value = stoch['d']

            # Aşırı satım kontrolü
            if k_value < oversold_level:
                # RSI de kontrol et
                rsi = stock.rsi()

                oversold_stocks.append({
                    'symbol': symbol,
                    'stoch_k': k_value,
                    'stoch_d': d_value,
                    'k_above_d': k_value > d_value,
                    'rsi': rsi,
                })

        except Exception as e:
            if verbose:
                print(f"   ⚠️ {symbol}: {e}")

    # K > D olanları öne al (alım sinyali)
    oversold_stocks.sort(key=lambda x: (not x['k_above_d'], x['stoch_k']))

    if verbose:
        print(f"🎯 {len(oversold_stocks)} Aşırı Satım Hissesi Bulundu:")
        print()

        if oversold_stocks:
            print(f"{'Sembol':<10} {'%K':>8} {'%D':>8} {'K>D':>6} {'RSI':>8} {'Sinyal':>10}")
            print("-" * 60)

            for s in oversold_stocks:
                k_above = "✅" if s['k_above_d'] else "❌"
                signal = "ALIM" if s['k_above_d'] and s['rsi'] < 30 else "BEKLE"
                rsi_str = f"{s['rsi']:.1f}" if s['rsi'] else "N/A"
                print(f"{s['symbol']:<10} {s['stoch_k']:>8.2f} {s['stoch_d']:>8.2f} {k_above:>6} {rsi_str:>8} {signal:>10}")

            print()
            buy_signals = [s for s in oversold_stocks if s['k_above_d'] and s.get('rsi', 50) < 30]
            print(f"💡 Güçlü alım sinyali (K>D ve RSI<30): {len(buy_signals)} hisse")
        else:
            print("   Aşırı satım bölgesinde hisse bulunamadı.")

    return oversold_stocks


if __name__ == "__main__":
    results = find_stochastic_oversold("XU030")
