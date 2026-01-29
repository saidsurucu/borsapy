"""
VIOP Baz Takipçisi
==================

Spot fiyat ile vadeli fiyat arasındaki farkı (baz) takip eder.
Pozitif baz = Contango (vadeli > spot)
Negatif baz = Backwardation (spot > vadeli)

Kullanım:
    python examples/viop_basis_tracker.py
"""

import borsapy as bp


def track_viop_basis(verbose: bool = True) -> dict:
    """VIOP baz takibi yap."""

    if verbose:
        print("📊 VIOP BAZ TAKİPÇİSİ")
        print("=" * 80)
        print()

    # BIST30 spot ve vadeli
    results = {}

    # XU030 spot fiyat
    try:
        xu030 = bp.Index("XU030")
        xu030_spot = xu030.info.get('last', 0)

        if verbose:
            print(f"📈 BIST30 Spot: {xu030_spot:,.2f}")
            print()

        # VIOP kontratları
        contracts = bp.viop_contracts("XU030D", full_info=True)

        if contracts:
            if verbose:
                print("📋 BIST30 VADELİ KONTRATLARI:")
                print("-" * 80)
                print(f"{'Kontrat':<15} {'Vade':>12} {'Son Fiyat':>12} {'Baz':>10} {'Baz %':>10} {'Durum':>12}")
                print("-" * 80)

            for contract in contracts[:4]:  # İlk 4 kontrat
                symbol = contract.get('symbol')
                if not symbol:
                    continue

                try:
                    # TradingView'dan vadeli fiyat
                    stream = bp.TradingViewStream()
                    stream.connect()
                    stream.subscribe(symbol)
                    quote = stream.wait_for_quote(symbol, timeout=5)
                    stream.disconnect()

                    if quote:
                        futures_price = quote.get('last', 0)

                        if futures_price and xu030_spot:
                            basis = futures_price - xu030_spot
                            basis_pct = (basis / xu030_spot) * 100

                            # Durum belirleme
                            if basis_pct > 0.5:
                                status = "📈 Contango"
                            elif basis_pct < -0.5:
                                status = "📉 Backwardation"
                            else:
                                status = "➡️ Nötr"

                            results[symbol] = {
                                'symbol': symbol,
                                'spot': xu030_spot,
                                'futures': futures_price,
                                'basis': basis,
                                'basis_pct': basis_pct,
                                'status': status,
                            }

                            if verbose:
                                month = contract.get('month_code', '')
                                year = contract.get('year', '')
                                print(f"{symbol:<15} {month}/{year:>10} {futures_price:>12,.2f} "
                                      f"{basis:>+10.2f} %{basis_pct:>+9.2f} {status:>12}")

                except Exception as e:
                    if verbose:
                        print(f"{symbol:<15} ⚠️ Veri alınamadı: {e}")

        if verbose:
            print()
            print("=" * 80)
            print("💡 BAZ YORUMU:")
            print("   • Contango (Baz > 0): Vadeli fiyat spot'un üzerinde")
            print("     → Taşıma maliyeti, faiz beklentisi")
            print("   • Backwardation (Baz < 0): Spot fiyat vadeli'nin üzerinde")
            print("     → Kısa vadeli arz sıkışıklığı")

    except Exception as e:
        if verbose:
            print(f"❌ Hata: {e}")

    return results


def analyze_historical_basis(symbol: str = "THYAO", verbose: bool = True) -> dict:
    """Hisse için tarihsel baz analizi (pay vadeli vs spot)."""

    if verbose:
        print()
        print("=" * 80)
        print(f"📊 TARİHSEL BAZ ANALİZİ: {symbol}")
        print("=" * 80)
        print()

    try:
        # Spot fiyat
        stock = bp.Ticker(symbol)
        spot_price = stock.info.get('last', 0)

        if verbose:
            print(f"💰 {symbol} Spot Fiyat: {spot_price:,.2f} TL")

        # Vadeli kontratlar
        futures_symbol = f"{symbol}D"
        contracts = bp.viop_contracts(futures_symbol, full_info=True)

        if not contracts:
            if verbose:
                print(f"⚠️ {futures_symbol} için vadeli kontrat bulunamadı.")
            return {}

        if verbose:
            print()
            print(f"📋 {symbol} VADELİ KONTRATLARI:")
            print("-" * 60)

        results = {}
        for contract in contracts[:2]:
            c_symbol = contract.get('symbol')
            if c_symbol:
                try:
                    stream = bp.TradingViewStream()
                    stream.connect()
                    stream.subscribe(c_symbol)
                    quote = stream.wait_for_quote(c_symbol, timeout=5)
                    stream.disconnect()

                    if quote:
                        futures_price = quote.get('last', 0)
                        if futures_price and spot_price:
                            basis = futures_price - spot_price
                            basis_pct = (basis / spot_price) * 100

                            results[c_symbol] = {
                                'futures_price': futures_price,
                                'basis': basis,
                                'basis_pct': basis_pct,
                            }

                            if verbose:
                                print(f"   {c_symbol}: {futures_price:,.2f} TL "
                                      f"(Baz: {basis:+.2f} TL, %{basis_pct:+.2f})")

                except Exception as e:
                    if verbose:
                        print(f"   {c_symbol}: ⚠️ {e}")

        return {
            'symbol': symbol,
            'spot_price': spot_price,
            'contracts': results,
        }

    except Exception as e:
        if verbose:
            print(f"❌ Hata: {e}")
        return {}


if __name__ == "__main__":
    # BIST30 baz takibi
    basis_results = track_viop_basis()

    # Tek hisse baz analizi
    # analyze_historical_basis("THYAO")
