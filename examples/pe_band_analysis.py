"""
F/K Bandı Analizi
=================

Hissenin tarihsel F/K oranına göre değerleme analizi yapar.
Mevcut F/K, tarihsel ortalamanın altında/üstünde mi?

Kullanım:
    python examples/pe_band_analysis.py
"""

import pandas as pd
import numpy as np

import borsapy as bp


def analyze_pe_band(symbol: str, verbose: bool = True) -> dict:
    """Tek hisse için F/K bandı analizi."""

    if verbose:
        print(f"📊 F/K Bandı Analizi: {symbol}")
        print("=" * 60)
        print()

    stock = bp.Ticker(symbol)
    info = stock.info

    current_pe = info.get('trailingPE')
    current_price = info.get('last')
    eps = info.get('trailingEps')

    # EPS yoksa F/K ve fiyattan hesapla
    if not eps and current_pe and current_price:
        eps = current_price / current_pe

    if not current_pe or not eps:
        if verbose:
            print("❌ F/K veya EPS verisi bulunamadı.")
        return {}

    # Tarihsel fiyat al
    df = stock.history(period="2y")

    if df is None or len(df) < 100:
        if verbose:
            print("❌ Yeterli tarihsel veri yok.")
        return {}

    # Tarihsel F/K hesapla (EPS sabit varsayarak yaklaşık)
    # Not: Gerçek tarihsel F/K için çeyreklik EPS verileri gerekir
    df['Estimated_PE'] = df['Close'] / eps

    # İstatistikler
    pe_mean = df['Estimated_PE'].mean()
    pe_std = df['Estimated_PE'].std()
    pe_min = df['Estimated_PE'].min()
    pe_max = df['Estimated_PE'].max()
    pe_median = df['Estimated_PE'].median()

    # Percentile
    pe_percentile = (df['Estimated_PE'] < current_pe).mean() * 100

    # F/K bandları
    pe_1std_low = pe_mean - pe_std
    pe_1std_high = pe_mean + pe_std
    pe_2std_low = pe_mean - 2 * pe_std
    pe_2std_high = pe_mean + 2 * pe_std

    # Değerleme durumu
    if current_pe < pe_1std_low:
        valuation = "UCUZ"
        valuation_emoji = "🟢"
    elif current_pe > pe_1std_high:
        valuation = "PAHALI"
        valuation_emoji = "🔴"
    else:
        valuation = "NORMAL"
        valuation_emoji = "🟡"

    # Hedef fiyat (ortalama F/K'ya göre)
    fair_price = pe_mean * eps
    upside = ((fair_price - current_price) / current_price) * 100

    result = {
        'symbol': symbol,
        'current_price': current_price,
        'current_pe': current_pe,
        'eps': eps,
        'pe_mean': pe_mean,
        'pe_median': pe_median,
        'pe_std': pe_std,
        'pe_min': pe_min,
        'pe_max': pe_max,
        'pe_percentile': pe_percentile,
        'valuation': valuation,
        'fair_price': fair_price,
        'upside_pct': upside,
    }

    if verbose:
        print(f"💰 Mevcut Fiyat: {current_price:.2f} TL")
        print(f"📈 Mevcut F/K: {current_pe:.2f}")
        print(f"💵 EPS (TTM): {eps:.2f} TL")
        print()

        print("📊 TARİHSEL F/K İSTATİSTİKLERİ (2 Yıl):")
        print("-" * 40)
        print(f"   Ortalama F/K: {pe_mean:.2f}")
        print(f"   Medyan F/K: {pe_median:.2f}")
        print(f"   Std Sapma: {pe_std:.2f}")
        print(f"   Min F/K: {pe_min:.2f}")
        print(f"   Max F/K: {pe_max:.2f}")
        print()

        print("📏 F/K BANTLARI:")
        print("-" * 40)
        print(f"   -2σ (Çok Ucuz): {pe_2std_low:.2f}")
        print(f"   -1σ (Ucuz):     {pe_1std_low:.2f}")
        print(f"   Ortalama:       {pe_mean:.2f}")
        print(f"   +1σ (Pahalı):   {pe_1std_high:.2f}")
        print(f"   +2σ (Çok Pahalı): {pe_2std_high:.2f}")
        print()

        print(f"🎯 DEĞERLEME: {valuation_emoji} {valuation}")
        print(f"   Mevcut F/K ({current_pe:.2f}) tarihsel verilerin %{pe_percentile:.0f}'inde")
        print()

        print(f"💎 HEDEF FİYAT (Ortalama F/K'ya göre):")
        print(f"   Adil Değer: {fair_price:.2f} TL")
        upside_emoji = "📈" if upside > 0 else "📉"
        print(f"   Potansiyel: {upside_emoji} %{upside:+.1f}")

    return result


def scan_undervalued_pe(index_name: str = "XU030", verbose: bool = True) -> pd.DataFrame:
    """F/K bandına göre ucuz hisseleri tara."""

    if verbose:
        print()
        print("=" * 70)
        print(f"🔍 F/K Bandı Taraması: {index_name}")
        print("=" * 70)
        print()

    index = bp.Index(index_name)
    symbols = index.component_symbols[:15]  # İlk 15 hisse (hız için)

    results = []

    for symbol in symbols:
        try:
            result = analyze_pe_band(symbol, verbose=False)
            if result:
                results.append(result)
        except Exception:
            pass

    df = pd.DataFrame(results)

    if df.empty:
        if verbose:
            print("❌ Veri bulunamadı.")
        return df

    # Ucuz olanları filtrele
    df = df.sort_values('pe_percentile', ascending=True)

    if verbose:
        print("🟢 EN UCUZ HİSSELER (Düşük F/K Percentile):")
        print("-" * 70)
        print(f"{'Sembol':<10} {'F/K':>8} {'Ort F/K':>10} {'Percentile':>12} {'Değerleme':>12} {'Potansiyel':>12}")
        print("-" * 70)

        for _, row in df.head(15).iterrows():
            print(f"{row['symbol']:<10} {row['current_pe']:>8.2f} {row['pe_mean']:>10.2f} "
                  f"%{row['pe_percentile']:>11.0f} {row['valuation']:>12} %{row['upside_pct']:>+11.1f}")

    return df


if __name__ == "__main__":
    # Tek hisse analizi
    analyze_pe_band("THYAO")

    # Toplu tarama
    df = scan_undervalued_pe("XU030")

    if not df.empty:
        df.to_csv("pe_band_analysis.csv", index=False)
        print()
        print("📁 Sonuçlar 'pe_band_analysis.csv' dosyasına kaydedildi.")
