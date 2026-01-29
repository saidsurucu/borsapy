"""
Borç Analizi
============

Şirketlerin borçluluk durumunu analiz eder.
Düşük borçlu, güçlü bilançolu şirketleri bulur.

Kullanım:
    python examples/debt_analysis.py
"""

import pandas as pd

import borsapy as bp


def get_debt_metrics(stock: bp.Ticker) -> dict | None:
    """Finansal tablolardan borç metriklerini çek."""

    try:
        bs = stock.balance_sheet
        inc = stock.income_stmt

        if bs is None or bs.empty:
            return None

        # Bilanço verileri (son dönem)
        def get_value(df, key):
            if key in df.index:
                val = df.loc[key].iloc[0]
                return float(val) if pd.notna(val) else 0
            return 0

        # Özkaynaklar
        total_equity = get_value(bs, 'Özkaynaklar')
        if total_equity == 0:
            total_equity = get_value(bs, '  Ana Ortaklığa Ait Özkaynaklar')

        # Nakit
        total_cash = get_value(bs, '  Nakit ve Nakit Benzerleri')

        # Finansal borçlar (kısa + uzun vadeli)
        # Not: "Finansal Borçlar" hem kısa hem uzun vadeli'de var, toplam alıyoruz
        short_term_debt = 0
        long_term_debt = 0

        # Bilanço'da indeks ile kısa/uzun vadeliyi ayırt et
        found_short = False
        for idx, row_name in enumerate(bs.index):
            if row_name == 'Kısa Vadeli Yükümlülükler':
                found_short = True
            elif row_name == 'Uzun Vadeli Yükümlülükler':
                found_short = False
            elif row_name == '  Finansal Borçlar':
                val = bs.iloc[idx, 0]
                if pd.notna(val):
                    if found_short:
                        short_term_debt = float(val)
                    else:
                        long_term_debt = float(val)

        total_debt = short_term_debt + long_term_debt
        net_debt = total_debt - total_cash

        # Gelir tablosundan EBITDA hesapla
        ebitda = 0
        if inc is not None and not inc.empty:
            faaliyet_kari = get_value(inc, 'FAALİYET KARI (ZARARI)')
            amortisman = get_value(inc, 'Amortisman Giderleri')
            ebitda = faaliyet_kari + amortisman

        # Cari oran için dönen varlıklar / kısa vadeli yükümlülükler
        donen_varliklar = get_value(bs, 'Dönen Varlıklar')
        kisa_vadeli_yuk = get_value(bs, 'Kısa Vadeli Yükümlülükler')

        current_ratio = donen_varliklar / kisa_vadeli_yuk if kisa_vadeli_yuk > 0 else None

        return {
            'total_debt': total_debt,
            'total_equity': total_equity,
            'total_cash': total_cash,
            'net_debt': net_debt,
            'ebitda': ebitda,
            'current_ratio': current_ratio,
        }

    except Exception:
        return None


def analyze_debt(index_name: str = "XU030", verbose: bool = True) -> pd.DataFrame:
    """Şirketlerin borç durumunu analiz et."""

    if verbose:
        print(f"📊 Borç Analizi: {index_name}")
        print("=" * 70)
        print()

    index = bp.Index(index_name)
    symbols = index.component_symbols[:15]  # İlk 15 hisse (hız için)

    if verbose:
        print(f"🔍 {len(symbols)} hisse analiz ediliyor...")
        print()

    debt_data = []

    for symbol in symbols:
        try:
            stock = bp.Ticker(symbol)
            metrics = get_debt_metrics(stock)

            if metrics is None:
                continue

            total_debt = metrics['total_debt']
            total_equity = metrics['total_equity']
            total_cash = metrics['total_cash']
            net_debt = metrics['net_debt']
            ebitda = metrics['ebitda']
            current_ratio = metrics['current_ratio']

            # Oranlar hesapla
            debt_to_equity = (total_debt / total_equity) if total_equity > 0 else None
            net_debt_to_ebitda = (net_debt / ebitda) if ebitda > 0 else None
            cash_to_debt = (total_cash / total_debt) if total_debt > 0 else None

            debt_data.append({
                'symbol': symbol,
                'total_debt_m': total_debt / 1e6,
                'total_equity_m': total_equity / 1e6,
                'net_debt_m': net_debt / 1e6,
                'debt_to_equity': debt_to_equity,
                'net_debt_ebitda': net_debt_to_ebitda,
                'cash_to_debt': cash_to_debt,
                'current_ratio': current_ratio,
            })

        except Exception as e:
            if verbose:
                print(f"   ⚠️ {symbol}: {e}")

    df = pd.DataFrame(debt_data)

    if df.empty:
        if verbose:
            print("❌ Veri bulunamadı.")
        return df

    # Borç/Özsermaye'ye göre sırala
    df = df.sort_values('debt_to_equity', ascending=True, na_position='last')

    if verbose:
        print("📉 DÜŞÜK BORÇLU ŞİRKETLER (Borç/Özsermaye < 1)")
        print("-" * 80)
        print(f"{'Sembol':<10} {'Borç/Öz':>10} {'Net Borç/EBITDA':>15} {'Nakit/Borç':>12} {'Cari Oran':>10}")
        print("-" * 80)

        low_debt = df[df['debt_to_equity'] < 1].head(15)
        for _, row in low_debt.iterrows():
            d_e = f"{row['debt_to_equity']:.2f}" if pd.notna(row['debt_to_equity']) else "N/A"
            nd_ebitda = f"{row['net_debt_ebitda']:.2f}" if pd.notna(row['net_debt_ebitda']) else "N/A"
            cash_debt = f"{row['cash_to_debt']:.2f}" if pd.notna(row['cash_to_debt']) else "N/A"
            curr = f"{row['current_ratio']:.2f}" if pd.notna(row['current_ratio']) else "N/A"

            print(f"{row['symbol']:<10} {d_e:>10} {nd_ebitda:>15} {cash_debt:>12} {curr:>10}")

        print()
        print("📈 YÜKSEK BORÇLU ŞİRKETLER (Borç/Özsermaye > 2)")
        print("-" * 80)
        print(f"{'Sembol':<10} {'Borç/Öz':>10} {'Net Borç/EBITDA':>15} {'Nakit/Borç':>12} {'Cari Oran':>10}")
        print("-" * 80)

        high_debt = df[df['debt_to_equity'] > 2].tail(10)
        for _, row in high_debt.iterrows():
            d_e = f"{row['debt_to_equity']:.2f}" if pd.notna(row['debt_to_equity']) else "N/A"
            nd_ebitda = f"{row['net_debt_ebitda']:.2f}" if pd.notna(row['net_debt_ebitda']) else "N/A"
            cash_debt = f"{row['cash_to_debt']:.2f}" if pd.notna(row['cash_to_debt']) else "N/A"
            curr = f"{row['current_ratio']:.2f}" if pd.notna(row['current_ratio']) else "N/A"

            print(f"{row['symbol']:<10} {d_e:>10} {nd_ebitda:>15} {cash_debt:>12} {curr:>10}")

        print()
        print("=" * 70)
        print("💡 YORUM:")
        print("   • Borç/Özsermaye < 0.5: Çok düşük kaldıraç (güvenli)")
        print("   • Borç/Özsermaye 0.5-1: Sağlıklı kaldıraç")
        print("   • Borç/Özsermaye > 2: Yüksek kaldıraç (riskli)")
        print("   • Net Borç/EBITDA < 3: Borç ödeme kapasitesi iyi")

    return df


if __name__ == "__main__":
    df = analyze_debt("XU030")

    # CSV'ye kaydet
    if not df.empty:
        df.to_csv("debt_analysis_results.csv", index=False)
        print()
        print("📁 Sonuçlar 'debt_analysis_results.csv' dosyasına kaydedildi.")
