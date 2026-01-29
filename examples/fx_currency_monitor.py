"""
Döviz İzleme Paneli
===================

Majör döviz kurlarını ve değerli metalleri izler.
Teknik göstergeler ve trend analizi yapar.

Kullanım:
    python examples/fx_currency_monitor.py
"""

import pandas as pd

import borsapy as bp


def monitor_currencies(verbose: bool = True) -> pd.DataFrame:
    """Döviz kurlarını izle ve analiz et."""

    if verbose:
        print("📊 DÖVİZ İZLEME PANELİ")
        print("=" * 80)
        print()

    # İzlenecek dövizler
    currencies = ['USD', 'EUR', 'GBP', 'CHF', 'JPY']

    # Değerli metaller
    metals = ['gram-altin', 'ons-altin', 'gram-gumus']

    fx_data = []

    # Dövizler
    if verbose:
        print("💱 MAJÖR DÖVİZLER")
        print("-" * 80)
        print(f"{'Para'::<12} {'Alış':>10} {'Satış':>10} {'Değişim':>10} {'RSI':>8} {'Trend':>10}")
        print("-" * 80)

    for currency in currencies:
        try:
            fx = bp.FX(currency)
            current = fx.current

            # Tarihsel veri ve RSI
            try:
                df = fx.history(period="1mo")
                rsi = fx.rsi() if df is not None and len(df) > 14 else None

                # Trend belirleme
                if df is not None and len(df) > 5:
                    sma_5 = df['Close'].tail(5).mean()
                    last = df['Close'].iloc[-1]
                    trend = "📈 Yükseliş" if last > sma_5 else "📉 Düşüş"
                else:
                    trend = "➡️ Nötr"
            except Exception:
                rsi = None
                trend = "N/A"

            fx_data.append({
                'type': 'currency',
                'symbol': currency,
                'name': f"{currency}/TRY",
                'bid': current.get('bid'),
                'ask': current.get('ask'),
                'last': current.get('last'),
                'change_pct': current.get('change_percent'),
                'rsi': rsi,
                'trend': trend,
            })

            if verbose:
                bid = current.get('bid', 0) or 0
                ask = current.get('ask', 0) or 0
                change = current.get('change_percent', 0) or 0
                rsi_str = f"{rsi:.1f}" if rsi else "N/A"
                change_emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
                print(f"{currency + '/TRY':<12} {bid:>10.4f} {ask:>10.4f} "
                      f"{change_emoji} %{change:>+7.2f} {rsi_str:>8} {trend:>10}")

        except Exception as e:
            if verbose:
                print(f"{currency:<12} ⚠️ Hata: {e}")

    # Metaller
    if verbose:
        print()
        print("🥇 DEĞERLİ METALLER")
        print("-" * 80)
        print(f"{'Metal':<12} {'Alış':>10} {'Satış':>10} {'Değişim':>10} {'RSI':>8} {'Trend':>10}")
        print("-" * 80)

    for metal in metals:
        try:
            fx = bp.FX(metal)
            current = fx.current

            # Tarihsel veri ve RSI
            try:
                df = fx.history(period="1mo")
                rsi = fx.rsi() if df is not None and len(df) > 14 else None

                if df is not None and len(df) > 5:
                    sma_5 = df['Close'].tail(5).mean()
                    last = df['Close'].iloc[-1]
                    trend = "📈 Yükseliş" if last > sma_5 else "📉 Düşüş"
                else:
                    trend = "➡️ Nötr"
            except Exception:
                rsi = None
                trend = "N/A"

            fx_data.append({
                'type': 'metal',
                'symbol': metal,
                'name': metal,
                'bid': current.get('bid'),
                'ask': current.get('ask'),
                'last': current.get('last'),
                'change_pct': current.get('change_percent'),
                'rsi': rsi,
                'trend': trend,
            })

            if verbose:
                bid = current.get('bid', 0) or 0
                ask = current.get('ask', 0) or 0
                change = current.get('change_percent', 0) or 0
                rsi_str = f"{rsi:.1f}" if rsi else "N/A"
                change_emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
                print(f"{metal:<12} {bid:>10.2f} {ask:>10.2f} "
                      f"{change_emoji} %{change:>+7.2f} {rsi_str:>8} {trend:>10}")

        except Exception as e:
            if verbose:
                print(f"{metal:<12} ⚠️ Hata: {e}")

    df = pd.DataFrame(fx_data)

    if verbose:
        print()
        print("=" * 80)
        print("💡 RSI > 70: Aşırı alım bölgesi | RSI < 30: Aşırı satım bölgesi")

    return df


def analyze_fx_correlations(verbose: bool = True) -> pd.DataFrame:
    """Döviz korelasyonlarını analiz et."""

    if verbose:
        print()
        print("=" * 80)
        print("📈 DÖVİZ KORELASYONLARI (1 Aylık)")
        print("=" * 80)
        print()

    assets = ['USD', 'EUR', 'GBP', 'gram-altin']

    prices = {}
    for asset in assets:
        try:
            fx = bp.FX(asset)
            df = fx.history(period="1mo")
            if df is not None:
                prices[asset] = df['Close']
        except Exception:
            pass

    if len(prices) < 2:
        if verbose:
            print("❌ Yeterli veri yok.")
        return pd.DataFrame()

    # DataFrame oluştur
    price_df = pd.DataFrame(prices)

    # Korelasyon hesapla
    corr = price_df.corr()

    if verbose:
        print(corr.round(2).to_string())
        print()
        print("💡 Yorum:")
        print("   • Korelasyon > 0.7: Güçlü pozitif ilişki")
        print("   • Korelasyon < -0.7: Güçlü negatif ilişki")
        print("   • -0.3 < Korelasyon < 0.3: Zayıf ilişki")

    return corr


if __name__ == "__main__":
    # Ana panel
    df = monitor_currencies()

    # Korelasyon analizi
    corr = analyze_fx_correlations()

    if not df.empty:
        df.to_csv("fx_monitor.csv", index=False)
        print()
        print("📁 Sonuçlar 'fx_monitor.csv' dosyasına kaydedildi.")
