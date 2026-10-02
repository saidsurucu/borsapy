"""
Değer Hissesi Bulucu
====================

Basit değer yatırımı kriterleriyle incelemeye aday hisseleri listeler.
Puanlar şirketin gerçek değerini hesaplamaz; eksik veriler puan kazandırmaz.

Kriterler:
- Düşük F/K oranı (< 15)
- Düşük PD/DD oranı (< 1.5)
- Yüksek temettü verimi (> %3)
- Düşük borç/özsermaye oranı
- Pozitif net kar marjı

Kullanım:
    python examples/value_stock_finder.py
"""

from math import isfinite

import pandas as pd

import borsapy as bp

_SCORE_KEYS = ('pe', 'pb', 'dividend_yield', 'debt_to_equity')


def _finite_number(value) -> float | None:
    """Eksik veya sonlu olmayan değerleri None olarak koru."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) else None


def _first_number(info, *keys) -> float | None:
    """İlk geçerli değeri al; sıfır değeri yedek alanla değiştirme."""
    for key in keys:
        value = _finite_number(info.get(key))
        if value is not None:
            return value
    return None


def analyze_value_metrics(symbol: str) -> dict | None:
    """
    Hisse için değer metriklerini hesapla.

    Returns:
        Değer metrikleri dict veya None
    """
    try:
        ticker = bp.Ticker(symbol)
        info = ticker.info

        # Temel metrikler
        pe = _first_number(info, 'pe', 'trailingPE')
        pb = _first_number(info, 'pb', 'priceToBook')
        dividend_yield = _first_number(info, 'dividend_yield', 'dividendYield')
        market_cap = _first_number(info, 'market_cap', 'marketCap')

        # Finansal tablolardan ek metrikler
        try:
            balance_sheet = ticker.balance_sheet
            income_stmt = ticker.income_stmt

            # Borç/Özsermaye oranı
            total_debt = None
            total_equity = None
            debt_to_equity = None

            if not balance_sheet.empty:
                # Borç kalemlerini bul
                for idx in balance_sheet.index:
                    idx_lower = str(idx).lower()
                    if 'finansal borç' in idx_lower or 'financial debt' in idx_lower:
                        total_debt = _finite_number(balance_sheet.loc[idx].iloc[0])
                    if 'özkaynaklar' in idx_lower or 'equity' in idx_lower:
                        if 'ana ortaklık' in idx_lower or 'parent' in idx_lower:
                            total_equity = _finite_number(balance_sheet.loc[idx].iloc[0])

                if total_debt is not None and total_equity is not None and total_equity > 0:
                    debt_to_equity = total_debt / total_equity

            # Net kar marjı
            net_margin = None
            if not income_stmt.empty:
                revenue = None
                net_income = None

                for idx in income_stmt.index:
                    idx_lower = str(idx).lower()
                    if 'satış gelirleri' in idx_lower:
                        revenue = _finite_number(income_stmt.loc[idx].iloc[0])
                    if 'ana ortaklık payları' in idx_lower:
                        net_income = _finite_number(income_stmt.loc[idx].iloc[0])

                if revenue is not None and net_income is not None and revenue > 0:
                    net_margin = (net_income / revenue) * 100

        except Exception:
            debt_to_equity = None
            net_margin = None

        # Sonuç
        return {
            'symbol': symbol,
            'pe': round(pe, 2) if pe is not None else None,
            'pb': round(pb, 2) if pb is not None else None,
            'dividend_yield': round(dividend_yield, 2) if dividend_yield is not None else None,
            'debt_to_equity': round(debt_to_equity, 2) if debt_to_equity is not None else None,
            'net_margin': round(net_margin, 2) if net_margin is not None else None,
            'market_cap_m': round(market_cap / 1_000_000, 0) if market_cap is not None else None,
        }

    except Exception:
        return None


def calculate_value_score(metrics: dict) -> float:
    """
    Değer skoru hesapla (0-100).

    Her ölçüt en fazla 25 puan kazandırır. Eksik/geçersiz ölçütler sıfır puan
    kazandırır; kalan ölçütler yeniden ağırlıklandırılmaz. Bu nedenle veri
    kaybı bir şirketin puanını yükseltemez.
    """
    score = 0
    metrics = {key: _finite_number(metrics.get(key)) for key in _SCORE_KEYS}

    # F/K skoru (düşük = iyi)
    if metrics['pe'] and metrics['pe'] > 0:
        if metrics['pe'] < 5:
            score += 25
        elif metrics['pe'] < 10:
            score += 20
        elif metrics['pe'] < 15:
            score += 15
        elif metrics['pe'] < 20:
            score += 10

    # PD/DD skoru (düşük = iyi)
    if metrics['pb'] and metrics['pb'] > 0:
        if metrics['pb'] < 0.5:
            score += 25
        elif metrics['pb'] < 1.0:
            score += 20
        elif metrics['pb'] < 1.5:
            score += 15
        elif metrics['pb'] < 2.0:
            score += 10

    # Temettü skoru (yüksek = iyi)
    if metrics['dividend_yield']:
        if metrics['dividend_yield'] > 8:
            score += 25
        elif metrics['dividend_yield'] > 5:
            score += 20
        elif metrics['dividend_yield'] > 3:
            score += 15
        elif metrics['dividend_yield'] > 1:
            score += 10

    # Borç/Özsermaye skoru (düşük = iyi)
    if metrics['debt_to_equity'] is not None and metrics['debt_to_equity'] >= 0:
        if metrics['debt_to_equity'] < 0.3:
            score += 25
        elif metrics['debt_to_equity'] < 0.5:
            score += 20
        elif metrics['debt_to_equity'] < 1.0:
            score += 15
        elif metrics['debt_to_equity'] < 2.0:
            score += 10

    return float(score)


def scan_value_stocks(
    index: str = "XU100",
    pe_max: float = 15,
    pb_max: float = 1.5,
    dividend_min: float = 3.0,
    verbose: bool = True,
) -> pd.DataFrame:
    """Değer hissesi taraması."""

    if verbose:
        print("📊 Değer Hissesi Aday Taraması")
        print(f"   - Endeks: {index}")
        print(f"   - Max F/K: {pe_max}")
        print(f"   - Max PD/DD: {pb_max}")
        print(f"   - Min Temettü: %{dividend_min}")
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

        metrics = analyze_value_metrics(symbol)

        if metrics is None:
            continue

        # Filtreleme
        passes_pe = metrics['pe'] is not None and 0 < metrics['pe'] <= pe_max
        passes_pb = metrics['pb'] is not None and 0 < metrics['pb'] <= pb_max
        passes_div = metrics['dividend_yield'] is not None and metrics['dividend_yield'] >= dividend_min

        # En az 2 kriteri geçenler
        passed_count = sum([passes_pe, passes_pb, passes_div])

        if passed_count >= 2:
            metrics['value_score'] = calculate_value_score(metrics)
            metrics['metrics_available'] = sum(
                _finite_number(metrics.get(key)) is not None for key in _SCORE_KEYS
            )
            metrics['criteria_passed'] = passed_count
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
    df = df.sort_values('value_score', ascending=False).reset_index(drop=True)

    if verbose:
        print(f"🎯 {len(df)} Değer Hissesi Adayı Bulundu:")
        print()
        print(f"{'Sembol':<8} {'F/K':>8} {'PD/DD':>8} {'Temettü':>10} {'Borç/Öz':>10} {'Skor':>8} {'Veri':>6}")
        print("-" * 60)

        for _, row in df.head(20).iterrows():
            pe_str = f"{row['pe']:.1f}" if pd.notna(row['pe']) else "N/A"
            pb_str = f"{row['pb']:.2f}" if pd.notna(row['pb']) else "N/A"
            div_str = f"%{row['dividend_yield']:.1f}" if pd.notna(row['dividend_yield']) else "N/A"
            de_str = f"{row['debt_to_equity']:.2f}" if pd.notna(row['debt_to_equity']) else "N/A"
            coverage_str = f"{int(row['metrics_available'])}/4"

            print(f"{row['symbol']:<8} {pe_str:>8} {pb_str:>8} {div_str:>10} {de_str:>10} {row['value_score']:>7.1f} {coverage_str:>6}")

        print()
        print("💡 Değer Skoru: F/K, PD/DD, Temettü ve Borç/Özsermaye oranlarının")
        print("   ön eleme puanı (0-100); eksik veriler puan kazandırmaz.")
        print("   Veri sütunu mevcut ölçüt sayısını gösterir; şirketin gerçek değeri değildir.")

    return df


def main():
    print("=" * 80)
    print("borsapy - Değer Hissesi Bulucu")
    print("=" * 80)
    print()

    results = scan_value_stocks(
        index="XU100",
        pe_max=15,
        pb_max=1.5,
        dividend_min=3.0,
        verbose=True,
    )

    if not results.empty:
        results.to_csv("value_stocks_results.csv", index=False)
        print()
        print("📁 Sonuçlar 'value_stocks_results.csv' dosyasına kaydedildi.")

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
