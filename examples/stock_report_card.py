"""
Hisse Rapor Kartı
=================

Tek bir hisse için kapsamlı analiz raporu oluşturur:
- Temel veriler
- Teknik göstergeler
- Değerleme metrikleri
- Analist hedefleri

Kullanım:
    python examples/stock_report_card.py
"""

import borsapy as bp


def generate_stock_report(symbol: str, verbose: bool = True) -> dict:
    """Hisse için detaylı rapor kartı oluştur."""

    report = {'symbol': symbol}

    if verbose:
        print("=" * 70)
        print(f"📊 HİSSE RAPOR KARTI: {symbol}")
        print("=" * 70)
        print()

    stock = bp.Ticker(symbol)
    info = stock.info

    # 1. TEMEL BİLGİLER
    if verbose:
        print("📋 TEMEL BİLGİLER")
        print("-" * 50)
        print(f"   Şirket: {info.get('longName', info.get('shortName', symbol))}")
        print(f"   Sektör: {info.get('sector', 'N/A')}")
        print(f"   Alt Sektör: {info.get('industry', 'N/A')}")
        print()

    report['company'] = {
        'name': info.get('longName', info.get('shortName', symbol)),
        'sector': info.get('sector'),
        'industry': info.get('industry'),
    }

    # 2. FİYAT VERİLERİ
    last_price = info.get('last', 0)
    prev_close = info.get('previousClose', 0)
    change = info.get('change', 0)
    change_pct = info.get('change_percent', 0)
    high_52w = info.get('fiftyTwoWeekHigh', 0)
    low_52w = info.get('fiftyTwoWeekLow', 0)

    if verbose:
        print("💰 FİYAT VERİLERİ")
        print("-" * 50)
        change_emoji = "🟢" if change_pct and change_pct > 0 else "🔴" if change_pct and change_pct < 0 else "⚪"
        print(f"   Son Fiyat: {last_price:,.2f} TL {change_emoji} %{change_pct or 0:+.2f}")
        print(f"   Önceki Kapanış: {prev_close:,.2f} TL")
        print(f"   52 Hafta Yüksek: {high_52w:,.2f} TL")
        print(f"   52 Hafta Düşük: {low_52w:,.2f} TL")

        # 52 hafta range'inde pozisyon
        if high_52w and low_52w and last_price:
            range_pct = ((last_price - low_52w) / (high_52w - low_52w)) * 100
            print(f"   52H Range Pozisyonu: %{range_pct:.0f}")
        print()

    report['price'] = {
        'last': last_price,
        'change': change,
        'change_pct': change_pct,
        'high_52w': high_52w,
        'low_52w': low_52w,
    }

    # 3. DEĞERLEME METRİKLERİ
    pe = info.get('trailingPE')
    pb = info.get('priceToBook')
    ps = info.get('priceToSales')
    ev_ebitda = info.get('enterpriseToEbitda')
    div_yield = info.get('dividendYield')
    market_cap = info.get('marketCap', 0)

    if verbose:
        print("📊 DEĞERLEME METRİKLERİ")
        print("-" * 50)
        print(f"   Piyasa Değeri: {market_cap / 1e9:,.2f} Milyar TL")
        print(f"   F/K Oranı: {pe:.2f}" if pe else "   F/K Oranı: N/A")
        print(f"   PD/DD: {pb:.2f}" if pb else "   PD/DD: N/A")
        print(f"   F/S: {ps:.2f}" if ps else "   F/S: N/A")
        print(f"   EV/EBITDA: {ev_ebitda:.2f}" if ev_ebitda else "   EV/EBITDA: N/A")
        div_str = f"%{div_yield * 100:.2f}" if div_yield else "N/A"
        print(f"   Temettü Verimi: {div_str}")
        print()

    report['valuation'] = {
        'market_cap': market_cap,
        'pe': pe,
        'pb': pb,
        'ps': ps,
        'ev_ebitda': ev_ebitda,
        'dividend_yield': div_yield,
    }

    # 4. TEKNİK GÖSTERGELER
    if verbose:
        print("📈 TEKNİK GÖSTERGELER")
        print("-" * 50)

    try:
        rsi = stock.rsi()
        macd = stock.macd()
        bb = stock.bollinger_bands()
        sma_50 = stock.sma(sma_period=50)
        sma_200 = stock.sma(sma_period=200)

        if verbose:
            # RSI
            rsi_status = "Aşırı Alım" if rsi and rsi > 70 else "Aşırı Satım" if rsi and rsi < 30 else "Nötr"
            print(f"   RSI (14): {rsi:.2f} ({rsi_status})" if rsi else "   RSI: N/A")

            # MACD
            if macd:
                macd_signal = "Bullish" if macd['macd'] > macd['signal'] else "Bearish"
                print(f"   MACD: {macd['macd']:.4f} ({macd_signal})")

            # Bollinger
            if bb:
                if last_price > bb['upper']:
                    bb_pos = "Üst Band Üstünde"
                elif last_price < bb['lower']:
                    bb_pos = "Alt Band Altında"
                else:
                    bb_pos = "Band İçinde"
                print(f"   Bollinger: {bb_pos}")

            # SMA Trend
            if sma_50 and sma_200:
                trend = "📈 Yükseliş" if sma_50 > sma_200 else "📉 Düşüş"
                print(f"   SMA50/200: {trend}")

            print()

        report['technicals'] = {
            'rsi': rsi,
            'macd': macd,
            'bollinger': bb,
            'sma_50': sma_50,
            'sma_200': sma_200,
        }

    except Exception as e:
        if verbose:
            print(f"   ⚠️ Teknik gösterge hatası: {e}")
            print()

    # 5. ANALİST HEDEFLERİ
    if verbose:
        print("🎯 ANALİST HEDEFLERİ")
        print("-" * 50)

    try:
        targets = stock.analyst_price_targets
        if targets and not targets.empty:
            avg_target = targets['target'].mean()
            upside = ((avg_target - last_price) / last_price) * 100

            if verbose:
                print(f"   Ortalama Hedef: {avg_target:.2f} TL")
                upside_emoji = "📈" if upside > 0 else "📉"
                print(f"   Potansiyel: {upside_emoji} %{upside:+.1f}")
                print(f"   Analist Sayısı: {len(targets)}")

            report['analyst_targets'] = {
                'average': avg_target,
                'upside_pct': upside,
                'count': len(targets),
            }
        else:
            if verbose:
                print("   Analist hedefi bulunamadı.")

    except Exception:
        if verbose:
            print("   Analist hedefi bulunamadı.")

    # 6. ÖZET DEĞERLENDİRME
    if verbose:
        print()
        print("=" * 70)
        print("📋 ÖZET DEĞERLENDİRME")
        print("-" * 50)

        # Basit skor hesapla
        score = 0
        reasons = []

        # Değerleme
        if pe and pe < 15:
            score += 1
            reasons.append("✅ Düşük F/K")
        elif pe and pe > 30:
            score -= 1
            reasons.append("❌ Yüksek F/K")

        # Teknik
        if rsi and rsi < 30:
            score += 1
            reasons.append("✅ RSI aşırı satım")
        elif rsi and rsi > 70:
            score -= 1
            reasons.append("⚠️ RSI aşırı alım")

        # Temettü
        if div_yield and div_yield > 0.03:
            score += 1
            reasons.append("✅ Yüksek temettü")

        # Sonuç
        if score >= 2:
            verdict = "🟢 POZİTİF"
        elif score <= -1:
            verdict = "🔴 NEGATİF"
        else:
            verdict = "🟡 NÖTR"

        print(f"   Genel Görünüm: {verdict}")
        for reason in reasons:
            print(f"   {reason}")

        print("=" * 70)

        report['summary'] = {
            'score': score,
            'verdict': verdict,
            'reasons': reasons,
        }

    return report


if __name__ == "__main__":
    # Örnek hisse raporu
    report = generate_stock_report("THYAO")

    # JSON olarak kaydet
    import json
    with open(f"stock_report_{report['symbol']}.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    print()
    print(f"📁 Rapor 'stock_report_{report['symbol']}.json' dosyasına kaydedildi.")
