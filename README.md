# borsapy

[![PyPI version](https://img.shields.io/pypi/v/borsapy)](https://pypi.org/project/borsapy/)
[![PyPI downloads](https://img.shields.io/pypi/dm/borsapy)](https://pypi.org/project/borsapy/)
[![Python version](https://img.shields.io/pypi/pyversions/borsapy)](https://pypi.org/project/borsapy/)
[![License](https://img.shields.io/pypi/l/borsapy)](https://github.com/saidsurucu/borsapy/blob/master/LICENSE)
[![Documentation](https://img.shields.io/badge/docs-API%20Reference-blue)](https://saidsurucu.github.io/borsapy/borsapy.html)

Türk finansal piyasaları için Python veri kütüphanesi. BIST hisseleri, döviz, kripto, yatırım fonları ve ekonomik veriler için yfinance benzeri API.

[![Star History Chart](https://api.star-history.com/svg?repos=saidsurucu/borsapy&type=date&legend=top-left)](https://www.star-history.com/#saidsurucu/borsapy&type=date&legend=top-left)

## Kurulum

```bash
pip install borsapy
```

## Hızlı Başlangıç

```python
import borsapy as bp

# Hisse senedi verisi
hisse = bp.Ticker("THYAO")
print(hisse.info)                    # Anlık fiyat ve şirket bilgileri
print(hisse.history(period="1ay"))   # Geçmiş OHLCV verileri
print(hisse.balance_sheet)           # Bilanço

# Çoklu hisse
data = bp.download(["THYAO", "GARAN", "AKBNK"], period="1ay")
print(data)

# Döviz
usd = bp.FX("USD")
print(usd.current)                   # Güncel kur
print(usd.history(period="1ay"))     # Geçmiş veriler

# Kripto
btc = bp.Crypto("BTCTRY")
print(btc.current)                   # Güncel fiyat

# Yatırım fonu
fon = bp.Fund("AAK")
print(fon.info)                      # Fon bilgileri

# Enflasyon
enf = bp.Inflation()
print(enf.latest())                  # Son TÜFE verileri
```

---

## Ticker (Hisse Senedi)

`Ticker` sınıfı, BIST hisse senetleri için kapsamlı veri erişimi sağlar.

### Temel Kullanım

```python
import borsapy as bp

hisse = bp.Ticker("THYAO")

# Hızlı fiyat bilgisi (cache'den, API çağrısı yapmaz)
print(hisse.fast_info["last_price"])     # Son fiyat
print(hisse.fast_info["previous_close"]) # Önceki kapanış
print(hisse.fast_info["volume"])         # Hacim
print(hisse.fast_info["market_cap"])     # Piyasa değeri
print(hisse.fast_info["pe_ratio"])       # F/K oranı
print(hisse.fast_info["free_float"])     # Halka açıklık oranı
print(hisse.fast_info["foreign_ratio"])  # Yabancı oranı

# Detaylı bilgiler (tüm verileri yükler)
print(hisse.info["last"])           # Son fiyat
print(hisse.info["marketCap"])      # Piyasa değeri
print(hisse.info["trailingPE"])     # F/K oranı
print(hisse.info["dividendYield"])  # Temettü verimi
```

### Fiyat Geçmişi

```python
# Dönem bazlı
df = hisse.history(period="1ay")    # Son 1 ay
df = hisse.history(period="3ay")    # Son 3 ay
df = hisse.history(period="1y")     # Son 1 yıl
df = hisse.history(period="max")    # Tüm geçmiş

# Tarih aralığı
df = hisse.history(start="2024-01-01", end="2024-06-30")

# Farklı zaman dilimleri (interval)
df = hisse.history(period="1g", interval="1m")   # 1 dakikalık mumlar
df = hisse.history(period="1g", interval="3m")   # 3 dakikalık mumlar
df = hisse.history(period="1g", interval="5m")   # 5 dakikalık mumlar
df = hisse.history(period="1g", interval="15m")  # 15 dakikalık mumlar
df = hisse.history(period="1g", interval="30m")  # 30 dakikalık mumlar
df = hisse.history(period="1g", interval="45m")  # 45 dakikalık mumlar
df = hisse.history(period="5g", interval="1h")   # Saatlik mumlar
df = hisse.history(period="1ay", interval="1d")  # Günlük mumlar (varsayılan)
```

### Finansal Tablolar

```python
# Yıllık tablolar (sınai şirketler için)
print(hisse.balance_sheet)          # Bilanço
print(hisse.income_stmt)            # Gelir tablosu
print(hisse.cashflow)               # Nakit akış

# Çeyreklik tablolar
print(hisse.quarterly_balance_sheet)
print(hisse.quarterly_income_stmt)
print(hisse.quarterly_cashflow)

# TTM (Son 12 ay)
print(hisse.ttm_income_stmt)
print(hisse.ttm_cashflow)

# Bankalar için (UFRS formatı)
banka = bp.Ticker("AKBNK")
print(banka.get_balance_sheet(financial_group="UFRS"))
print(banka.get_income_stmt(financial_group="UFRS"))
print(banka.get_cashflow(financial_group="UFRS"))

# Banka çeyreklik tablolar
print(banka.get_balance_sheet(quarterly=True, financial_group="UFRS"))
print(banka.get_income_stmt(quarterly=True, financial_group="UFRS"))

# Banka TTM
print(banka.get_ttm_income_stmt(financial_group="UFRS"))
print(banka.get_ttm_cashflow(financial_group="UFRS"))
```

> **Not**: Sınai şirketler varsayılan olarak `XI_29` formatını kullanır. Bankalar için `financial_group="UFRS"` parametresi gereklidir.

### Temettü ve Sermaye Artırımları

```python
print(hisse.dividends)              # Temettü geçmişi
print(hisse.splits)                 # Sermaye artırımları
print(hisse.actions)                # Tüm kurumsal işlemler

# Geçmiş verilerde temettü ve split
df = hisse.history(period="1y", actions=True)
```

### Ortaklık Yapısı

```python
print(hisse.major_holders)          # Ana ortaklar
```

### Analist Verileri

```python
print(hisse.analyst_price_targets)  # Hedef fiyatlar
print(hisse.recommendations_summary) # AL/TUT/SAT dağılımı
print(hisse.recommendations)        # Detaylı tavsiyeler
```

### KAP Bildirimleri

```python
print(hisse.news)                   # Son bildirimler
print(hisse.calendar)               # Beklenen açıklamalar
print(hisse.earnings_dates)         # Finansal rapor tarihleri
```

### Diğer Bilgiler

```python
print(hisse.isin)                   # ISIN kodu
print(hisse.info["sector"])         # Sektör
print(hisse.info["industry"])       # Alt sektör
print(hisse.info["website"])        # Web sitesi
print(hisse.info["longBusinessSummary"])  # Faaliyet konusu
```

### ETF Sahipliği

Uluslararası ETF'lerin hisse pozisyonlarını görüntüleme.

```python
import borsapy as bp

stock = bp.Ticker("ASELS")

# ETF holder listesi (DataFrame)
holders = stock.etf_holders
print(holders)
#    symbol exchange                                      name  market_cap_usd  holding_weight_pct           issuer
# 0    IEMG     AMEX  iShares Core MSCI Emerging Markets ETF    118225730.76            0.090686  BlackRock, Inc.
# 1     VWO     AMEX     Vanguard FTSE Emerging Markets ETF     85480000.00            0.060000     Vanguard Inc

print(f"Total ETFs: {len(holders)}")
print(f"Top holder: {holders.iloc[0]['name']}")
print(f"Total weight: {holders['holding_weight_pct'].sum():.2f}%")
```

**DataFrame Sütunları:**

| Sütun | Açıklama |
|-------|----------|
| `symbol` | ETF sembolü (IEMG, VWO, TUR) |
| `exchange` | Borsa (AMEX, NASDAQ, LSE, XETR) |
| `name` | ETF tam adı |
| `market_cap_usd` | ETF'in bu hissedeki pozisyon değeri (USD) |
| `holding_weight_pct` | Ağırlık yüzdesi (0.09 = %0.09) |
| `issuer` | İhraççı (BlackRock, Vanguard, vb.) |
| `expense_ratio` | Gider oranı |
| `aum_usd` | Toplam varlık (USD) |

---

## Tickers ve download (Çoklu Hisse)

Birden fazla hisse için toplu veri çekme.

### Tickers Sınıfı

```python
import borsapy as bp

# Birden fazla hisse
hisseler = bp.Tickers(["THYAO", "GARAN", "AKBNK"])

# Her hissenin bilgilerine erişim
for sembol in hisseler.symbols:
    ticker = hisseler.tickers[sembol]
    print(f"{sembol}: {ticker.info['last']}")
```

### download Fonksiyonu

```python
# Basit kullanım
df = bp.download(["THYAO", "GARAN", "AKBNK"], period="1ay")

# Ticker bazlı gruplama
df = bp.download(["THYAO", "GARAN"], period="1ay", group_by="ticker")

# Sütun bazlı gruplama (varsayılan)
df = bp.download(["THYAO", "GARAN"], period="1ay", group_by="column")
```

---

## Index (Endeksler)

BIST endekslerine erişim - 79 endeks, bileşen listeleri dahil.

### Temel Kullanım

```python
import borsapy as bp

# Mevcut endeksler (33 popüler endeks)
print(bp.indices())
# ['XU100', 'XU050', 'XU030', 'XKTUM', 'XK100', 'XK030', 'XBANK', ...]

# Detaylı liste (bileşen sayısı ile)
print(bp.indices(detailed=True))
# [{'symbol': 'XU100', 'name': 'BIST 100', 'count': 100}, ...]

# Tüm BIST endeksleri (79 endeks)
print(bp.all_indices())
# [{'symbol': 'X030C', 'name': 'BIST 30 Capped', 'count': 30}, ...]

# Endeks verisi
xu100 = bp.Index("XU100")
print(xu100.info)                    # Güncel değer, değişim
print(xu100.history(period="1ay"))   # OHLCV geçmişi
```

### Endeks Bileşenleri

```python
# Endeks içindeki hisseler
xu030 = bp.Index("XU030")
print(xu030.components)              # [{'symbol': 'AKBNK', 'name': 'AKBANK'}, ...]
print(xu030.component_symbols)       # ['AKBNK', 'ASELS', 'BIMAS', ...]
print(len(xu030.components))         # 30

# Katılım endeksleri
xk030 = bp.Index("XK030")            # BIST Katılım 30
print(xk030.components)              # Faizsiz finans uyumlu 30 hisse
print(xk030.component_symbols)

xktum = bp.Index("XKTUM")            # BIST Katılım Tüm
print(len(xktum.components))         # 218 hisse
```

### Desteklenen Endeksler

| Kategori | Endeksler |
|----------|-----------|
| Ana | XU100, XU050, XU030, XUTUM |
| Katılım | XKTUM, XK100, XK050, XK030, XKTMT |
| Sektör | XBANK, XUSIN, XUMAL, XUTEK, XGIDA, XHOLD, ... |
| Tematik | XSRDK, XKURY, XYLDZ, XSPOR, XGMYO, ... |
| Şehir | XSIST, XSANK, XSIZM, XSBUR, ... |

---

## FX (Döviz ve Emtia)

Döviz kurları ve emtia fiyatları. **65 döviz** desteği.

### Döviz Kurları

```python
import borsapy as bp

usd = bp.FX("USD")
print(usd.current)                  # Güncel kur
print(usd.history(period="1ay"))    # Geçmiş veriler (günlük)

# Majör dövizler
eur = bp.FX("EUR")
gbp = bp.FX("GBP")
chf = bp.FX("CHF")
jpy = bp.FX("JPY")
cad = bp.FX("CAD")
aud = bp.FX("AUD")

# Diğer dövizler (65 döviz destekleniyor)
rub = bp.FX("RUB")    # Rus Rublesi
cny = bp.FX("CNY")    # Çin Yuanı
sar = bp.FX("SAR")    # Suudi Riyali
aed = bp.FX("AED")    # BAE Dirhemi
inr = bp.FX("INR")    # Hindistan Rupisi
# ... ve daha fazlası
```

### Dakikalık/Saatlik Veri (TradingView)

Bazı döviz çiftleri için intraday (dakikalık/saatlik) veri TradingView üzerinden sağlanır.

```python
import borsapy as bp

usd = bp.FX("USD")

# Dakikalık veri
df = usd.history(period="1g", interval="1m")    # Son 1 gün, 1 dakikalık
df = usd.history(period="1g", interval="5m")    # 5 dakikalık
df = usd.history(period="1g", interval="15m")   # 15 dakikalık
df = usd.history(period="1g", interval="30m")   # 30 dakikalık

# Saatlik veri
df = usd.history(period="5g", interval="1h")    # Son 5 gün, saatlik
df = usd.history(period="1ay", interval="4h")   # Son 1 ay, 4 saatlik

# Günlük ve üstü (varsayılan, canlidoviz kullanır)
df = usd.history(period="1ay", interval="1d")   # Günlük
df = usd.history(period="1ay")                  # Günlük (varsayılan)
```

**İntraday Destekleyen Dövizler (TradingView):**

| Döviz | Symbol | Not |
|-------|--------|-----|
| USD/TRY | `USD` | FX:USDTRY |
| EUR/TRY | `EUR` | FX:EURTRY |
| GBP/TRY | `GBP` | PEPPERSTONE:GBPTRY |
| TRY/JPY | `JPY` | FX:TRYJPY (ters çift) |

**İntraday Destekleyen Emtialar (TradingView):**

| Emtia | Symbol | Not |
|-------|--------|-----|
| Altın (Ons/USD) | `ons-altin` veya `XAU` | OANDA:XAUUSD |
| Gümüş (Ons/USD) | `XAG` | OANDA:XAGUSD |
| Platin (USD) | `XPT` | OANDA:XPTUSD |
| Paladyum (USD) | `XPD` | OANDA:XPDUSD |
| Brent Petrol | `BRENT` | TVC:UKOIL |
| WTI Petrol | `WTI` | TVC:USOIL |

> **Not**: Diğer dövizler (CHF, CAD, AUD, vb.) için TradingView'da TRY çifti bulunmadığından sadece günlük veri mevcuttur (canlidoviz.com). İntraday desteklenmeyen bir döviz için interval belirtilirse hata verir.

### Desteklenen Dövizler

| Kategori | Dövizler |
|----------|----------|
| Majör | USD, EUR, GBP, CHF, JPY, CAD, AUD, NZD |
| Avrupa | DKK, SEK, NOK, PLN, CZK, HUF, RON, BGN, HRK, RSD, BAM, MKD, ALL, MDL, UAH, BYR, ISK |
| Ortadoğu & Afrika | AED, SAR, QAR, KWD, BHD, OMR, JOD, IQD, IRR, LBP, SYP, EGP, LYD, TND, DZD, MAD, ZAR, ILS |
| Asya & Pasifik | CNY, INR, PKR, LKR, IDR, MYR, THB, PHP, KRW, KZT, AZN, GEL, SGD, HKD, TWD |
| Amerika | MXN, BRL, ARS, CLP, COP, PEN, UYU, CRC |
| Diğer | RUB, DVZSP1 (Sepet Kur) |

### Banka Kurları

```python
import borsapy as bp

usd = bp.FX("USD")

# Tüm bankaların kurları
print(usd.bank_rates)               # DataFrame: bank, buying, selling, updated
#          bank  buying  selling              updated
# 0      Akbank   34.85    35.15  2024-01-15 10:30:00
# 1    Garanti   34.82    35.12  2024-01-15 10:28:00
# ...

# Tek banka kuru
print(usd.bank_rate("akbank"))      # {'buying': 34.85, 'selling': 35.15, ...}
print(usd.bank_rate("garanti"))

# Desteklenen bankalar
print(bp.banks())                   # ['akbank', 'garanti', 'isbank', ...]
```

### Altın ve Emtialar

```python
# Altın (TRY)
gram_altin = bp.FX("gram-altin")
ceyrek = bp.FX("ceyrek-altin")
yarim = bp.FX("yarim-altin")
tam = bp.FX("tam-altin")
cumhuriyet = bp.FX("cumhuriyet-altin")
ata = bp.FX("ata-altin")

# Diğer değerli metaller (TRY)
gumus = bp.FX("gram-gumus")
ons_altin = bp.FX("ons-altin")
platin = bp.FX("gram-platin")

# Emtia (USD)
brent = bp.FX("BRENT")           # Brent Petrol
silver = bp.FX("XAG-USD")        # Gümüş Ons
platinum = bp.FX("XPT-USD")      # Platin Spot
palladium = bp.FX("XPD-USD")     # Paladyum Spot

print(gram_altin.current)
print(gram_altin.history(period="1ay"))
```

### Kurum Fiyatları (Kuyumcu/Banka)

```python
# Değerli metal kurum fiyatları
gold = bp.FX("gram-altin")

# Tüm kurumların fiyatları
print(gold.institution_rates)
#       institution institution_name       asset      buy     sell  spread
# 0     altinkaynak      Altınkaynak  gram-altin  6315.00  6340.00    0.40
# 1          akbank           Akbank  gram-altin  6310.00  6330.00    0.32

# Tek kurum fiyatı
print(gold.institution_rate("kapalicarsi"))
print(gold.institution_rate("akbank"))

# Desteklenen emtialar
print(bp.metal_institutions())
# ['gram-altin', 'gram-gumus', 'ons-altin', 'gram-platin']
```

### Kurum Bazlı Geçmiş (Metal + Döviz)

```python
# Metal geçmişi
gold = bp.FX("gram-altin")
gold.institution_history("akbank", period="1mo")       # Akbank 1 aylık
gold.institution_history("kapalicarsi", period="3mo")  # Kapalıçarşı 3 aylık

# Döviz geçmişi
usd = bp.FX("USD")
usd.institution_history("akbank", period="1mo")        # Akbank USD 1 aylık
usd.institution_history("garanti-bbva", period="5d")   # Garanti 5 günlük

# 27 kurum destekleniyor (bankalar + kuyumcular)
# Kuyumcular (kapalicarsi, harem, altinkaynak) OHLC verir
# Bankalar (akbank, garanti) sadece Close verir
```

---

## Crypto (Kripto Para)

BtcTurk üzerinden kripto para verileri.

```python
import borsapy as bp

# Mevcut çiftler
print(bp.crypto_pairs())

# Bitcoin/TRY
btc = bp.Crypto("BTCTRY")
print(btc.current)                  # Güncel fiyat
print(btc.history(period="1ay"))    # OHLCV geçmişi

# Ethereum/TRY
eth = bp.Crypto("ETHTRY")
print(eth.current)
```

---

## Fund (Yatırım Fonları)

TEFAS üzerinden yatırım fonu verileri.

### Temel Kullanım

```python
import borsapy as bp

# Fon arama
print(bp.search_funds("banka"))

# Fon verisi
fon = bp.Fund("AAK")
print(fon.info)                     # Fon bilgileri
print(fon.history(period="1ay"))    # Fiyat geçmişi
print(fon.performance)              # Performans verileri
```

### Varlık Dağılımı

```python
# Portföy varlık dağılımı
print(fon.allocation)               # Son 7 günlük dağılım
print(fon.allocation_history(period="3ay"))  # Son 3 ay (max ~100 gün)
#         date     asset_type    asset_name  weight
# 0 2024-01-15   Hisse Senedi        Stocks   45.2
# 1 2024-01-15      Ters-Repo  Reverse Repo   30.1
# ...

# info içinde de mevcut (ekstra API çağrısı yok)
print(fon.info['allocation'])
print(fon.info['isin'])             # ISIN kodu
print(fon.info['daily_return'])     # Günlük getiri
print(fon.info['weekly_return'])    # Haftalık getiri
print(fon.info['category_rank'])    # Kategori sırası (örn: 20/181)
```

### Fon Tarama

```python
# Getiri kriterlerine göre filtrele
df = bp.screen_funds(fund_type="YAT", min_return_1y=50)   # >%50 1Y getiri
df = bp.screen_funds(fund_type="EMK", min_return_ytd=20)  # Emeklilik fonları
df = bp.screen_funds(min_return_1m=5)                     # Son 1 ayda >%5

# Fon tipleri: YAT (yatırım), EMK (emeklilik), None (tümü)
```

### Fon Karşılaştırma

```python
# Birden fazla fonu karşılaştır (max 10)
result = bp.compare_funds(["AAK", "TTE", "AFO"])

print(result['funds'])              # Fon detayları listesi
print(result['rankings'])           # Sıralamalar
#   by_return_1y: ['AFO', 'TTE', 'AAK']
#   by_size: ['AFO', 'TTE', 'AAK']
#   by_risk_asc: ['AAK', 'TTE', 'AFO']

print(result['summary'])            # Özet
#   fund_count: 3
#   total_size: 23554985554.72
#   avg_return_1y: 53.65
#   best_return_1y: 100.84
#   worst_return_1y: 28.15
```

### Risk Metrikleri

```python
fon = bp.Fund("YAY")

# Sharpe oranı (10Y tahvil faizi ile)
print(fon.sharpe_ratio())              # 1Y Sharpe
print(fon.sharpe_ratio(period="3y"))   # 3Y Sharpe

# Tüm risk metrikleri
metrics = fon.risk_metrics(period="1y")
print(metrics['annualized_return'])     # Yıllık getiri (%)
print(metrics['annualized_volatility']) # Yıllık volatilite (%)
print(metrics['sharpe_ratio'])          # Sharpe oranı
print(metrics['sortino_ratio'])         # Sortino oranı (downside risk)
print(metrics['max_drawdown'])          # Maksimum düşüş (%)

# Uzun dönem desteği
fon.history(period="3y")   # 3 yıllık veri
fon.history(period="5y")   # 5 yıllık veri
fon.history(period="max")  # Tüm veri (5 yıla kadar)
```

---

## Portfolio (Portföy Yönetimi)

Çoklu varlık portföylerini yönetme, performans takibi ve risk metrikleri.

### Temel Kullanım

```python
import borsapy as bp

# Portföy oluşturma
portfolio = bp.Portfolio()

# Varlık ekleme (4 tip destekleniyor)
portfolio.add("THYAO", shares=100, cost=280.0)          # Hisse - adet + maliyet
portfolio.add("GARAN", shares=200)                       # Hisse - güncel fiyattan
portfolio.add("gram-altin", shares=10, asset_type="fx")  # Emtia/Döviz (FX)
portfolio.add("USD", shares=1000, asset_type="fx")       # Döviz
portfolio.add("BTCTRY", shares=0.5)                      # Kripto (auto-detect)
portfolio.add("YAY", shares=1000, asset_type="fund")     # Yatırım Fonu

# Benchmark ayarlama (Index karşılaştırması için)
portfolio.set_benchmark("XU100")                         # XU030, XK030 da olabilir

# Portföy durumu
print(portfolio.holdings)     # DataFrame: symbol, shares, cost, current_price, value, weight, pnl, pnl_pct
print(portfolio.value)        # Toplam değer (TL)
print(portfolio.cost)         # Toplam maliyet
print(portfolio.pnl)          # Kar/zarar (TL)
print(portfolio.pnl_pct)      # Kar/zarar (%)
print(portfolio.weights)      # {'THYAO': 0.45, 'GARAN': 0.35, ...}
```

### Desteklenen Varlık Tipleri

| Tip | Sınıf | Otomatik Algılama | Örnekler |
|-----|-------|-------------------|----------|
| **stock** | `Ticker` | Varsayılan | THYAO, GARAN, ASELS |
| **fx** | `FX` | ✅ 65 döviz + metaller + emtia | USD, EUR, gram-altin, BRENT |
| **crypto** | `Crypto` | ✅ *TRY pattern (6+ karakter) | BTCTRY, ETHTRY |
| **fund** | `Fund` | ❌ `asset_type="fund"` gerekli | AAK, TTE, YAY |

**Not**: Index'ler (XU100, XU030) satın alınamaz, **benchmark** olarak kullanılır.

### Performans ve Geçmiş

```python
# Geçmiş performans (mevcut pozisyonlarla)
hist = portfolio.history(period="1y")
print(hist)
#                   Value  Daily_Return
# Date
# 2024-01-02  150000.00           NaN
# 2024-01-03  152300.00      0.0153
# ...

# Performans özeti
print(portfolio.performance)
# {'total_return': 25.5, 'total_value': 187500.0, 'total_cost': 150000.0, 'total_pnl': 37500.0}
```

### Risk Metrikleri

```python
# Tüm risk metrikleri
metrics = portfolio.risk_metrics(period="1y")
print(metrics)
# {'annualized_return': 18.2,
#  'annualized_volatility': 22.5,
#  'sharpe_ratio': 0.65,
#  'sortino_ratio': 0.82,
#  'max_drawdown': -15.3,
#  'beta': 1.12,
#  'alpha': 2.5,
#  'risk_free_rate': 28.0,
#  'trading_days': 252}

# Kısa yollar
print(portfolio.sharpe_ratio())           # Sharpe oranı
print(portfolio.sortino_ratio())          # Sortino oranı
print(portfolio.beta())                   # Benchmark'a göre beta (varsayılan: XU100)
print(portfolio.beta(benchmark="XU030"))  # Farklı benchmark

# Korelasyon matrisi
corr = portfolio.correlation_matrix(period="1y")
print(corr)
#          THYAO    GARAN  gram-altin
# THYAO     1.00     0.75       0.15
# GARAN     0.75     1.00       0.12
# gram-altin 0.15    0.12       1.00
```

### Varlık Yönetimi

```python
# Varlık güncelleme
portfolio.update("THYAO", shares=150, cost=290.0)

# Varlık kaldırma
portfolio.remove("GARAN")

# Portföyü temizle
portfolio.clear()

# Method chaining
portfolio.add("THYAO", shares=100, cost=280).add("GARAN", shares=200, cost=50).set_benchmark("XU030")
```

### Import/Export

```python
# Dict olarak export
data = portfolio.to_dict()
print(data)
# {'benchmark': 'XU100', 'holdings': [
#     {'symbol': 'THYAO', 'shares': 100, 'cost_per_share': 280.0, 'asset_type': 'stock'},
#     ...
# ]}

# Dict'ten import
portfolio2 = bp.Portfolio.from_dict(data)

# JSON'a kaydetme
import json
with open("portfolio.json", "w") as f:
    json.dump(portfolio.to_dict(), f)

# JSON'dan yükleme
with open("portfolio.json") as f:
    portfolio3 = bp.Portfolio.from_dict(json.load(f))
```

### Teknik Analiz (TechnicalMixin)

Portfolio sınıfı TechnicalMixin'den miras aldığı için teknik göstergeleri de kullanabilir:

```python
# Portfolio history üzerinde teknik analiz
portfolio.rsi()                    # RSI
portfolio.sma()                    # SMA
portfolio.macd()                   # MACD
portfolio.bollinger_bands()        # Bollinger Bands
```

---

## Teknik Analiz

Tüm varlık sınıfları için teknik analiz göstergeleri (Ticker, Index, Crypto, FX, Fund).

### Tekil Değerler

```python
import borsapy as bp

hisse = bp.Ticker("THYAO")

# RSI (Relative Strength Index)
print(hisse.rsi())                    # 65.2 (son değer)
print(hisse.rsi(rsi_period=7))        # 7 periyotluk RSI

# Hareketli Ortalamalar
print(hisse.sma())                    # 20 günlük SMA
print(hisse.sma(sma_period=50))       # 50 günlük SMA
print(hisse.ema(ema_period=12))       # 12 günlük EMA

# MACD
print(hisse.macd())
# {'macd': 2.5, 'signal': 1.8, 'histogram': 0.7}

# Bollinger Bands
print(hisse.bollinger_bands())
# {'upper': 310.2, 'middle': 290.5, 'lower': 270.8}

# Stochastic
print(hisse.stochastic())
# {'k': 75.2, 'd': 68.5}

# ATR (Average True Range)
print(hisse.atr())                    # 4.25

# OBV (On-Balance Volume)
print(hisse.obv())                    # 1250000

# VWAP (Volume Weighted Average Price)
print(hisse.vwap())                   # 285.5

# ADX (Average Directional Index)
print(hisse.adx())                    # 32.5
```

### TechnicalAnalyzer ile Tam Seriler

```python
import borsapy as bp

hisse = bp.Ticker("THYAO")

# TechnicalAnalyzer oluştur
ta = hisse.technicals(period="1y")

# Tüm göstergelerin son değerleri
print(ta.latest)
# {'sma_20': 285.5, 'ema_12': 287.2, 'rsi_14': 65.2, 'macd': 2.5, ...}

# Tek tek seriler (pd.Series)
print(ta.rsi())                       # 252 değerlik RSI serisi
print(ta.sma(20))                     # 20 günlük SMA serisi
print(ta.ema(12))                     # 12 günlük EMA serisi

# DataFrame döndürenler
print(ta.macd())                      # MACD, Signal, Histogram sütunları
print(ta.bollinger_bands())           # BB_Upper, BB_Middle, BB_Lower
print(ta.stochastic())                # Stoch_K, Stoch_D
```

### DataFrame ile Tüm Göstergeler

```python
import borsapy as bp

hisse = bp.Ticker("THYAO")

# OHLCV + tüm göstergeler tek DataFrame'de
df = hisse.history_with_indicators(period="3ay")
print(df.columns)
# ['Open', 'High', 'Low', 'Close', 'Volume', 'SMA_20', 'EMA_12',
#  'RSI_14', 'MACD', 'Signal', 'Histogram', 'BB_Upper', 'BB_Middle',
#  'BB_Lower', 'ATR_14', 'Stoch_K', 'Stoch_D', 'OBV', 'VWAP', 'ADX_14']

# Sadece belirli göstergeler
df = hisse.history_with_indicators(period="1ay", indicators=["sma", "rsi", "macd"])
```

### Tüm Varlık Sınıflarında Çalışır

```python
import borsapy as bp

# Hisse
bp.Ticker("THYAO").rsi()

# Endeks
bp.Index("XU100").macd()

# Kripto
bp.Crypto("BTCTRY").bollinger_bands()

# Döviz (Volume gerektiren göstergeler NaN döner)
bp.FX("USD").rsi()

# Yatırım Fonu
bp.Fund("AAK").stochastic()

# Altın
bp.FX("gram-altin").sma()
```

### Standalone Fonksiyonlar

```python
import borsapy as bp
from borsapy.technical import (
    calculate_sma, calculate_ema, calculate_rsi, calculate_macd,
    calculate_bollinger_bands, calculate_atr, calculate_stochastic,
    calculate_obv, calculate_vwap, calculate_adx, add_indicators
)

# Herhangi bir DataFrame üzerinde kullanım
df = bp.download("THYAO", period="1y")

# Tekil göstergeler
rsi = calculate_rsi(df, period=14)
macd_df = calculate_macd(df, fast=12, slow=26, signal=9)
bb_df = calculate_bollinger_bands(df, period=20, std_dev=2.0)

# Tüm göstergeleri ekle
df_with_indicators = add_indicators(df)
df_with_indicators = add_indicators(df, indicators=["sma", "rsi"])  # Sadece belirli göstergeler
```

### Desteklenen Göstergeler

| Gösterge | Metod | Açıklama |
|----------|-------|----------|
| SMA | `sma()` | Basit Hareketli Ortalama |
| EMA | `ema()` | Üstel Hareketli Ortalama |
| RSI | `rsi()` | Göreceli Güç Endeksi (0-100) |
| MACD | `macd()` | Hareketli Ortalama Yakınsama/Iraksama |
| Bollinger Bands | `bollinger_bands()` | Üst/Orta/Alt bantlar |
| ATR | `atr()` | Ortalama Gerçek Aralık |
| Stochastic | `stochastic()` | Stokastik Osilatör (%K, %D) |
| OBV | `obv()` | Denge Hacmi (Volume gerektirir) |
| VWAP | `vwap()` | Hacim Ağırlıklı Ortalama Fiyat (Volume gerektirir) |
| ADX | `adx()` | Ortalama Yön Endeksi (0-100) |

### Heikin Ashi Charts

Alternatif mum grafiği hesaplama yöntemi.

```python
import borsapy as bp

stock = bp.Ticker("THYAO")

# Pure function ile
df = stock.history(period="1y")
ha_df = bp.calculate_heikin_ashi(df)
# Sütunlar: HA_Open, HA_High, HA_Low, HA_Close, Volume

# Convenience method
ha_df = stock.heikin_ashi(period="1y")

# TechnicalAnalyzer ile
ta = stock.technicals(period="1y")
ha_df = ta.heikin_ashi()
```

**Heikin Ashi Formülü:**
```
HA_Close = (Open + High + Low + Close) / 4
HA_Open  = (Prev_HA_Open + Prev_HA_Close) / 2  (ilk satır: (O+C)/2)
HA_High  = max(High, HA_Open, HA_Close)
HA_Low   = min(Low, HA_Open, HA_Close)
```

### TradingView TA Sinyalleri

TradingView Scanner API ile teknik analiz sinyalleri (AL/SAT/TUT).

```python
import borsapy as bp

stock = bp.Ticker("THYAO")

# Tek timeframe (varsayılan: günlük)
signals = stock.ta_signals()
print(signals['summary']['recommendation'])  # "STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"
print(signals['summary']['buy'])             # 12 (AL sinyali veren gösterge sayısı)
print(signals['oscillators']['compute']['RSI'])  # "BUY", "SELL", "NEUTRAL"
print(signals['moving_averages']['values']['EMA20'])  # 285.5

# Belirli timeframe
signals_1h = stock.ta_signals(interval="1h")   # Saatlik
signals_4h = stock.ta_signals(interval="4h")   # 4 saatlik
signals_1w = stock.ta_signals(interval="1W")   # Haftalık

# Tüm timeframe'ler tek seferde
all_signals = stock.ta_signals_all_timeframes()
print(all_signals['1h']['summary']['recommendation'])
print(all_signals['1d']['summary']['recommendation'])
print(all_signals['1W']['summary']['recommendation'])

# Diğer varlık sınıfları için de çalışır
bp.Index("XU100").ta_signals()
bp.FX("USD").ta_signals()
bp.Crypto("BTCTRY").ta_signals()
```

**Desteklenen Timeframe'ler:** `1m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `1d`, `1W`, `1M`

**Sinyal Çıktı Formatı:**
```python
{
    "symbol": "THYAO",
    "exchange": "BIST",
    "interval": "1d",
    "summary": {
        "recommendation": "BUY",  # STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL
        "buy": 12, "sell": 5, "neutral": 9
    },
    "oscillators": {
        "recommendation": "NEUTRAL",
        "buy": 2, "sell": 2, "neutral": 7,
        "compute": {"RSI": "NEUTRAL", "MACD": "SELL", ...},
        "values": {"RSI": 48.95, "MACD.macd": 3.78, ...}
    },
    "moving_averages": {
        "recommendation": "BUY",
        "buy": 10, "sell": 3, "neutral": 2,
        "compute": {"EMA10": "BUY", "SMA20": "BUY", ...},
        "values": {"EMA10": 285.5, "SMA20": 284.2, ...}
    }
}
```

---

## Gerçek Zamanlı Veri Akışı (TradingView Streaming)

Düşük gecikmeli, yüksek verimli gerçek zamanlı veri akışı. Persistent WebSocket bağlantısı ile anlık fiyat ve mum verisi.

### Temel Kullanım

```python
import borsapy as bp

# Stream oluştur ve bağlan
stream = bp.TradingViewStream()
stream.connect()

# Sembollere abone ol
stream.subscribe("THYAO")
stream.subscribe("GARAN")
stream.subscribe("ASELS")

# Anlık fiyat al (cached, <1ms)
quote = stream.get_quote("THYAO")
print(quote['last'])           # 299.0
print(quote['bid'])            # 298.9
print(quote['ask'])            # 299.1
print(quote['volume'])         # 12345678
print(quote['change_percent']) # 2.5

# İlk quote için bekle (blocking)
quote = stream.wait_for_quote("THYAO", timeout=5.0)

# Callback ile real-time updates
def on_price_update(symbol, quote):
    print(f"{symbol}: {quote['last']} ({quote['change_percent']:+.2f}%)")

stream.on_quote("THYAO", on_price_update)

# Tüm semboller için callback
stream.on_any_quote(lambda s, q: print(f"{s}: {q['last']}"))

# Bağlantıyı kapat
stream.disconnect()
```

### Context Manager Kullanımı

```python
import borsapy as bp

with bp.TradingViewStream() as stream:
    stream.subscribe("THYAO")
    quote = stream.wait_for_quote("THYAO", timeout=5.0)
    print(quote['last'])
```

### Chart Verileri (OHLCV Streaming)

Gerçek zamanlı mum grafiği verisi.

```python
import borsapy as bp

stream = bp.TradingViewStream()
stream.connect()

# Mum grafiği aboneliği
stream.subscribe_chart("THYAO", "1m")   # 1 dakikalık mumlar
stream.subscribe_chart("GARAN", "5m")   # 5 dakikalık mumlar
stream.subscribe_chart("ASELS", "1h")   # Saatlik mumlar

# Callback ile mum güncellemeleri
def on_candle(symbol, interval, candle):
    print(f"{symbol} {interval}: O={candle['open']} H={candle['high']} L={candle['low']} C={candle['close']}")

stream.on_candle("THYAO", "1m", on_candle)

# Tüm mumlar için callback
stream.on_any_candle(lambda s, i, c: print(f"{s} {i}: {c['close']}"))

# Cached mum verisi al
candle = stream.get_candle("THYAO", "1m")
candles = stream.get_candles("THYAO", "1m")  # Tüm mumlar (list)

# İlk mum için bekle
candle = stream.wait_for_candle("THYAO", "1m", timeout=10.0)

stream.disconnect()
```

**Desteklenen Timeframe'ler:** `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1wk`, `1mo`

### TradingView Kimlik Doğrulama (Gerçek Zamanlı Veri)

Varsayılan olarak TradingView verileri ~15 dakika gecikmeli. Gerçek zamanlı BIST verisi için TradingView'da aşağıdaki aboneliklere ihtiyacınız var:

1. **Essential** veya üzeri plan (Pro, Pro+, Premium)
2. **BIST Real-time Market Data** paketi (ek ücretli)

> TradingView hesabınızda: Profil → Hesap ve Faturalama → Piyasa Verileri Abonelikleri → "Borsa Istanbul" ekleyin.

```python
import borsapy as bp

# Yöntem 1: Username/Password ile login
bp.set_tradingview_auth(
    username="user@email.com",
    password="mypassword"
)

# Yöntem 2: Mevcut session token ile
bp.set_tradingview_auth(
    session="abc123...",          # sessionid cookie
    session_sign="xyz789..."      # sessionid_sign cookie
)

# Artık gerçek zamanlı veri
stream = bp.TradingViewStream()
stream.connect()
stream.subscribe("THYAO")
quote = stream.wait_for_quote("THYAO")
print(quote['last'])  # Gerçek zamanlı fiyat

# Logout
bp.clear_tradingview_auth()
```

**Session süresi:** ~30 gün (remember=on ile)

**Chrome DevTools ile Cookie Alma:**

1. TradingView'a giriş yapın (tradingview.com)
2. `F12` veya `Ctrl+Shift+I` ile DevTools'u açın
3. **Application** sekmesine gidin
4. Sol menüden **Cookies** → `https://www.tradingview.com` seçin
5. Aşağıdaki cookie'leri bulun ve değerlerini kopyalayın:
   - `sessionid` → `session` parametresi
   - `sessionid_sign` → `session_sign` parametresi

```python
bp.set_tradingview_auth(
    session="kopyaladığınız_sessionid_değeri",
    session_sign="kopyaladığınız_sessionid_sign_değeri"
)
```

### Quote Alanları (46 alan)

| Kategori | Alanlar |
|----------|---------|
| **Fiyat** | `last`, `change`, `change_percent`, `bid`, `ask`, `bid_size`, `ask_size`, `volume` |
| **OHLC** | `open`, `high`, `low`, `prev_close` |
| **Temel** | `market_cap`, `pe_ratio`, `eps`, `dividend_yield`, `beta` |
| **52 Hafta** | `high_52_week`, `low_52_week` |
| **Meta** | `description`, `currency`, `timestamp` |

### Performans Karşılaştırması

| Metrik | Eski (get_quote) | Yeni (TradingViewStream) |
|--------|------------------|--------------------------|
| Gecikme | ~7000ms | ~50-100ms |
| Throughput | 0.1 req/s | 10-20 req/s |
| Bağlantı | Her istekte yeni | Tek persistent |
| Cached Quote | N/A | <1ms |

> **Teşekkür:** Bu TradingView entegrasyonu [Mathieu2301/TradingView-API](https://github.com/Mathieu2301/TradingView-API) projesinden ilham alınarak geliştirilmiştir.

---

## Sembol Arama (Search)

TradingView symbol search API ile çoklu piyasada sembol arama.

```python
import borsapy as bp

# Basit arama
bp.search("banka")           # ['AKBNK', 'GARAN', 'ISCTR', ...]
bp.search("enerji")          # ['AKSEN', 'ODAS', 'ZOREN', ...]
bp.search("THY")             # ['THYAO']

# Tip filtreleme
bp.search("gold", type="forex")     # Altın pariteleri
bp.search("BTC", type="crypto")     # Kripto
bp.search("XU", type="index")       # Endeksler
bp.search("F_XU030", type="futures") # Vadeli kontratlar

# Exchange filtresi
bp.search("GARAN", exchange="BIST")  # Sadece BIST

# Detaylı sonuç
results = bp.search("THYAO", full_info=True)
# [{'symbol': 'THYAO', 'exchange': 'BIST', 'description': 'TURK HAVA YOLLARI', ...}]

# Kısa yol fonksiyonları
bp.search_bist("banka")      # Sadece BIST hisseleri
bp.search_crypto("ETH")      # Sadece kripto
bp.search_forex("USD")       # Sadece forex
bp.search_index("XU")        # Sadece endeksler
```

**Desteklenen Tipler:** `stock`, `forex`, `crypto`, `index`, `futures`, `bond`, `fund`

---

## Replay Mode (Backtesting için Tarihsel Oynatma)

Backtesting için tarihsel veriyi candle-by-candle oynatma.

```python
import borsapy as bp

# Basit replay
session = bp.create_replay("THYAO", period="6mo", speed=5.0)

for candle in session.replay():
    print(f"{candle['timestamp']}: Close={candle['close']}")
    # Trading logic...

# Callback ile
def on_candle(c):
    print(f"Progress: {c['_index']}/{c['_total']} ({c['_progress']:.1%})")

session.on_candle(on_candle)
list(session.replay())  # Callback'ler otomatik çalışır

# Tarih filtresi ile
for candle in session.replay_filtered(
    start_date="2024-01-01",
    end_date="2024-06-01"
):
    # Sadece belirlenen tarih aralığı
    pass

# İstatistikler
print(session.stats())
# {'symbol': 'THYAO', 'total_candles': 252, 'progress': 0.5, ...}
```

**Candle Formatı:**
```python
{
    "timestamp": datetime,
    "open": 285.0,
    "high": 286.5,
    "low": 284.0,
    "close": 285.5,
    "volume": 123456,
    "_index": 42,      # Kaçıncı candle
    "_total": 252,     # Toplam candle sayısı
    "_progress": 0.167 # İlerleme (0.0-1.0)
}
```

---

## Backtest Engine

Strateji backtesting framework'ü. Kendi stratejilerinizi geçmiş verilere karşı test edin.

### Temel Kullanım

```python
import borsapy as bp

# Strateji tanımla
def rsi_strategy(candle, position, indicators):
    """
    Args:
        candle: {'timestamp', 'open', 'high', 'low', 'close', 'volume'}
        position: 'long' | 'short' | None
        indicators: {'rsi': 48.5, 'sma_20': 285.5, ...}
    Returns:
        'BUY' | 'SELL' | 'HOLD' | None
    """
    if indicators.get('rsi', 50) < 30 and position is None:
        return 'BUY'
    elif indicators.get('rsi', 50) > 70 and position == 'long':
        return 'SELL'
    return 'HOLD'

# Backtest çalıştır
result = bp.backtest(
    "THYAO",
    rsi_strategy,
    period="1y",
    capital=100000,
    commission=0.001,
    indicators=['rsi', 'sma_20']
)

# Sonuçlar
print(result.summary())
print(f"Net Profit: {result.net_profit:.2f} TL")
print(f"Net Profit %: {result.net_profit_pct:.2f}%")
print(f"Win Rate: {result.win_rate:.1f}%")
print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
print(f"Max Drawdown: {result.max_drawdown:.2f}%")
print(f"Total Trades: {result.total_trades}")

# DataFrame export
print(result.trades_df)      # Trade history
print(result.equity_curve)   # Equity over time
```

### Backtest Class ile Detaylı Kullanım

```python
import borsapy as bp

bt = bp.Backtest(
    symbol="GARAN",
    strategy=rsi_strategy,
    period="2y",
    capital=50000,
    commission=0.001,
    indicators=['rsi', 'macd', 'bollinger']
)

result = bt.run()
```

### BacktestResult Metrikleri

| Metrik | Açıklama |
|--------|----------|
| `net_profit` | Net kar (TL) |
| `net_profit_pct` | Net kar yüzdesi |
| `total_trades` | Toplam işlem sayısı |
| `winning_trades` | Kazançlı işlem sayısı |
| `losing_trades` | Kayıplı işlem sayısı |
| `win_rate` | Kazanç oranı (%) |
| `profit_factor` | Brüt kar / Brüt zarar |
| `sharpe_ratio` | Risk-adjusted return |
| `sortino_ratio` | Downside risk-adjusted return |
| `max_drawdown` | Maksimum düşüş (%) |
| `avg_trade` | Ortalama işlem karı |
| `buy_hold_return` | Buy & Hold getirisi |
| `vs_buy_hold` | Strateji vs Buy & Hold |
| `trades_df` | Trade DataFrame (entry, exit, profit, duration) |
| `equity_curve` | Portföy değeri zaman serisi |

### Desteklenen Göstergeler

| Gösterge | Format | Açıklama |
|----------|--------|----------|
| RSI | `rsi`, `rsi_7`, `rsi_21` | RSI (varsayılan 14) |
| SMA | `sma_20`, `sma_50`, `sma_200` | Simple Moving Average |
| EMA | `ema_12`, `ema_26`, `ema_50` | Exponential Moving Average |
| MACD | `macd` | MACD, Signal, Histogram |
| Bollinger | `bollinger` | Upper, Middle, Lower bands |
| ATR | `atr`, `atr_20` | Average True Range |
| Stochastic | `stochastic` | %K, %D |
| ADX | `adx` | Average Directional Index |

---

## Pine Script Streaming Indicators

TradingView'ın Pine Script göstergelerini gerçek zamanlı olarak alın.

```python
import borsapy as bp

stream = bp.TradingViewStream()
stream.connect()

# Önce chart'a abone ol
stream.subscribe_chart("THYAO", "1m")

# Pine gösterge ekle
stream.add_study("THYAO", "1m", "RSI")           # Varsayılan ayarlar
stream.add_study("THYAO", "1m", "RSI", length=7) # Custom period
stream.add_study("THYAO", "1m", "MACD")
stream.add_study("THYAO", "1m", "BB")            # Bollinger Bands

# Değerleri bekle ve al
rsi = stream.wait_for_study("THYAO", "1m", "RSI", timeout=10)
print(rsi['value'])  # 48.5

# Tüm göstergeleri al
studies = stream.get_studies("THYAO", "1m")
print(studies)
# {
#     'RSI': {'value': 48.5},
#     'MACD': {'macd': 3.2, 'signal': 2.8, 'histogram': 0.4},
#     'BB': {'upper': 296.8, 'middle': 285.0, 'lower': 273.2}
# }

# Callback ile real-time updates
def on_rsi_update(symbol, interval, indicator, values):
    print(f"{symbol} {indicator}: {values}")

stream.on_study("THYAO", "1m", "RSI", on_rsi_update)
stream.on_any_study(lambda s, i, n, v: print(f"{s} {n}: {v}"))

stream.disconnect()
```

### Desteklenen Pine Göstergeler

| Gösterge | TradingView ID | Outputs |
|----------|----------------|---------|
| RSI | `STD;RSI` | value |
| MACD | `STD;MACD` | macd, signal, histogram |
| BB/Bollinger | `STD;BB` | upper, middle, lower |
| EMA | `STD;EMA` | value |
| SMA | `STD;SMA` | value |
| Stochastic | `STD;Stochastic` | k, d |
| ATR | `STD;ATR` | value |
| ADX | `STD;ADX` | adx, plus_di, minus_di |
| OBV | `STD;OBV` | value |
| VWAP | `STD;VWAP` | value |
| Ichimoku | `STD;Ichimoku%Cloud` | conversion, base, span_a, span_b |
| Supertrend | `STD;Supertrend` | value, direction |
| Parabolic SAR | `STD;Parabolic%SAR` | value |
| CCI | `STD;CCI` | value |
| MFI | `STD;MFI` | value |

### Custom Indicator Kullanımı

TradingView auth ile custom/community göstergeler kullanabilirsiniz.

```python
import borsapy as bp

# TradingView auth ayarla
bp.set_tradingview_auth(
    session="sessionid_cookie",
    signature="sessionid_sign_cookie"
)

stream = bp.TradingViewStream()
stream.connect()
stream.subscribe_chart("THYAO", "1m")

# Public community indicator
stream.add_study("THYAO", "1m", "PUB;abc123")

# User's own indicator
stream.add_study("THYAO", "1m", "USER;xyz789")

values = stream.get_study("THYAO", "1m", "PUB;abc123")
```

---

## Inflation (Enflasyon)

TCMB enflasyon verileri.

```python
import borsapy as bp

enf = bp.Inflation()

# Son TÜFE verileri (Tüketici Fiyat Endeksi)
print(enf.latest())
print(enf.tufe())                   # TÜFE geçmişi

# ÜFE verileri (Üretici Fiyat Endeksi)
print(enf.ufe())

# Enflasyon hesaplayıcı
# 100.000 TL'nin 2020-01'den 2024-01'e değeri
sonuc = enf.calculate(100000, "2020-01", "2024-01")
print(sonuc)
```

---

## VIOP (Vadeli İşlem ve Opsiyon)

İş Yatırım üzerinden vadeli işlem ve opsiyon verileri.

### Temel Kullanım

```python
import borsapy as bp

viop = bp.VIOP()

# Tüm vadeli işlem kontratları
print(viop.futures)

# Tüm opsiyonlar
print(viop.options)

# Vadeli işlem alt kategorileri
print(viop.stock_futures)      # Pay vadeli
print(viop.index_futures)      # Endeks vadeli
print(viop.currency_futures)   # Döviz vadeli
print(viop.commodity_futures)  # Emtia vadeli

# Opsiyon alt kategorileri
print(viop.stock_options)      # Pay opsiyonları
print(viop.index_options)      # Endeks opsiyonları

# Sembol bazlı arama
print(viop.get_by_symbol("THYAO"))  # THYAO'nun tüm türevleri
```

### VIOP Kontrat Arama ve Listeleme

```python
import borsapy as bp

# Mevcut VIOP kontratlarını listele
contracts = bp.viop_contracts("XU030D")  # BIST30 vadeli kontratları
print(contracts)  # ['XU030DG2026', 'XU030DJ2026', ...]

# Altın vadeli kontratları (D eki yok)
gold_contracts = bp.viop_contracts("XAUTRY")
print(gold_contracts)  # ['XAUTRYG2026', 'XAUTRYJ2026', ...]

# VIOP sembol arama
bp.search_viop("XU030")    # ['XU030D', 'XU030DG2026', ...]
bp.search_viop("gold")     # Altın vadeli kontratları

# Detaylı kontrat bilgisi
contracts = bp.viop_contracts("XU030D", full_info=True)
# [
#     {'symbol': 'XU030DG2026', 'month_code': 'G', 'year': '2026', ...},
#     {'symbol': 'XU030DJ2026', 'month_code': 'J', 'year': '2026', ...},
# ]
```

### VIOP Gerçek Zamanlı Streaming

TradingView WebSocket ile vadeli kontratların gerçek zamanlı fiyatları.

```python
import borsapy as bp

stream = bp.TradingViewStream()
stream.connect()

# Vadeli kontrata abone ol (belirli vade)
stream.subscribe("XU030DG2026")      # BIST30 Şubat 2026
stream.subscribe("XAUTRYG2026")      # Altın TRY Şubat 2026
stream.subscribe("USDTRYG2026")      # Dolar TRY Şubat 2026

# Fiyat al
quote = stream.wait_for_quote("XU030DG2026", timeout=5)
print(f"BIST30 Vadeli: {quote['last']} TL, Değişim: {quote['change_percent']:.2f}%")

# Callback ile
def on_viop_update(symbol, quote):
    print(f"{symbol}: {quote['last']} TL, Vol: {quote['volume']}")

stream.on_quote("XU030DG2026", on_viop_update)

# Chart verileri (OHLCV)
stream.subscribe_chart("XU030DG2026", "1m")
candle = stream.wait_for_candle("XU030DG2026", "1m")
print(f"Open: {candle['open']}, Close: {candle['close']}")

stream.disconnect()
```

### VIOP Kontrat Formatı

Kontrat formatı: Base symbol + Month code + Year (örn: `XU030DG2026`)

**Ay Kodları:**

| Kod | Ay |
|-----|-----|
| F | Ocak |
| G | Şubat |
| H | Mart |
| J | Nisan |
| K | Mayıs |
| M | Haziran |
| N | Temmuz |
| Q | Ağustos |
| U | Eylül |
| V | Ekim |
| X | Kasım |
| Z | Aralık |

**Desteklenen VIOP Kontratları:**

| Tip | Örnek Base Symbol | Açıklama |
|-----|-------------------|----------|
| Endeks | `XU030D`, `XU100D`, `XLBNKD` | BIST endeks vadeli |
| Döviz | `USDTRYD`, `EURTRD` | Döviz vadeli |
| Altın | `XAUTRY`, `XAUUSD` | Altın vadeli (TRY/USD, D eki yok) |
| Hisse | `THYAOD`, `GARAND` | Pay vadeli |

> **Not**: Continuous kontratlar (`XU030D1!`) TradingView WebSocket'te çalışmıyor. Belirli vade kontratları kullanın (örn: `XU030DG2026`).

---

## Bond (Tahvil/Bono)

Türk devlet tahvili faiz oranları.

```python
import borsapy as bp

# Tüm tahvil faizleri
print(bp.bonds())
#                 name maturity   yield  change  change_pct
# 0   2 Yıllık Tahvil       2Y   26.42    0.40        1.54
# 1   5 Yıllık Tahvil       5Y   27.15    0.35        1.31
# 2  10 Yıllık Tahvil      10Y   28.03    0.42        1.52

# Tek tahvil
bond = bp.Bond("10Y")               # 2Y, 5Y, 10Y
print(bond.yield_rate)              # Faiz oranı (örn: 28.03)
print(bond.yield_decimal)           # Ondalık (örn: 0.2803)
print(bond.change_pct)              # Günlük değişim (%)
print(bond.info)                    # Tüm bilgiler

# Risk-free rate (DCF hesaplamaları için)
rfr = bp.risk_free_rate()           # 10Y faiz oranı (ondalık)
print(rfr)                          # 0.2803
```

---

## TCMB (Merkez Bankası Faiz Oranları)

TCMB politika faizi ve koridor oranları.

```python
import borsapy as bp

tcmb = bp.TCMB()

# Güncel oranlar
print(tcmb.policy_rate)             # 1 hafta repo faizi (%)
print(tcmb.overnight)               # {'borrowing': 36.5, 'lending': 41.0}
print(tcmb.late_liquidity)          # {'borrowing': 0.0, 'lending': 44.0}

# Tüm oranlar (DataFrame)
print(tcmb.rates)
#              type  borrowing  lending
# 0          policy        NaN     38.0
# 1       overnight       36.5     41.0
# 2  late_liquidity        0.0     44.0

# Geçmiş veriler
print(tcmb.history("policy"))           # 1 hafta repo geçmişi (2010+)
print(tcmb.history("overnight"))        # Gecelik faiz geçmişi
print(tcmb.history("late_liquidity", period="1y"))  # Son 1 yıl LON

# Kısa yol fonksiyonu
print(bp.policy_rate())             # Güncel politika faizi
```

### Desteklenen Oranlar

| Oran | Açıklama |
|------|----------|
| `policy_rate` | 1 hafta repo faizi (politika faizi) |
| `overnight` | Gecelik (O/N) koridor oranları (borrowing/lending) |
| `late_liquidity` | Geç likidite penceresi (LON) oranları |

---

## Eurobond (Türk Devlet Tahvilleri)

Yabancı para cinsinden (USD/EUR) Türk devlet tahvilleri.

```python
import borsapy as bp

# Tüm eurobondlar (38+ tahvil)
df = bp.eurobonds()
print(df)
#            isin   maturity  days_to_maturity currency  bid_price  bid_yield  ask_price  ask_yield
# 0  US900123DG28 2033-01-19              2562      USD     120.26       6.55     122.19       6.24
# ...

# Para birimine göre filtre
df_usd = bp.eurobonds(currency="USD")   # Sadece USD (34 tahvil)
df_eur = bp.eurobonds(currency="EUR")   # Sadece EUR (4 tahvil)

# Tek eurobond (ISIN ile)
bond = bp.Eurobond("US900123DG28")
print(bond.isin)                    # US900123DG28
print(bond.maturity)                # 2033-01-19
print(bond.currency)                # USD
print(bond.days_to_maturity)        # 2562
print(bond.bid_price)               # 120.26
print(bond.bid_yield)               # 6.55
print(bond.ask_price)               # 122.19
print(bond.ask_yield)               # 6.24
print(bond.info)                    # Tüm veriler (dict)
```

### Eurobond Verileri

| Alan | Açıklama |
|------|----------|
| `isin` | Uluslararası tahvil kimlik numarası |
| `maturity` | Vade tarihi |
| `days_to_maturity` | Vadeye kalan gün |
| `currency` | Para birimi (USD veya EUR) |
| `bid_price` | Alış fiyatı |
| `bid_yield` | Alış getirisi (%) |
| `ask_price` | Satış fiyatı |
| `ask_yield` | Satış getirisi (%) |

---

## EconomicCalendar (Ekonomik Takvim)

Ekonomik olaylar ve göstergeler.

```python
import borsapy as bp

cal = bp.EconomicCalendar()

# Bu haftanın olayları
df = cal.events(period="1w")
#         Date   Time  Country Importance                    Event   Actual Forecast Previous
# 0 2024-01-15  10:00  Türkiye       high     İşsizlik Oranı (Kas)     9.2%     9.3%     9.1%
# 1 2024-01-16  14:30      ABD       high  Perakende Satışlar (Ara)    0.6%     0.4%     0.3%

# Filtreleme
df = cal.events(period="1ay", country="TR")              # Sadece Türkiye
df = cal.events(period="1w", importance="high")          # Sadece önemli
df = cal.events(country="TR", importance="high")         # TR + önemli

# Kısayollar
df = cal.today()                    # Bugünkü olaylar
df = cal.this_week()                # Bu hafta
df = cal.this_month()               # Bu ay

# Fonksiyon olarak
df = bp.economic_calendar(period="1w", country="TR")

# Desteklenen ülkeler
# TR (Türkiye), US (ABD), EU (Euro Bölgesi), DE (Almanya),
# GB (İngiltere), JP (Japonya), CN (Çin)

# Önem seviyeleri: high, medium, low
```

---

## Screener (Hisse Tarama)

BIST hisselerini 40+ kritere göre filtreleme (İş Yatırım API).

### Hızlı Başlangıç

```python
import borsapy as bp

# Hazır şablonlar
df = bp.screen_stocks(template="high_dividend")    # Temettü verimi > %2
df = bp.screen_stocks(template="low_pe")           # F/K < 10
df = bp.screen_stocks(template="high_roe")         # ROE > %15
df = bp.screen_stocks(template="high_upside")      # Getiri potansiyeli > 0

# Doğrudan filtreler
df = bp.screen_stocks(pe_max=10)                   # F/K en fazla 10
df = bp.screen_stocks(dividend_yield_min=3)        # Temettü verimi min %3
df = bp.screen_stocks(roe_min=20, pb_max=2)        # ROE > %20, PD/DD < 2

# Sektör/endeks ile kombine
df = bp.screen_stocks(sector="Bankacılık", dividend_yield_min=3)
df = bp.screen_stocks(sector="Holding", pe_max=8)
```

### Mevcut Şablonlar

| Şablon | Açıklama | Kriter |
|--------|----------|--------|
| `small_cap` | Küçük şirketler | Piyasa değeri < ~43B TL |
| `mid_cap` | Orta boy şirketler | Piyasa değeri 43B-215B TL |
| `large_cap` | Büyük şirketler | Piyasa değeri > 215B TL |
| `high_dividend` | Yüksek temettü | Temettü verimi > %2 |
| `low_pe` | Düşük F/K | F/K < 10 |
| `high_roe` | Yüksek ROE | ROE > %15 |
| `high_upside` | Pozitif potansiyel | Getiri potansiyeli > 0 |
| `low_upside` | Negatif potansiyel | Getiri potansiyeli < 0 |
| `high_volume` | Yüksek hacim | 3 aylık hacim > $1M |
| `low_volume` | Düşük hacim | 3 aylık hacim < $0.5M |
| `high_net_margin` | Yüksek kar marjı | Net kar marjı > %10 |
| `high_return` | Haftalık artış | 1 hafta getiri > 0 |
| `high_foreign_ownership` | Yüksek yabancı oranı | Yabancı oranı > %30 |
| `buy_recommendation` | AL tavsiyesi | Analist tavsiyesi: AL |
| `sell_recommendation` | SAT tavsiyesi | Analist tavsiyesi: SAT |

### Fluent API (Gelişmiş Kullanım)

```python
screener = bp.Screener()

# Değerleme filtreleri
screener.add_filter("pe", max=15)                  # F/K < 15
screener.add_filter("pb", max=2)                   # PD/DD < 2
screener.add_filter("ev_ebitda", max=8)            # FD/FAVÖK < 8

# Temettü filtresi
screener.add_filter("dividend_yield", min=3)       # Temettü verimi > %3

# Karlılık filtreleri
screener.add_filter("roe", min=15)                 # ROE > %15
screener.add_filter("net_margin", min=10)          # Net kar marjı > %10

# Piyasa değeri (TL, milyon)
screener.add_filter("market_cap", min=10000)       # > 10 milyar TL

# Getiri filtreleri
screener.add_filter("return_1w", min=0)            # Haftalık getiri pozitif
screener.add_filter("return_1m", min=5)            # Aylık getiri > %5

# Sektör/endeks/tavsiye
screener.set_sector("Bankacılık")
screener.set_index("BIST 100")
screener.set_recommendation("AL")                  # AL, TUT, SAT

results = screener.run()
```

### Tüm Filtre Kriterleri

#### Fiyat ve Piyasa Değeri
| Kriter | Açıklama |
|--------|----------|
| `price` | Kapanış fiyatı (TL) |
| `market_cap` | Piyasa değeri (mn TL) |
| `market_cap_usd` | Piyasa değeri (mn $) |
| `float_ratio` | Halka açıklık oranı (%) |
| `float_market_cap` | Halka açık piyasa değeri (mn $) |

#### Değerleme Çarpanları
| Kriter | Açıklama |
|--------|----------|
| `pe` | Cari F/K (Fiyat/Kazanç) |
| `pb` | Cari PD/DD (Piyasa Değeri/Defter Değeri) |
| `ev_ebitda` | Cari FD/FAVÖK |
| `ev_sales` | Cari FD/Satışlar |
| `pe_2025` | 2025 tahmini F/K |
| `pb_2025` | 2025 tahmini PD/DD |
| `ev_ebitda_2025` | 2025 tahmini FD/FAVÖK |
| `pe_hist_avg` | Tarihsel ortalama F/K |
| `pb_hist_avg` | Tarihsel ortalama PD/DD |

#### Temettü
| Kriter | Açıklama |
|--------|----------|
| `dividend_yield` | 2024 temettü verimi (%) |
| `dividend_yield_2025` | 2025 tahmini temettü verimi (%) |
| `dividend_yield_5y_avg` | 5 yıllık ortalama temettü verimi (%) |

#### Karlılık
| Kriter | Açıklama |
|--------|----------|
| `roe` | Cari ROE (%) |
| `roa` | Cari ROA (%) |
| `net_margin` | 2025 net kar marjı (%) |
| `ebitda_margin` | 2025 FAVÖK marjı (%) |
| `roe_2025` | 2025 tahmini ROE |
| `roa_2025` | 2025 tahmini ROA |

#### Getiri (Relatif - Endekse Göre)
| Kriter | Açıklama |
|--------|----------|
| `return_1d` | 1 gün relatif getiri (%) |
| `return_1w` | 1 hafta relatif getiri (%) |
| `return_1m` | 1 ay relatif getiri (%) |
| `return_1y` | 1 yıl relatif getiri (%) |
| `return_ytd` | Yıl başından beri relatif getiri (%) |

#### Getiri (TL Bazlı)
| Kriter | Açıklama |
|--------|----------|
| `return_1d_tl` | 1 gün TL getiri (%) |
| `return_1w_tl` | 1 hafta TL getiri (%) |
| `return_1m_tl` | 1 ay TL getiri (%) |
| `return_1y_tl` | 1 yıl TL getiri (%) |
| `return_ytd_tl` | Yıl başından beri TL getiri (%) |

#### Hacim ve Likidite
| Kriter | Açıklama |
|--------|----------|
| `volume_3m` | 3 aylık ortalama hacim (mn $) |
| `volume_12m` | 12 aylık ortalama hacim (mn $) |

#### Yabancı ve Hedef Fiyat
| Kriter | Açıklama |
|--------|----------|
| `foreign_ratio` | Yabancı oranı (%) |
| `foreign_ratio_1w_change` | Yabancı oranı 1 haftalık değişim (baz puan) |
| `foreign_ratio_1m_change` | Yabancı oranı 1 aylık değişim (baz puan) |
| `target_price` | Hedef fiyat (TL) |
| `upside_potential` | Getiri potansiyeli (%) |

#### Endeks Ağırlıkları
| Kriter | Açıklama |
|--------|----------|
| `bist100_weight` | BIST 100 endeks ağırlığı |
| `bist50_weight` | BIST 50 endeks ağırlığı |
| `bist30_weight` | BIST 30 endeks ağırlığı |

### Örnek Stratejiler

```python
import borsapy as bp

# Değer Yatırımı: Düşük çarpanlar, yüksek temettü
screener = bp.Screener()
screener.add_filter("pe", max=10)
screener.add_filter("pb", max=1.5)
screener.add_filter("dividend_yield", min=4)
value_stocks = screener.run()

# Büyüme Yatırımı: Yüksek ROE, pozitif momentum
screener = bp.Screener()
screener.add_filter("roe", min=20)
screener.add_filter("return_1m", min=0)
screener.add_filter("market_cap", min=50000)  # Büyük şirketler (>50B TL)
growth_stocks = screener.run()

# Temettü Avcısı: Banka hisseleri, yüksek temettü
df = bp.screen_stocks(
    sector="Bankacılık",
    dividend_yield_min=5,
    pe_max=6
)

# Yabancı Takibi: Yabancıların ilgi gösterdiği hisseler
screener = bp.Screener()
screener.add_filter("foreign_ratio", min=40)
screener.add_filter("foreign_ratio_1m_change", min=1)  # Son 1 ayda artan
foreign_favorites = screener.run()

# Analist Favorileri: AL tavsiyeli, yüksek potansiyel
df = bp.screen_stocks(
    template="buy_recommendation",
    upside_potential_min=20
)
```

### Yardımcı Fonksiyonlar

```python
# Tüm filtre kriterleri (API'den)
print(bp.screener_criteria())
# [{'id': '7', 'name': 'Kapanış (TL)', 'min': '1.1', 'max': '14087.5'}, ...]

# Sektör listesi (53 sektör)
print(bp.sectors())
# ['Bankacılık', 'Holding ve Yatırım', 'Enerji', 'Gıda', ...]

# Endeks listesi
print(bp.stock_indices())
# ['BIST 30', 'BIST 50', 'BIST 100', 'BIST BANKA', ...]
```

### Çıktı Formatı

```python
df = bp.screen_stocks(template="high_dividend")
print(df.columns)
# Index(['symbol', 'name', 'criteria_7', 'criteria_33', ...], dtype='object')
#
# symbol: Hisse kodu (THYAO, GARAN, vb.)
# name: Şirket adı
# criteria_X: İlgili kriter değerleri (X = kriter ID)
```

---

## Şirket Listesi

BIST şirketlerini listeleme ve arama.

```python
import borsapy as bp

# Tüm şirketler
df = bp.companies()
print(df)

# Şirket arama
sonuc = bp.search_companies("banka")
print(sonuc)
```

---

## Veri Kaynakları

| Modül | Kaynak | Açıklama |
|-------|--------|----------|
| Ticker | İş Yatırım, TradingView, KAP, hedeffiyat.com.tr, isinturkiye.com.tr | Hisse verileri, finansallar, bildirimler, analist hedefleri, ISIN, ETF sahipliği |
| Index | TradingView, BIST | BIST endeksleri, bileşen listeleri |
| FX | canlidoviz.com, doviz.com, TradingView | 65 döviz, altın, emtia; banka/kurum kurları; intraday (TradingView) |
| Crypto | BtcTurk | Kripto para verileri |
| Fund | TEFAS | Yatırım fonu verileri, varlık dağılımı, tarama/karşılaştırma |
| Inflation | TCMB | Enflasyon verileri |
| VIOP | İş Yatırım, TradingView | Vadeli işlem/opsiyon; gerçek zamanlı streaming |
| Bond | doviz.com | Devlet tahvili faiz oranları (2Y, 5Y, 10Y) |
| TCMB | tcmb.gov.tr | Merkez Bankası faiz oranları (politika, gecelik, LON) |
| Eurobond | ziraatbank.com.tr | Türk devlet eurobondları (USD/EUR, 38+ tahvil) |
| EconomicCalendar | doviz.com | Ekonomik takvim (TR, US, EU, DE, GB, JP, CN) |
| Screener | İş Yatırım | Hisse tarama (İş Yatırım gelişmiş hisse arama) |
| TradingViewStream | TradingView WebSocket | Gerçek zamanlı fiyat, OHLCV, Pine Script göstergeleri |
| Search | TradingView | Sembol arama (hisse, döviz, kripto, endeks, vadeli) |
| Backtest | Yerel | Strateji backtesting engine |

---

## yfinance ile Karşılaştırma

### Ortak Özellikler
- `Ticker`, `Tickers` sınıfları
- `download()` fonksiyonu
- `info`, `history()`, finansal tablolar
- Temettü, split, kurumsal işlemler
- Analist hedefleri ve tavsiyeler

### borsapy'ye Özgü
- **TradingViewStream**: Gerçek zamanlı WebSocket streaming - quote, OHLCV, Pine Script göstergeleri
- **Backtest Engine**: Strateji backtesting framework - Sharpe, max drawdown, trade analizi
- **Replay Mode**: Backtesting için tarihsel candle-by-candle oynatma
- **Search**: TradingView sembol arama - hisse, döviz, kripto, endeks, vadeli
- **TA Signals**: TradingView teknik analiz sinyalleri - AL/SAT/TUT (11 oscillator + 17 MA)
- **Heikin Ashi**: Alternatif mum grafiği hesaplama
- **ETF Holders**: Uluslararası ETF'lerin hisse pozisyonları
- **Portfolio**: Çoklu varlık portföy yönetimi + risk metrikleri (Sharpe, Sortino, Beta, Alpha)
- **FX**: Döviz ve emtia verileri + banka kurları + intraday (TradingView)
- **Crypto**: Kripto para (BtcTurk)
- **Fund**: Yatırım fonları + varlık dağılımı + tarama/karşılaştırma (TEFAS)
- **Inflation**: Enflasyon verileri ve hesaplayıcı (TCMB)
- **VIOP**: Vadeli işlem/opsiyon + gerçek zamanlı streaming + kontrat arama
- **Bond**: Devlet tahvili faiz oranları + risk_free_rate (doviz.com)
- **TCMB**: Merkez Bankası faiz oranları - politika, gecelik, LON + geçmiş (tcmb.gov.tr)
- **Eurobond**: Türk devlet eurobondları - 38+ tahvil, USD/EUR (ziraatbank.com.tr)
- **EconomicCalendar**: Ekonomik takvim - 7 ülke desteği (doviz.com)
- **Screener**: Hisse tarama - 50+ kriter, sektör/endeks filtreleme (İş Yatırım)
- **Teknik Analiz**: 10+ gösterge (SMA, EMA, RSI, MACD, Bollinger, ATR, Stochastic, OBV, VWAP, ADX, Heikin Ashi)
- **KAP Entegrasyonu**: Resmi bildirimler ve takvim

---

## Katkıda Bulunma

Ek özellik istekleri ve öneriler için [GitHub Discussions](https://github.com/saidsurucu/borsapy/discussions) üzerinden tartışma açabilirsiniz.

---

## Sorumluluk Reddi

Bu kütüphane aracılığıyla erişilen veriler, ilgili veri kaynaklarına aittir:
- **İş Yatırım** (isyatirim.com.tr): Finansal tablolar, hisse tarama, VIOP
- **TradingView** (tradingview.com): Hisse OHLCV, endeksler, gerçek zamanlı streaming, teknik analiz sinyalleri, sembol arama, ETF sahipliği
- **KAP** (kap.org.tr): Şirket bildirimleri, ortaklık yapısı
- **TCMB** (tcmb.gov.tr): Enflasyon verileri, merkez bankası faiz oranları
- **BtcTurk**: Kripto para verileri
- **TEFAS** (tefas.gov.tr): Yatırım fonu verileri
- **doviz.com**: Döviz kurları, banka kurları, ekonomik takvim, tahvil faizleri
- **canlidoviz.com**: Döviz kurları, emtia fiyatları
- **Ziraat Bankası** (ziraatbank.com.tr): Eurobond verileri
- **hedeffiyat.com.tr**: Analist hedef fiyatları
- **isinturkiye.com.tr**: ISIN kodları

Kütüphane yalnızca kişisel kullanım amacıyla hazırlanmıştır ve veriler ticari amaçlarla kullanılamaz.

---

## Lisans

Apache 2.0
