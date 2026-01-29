"""
Kripto Momentum Tarayıcı
========================

Kripto paralarda momentum analizi yapar.
En yüksek momentum gösteren coinleri bulur.

Kullanım:
    python examples/crypto_momentum.py
"""

import pandas as pd

import borsapy as bp


def scan_crypto_momentum(verbose: bool = True) -> pd.DataFrame:
    """Kripto momentum taraması yap."""

    if verbose:
        print("📊 KRİPTO MOMENTUM TARAYICI")
        print("=" * 80)
        print()

    # Popüler kripto paralar
    cryptos = [
        'BTCTRY', 'ETHTRY', 'XRPTRY', 'AVXTRY', 'DOGETRY',
        'ADATRY', 'SOLTRY', 'DOTTRY', 'LINKTRY', 'MATICTRY',
        'LTCTRY', 'USDTTRY', 'ATOMTRY', 'XLMTRY', 'ALGOTRY',
    ]

    momentum_data = []

    for symbol in cryptos:
        try:
            crypto = bp.Crypto(symbol)
            info = crypto.info

            # Temel bilgiler
            last_price = info.get('last', 0)
            change_24h = info.get('change_percent', 0) or 0
            volume_24h = info.get('volume', 0) or 0
            high_24h = info.get('high', 0) or 0
            low_24h = info.get('low', 0) or 0

            # Teknik göstergeler
            try:
                rsi = crypto.rsi()
                macd_data = crypto.macd()
                macd = macd_data.get('macd', 0) if macd_data else 0
                signal = macd_data.get('signal', 0) if macd_data else 0
            except Exception:
                rsi = None
                macd = 0
                signal = 0

            # Momentum skoru hesapla
            # RSI 50 üstü pozitif, MACD > Signal pozitif, 24h değişim pozitif
            momentum_score = 0
            if rsi and rsi > 50:
                momentum_score += 30
            if rsi and rsi > 70:
                momentum_score += 10
            if macd > signal:
                momentum_score += 30
            if change_24h > 0:
                momentum_score += 20
            if change_24h > 5:
                momentum_score += 10

            momentum_data.append({
                'symbol': symbol,
                'price': last_price,
                'change_24h': change_24h,
                'volume': volume_24h,
                'high_24h': high_24h,
                'low_24h': low_24h,
                'rsi': rsi,
                'macd': macd,
                'signal': signal,
                'macd_bullish': macd > signal,
                'momentum_score': momentum_score,
            })

        except Exception as e:
            if verbose:
                print(f"   ⚠️ {symbol}: {e}")

    df = pd.DataFrame(momentum_data)

    if df.empty:
        if verbose:
            print("❌ Veri bulunamadı.")
        return df

    # Momentum skoruna göre sırala
    df = df.sort_values('momentum_score', ascending=False)

    if verbose:
        print("🚀 EN YÜKSEK MOMENTUM")
        print("-" * 90)
        print(f"{'Coin':<12} {'Fiyat':>12} {'24h Değişim':>12} {'RSI':>8} {'MACD':>8} {'Skor':>8}")
        print("-" * 90)

        for _, row in df.head(10).iterrows():
            change_emoji = "🟢" if row['change_24h'] > 0 else "🔴"
            rsi_str = f"{row['rsi']:.1f}" if row['rsi'] else "N/A"
            macd_emoji = "📈" if row['macd_bullish'] else "📉"
            print(f"{row['symbol']:<12} {row['price']:>12.2f} "
                  f"{change_emoji} %{row['change_24h']:>+9.2f} {rsi_str:>8} "
                  f"{macd_emoji:>8} {row['momentum_score']:>8}")

        print()
        print("📉 EN DÜŞÜK MOMENTUM")
        print("-" * 90)
        print(f"{'Coin':<12} {'Fiyat':>12} {'24h Değişim':>12} {'RSI':>8} {'MACD':>8} {'Skor':>8}")
        print("-" * 90)

        for _, row in df.tail(5).iterrows():
            change_emoji = "🟢" if row['change_24h'] > 0 else "🔴"
            rsi_str = f"{row['rsi']:.1f}" if row['rsi'] else "N/A"
            macd_emoji = "📈" if row['macd_bullish'] else "📉"
            print(f"{row['symbol']:<12} {row['price']:>12.2f} "
                  f"{change_emoji} %{row['change_24h']:>+9.2f} {rsi_str:>8} "
                  f"{macd_emoji:>8} {row['momentum_score']:>8}")

        print()
        print("=" * 80)
        print("💡 MOMENTUM SKORU HESAPLAMA:")
        print("   • RSI > 50: +30 puan")
        print("   • RSI > 70: +10 puan (ek)")
        print("   • MACD > Signal: +30 puan")
        print("   • 24h Değişim > 0: +20 puan")
        print("   • 24h Değişim > 5%: +10 puan (ek)")

    return df


def analyze_single_crypto(symbol: str, verbose: bool = True) -> dict:
    """Tek kripto detaylı analiz."""

    if verbose:
        print()
        print("=" * 70)
        print(f"📊 DETAYLI ANALİZ: {symbol}")
        print("=" * 70)
        print()

    crypto = bp.Crypto(symbol)
    info = crypto.info

    # Tarihsel veri
    df = crypto.history(period="1mo")

    result = {
        'symbol': symbol,
        'price': info.get('last'),
        'change_24h': info.get('change_percent'),
        'volume': info.get('volume'),
    }

    if df is not None and len(df) > 14:
        # Teknik göstergeler
        result['rsi'] = crypto.rsi()
        result['macd'] = crypto.macd()
        result['bollinger'] = crypto.bollinger_bands()

        # Son 7 gün performans
        if len(df) >= 7:
            week_ago = df['Close'].iloc[-7]
            current = df['Close'].iloc[-1]
            result['change_7d'] = ((current - week_ago) / week_ago) * 100

        if verbose:
            print(f"💰 Fiyat: {result['price']:,.2f} TL")
            print(f"📈 24h Değişim: %{result.get('change_24h', 0):+.2f}")
            print(f"📊 7 Gün Değişim: %{result.get('change_7d', 0):+.2f}")
            print()
            print(f"📉 RSI: {result.get('rsi', 'N/A')}")
            if result.get('macd'):
                print(f"📊 MACD: {result['macd'].get('macd', 0):.4f}")
                print(f"   Signal: {result['macd'].get('signal', 0):.4f}")
            if result.get('bollinger'):
                bb = result['bollinger']
                print(f"📏 Bollinger: {bb.get('lower', 0):.2f} - {bb.get('middle', 0):.2f} - {bb.get('upper', 0):.2f}")

    return result


if __name__ == "__main__":
    # Momentum taraması
    df = scan_crypto_momentum()

    # En yüksek momentum'lu coin'i detaylı analiz et
    if not df.empty:
        top_coin = df.iloc[0]['symbol']
        analyze_single_crypto(top_coin)

        df.to_csv("crypto_momentum.csv", index=False)
        print()
        print("📁 Sonuçlar 'crypto_momentum.csv' dosyasına kaydedildi.")
