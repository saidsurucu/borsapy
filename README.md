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
# Yıllık tablolar
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
```

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

BIST endekslerine erişim.

```python
import borsapy as bp

# Mevcut endeksler
print(bp.indices())

# Endeks verisi
xu100 = bp.Index("XU100")
print(xu100.history(period="1ay"))
```

---

## FX (Döviz ve Emtia)

Döviz kurları ve emtia fiyatları.

### Döviz Kurları

```python
import borsapy as bp

usd = bp.FX("USD")
print(usd.current)                  # Güncel kur
print(usd.history(period="1ay"))    # Geçmiş veriler

# Diğer dövizler
eur = bp.FX("EUR")
gbp = bp.FX("GBP")
chf = bp.FX("CHF")
```

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
# Altın
gram_altin = bp.FX("gram-altin")
ceyrek = bp.FX("ceyrek-altin")
yarim = bp.FX("yarim-altin")
tam = bp.FX("tam-altin")
cumhuriyet = bp.FX("cumhuriyet-altini")

# Diğer değerli metaller
gumus = bp.FX("gram-gumus")
ons_altin = bp.FX("ons-altin")
platin = bp.FX("gram-platin")
paladyum = bp.FX("gram-paladyum")

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
# ['gram-altin', 'gram-gumus', 'ons-altin', 'gram-platin', 'gram-paladyum']
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
| Ticker | İş Yatırım, Paratic, KAP, hedeffiyat.com.tr, isinturkiye.com.tr | Hisse verileri, finansallar, bildirimler, analist hedefleri, ISIN |
| Index | Paratic | BIST endeksleri |
| FX | doviz.com | Döviz kurları, altın, emtia, banka kurları |
| Crypto | BtcTurk | Kripto para verileri |
| Fund | TEFAS | Yatırım fonu verileri, varlık dağılımı, tarama/karşılaştırma |
| Inflation | TCMB | Enflasyon verileri |
| VIOP | İş Yatırım | Vadeli işlem ve opsiyon |
| Bond | doviz.com | Devlet tahvili faiz oranları (2Y, 5Y, 10Y) |
| EconomicCalendar | doviz.com | Ekonomik takvim (TR, US, EU, DE, GB, JP, CN) |
| Screener | İş Yatırım | Hisse tarama (İş Yatırım gelişmiş hisse arama) |

---

## yfinance ile Karşılaştırma

### Ortak Özellikler
- `Ticker`, `Tickers` sınıfları
- `download()` fonksiyonu
- `info`, `history()`, finansal tablolar
- Temettü, split, kurumsal işlemler
- Analist hedefleri ve tavsiyeler

### borsapy'ye Özgü
- **FX**: Döviz ve emtia verileri + banka kurları (doviz.com)
- **Crypto**: Kripto para (BtcTurk)
- **Fund**: Yatırım fonları + varlık dağılımı + tarama/karşılaştırma (TEFAS)
- **Inflation**: Enflasyon verileri ve hesaplayıcı (TCMB)
- **VIOP**: Vadeli işlem ve opsiyon (İş Yatırım)
- **Bond**: Devlet tahvili faiz oranları + risk_free_rate (doviz.com)
- **EconomicCalendar**: Ekonomik takvim - 7 ülke desteği (doviz.com)
- **Screener**: Hisse tarama - 50+ kriter, sektör/endeks filtreleme (İş Yatırım)
- **KAP Entegrasyonu**: Resmi bildirimler ve takvim

---

## Katkıda Bulunma

Ek özellik istekleri ve öneriler için [GitHub Discussions](https://github.com/saidsurucu/borsapy/discussions) üzerinden tartışma açabilirsiniz.

---

## Sorumluluk Reddi

Bu kütüphane aracılığıyla erişilen veriler, ilgili veri kaynaklarına aittir:
- **İş Yatırım** (isyatirim.com.tr): Finansal tablolar, hisse tarama, VIOP
- **Paratic** (paratic.com): Hisse OHLCV, endeksler
- **KAP** (kap.org.tr): Şirket bildirimleri, ortaklık yapısı
- **TCMB**: Enflasyon verileri
- **BtcTurk**: Kripto para verileri
- **TEFAS** (tefas.gov.tr): Yatırım fonu verileri
- **doviz.com**: Döviz kurları, banka kurları, ekonomik takvim, tahvil faizleri
- **hedeffiyat.com.tr**: Analist hedef fiyatları
- **isinturkiye.com.tr**: ISIN kodları

Kütüphane yalnızca kişisel kullanım amacıyla hazırlanmıştır ve veriler ticari amaçlarla kullanılamaz.

---

## Lisans

Apache 2.0
