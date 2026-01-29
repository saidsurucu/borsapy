# borsapy CLI

Türk finansal piyasaları için komut satırı arayüzü.

## Kurulum

```bash
pip install borsapy
```

Kurulum sonrası `borsapy` komutu kullanılabilir:

```bash
borsapy --help
```

## Hızlı Başlangıç

```bash
# Fiyat sorgula
borsapy price THYAO

# Geçmiş veriler
borsapy history THYAO --period 1y --output csv > thyao.csv

# Teknik sinyaller
borsapy signals THYAO

# Canlı izleme
borsapy watch THYAO GARAN ASELS
```

---

## Komutlar

### Fiyat ve Piyasa Verileri

| Komut | Açıklama | Örnek |
|-------|----------|-------|
| `price` | Hızlı fiyat sorgulama | `borsapy price THYAO GARAN` |
| `quote` | Detaylı kotasyon | `borsapy quote THYAO` |
| `history` | OHLCV geçmiş verileri | `borsapy history THYAO --period 1y` |
| `watch` | Canlı fiyat izleme | `borsapy watch THYAO --interval 0.5` |

### Teknik Analiz

| Komut | Açıklama | Örnek |
|-------|----------|-------|
| `technical` | Teknik göstergeler | `borsapy technical THYAO` |
| `signals` | TradingView TA sinyalleri | `borsapy signals THYAO --interval 1h` |
| `scan` | Teknik tarama | `borsapy scan "rsi < 30" --index XU030` |

### Temel Analiz

| Komut | Açıklama | Örnek |
|-------|----------|-------|
| `financials` | Mali tablolar | `borsapy financials THYAO --balance` |
| `holders` | Hissedar bilgileri | `borsapy holders THYAO --etf` |
| `targets` | Analist hedef fiyatları | `borsapy targets THYAO` |
| `dividends` | Temettü geçmişi | `borsapy dividends THYAO` |
| `splits` | Sermaye artırımları | `borsapy splits KAYSE` |
| `news` | KAP bildirimleri | `borsapy news THYAO` |

### Tarama ve Karşılaştırma

| Komut | Açıklama | Örnek |
|-------|----------|-------|
| `screen` | Temel tarama | `borsapy screen --template high_dividend` |
| `scan` | Teknik tarama | `borsapy scan "macd > signal"` |
| `compare` | Hisse karşılaştırma | `borsapy compare THYAO PGSUS TAVHL` |
| `search` | Sembol arama | `borsapy search banka` |

### Endeks ve Şirketler

| Komut | Açıklama | Örnek |
|-------|----------|-------|
| `index` | Endeks bileşenleri | `borsapy index XU030` |
| `companies` | BIST şirketleri | `borsapy companies --search THY` |

### Döviz ve Emtia

| Komut | Açıklama | Örnek |
|-------|----------|-------|
| `fx-rates` | Banka/kurum kurları | `borsapy fx-rates USD` |

### Faiz ve Tahvil

| Komut | Açıklama | Örnek |
|-------|----------|-------|
| `bonds` | Devlet tahvili faizleri | `borsapy bonds 10Y` |
| `eurobond` | Eurobond verileri | `borsapy eurobond --currency USD` |
| `tcmb` | TCMB faiz oranları | `borsapy tcmb --history` |

### Yatırım Fonları

| Komut | Açıklama | Örnek |
|-------|----------|-------|
| `fund` | TEFAS fon verileri | `borsapy fund YAY --allocation` |

### Vadeli İşlemler

| Komut | Açıklama | Örnek |
|-------|----------|-------|
| `viop` | VİOP kontratları | `borsapy viop XU030D` |

### Ekonomi

| Komut | Açıklama | Örnek |
|-------|----------|-------|
| `economic` | Ekonomik takvim | `borsapy economic --country TR` |
| `inflation` | Enflasyon verileri | `borsapy inflation --history` |

### Kimlik Doğrulama

| Komut | Açıklama | Örnek |
|-------|----------|-------|
| `auth login` | TradingView girişi | `borsapy auth login` |
| `auth logout` | Çıkış | `borsapy auth logout` |
| `auth status` | Durum kontrolü | `borsapy auth status` |

---

## Komut Detayları

### price - Hızlı Fiyat Sorgulama

```bash
borsapy price THYAO
borsapy price THYAO GARAN ASELS
borsapy price USD EUR --type fx
borsapy price BTCTRY --type crypto
borsapy price THYAO -o json
```

**Seçenekler:**
- `--type, -t`: Varlık tipi (`stock`, `fx`, `crypto`, `fund`)
- `--output, -o`: Çıktı formatı (`table`, `json`, `csv`)

---

### quote - Detaylı Kotasyon

```bash
borsapy quote THYAO
borsapy quote USD --type fx
borsapy quote BTCTRY --type crypto
borsapy quote YAY --type fund
```

Fiyat, değişim, hacim, piyasa değeri, F/K, F/DD, temettü verimi, 52 haftalık aralık gibi detaylı bilgiler gösterir.

---

### history - Geçmiş Veriler

```bash
borsapy history THYAO
borsapy history THYAO --period 1y --interval 1d
borsapy history THYAO --period 5d --interval 1h
borsapy history THYAO --actions              # Temettü ve bölünmeler dahil
borsapy history THYAO -o csv > data.csv      # CSV'ye kaydet
```

**Seçenekler:**
- `--period, -p`: Dönem (`1d`, `5d`, `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `max`)
- `--interval, -i`: Aralık (`1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1wk`, `1mo`)
- `--actions, -a`: Temettü ve bölünmeleri dahil et
- `--type, -t`: Varlık tipi
- `--output, -o`: Çıktı formatı

---

### watch - Canlı İzleme

```bash
borsapy watch THYAO GARAN ASELS
borsapy watch THYAO --interval 0.5
borsapy watch THYAO GARAN --duration 60
```

TradingView WebSocket üzerinden canlı fiyat izleme. Ctrl+C ile durdurulur.

**Seçenekler:**
- `--interval, -i`: Güncelleme aralığı (saniye, varsayılan: 1.0)
- `--duration, -d`: Süre (saniye, belirtilmezse sınırsız)

---

### technical - Teknik Göstergeler

```bash
borsapy technical THYAO
borsapy technical THYAO -i rsi -i macd
borsapy technical THYAO -i bollinger --period 6mo
borsapy technical USD --type fx
```

**Desteklenen Göstergeler:**
- `rsi` - RSI (14)
- `sma` - SMA (20)
- `ema` - EMA (12)
- `macd` - MACD (12, 26, 9)
- `bollinger` - Bollinger Bantları (20, 2)
- `stochastic` - Stokastik (14, 3)
- `atr` - ATR (14)
- `adx` - ADX (14)
- `obv` - OBV
- `vwap` - VWAP
- `supertrend` - Supertrend (10, 3)

---

### signals - TradingView Sinyalleri

```bash
borsapy signals THYAO
borsapy signals THYAO --interval 1h
borsapy signals THYAO --all              # Tüm zaman dilimleri
borsapy signals THYAO --detail           # Oscillator ve MA detayları
```

TradingView Scanner API'den BUY/SELL/NEUTRAL sinyalleri.

**Seçenekler:**
- `--interval, -i`: Zaman dilimi (`1m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `1d`, `1W`, `1M`)
- `--all, -a`: Tüm zaman dilimleri için sinyal
- `--detail, -d`: Oscillator ve MA detayları
- `--type, -t`: Varlık tipi

---

### scan - Teknik Tarama

```bash
borsapy scan "rsi < 30" --index XU030
borsapy scan "close > sma_50" --index XU100
borsapy scan "rsi < 30 and volume > 1000000"
borsapy scan "macd > signal" --interval 1h
borsapy scan "sma_20 crosses_above sma_50"
```

TradingView Scanner API ile teknik koşullara göre tarama.

**Desteklenen Alanlar:**
- Fiyat: `price`, `close`, `open`, `high`, `low`, `volume`, `change_percent`, `market_cap`
- RSI: `rsi`, `rsi_7`, `rsi_14`
- SMA: `sma_5`, `sma_10`, `sma_20`, `sma_50`, `sma_100`, `sma_200`
- EMA: `ema_5`, `ema_10`, `ema_12`, `ema_20`, `ema_26`, `ema_50`, `ema_100`, `ema_200`
- MACD: `macd`, `signal`, `histogram`
- Stokastik: `stoch_k`, `stoch_d`
- Diğer: `adx`, `bb_upper`, `bb_middle`, `bb_lower`, `atr`, `cci`, `wr`

**Operatörler:**
- Karşılaştırma: `<`, `>`, `<=`, `>=`, `==`
- Mantıksal: `and`, `or`
- Kesişim: `crosses_above`, `crosses_below`, `crosses`
- Yüzde: `above_pct`, `below_pct`

---

### financials - Mali Tablolar

```bash
borsapy financials THYAO                    # Tümü
borsapy financials THYAO --balance          # Bilanço
borsapy financials THYAO --income           # Gelir tablosu
borsapy financials THYAO --cashflow         # Nakit akışı
borsapy financials THYAO --quarterly        # Çeyreklik
borsapy financials THYAO --ttm              # Son 12 ay
borsapy financials AKBNK --group UFRS       # Banka formatı
borsapy financials THYAO -b -q -n 8         # Son 8 çeyrek bilanço
```

**Seçenekler:**
- `--balance, -b`: Bilanço
- `--income, -i`: Gelir tablosu
- `--cashflow, -c`: Nakit akışı
- `--quarterly, -q`: Çeyreklik veri
- `--ttm, -t`: Trailing 12 months
- `--group, -g`: Mali tablo grubu (`XI_29` sınai, `UFRS` banka)
- `--limit, -n`: Dönem sayısı (varsayılan: 4)

---

### holders - Hissedar Bilgileri

```bash
borsapy holders THYAO                 # Ana hissedarlar
borsapy holders ASELS --etf           # ETF sahipleri
borsapy holders THYAO --etf -n 10     # İlk 10 ETF
```

**Seçenekler:**
- `--etf, -e`: ETF sahiplerini göster
- `--limit, -n`: Sonuç limiti (varsayılan: 20)

---

### targets - Analist Hedefleri

```bash
borsapy targets THYAO                    # Hedef fiyat özeti
borsapy targets THYAO --recommendations  # AL/TUT/SAT tavsiyesi
borsapy targets THYAO --summary          # Analist dağılımı
```

**Seçenekler:**
- `--recommendations, -r`: Tavsiye göster
- `--summary, -s`: Özet dağılım

---

### screen - Temel Tarama

```bash
borsapy screen --template high_dividend
borsapy screen --template buy_recommendation --index XU030
borsapy screen --pe-max 10 --div-min 3
borsapy screen --sector Bankacılık --roe-min 15
borsapy screen --rec AL --mcap-min 1000
```

**Şablonlar:**
- Büyüklük: `small_cap`, `mid_cap`, `large_cap`
- Değer: `high_dividend`, `low_pe`, `high_roe`
- Momentum: `high_upside`, `low_upside`, `high_return`
- Hacim: `high_volume`, `low_volume`
- Analist: `buy_recommendation`, `sell_recommendation`

**Filtreler:**
- `--sector, -s`: Sektör
- `--index, -x`: Endeks
- `--rec, -r`: Tavsiye (`AL`, `SAT`, `TUT`)
- `--mcap-min/max`: Piyasa değeri (milyon TL)
- `--pe-min/max`: F/K oranı
- `--pb-min/max`: F/DD oranı
- `--div-min`: Min temettü verimi (%)
- `--roe-min`: Min özkaynak karlılığı (%)
- `--upside-min`: Min yükseliş potansiyeli (%)
- `--foreign-min`: Min yabancı oranı (%)

---

### index - Endeks Bilgileri

```bash
borsapy index XU030                   # Endeks bilgisi ve bileşenler
borsapy index XU100 --symbols         # Sadece semboller
borsapy index --list                  # Popüler endeksler
borsapy index --all                   # Tüm endeksler (79)
```

**Seçenekler:**
- `--symbols, -s`: Sadece sembol listesi
- `--list, -l`: Popüler endeks listesi
- `--all, -a`: Tüm BIST endeksleri

---

### fx-rates - Banka/Kurum Kurları

```bash
borsapy fx-rates USD                      # Tüm banka USD kurları
borsapy fx-rates EUR --bank akbank        # Akbank EUR kuru
borsapy fx-rates gram-altin               # Altın fiyatları
borsapy fx-rates gram-gumus --institution kapalicarsi
borsapy fx-rates --banks                  # Banka listesi
borsapy fx-rates --institutions           # Kurum listesi
```

**Desteklenen Varlıklar:**
- Döviz: USD, EUR, GBP, CHF, JPY, CAD, AUD + 58 diğer
- Metal: `gram-altin`, `gram-gumus`, `ons-altin`, `gram-platin`, `gram-paladyum`

---

### viop - VİOP Kontratları

```bash
borsapy viop XU030D                   # BIST30 vadeli kontratları
borsapy viop XAUTRY                   # Altın vadeli
borsapy viop XU030D --detail          # Detaylı bilgi
borsapy viop --search gold            # VIOP sembol arama
```

**Kontrat Formatı:** Base + Ay Kodu + Yıl (örn: `XU030DG2026`)

**Ay Kodları:** F=Oca, G=Şub, H=Mar, J=Nis, K=May, M=Haz, N=Tem, Q=Ağu, U=Eyl, V=Eki, X=Kas, Z=Ara

---

### fund - Yatırım Fonları

```bash
borsapy fund YAY                      # Fon bilgisi
borsapy fund YAY --allocation         # Varlık dağılımı
borsapy fund YAY --risk               # Risk metrikleri
borsapy fund --screen --type YAT --min-return-1y 50
borsapy fund --compare YAY TTE AFO
```

**Seçenekler:**
- `--allocation, -a`: Varlık dağılımı
- `--risk, -r`: Risk metrikleri (Sharpe, Sortino, max drawdown)
- `--screen`: Fon tarama
- `--compare, -c`: Fon karşılaştırma
- `--type, -t`: Fon tipi (`YAT` yatırım, `EMK` emeklilik)
- `--min-return-1y`: Min 1 yıllık getiri

---

### bonds - Tahvil Faizleri

```bash
borsapy bonds                         # Tüm tahviller
borsapy bonds 10Y                     # 10 yıllık tahvil
borsapy bonds --risk-free             # Risksiz faiz (DCF için)
```

**Vadeler:** `2Y`, `5Y`, `10Y`

---

### eurobond - Eurobond Verileri

```bash
borsapy eurobond                      # Tüm eurobondlar
borsapy eurobond US900123DG28         # Tek eurobond
borsapy eurobond --currency USD       # Sadece USD
borsapy eurobond --currency EUR       # Sadece EUR
```

---

### tcmb - TCMB Faiz Oranları

```bash
borsapy tcmb                          # Güncel oranlar
borsapy tcmb --type overnight         # Gecelik faiz
borsapy tcmb --history                # Politika faizi geçmişi
borsapy tcmb --history -t overnight   # Gecelik faiz geçmişi
```

**Faiz Tipleri:**
- `policy`: 1 hafta repo (politika faizi)
- `overnight`: Gecelik borçlanma/borç verme
- `late_liquidity`: Geç likidite penceresi

---

### economic - Ekonomik Takvim

```bash
borsapy economic
borsapy economic --period today
borsapy economic --country TR
borsapy economic --importance high
borsapy economic --country TR --importance high
```

**Seçenekler:**
- `--period, -p`: Dönem (`today`, `1d`, `1w`, `1mo`)
- `--country, -c`: Ülke (TR, US, EU, vb.)
- `--importance, -i`: Önem (`high`, `medium`, `low`)

---

### inflation - Enflasyon Verileri

```bash
borsapy inflation                              # Son TÜFE/ÜFE
borsapy inflation 100000 -s 2020-01 -e 2024-01 # Hesaplama
borsapy inflation --history                    # Son 12 ay
borsapy inflation --history -l 24              # Son 24 ay
borsapy inflation --history --type ufe         # ÜFE geçmişi
```

**Seçenekler:**
- `--start, -s`: Başlangıç tarihi (YYYY-MM)
- `--end, -e`: Bitiş tarihi (YYYY-MM)
- `--history, -h`: Geçmiş veriler
- `--type, -t`: Enflasyon tipi (`tufe`, `ufe`)
- `--limit, -l`: Geçmiş satır sayısı

---

## Çıktı Formatları

Tüm komutlar `--output` veya `-o` ile çıktı formatı belirleyebilir:

| Format | Açıklama | Kullanım |
|--------|----------|----------|
| `table` | Renkli terminal tablosu (varsayılan) | `-o table` |
| `json` | JSON formatı | `-o json` |
| `csv` | CSV formatı | `-o csv` |

```bash
# JSON çıktısı
borsapy price THYAO -o json

# CSV'ye kaydet
borsapy history THYAO --period 1y -o csv > thyao.csv

# jq ile işle
borsapy quote THYAO -o json | jq '.last'
```

---

## TradingView Kimlik Doğrulama

TradingView verileri varsayılan olarak ~15 dakika gecikmeli. Gerçek zamanlı veri için:

### Giriş Yöntemleri

```bash
# Kullanıcı adı/şifre ile
borsapy auth login -u email@example.com -p password

# Session cookie ile
borsapy auth login -s sessionid --session-sign signature

# İnteraktif (şifreyi gizli girer)
borsapy auth login
```

### Cookie Alma

1. tradingview.com'a giriş yapın
2. Geliştirici Araçları (F12) → Application → Cookies
3. `sessionid` ve `sessionid_sign` değerlerini kopyalayın

### Durum Kontrolü

```bash
borsapy auth status
borsapy auth logout
```

---

## Varlık Tipleri

Birçok komut otomatik varlık tipi algılar, ancak `--type` ile belirtilebilir:

| Tip | Açıklama | Örnekler |
|-----|----------|----------|
| `stock` | BIST hisseleri (varsayılan) | THYAO, GARAN, ASELS |
| `fx` | Döviz ve emtia | USD, EUR, gram-altin |
| `crypto` | Kripto paralar | BTCTRY, ETHTRY |
| `fund` | TEFAS fonları | YAY, TTE, AAK |

```bash
borsapy price USD --type fx
borsapy quote BTCTRY --type crypto
borsapy history YAY --type fund
```

---

## Endeksler

Tarama ve filtreleme için kullanılabilir endeksler:

| Endeks | Açıklama |
|--------|----------|
| `XU030` | BIST 30 |
| `XU100` | BIST 100 |
| `XK030` | Katılım 30 |
| `XBANK` | Banka |
| `XUSIN` | Sınai |
| `XHOLD` | Holding |
| `XUTEK` | Teknoloji |

Tüm endeksler için: `borsapy index --all`

---

## Örnekler

### Günlük Analiz Workflow

```bash
# Piyasa özeti
borsapy index XU030
borsapy economic --period today --country TR

# Portföy takibi
borsapy watch THYAO GARAN ASELS AKBNK

# Fırsat tarama
borsapy scan "rsi < 30" --index XU100
borsapy screen --template high_dividend --index XU030
```

### Veri Dışa Aktarma

```bash
# Hisse geçmişi
borsapy history THYAO --period 5y -o csv > thyao_5y.csv

# Endeks bileşenleri
borsapy index XU100 --symbols -o json > xu100.json

# Mali tablolar
borsapy financials THYAO -o json > thyao_financials.json
```

### Analiz Zincirleme

```bash
# Düşük F/K ve yüksek temettü
borsapy screen --pe-max 8 --div-min 4 --index XU100

# Oversold + yüksek hacim
borsapy scan "rsi < 25 and volume > 5000000"

# Analist favorileri
borsapy screen --rec AL --upside-min 30
```

---

## Hata Ayıklama

Komut çalışmıyorsa:

```bash
# Versiyon kontrolü
borsapy --version

# Yardım
borsapy --help
borsapy <komut> --help

# Auth durumu
borsapy auth status
```

Yaygın sorunlar:

- **Veri yok**: TradingView auth gerekebilir
- **Timeout**: İnternet bağlantısı veya API erişimi
- **Bilinmeyen sembol**: `borsapy search <query>` ile kontrol edin
