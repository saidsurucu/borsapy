"""
Haftalık Piyasa Raporu
======================

Haftanın piyasa özetini oluşturur:
- Endeks performansları
- Sektör performansları
- En çok yükselen/düşen hisseler
- Döviz ve emtia özeti

Kullanım:
    python examples/weekly_market_report.py
"""

from datetime import datetime

import pandas as pd

import borsapy as bp


def generate_weekly_report(verbose: bool = True) -> dict:
    """Haftalık piyasa raporu oluştur."""

    report = {}
    report_date = datetime.now().strftime("%d.%m.%Y")

    if verbose:
        print("=" * 80)
        print(f"📊 HAFTALIK PİYASA RAPORU - {report_date}")
        print("=" * 80)
        print()

    # 1. ENDEKS PERFORMANSLARI
    if verbose:
        print("📈 ENDEKS PERFORMANSLARI")
        print("-" * 60)

    indices = ['XU100', 'XU030', 'XBANK', 'XUSIN', 'XHOLD']
    index_data = []

    for idx_name in indices:
        try:
            idx = bp.Index(idx_name)
            df = idx.history(period="1w")

            if df is not None and len(df) > 1:
                start = df['Close'].iloc[0]
                end = df['Close'].iloc[-1]
                change = ((end - start) / start) * 100

                index_data.append({
                    'index': idx_name,
                    'close': end,
                    'change_pct': change,
                })

                if verbose:
                    emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
                    print(f"   {idx_name:<10} {end:>10,.2f} {emoji} %{change:>+7.2f}")

        except Exception:
            pass

    report['indices'] = index_data

    # 2. EN ÇOK YÜKSELENLER/DÜŞENLER
    if verbose:
        print()
        print("🏆 HAFTANIN EN ÇOK YÜKSELENLERİ (XU100)")
        print("-" * 60)

    try:
        xu100 = bp.Index("XU100")
        symbols = xu100.component_symbols[:30]  # İlk 30 hisse

        stock_changes = []
        for symbol in symbols:
            try:
                stock = bp.Ticker(symbol)
                df = stock.history(period="1w")

                if df is not None and len(df) > 1:
                    start = df['Close'].iloc[0]
                    end = df['Close'].iloc[-1]
                    change = ((end - start) / start) * 100
                    volume = df['Volume'].sum()

                    stock_changes.append({
                        'symbol': symbol,
                        'close': end,
                        'change_pct': change,
                        'volume': volume,
                    })

            except Exception:
                pass

        # Sırala
        df_stocks = pd.DataFrame(stock_changes)
        if not df_stocks.empty:
            df_stocks = df_stocks.sort_values('change_pct', ascending=False)

            # En çok yükselenler
            top_5 = df_stocks.head(5)
            if verbose:
                print(f"   {'Sembol':<10} {'Fiyat':>10} {'Değişim':>10}")
                for _, row in top_5.iterrows():
                    print(f"   {row['symbol']:<10} {row['close']:>10.2f} 📈 %{row['change_pct']:>+7.2f}")

            report['top_gainers'] = top_5.to_dict('records')

            # En çok düşenler
            if verbose:
                print()
                print("📉 HAFTANIN EN ÇOK DÜŞENLERİ")
                print("-" * 60)

            bottom_5 = df_stocks.tail(5).iloc[::-1]
            if verbose:
                print(f"   {'Sembol':<10} {'Fiyat':>10} {'Değişim':>10}")
                for _, row in bottom_5.iterrows():
                    print(f"   {row['symbol']:<10} {row['close']:>10.2f} 📉 %{row['change_pct']:>+7.2f}")

            report['top_losers'] = bottom_5.to_dict('records')

    except Exception as e:
        if verbose:
            print(f"   ⚠️ Hisse verisi alınamadı: {e}")

    # 3. DÖVİZ VE EMTİA
    if verbose:
        print()
        print("💱 DÖVİZ VE EMTİA")
        print("-" * 60)

    fx_data = []
    fx_assets = [
        ('USD', 'Dolar'),
        ('EUR', 'Euro'),
        ('GBP', 'Sterlin'),
        ('gram-altin', 'Gram Altın'),
    ]

    for symbol, name in fx_assets:
        try:
            fx = bp.FX(symbol)
            current = fx.current
            df = fx.history(period="1w")

            if df is not None and len(df) > 1:
                start = df['Close'].iloc[0]
                end = df['Close'].iloc[-1]
                change = ((end - start) / start) * 100

                fx_data.append({
                    'symbol': symbol,
                    'name': name,
                    'close': end,
                    'change_pct': change,
                })

                if verbose:
                    emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
                    print(f"   {name:<15} {end:>12.4f} {emoji} %{change:>+7.2f}")

        except Exception:
            pass

    report['fx'] = fx_data

    # 4. FAİZ ORANLARI
    if verbose:
        print()
        print("🏦 FAİZ ORANLARI")
        print("-" * 60)

    try:
        tcmb = bp.TCMB()
        policy = tcmb.policy_rate

        bonds = bp.bonds()

        if verbose:
            print(f"   TCMB Politika Faizi: %{policy:.2f}")

            if not bonds.empty:
                for _, row in bonds.head(3).iterrows():
                    tenor = row.get('tenor', row.get('maturity', 'N/A'))
                    rate = row.get('yield', row.get('rate', 0))
                    print(f"   {tenor} Tahvil: %{rate:.2f}")

        report['rates'] = {
            'policy_rate': policy,
            'bonds': bonds.head(5).to_dict('records') if not bonds.empty else [],
        }

    except Exception as e:
        if verbose:
            print(f"   ⚠️ Faiz verisi alınamadı: {e}")

    # 5. KRİPTO
    if verbose:
        print()
        print("₿ KRİPTO PARALAR")
        print("-" * 60)

    crypto_data = []
    cryptos = ['BTCTRY', 'ETHTRY']

    for symbol in cryptos:
        try:
            crypto = bp.Crypto(symbol)
            info = crypto.info

            crypto_data.append({
                'symbol': symbol,
                'price': info.get('last', 0),
                'change_24h': info.get('change_percent', 0),
            })

            if verbose:
                price = info.get('last', 0)
                change = info.get('change_percent', 0) or 0
                emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
                print(f"   {symbol:<10} {price:>15,.2f} TL {emoji} %{change:>+7.2f} (24h)")

        except Exception:
            pass

    report['crypto'] = crypto_data

    # ÖZET
    if verbose:
        print()
        print("=" * 80)
        print("📋 HAFTA ÖZETİ:")

        if index_data:
            xu100_change = next((i['change_pct'] for i in index_data if i['index'] == 'XU100'), 0)
            market_emoji = "📈" if xu100_change > 0 else "📉" if xu100_change < 0 else "➡️"
            print(f"   {market_emoji} BIST100 haftalık: %{xu100_change:+.2f}")

        if fx_data:
            usd_change = next((f['change_pct'] for f in fx_data if f['symbol'] == 'USD'), 0)
            usd_emoji = "📈" if usd_change > 0 else "📉" if usd_change < 0 else "➡️"
            print(f"   {usd_emoji} USD/TRY haftalık: %{usd_change:+.2f}")

        print("=" * 80)

    return report


if __name__ == "__main__":
    report = generate_weekly_report()

    # JSON olarak kaydet
    import json
    with open("weekly_market_report.json", "w", encoding="utf-8") as f:
        # DataFrame'leri dict'e çevir
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    print()
    print("📁 Rapor 'weekly_market_report.json' dosyasına kaydedildi.")
