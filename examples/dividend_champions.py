"""
Temettü Şampiyonları
====================

Düzenli ve artan temettü ödeyen şirketleri bulur:
- Son 3+ yıl kesintisiz temettü ödemesi
- Temettü artış trendi
- Yüksek temettü verimi

Kullanım:
    python examples/dividend_champions.py
"""

import pandas as pd

import borsapy as bp


def analyze_dividend_history(symbol: str) -> dict | None:
    """
    Temettü geçmişi analizi yap.

    Returns:
        Temettü metrikleri veya None
    """
    try:
        ticker = bp.Ticker(symbol)

        # Temettü verisi
        dividends = ticker.dividends

        if dividends.empty:
            return None

        # Yıllara göre grupla
        dividends_by_year = dividends.groupby(dividends.index.year).sum()

        if len(dividends_by_year) < 2:
            return None

        years = sorted(dividends_by_year.index.tolist(), reverse=True)
        dividend_amounts = [dividends_by_year[y] for y in years]

        # Kesintisiz ödeme sayısı
        consecutive_years = 0
        for i, amount in enumerate(dividend_amounts):
            if amount > 0:
                consecutive_years += 1
            else:
                break

        # Artış yılları
        increasing_years = 0
        for i in range(len(dividend_amounts) - 1):
            if dividend_amounts[i] > dividend_amounts[i + 1]:
                increasing_years += 1
            else:
                break

        # Temettü büyüme oranı (CAGR)
        if len(dividend_amounts) >= 3 and dividend_amounts[-1] > 0:
            years_count = len(dividend_amounts) - 1
            cagr = ((dividend_amounts[0] / dividend_amounts[-1]) ** (1 / years_count) - 1) * 100
        else:
            cagr = None

        # Güncel temettü verimi
        info = ticker.info
        current_yield = info.get('dividend_yield') or info.get('dividendYield', 0)
        last_price = info.get('last') or info.get('regularMarketPrice', 0)

        # Son temettü
        last_dividend = dividend_amounts[0] if dividend_amounts else 0
        last_year = years[0] if years else None

        return {
            'symbol': symbol,
            'consecutive_years': consecutive_years,
            'increasing_years': increasing_years,
            'total_years': len(years),
            'current_yield': round(current_yield, 2) if current_yield else 0,
            'last_dividend': round(last_dividend, 4),
            'last_year': last_year,
            'dividend_cagr': round(cagr, 1) if cagr else None,
            'last_price': round(last_price, 2) if last_price else None,
            'history': list(zip(years, [round(d, 4) for d in dividend_amounts])),
        }

    except Exception:
        return None


def calculate_dividend_score(metrics: dict) -> float:
    """Temettü skoru hesapla (0-100)."""
    score = 0

    # Kesintisiz yıl (max 30 puan)
    score += min(metrics['consecutive_years'] * 6, 30)

    # Artış yılları (max 25 puan)
    score += min(metrics['increasing_years'] * 5, 25)

    # Temettü verimi (max 25 puan)
    if metrics['current_yield']:
        if metrics['current_yield'] > 8:
            score += 25
        elif metrics['current_yield'] > 5:
            score += 20
        elif metrics['current_yield'] > 3:
            score += 15
        elif metrics['current_yield'] > 1:
            score += 10

    # CAGR (max 20 puan)
    if metrics['dividend_cagr']:
        if metrics['dividend_cagr'] > 20:
            score += 20
        elif metrics['dividend_cagr'] > 10:
            score += 15
        elif metrics['dividend_cagr'] > 5:
            score += 10
        elif metrics['dividend_cagr'] > 0:
            score += 5

    return round(score, 1)


def scan_dividend_champions(
    index: str = "XU100",
    min_consecutive_years: int = 3,
    min_yield: float = 2.0,
    verbose: bool = True,
) -> pd.DataFrame:
    """Temettü şampiyonları taraması."""

    if verbose:
        print(f"📊 Temettü Şampiyonları Tarama")
        print(f"   - Endeks: {index}")
        print(f"   - Min kesintisiz yıl: {min_consecutive_years}")
        print(f"   - Min temettü verimi: %{min_yield}")
        print()

    idx = bp.Index(index)
    symbols = idx.component_symbols

    if verbose:
        print(f"🔍 {len(symbols)} hisse analiz ediliyor...")
        print("-" * 80)

    results = []

    for i, symbol in enumerate(symbols):
        if verbose:
            print(f"\r   İşleniyor: {i+1}/{len(symbols)} - {symbol:8}", end="", flush=True)

        metrics = analyze_dividend_history(symbol)

        if metrics is None:
            continue

        # Filtreler
        if metrics['consecutive_years'] >= min_consecutive_years:
            if metrics['current_yield'] >= min_yield or metrics['increasing_years'] >= 2:
                metrics['dividend_score'] = calculate_dividend_score(metrics)
                results.append(metrics)

    if verbose:
        print()
        print("-" * 80)
        print()

    if not results:
        if verbose:
            print("❌ Kriterlere uyan hisse bulunamadı.")
        return pd.DataFrame()

    # Skora göre sırala
    df = pd.DataFrame(results)
    df = df.sort_values('dividend_score', ascending=False).reset_index(drop=True)

    if verbose:
        print(f"🏆 {len(df)} Temettü Şampiyonu Bulundu:")
        print()
        print(f"{'Sembol':<8} {'Kesintisiz':>10} {'Artış':>8} {'Verim':>10} {'CAGR':>10} {'Skor':>8}")
        print("-" * 65)

        for _, row in df.head(20).iterrows():
            cagr_str = f"%{row['dividend_cagr']:.1f}" if row['dividend_cagr'] else "N/A"
            print(f"{row['symbol']:<8} "
                  f"{row['consecutive_years']:>8} yıl "
                  f"{row['increasing_years']:>6} yıl "
                  f"%{row['current_yield']:>8.1f} "
                  f"{cagr_str:>10} "
                  f"{row['dividend_score']:>7.1f}")

        # En iyi 5 için detay
        print()
        print("📜 Temettü Geçmişi (İlk 5):")
        for _, row in df.head(5).iterrows():
            history_str = " → ".join([f"{y}:{d:.2f}" for y, d in row['history'][:5]])
            print(f"   {row['symbol']}: {history_str}")

    # history sütununu kaldır (export için)
    df = df.drop(columns=['history'], errors='ignore')

    return df


def main():
    print("=" * 80)
    print("borsapy - Temettü Şampiyonları")
    print("=" * 80)
    print()

    results = scan_dividend_champions(
        index="XU100",
        min_consecutive_years=3,
        min_yield=2.0,
        verbose=True,
    )

    if not results.empty:
        results.to_csv("dividend_champions_results.csv", index=False)
        print()
        print("📁 Sonuçlar 'dividend_champions_results.csv' dosyasına kaydedildi.")

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
