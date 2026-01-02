# borsapy

Türk finansal piyasaları için Python veri kütüphanesi. BIST hisseleri, döviz, kripto, yatırım fonları ve ekonomik veriler için yfinance benzeri API.

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

# Farklı zaman dilimleri
df = hisse.history(period="5g", interval="1sa")  # 5 gün, saatlik
df = hisse.history(period="1ay", interval="1g")  # 1 ay, günlük
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

### Altın ve Emtialar

```python
# Altın
gram_altin = bp.FX("gram-altin")
ceyrek = bp.FX("ceyrek-altin")
yarim = bp.FX("yarim-altin")
tam = bp.FX("tam-altin")
cumhuriyet = bp.FX("cumhuriyet-altini")

# Gümüş
gumus = bp.FX("gumus")

print(gram_altin.current)
print(gram_altin.history(period="1ay"))
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
| FX | doviz.com | Döviz kurları, altın, emtia |
| Crypto | BtcTurk | Kripto para verileri |
| Fund | TEFAS | Yatırım fonu verileri |
| Inflation | TCMB | Enflasyon verileri |
| VIOP | İş Yatırım | Vadeli işlem ve opsiyon |

---

## yfinance ile Karşılaştırma

### Ortak Özellikler
- `Ticker`, `Tickers` sınıfları
- `download()` fonksiyonu
- `info`, `history()`, finansal tablolar
- Temettü, split, kurumsal işlemler
- Analist hedefleri ve tavsiyeler

### borsapy'ye Özgü
- **FX**: Döviz ve emtia verileri (doviz.com)
- **Crypto**: Kripto para (BtcTurk)
- **Fund**: Yatırım fonları (TEFAS)
- **Inflation**: Enflasyon verileri ve hesaplayıcı (TCMB)
- **VIOP**: Vadeli işlem ve opsiyon
- **KAP Entegrasyonu**: Resmi bildirimler ve takvim

---

## Katkıda Bulunma

Ek özellik istekleri ve öneriler için [GitHub Discussions](https://github.com/saidsurucu/borsapy/discussions) üzerinden tartışma açabilirsiniz.

---

## Lisans

Apache 2.0
