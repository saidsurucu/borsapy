# borsapy - Project Instructions

## Overview
borsapy is a yfinance-like Python library for Turkish financial markets data.
**CRITICAL**: No yfinance dependency - all data comes from local Turkish sources.

---

## Changelog

### v0.10.0 (2026-05-04)

**Yeni modül**: TCMB EVDS3 (Elektronik Veri Dağıtım Sistemi) wrapper.
**Veri çekme için ücretsiz EVDS API key zorunlu** (https://evds3.tcmb.gov.tr → BENİM SAYFAM → Kayıt Ol).

#### Context

TCMB, EVDS sistemini 2025 sonunda **evds3.tcmb.gov.tr**'ye taşıdı ve eski
**evds2.tcmb.gov.tr** REST API'sini (`/service/evds/?key=...`) tamamen
kapattı — tüm istekler v3 SPA HTML'ine 302 redirect oluyor. Bu PyPI'daki
`evds`, `evdsAPI` benzeri tüm Python paketlerini kırdı. v3 backend'i
`/igmevdsms-dis/...` prefix'inde yeni endpoint'ler sunuyor; resmi REST
yolunun (key gerektirir) yanı sıra anonim katalog endpoint'leri de var.

EVDS Türkiye'nin tek resmi makro veri kaynağı (faiz, döviz, enflasyon,
ödemeler dengesi, para arzı, reel sektör, bekleyiş anketleri vs); borsapy
bu boşluğu doldurur. Mevcut `Inflation` ve `TCMB` sınıfları yan yana çalışmaya
devam eder (geriye uyumluluk).

#### New Features

- **`bp.EVDS()` sınıfı**: 145 kategori → on binlerce seri için tam katalog
  navigasyonu, arama, dashboard'lar, Excel export.
  ```python
  import borsapy as bp

  ev = bp.EVDS()
  ev.categories                       # 145 kategori (DataFrame)
  ev.datagroups(category_id=400401)   # Kısa Vadeli Dış Borç → 6 datagroup
  ev.series_in_group("bie_dkdovizgn") # Günlük döviz → 137 seri
  ev.search("dolar")                  # Kategori/datagroup'larda arama
  ev.dashboard("baslica-gostergeler") # 9-chart "Başlıca Göstergeler"
  ```

- **`bp.EVDSSeries('TP.DK.USD.A')`**: yfinance.Ticker benzeri seri sarmalayıcı.
  ```python
  usd = ev.series("TP.DK.USD.A")
  usd.info               # SERIE_NAME, FREQUENCY_STR, BIRIMI, DATAGROUP_CODE
  usd.range              # (start_date, end_date)
  usd.history(period="1y")
  ```

- **Modül-seviye shortcut'lar** (yfinance benzeri tek satır):
  ```python
  bp.evds_series("TP.DK.USD.A", period="1y")                # tek seri
  bp.evds_series("TP.FG.J0", period="3y", formula="yoy_pct") # TÜFE yıllık
  bp.evds_download(["TP.DK.USD.A", "TP.DK.EUR.A"], period="1mo")  # çoklu
  bp.evds_categories()                                       # 145 kategori
  bp.evds_search("kur", scope="datagroups")                  # arama
  ```

- **API Key Yönetimi**: Veri çekme için ücretsiz API key (TCMB →
  https://evds3.tcmb.gov.tr → BENİM SAYFAM → Kayıt Ol).
  ```python
  bp.set_evds_key("YOUR_API_KEY")
  # veya: export EVDS_API_KEY="..."
  bp.get_evds_key()
  bp.clear_evds_key()
  ```

#### Architecture (v3 Backend Reverse Engineering)

İki paralel API katmanı:

| Endpoint | Method | Auth | Durum |
|----------|--------|------|-------|
| `/?series=A-B-C&startDate=...&type=json&...` | GET | API key | ✅ asıl veri |
| `/categories/withDatagroups/type=json` | GET | anonim | ✅ |
| `/serieList/fe/type=json&code=X` | GET | anonim | ✅ |
| `/dashboards/{slug}` | GET | anonim | ✅ |
| `/genel-ayarlar?key=X` | GET | anonim | ✅ |
| `/announcements` | GET | anonim | ✅ |
| `/serieList/baslangicBitis` | POST | session cookie | ✅ |
| ~~`/fe`~~ | ~~POST~~ | ~~session cookie~~ | ❌ kaldırıldı |
| ~~`/fe/excel-indir`~~ | ~~POST~~ | ~~session cookie~~ | ❌ kaldırıldı |

- **Sistem limitleri**: `MAX_SERIE_COUNT=400`, `MAX_GRID_COUNT=900`
- **Series kodu**: kullanıcıdan dot-form (`TP.DK.USD.A`), backend underscore
  (`TP_DK_USD_A`) — provider otomatik dönüştürür
- **Tarih formatı**: DD-MM-YYYY (provider YYYY-MM-DD'i de kabul eder)
- **Frequency enum**: snake_case (`"daily"|"monthly"|...`) → backend integer
  (1=DAY, 5=MONTH, 8=YEAR). Bundle JS'sinden çıkarıldı:
  `[1,"Date"],[2,"WORKDAY"],[5,"MONTH"],[6,"QUARTER"],[8,"YEAR"]`
- **Aggregation**: `avg|min|max|first|last|sum`
- **Formula**: `level|pct_change|diff|yoy_pct|yoy_diff|moving_avg|...`

#### Veri Çekme Yolu (sadece REST GET)

`bp.set_evds_key(...)` → `GET /igmevdsms-dis/?series=...&key=...` resmi REST
endpoint'i (fatihmete/evds v0.4.0 ile aynı kontrat). API key olmadan
`get_series_data()` net bir `APIError` fırlatır.

**SPA-internal `POST /fe` ve `POST /fe/excel-indir` yolları KALDIRILDI**:
TCMB gateway'i bu endpoint'lere her dış istemciye (curl, httpx, gerçek
Chrome, Scrapling stealth) HTTP 500 dönüyor — SPA'nın kendi dashboard
chart-refresh istekleri bile 500 alıyor. `[evds]` optional extra ve
Scrapling/Camoufox fallback'i de gerek kalmadığından kaldırıldı.

#### Mevcut Inflation/TCMB Modülleri ile İlişki

EVDS bu iki modülü kapsayacak şekilde daha geniş ama **deprecate edilmedi**:
- `bp.Inflation()` → TÜFE/ÜFE özel HTML scraper'ı (TCMB sayfası)
- `bp.TCMB()` → Faiz oranları HTML scraper'ı
- `bp.EVDS()` → tam EVDS katalog erişimi (TÜFE: `bp.evds_series('TP.FG.J0', formula='yoy_pct')`)

Yeni kodlarda EVDS tercih edilmeli; eski modüller geriye uyumluluk için
korundu.

#### TCMB Resmi PDF Kılavuzlarından Eklenen Ek Özellikler

İlk sürüm yayınlandıktan sonra TCMB'nin 4 resmi PDF kılavuzu (Web Servis,
Python, Excel, ve `evds3.tcmb.gov.tr/dokumanlar`'daki Arama + Rapor Sayfası
kılavuzları) detaylı incelendi. Buradan çıkan ek özellikler:

**Veri çekme**:
- `EVDS().datagroup_data(datagroup_code, period="...")` — `/datagroup=X&...`
  endpoint'i ile bir veri grubundaki **tüm seriler tek HTTP call'da** (örn.
  `bie_dkdovizgn` 137 günlük döviz serisi). 100+ seri için manuel
  `evds_download(...)` listesinden çok daha hızlı.
- **1000-gözlem auto-chunking** — TCMB silently keserdi; provider artık
  client-side chunked + dedup yapıyor. `period="max"`, 10+ yıllık günlük
  seriler tek çağrı gibi davranır. Helpers: `_estimate_observations`,
  `_split_window`, `_merge_chunks`.
- **`end=None` → `01-01-2999`** — TCMB tavsiyesi "always-current" sentinel.
  `start` veriyi ama `end` vermezse provider 2999'u set eder.
- `output_format="csv"|"xml"` — provider seviye CSV/XML çıktı (chunking
  devre dışı bu modlarda).
- `decimal_separator=","` — Türk locale Excel için (provider + user-facing).

**Katalog/metadata**:
- Datagroup metadata yeni alanlar (anonim `/categories/withDatagroups`'tan
  zaten geliyordu, DataFrame'e eklendi): `METADATA_LINK`, `METADATA_LINK_EN`,
  `REV_POL_LINK`, `REV_POL_LINK_EN`, `APP_CHA_LINK`, `APP_CHA_LINK_EN`,
  `NOTE`, `NOTE_EN`, `DATA_SOURCE_EN`. Toplam 20 sütun.
- `EVDS().search_server(term)` — TCMB resmi `/searchResults?searchVal=X`
  full-text indeksi. Etiketleri (tags) ve rapor sayfalarını da indeksliyor.
  Client-side `search()`'ten geniş; max 100 kayıt/kategori.
- `EVDS().home_page_dashboards()` — `/dashboards/home-page-dashboards` ile
  TCMB'nin ana sayfada gösterdiği 10 küratörlü pano (Rezervler, Cari
  İşlemler, Yurt Dışı Portföy, Parasal Büyüklükler, Kart Harcamaları,
  TÜFE, Borç-GSYİH, FX Mevduat, TL Faiz, Brüt Dış Borç).
- `EVDS().dashboard_by_id(encoded_id)` — `/public/dashboards/portlet/{id}`
  ile herhangi bir panoyu encoded_id ile çek.

**Resmi REST katalog yedekleri** (key gerekli, anonim SPA endpoint'lerine
yedek olarak sunulur):
- `EVDSProvider.get_categories_rest()` — `/categories/type=json`
- `EVDSProvider.get_datagroups_rest(code=None)` — `/datagroups/mode=0|1&...`
- `EVDSProvider.get_series_list_rest(code)` — `/serieList/type=json&code=X`

**Frekansa-Ait-İlk-Gün Kuralı** (README dokümantasyonu):
TCMB Web Servis kılavuzu: yıllık/aylık/çeyreklik seriler için `start`
parametresi dönemin ilk gününe set edilmeli (örn. yıllık için `01-01-YYYY`).
Aksi halde dönem atlanır (kılavuz örneği: `02-01-2005` → 2005 atlanır,
2006'dan başlar).

#### Technical Changes

- `borsapy/_providers/evds.py` (NEW, ~900 satır): `EVDSProvider`,
  `BaseProvider` miras, browser-like headers, sticky cookie session,
  FREQUENCY/AGGREGATION/FORMULA enum'ları, `NUMERIC_FREQ_NORMALIZE`
  (legacy v2 9/13/16/18 ↔ v3 1..8), dot↔underscore code transformer,
  anonim catalog GET'leri, REST GET data (key zorunlu, path-style URL),
  POST `/serieList/baslangicBitis`, `_estimate_observations` +
  `_split_window` + `_merge_chunks` (1000-obs auto-chunking),
  `_rest_data_get` (CSV/XML destekli generic GET), `get_datagroup_data`,
  `get_home_page_dashboards`, `get_dashboard_by_encoded_id`,
  `search_server`, `get_*_rest` (3 resmi REST katalog yedeği).
- `borsapy/evds.py` (NEW, ~600 satır): `EVDS` class — `categories`,
  `datagroups`, `series_in_group`, `search`, `search_server`, `series`,
  `dashboard`, `dashboard_by_id`, `home_page_dashboards`, `datagroup_data`,
  `announcements`. `EVDSSeries` wrapper — `code`, `info`, `range`,
  `native_frequency`, `datagroup`, `history(period/start/end/frequency/
  aggregation/formula/decimals/decimal_separator)`. `_resolve_window`
  (end=None → 01-01-2999 sentinel), `_frame_from_payload` (Tarih/UNIXTIME
  parse, formula suffix `-3` strip, single-series → "Value" rename).
  Module shortcuts: `evds_series`, `evds_download`, `evds_categories`,
  `evds_search`, `set_evds_key`, `get_evds_key`, `clear_evds_key`.
- `borsapy/cache.py`: `TTL.EVDS_CATALOG=86400`, `TTL.EVDS_DATA=300`,
  `TTL.EVDS_DASHBOARD=300`.
- `borsapy/__init__.py`: 9 yeni public sembol (EVDS, EVDSSeries, evds_*,
  set/get/clear_evds_key).
- `tests/test_evds.py`: 58 unit + 10 integration test. README'deki 38
  EVDS örneği canlı API ile birebir doğrulandı. PDF kılavuzlarından
  eklenen 13 yeni özellik için ayrı smoke testleri.
- `README.md`: kapsamlı EVDS bölümü (~280 satır) — API anahtarı alma
  adımları (5 adım), katalog navigasyonu, search, dashboards, çoklu seri,
  frekans/formula/aggregation tabloları, sistem limitleri, frekansa-ait-
  ilk-gün kuralı, CSV/XML çıktı, resmi REST katalog yedekleri.
- `pyproject.toml`: `0.10.0`. `[evds]` optional extra (Scrapling fallback)
  başta eklendi, sonradan POST /fe yolunun kullanışsızlığı netleşince
  kaldırıldı.

Release: `v0.10.0` GitHub release oluşturuldu, PyPI workflow tetiklendi.

---

### v0.9.0 (2026-05-03)

**Breaking change**: TEFAS production API geçişinin (Nisan 2026) tamamlanması.
Tüm `/api/DB/*` legacy endpointleri 404 dönüyor; provider tamamen yeni
`/api/funds/*` v2 mimarisine taşındı.

#### Migration (TEFAS v2)
- **`Fund.history()`**: Yeni `fonFiyatBilgiGetir` endpointi kullanılıyor
  - Sabit `periyod` enum'una map ediliyor: `1d`/`5d` → 13 (haftalık), `1mo` → 1, `3mo` → 3, `6mo` → 6, `ytd` → 0, `1y` → 12, `3y` → 36, `5y` → 60, `max` → 60
  - **Maksimum 5 yıl geçmiş** (eski `period="max"` artık kapsanan en uzun aralık 5y)
  - Keyfi `start`/`end` aralıkları en küçük kapsayan bucket'ı çekip client-side filtreliyor
  - DataFrame'in `Price` sütunu çalışıyor; `FundSize`/`Investors` sütunları geriye uyumluluk için NaN/0 dolduruluyor (yeni API döndürmüyor)
- **`Fund.info`**: `fonProfilBilgiGetir` endpointi keşfedildi, profil alanları geri restore edildi
  - Restore: `isin`, `kap_link`, `first_trading_time`, `last_trading_time`, `buy_valor`, `sell_valor`, `entry_fee`, `exit_fee`, `min_purchase`, `min_redemption`, `max_purchase`, `max_redemption`, `tefas_status`
  - Yeni alan: `fund_class` ("YAT"/"EMK") — `_lookup_fund_returns` üzerinden iki listeye düşerek otomatik tespit
  - Hâlâ yok: `weekly_return` (None döner — yeni API döndürmüyor)
- **`Fund.allocation`**: Scrapling tabanlı StealthyFetcher ile SSR scraper'a geçti
  - TEFAS yeni Next.js sitesi allocation'ı SSR HTML içine embed ediyor (`varlikData`)
  - Akamai TSPD JS challenge plain headless Chromium'u da yakalıyor → Scrapling'in patchright tabanlı StealthyFetcher'ı kullanılıyor (stealth Playwright/Chromium fork)
  - `pip install borsapy[allocation]` + `playwright install chromium` (one-time browser binary)
  - Sadece güncel snapshot dönüyor (tek tarih), sıralı asset listesi
- **`Fund.allocation_history()`**: Deprecated. TEFAS tarihsel allocation'ı artık hiçbir endpointte sunmuyor. `DeprecationWarning` ile `Fund.allocation`'ı döndürüyor
- **`Fund.get_holdings(api_key=...)`**: `kap_link` artık restore olduğu için tekrar çalışıyor (PR #16'dan sonra `kap_link=None` olduğu için sessizce kırılmıştı)
- **`Fund._detect_fund_type()`**: Eski `_fetch_history_chunk` çağrıları kaldırıldı — yeni `info["fund_class"]` üzerinden detect ediliyor

#### Removed
- `_get_history_chunked()`, `_fetch_history_chunk()` (eski 90 günlük chunk mantığı yeni API'de gerekli değil)
- `BASE_URL_LEGACY` constant
- `MAX_CHUNK_DAYS` constant

#### Optional Dependency
- `[allocation]` extra eklendi: `pip install borsapy[allocation]` → `scrapling[fetchers]>=0.4.0` (patchright + playwright dahil)

#### Technical Changes
- `_providers/tefas.py`: `_PERIOD_TO_PERIYOD` dict, `_PERIYOD_MAX`, `_resolve_periyod()`, `_lookup_fund_returns()`, `_build_allocation_pattern()`, `_fetch_fund_page_html()` (Playwright wrapper)
- `_providers/tefas.py`: `get_fund_detail()` artık 3 endpoint çağırıyor — `fonBilgiGetir`, `fonGetiriBazliBilgiGetir`, `fonProfilBilgiGetir`
- `fund.py`: `_detect_fund_type()` basitleştirildi, history/allocation docstring'leri güncellendi
- `pyproject.toml`: `[project.optional-dependencies] allocation = ["playwright>=1.40.0"]`
- `tests/test_management_fees.py`: Mock'lar v2 envelope'a güncellendi (camelCase + `{errorCode, errorMessage, resultList}` zarfı)
- `tests/test_tefas_v2.py`: 21 yeni unit test (periyod mapping, history mock, profile merge, fund_class detection, allocation HTML parsing, Playwright lazy import)

Issue: closes #15.

---

### v0.8.4 (2026-03-28)

#### Bug Fixes
- **`start`/`end` parametresi düzeltildi**: `history(start=..., end=...)` artık doğru tarih aralığını döndürüyor
  - **Sorun**: TradingView WebSocket API her zaman son N bar'ı döndürüyor, tarih aralığı belirleyemiyordu. `start="2020-01-01", end="2020-12-31"` denildiğinde ~365 bar hesaplanıyordu ama TradingView bugünden geriye son 365 günü döndürüyordu.
  - **Çözüm 1**: `_calculate_bars()` artık `start`'tan bugüne kadar bar hesaplıyor (eski veriyi de kapsayacak şekilde)
  - **Çözüm 2**: DataFrame döndükten sonra `start`/`end` tarihlerine göre client-side filtreleme eklendi
  - **Bonus fix**: `start = time.time()` değişken ismi `t0` olarak değiştirildi (parametre shadowing bug)

  ```python
  import borsapy as bp
  stock = bp.Ticker("THYAO")

  # Artık doğru çalışıyor
  df = stock.history(start="2020-01-01", end="2020-12-31")
  print(df.index[0])   # 2020-01-02
  print(df.index[-1])  # 2020-12-31
  ```

#### New Features
- **Split-unadjusted (gerçek) fiyatlar**: `history(adjust=False)` ile ham fiyatlar alınabiliyor
  - TradingView varsayılan olarak split-adjusted fiyat döndürüyor
  - `adjust=False` ile İş Yatırım splits verisi kullanılarak ters-düzeltme yapılıyor
  - Split tarihinden önceki fiyatlar kümülatif split oranıyla çarpılıyor
  - Split sonrası fiyatlar değişmez (bugünkü fiyat = gerçek fiyat)

  ```python
  import borsapy as bp
  stock = bp.Ticker("THYAO")

  # Split-adjusted (varsayılan)
  df_adj = stock.history(period="max")
  print(df_adj.iloc[0]["Close"])   # ~2.39 TL (adjusted)

  # Gerçek fiyatlar
  df_raw = stock.history(period="max", adjust=False)
  print(df_raw.iloc[0]["Close"])   # Gerçek nominal fiyat

  # Son fiyat her iki modda da aynı
  df_adj.iloc[-1]["Close"] == df_raw.iloc[-1]["Close"]  # True
  ```

  **`adjust` Parametresi:**
  | Değer | Açıklama |
  |-------|----------|
  | `True` | Split-adjusted fiyatlar (varsayılan, geriye uyumlu) |
  | `False` | Gerçek nominal fiyatlar (İş Yatırım splits verisi ile ters-düzeltme) |

#### Technical Changes
- `_providers/tradingview.py`: `_calculate_bars()` — `start` verildiğinde `start→now` arası bar hesaplıyor
- `_providers/tradingview.py`: DataFrame döndükten sonra `start`/`end` client-side filtresi eklendi
- `_providers/tradingview.py`: `start = time.time()` → `t0 = time.time()` (parametre shadowing fix)
- `ticker.py`: `history()` metoduna `adjust: bool = True` parametresi eklendi
- `ticker.py`: `_unadjust_prices()` metodu eklendi — splits verisinden kümülatif ters-düzeltme faktörü hesaplıyor

---

### v0.8.3 (2026-03-09)

#### Changes
- **Batch boyutu 5→4**: `_MAX_PERIODS_PER_CALL` 5'ten 4'e düşürüldü
  - İş Yatırım MaliTablo API'si 5 dönemlik isteklerde bazen boş sonuç döndürüyordu
  - 4'lü batch'ler daha güvenilir çalışıyor
  - `last_n=5` artık 2 batch (4+1), `last_n=10` artık 3 batch (4+4+2)

#### Technical Changes
- `_providers/isyatirim.py`: `_MAX_PERIODS_PER_CALL = 5` → `4`
- `_providers/isyatirim.py`: Hardcoded `periods[:5]` → `periods[:self._MAX_PERIODS_PER_CALL]` (2 yer)
- `tests/test_financial_statements.py`: Batch boyutu testleri güncellendi (53 test)

---

### v0.8.2 (2026-03-09)

#### Bug Fixes
- **Mali tablo itemCode filtresi**: `get_balance_sheet()`, `get_income_stmt()`, `get_cashflow()` artık doğru satırları döndürüyor
  - **Sorun**: İş Yatırım MaliTablo API'si `table_name` parametresini yoksayıp tüm tabloları tek bir response'ta döndürüyordu. Bu yüzden her üç metod aynı ~147 satırlık karışık veriyi döndürüyordu.
  - **Çözüm**: API response'u `itemCode` ön ekine göre filtreleniyor: 1xxx/2xxx=Bilanço, 3xxx=Gelir Tablosu, 4xxx=Nakit Akış
  - Geriye uyumlu: Mevcut API değişmedi, sadece dönen veriler artık doğru

  ```python
  import borsapy as bp
  stock = bp.Ticker("THYAO")

  bs = stock.get_balance_sheet()    # ~70 satır (eskiden ~147)
  inc = stock.get_income_stmt()     # ~43 satır (eskiden ~147)
  cf = stock.get_cashflow()         # ~34 satır (eskiden ~147)
  # Artık tablolar arası sıfır satır çakışması
  ```

  **UFRS bankalarda nakit akış tablosu yok**:
  ```python
  banka = bp.Ticker("AKBNK")
  banka.get_balance_sheet(financial_group="UFRS")  # ~130 satır ✓
  banka.get_income_stmt(financial_group="UFRS")    # ~62 satır ✓
  banka.get_cashflow(financial_group="UFRS")       # DataNotAvailableError (4xxx yok)
  ```

#### Technical Changes
- `_providers/isyatirim.py`: `ITEM_CODE_PREFIXES` class sabiti eklendi
  - `balance_sheet: ("1", "2")`, `income_stmt: ("3",)`, `cashflow: ("4",)`
- `_providers/isyatirim.py`: `get_financial_statements()` — tablo-bazlı for-loop kaldırıldı, tek batch loop
- `_providers/isyatirim.py`: `_fetch_financial_table()` — `table_name` → `statement_type` parametresi
- `_providers/isyatirim.py`: `_parse_financial_response()` — `statement_type` ile itemCode prefix filtresi
- `README.md`: UFRS cashflow örnekleri kaldırıldı, satır sayısı notları eklendi
- `tests/test_financial_statements.py`: Mock imzaları güncellendi, `TestItemCodeFiltering` (7 test) eklendi, toplam 52 test

---

### v0.8.1 (2026-03-02)

#### New Features
- **Parametrik Finansal Tablolar (last_n)**: Mali tablolarda 5'ten fazla dönem çekme desteği
  ```python
  import borsapy as bp

  stock = bp.Ticker("THYAO")

  # Varsayılan (5 dönem, geriye uyumlu)
  stock.get_income_stmt()

  # 10 yıllık gelir tablosu (2 API çağrısı)
  stock.get_income_stmt(last_n=10)

  # 20 çeyreklik bilanço (4 API çağrısı)
  stock.get_balance_sheet(quarterly=True, last_n=20)

  # Tüm mevcut dönemler (~15 yıllık / ~40 çeyreklik)
  stock.get_cashflow(last_n="all")

  # Legacy property'ler değişmedi
  stock.income_stmt          # Hala 5 dönem
  stock.get_ttm_income_stmt()  # TTM etkilenmedi
  ```

  **last_n Parametresi:**
  | Değer | Açıklama |
  |-------|----------|
  | `None` | Varsayılan 5 dönem (geriye uyumlu) |
  | `int` | Tam sayı kadar dönem (örn: 10, 20) |
  | `"all"` | Tüm mevcut dönemler (~15 yıllık, ~40 çeyreklik) |

  **Desteklenen Metodlar:**
  | Metod | Açıklama |
  |-------|----------|
  | `get_income_stmt(last_n=...)` | Gelir tablosu |
  | `get_balance_sheet(last_n=...)` | Bilanço |
  | `get_cashflow(last_n=...)` | Nakit akış tablosu |

#### Technical Changes
- `_providers/isyatirim.py`: `get_financial_statements()` metoduna `last_n` parametresi eklendi
  - `_resolve_last_n()`: Parametre validasyonu (None→5, int→exact, "all"→15/40, invalid→ValueError)
  - `_period_sort_key()`: Dönem sütun sıralaması (2024Q3 > 2024Q2 > 2024Q1)
  - 5'ten fazla dönem istendiğinde otomatik batch (5'erli API çağrıları)
  - Batch sonuçları horizontal merge + dedup
  - Cache key'e count dahil (farklı last_n = farklı cache)
- `_providers/isyatirim.py`: `_get_periods()` bug fix — quarterly artık tam `count` tuple üretiyor (eskiden `count*4`)
- `_providers/isyatirim.py`: `_fetch_financial_table()` ve `_parse_financial_response()` metodlarına explicit `quarterly` parametresi eklendi (tek çeyrek batch misdetection fix)
- `ticker.py`: `get_balance_sheet()`, `get_income_stmt()`, `get_cashflow()` metodlarına `last_n` parametresi eklendi
- Legacy property'ler (`income_stmt`, `balance_sheet`, vb.) ve TTM metodları değişmedi
- `tests/test_financial_statements.py`: 45 unit test (resolve_last_n, _get_periods, sort_key, parsing, batching, cache, ticker passthrough, merge dedup, edge cases)

---

### v0.7.6 (2026-03-01)

#### New Features
- **Twitter/X Tweet Arama**: Hisse, fon, doviz ve kripto icin Twitter/X tweet arama ozelligi
  ```python
  import borsapy as bp

  # Auth (tek sefer — browser DevTools > Application > Cookies > x.com)
  bp.set_twitter_auth(auth_token="...", ct0="...")
  # veya
  bp.set_twitter_auth(cookies_file="cookies.json")

  # Standalone arama
  df = bp.search_tweets("$THYAO", period="7d")
  df = bp.search_tweets("dolar kur", period="1d", lang="tr", limit=50)

  # Asset entegrasyonu
  bp.Ticker("THYAO").tweets(period="7d")    # $THYAO OR #THYAO OR THYAO OR "TURK HAVA YOLLARI"
  bp.Fund("AAK").tweets(period="7d")        # #AAK OR AAK OR "AK PORTFOY KISA VADELI BONO"
  bp.FX("USD").tweets(period="7d")          # $USDTRY OR dolar kur OR dolar TL
  bp.Crypto("BTCTRY").tweets(period="7d")   # $BTC OR #Bitcoin

  # Custom query override
  bp.Ticker("THYAO").tweets(query="THY ucak grev")
  ```

  **Yeni Fonksiyon ve Property'ler:**
  | Metod/Fonksiyon | Donus | Aciklama |
  |-----------------|-------|----------|
  | `bp.search_tweets(query, period, lang, limit)` | `DataFrame` | Tweet arama |
  | `bp.set_twitter_auth(auth_token, ct0)` | `None` | Twitter auth ayarla |
  | `bp.clear_twitter_auth()` | `None` | Twitter auth temizle |
  | `bp.get_twitter_auth()` | `dict/None` | Mevcut auth bilgisi |
  | `Ticker.tweets(period, query)` | `DataFrame` | Hisse tweetleri |
  | `Fund.tweets(period, query)` | `DataFrame` | Fon tweetleri |
  | `FX.tweets(period, query)` | `DataFrame` | Doviz/emtia tweetleri |
  | `Crypto.tweets(period, query)` | `DataFrame` | Kripto tweetleri |

  **DataFrame Sutunlari:**
  | Sutun | Tip | Aciklama |
  |-------|-----|----------|
  | `tweet_id` | str | Tweet ID |
  | `created_at` | datetime | Tarih |
  | `text` | str | Tweet metni |
  | `author_handle` | str | @kullanici |
  | `author_name` | str | Gorunen isim |
  | `likes` | int | Begeni |
  | `retweets` | int | Retweet |
  | `replies` | int | Yanit |
  | `views` | int | Goruntulenme |
  | `quotes` | int | Alinti |
  | `bookmarks` | int | Yer imi |
  | `author_followers` | int | Takipci sayisi |
  | `author_verified` | bool | Dogrulanmis mi |
  | `lang` | str | Dil kodu |
  | `url` | str | Tweet linki |

  **Not:** Optional dependency — `pip install borsapy[twitter]` ile yuklenir. Scweet>=4.0.0 gerektirir.

#### Technical Changes
- `_providers/twitter.py`: Yeni Twitter provider (~390 satir)
  - `set_twitter_auth()`, `clear_twitter_auth()`, `get_twitter_auth()` — auth yonetimi
  - `TwitterProvider` class: Scweet wrapper, temp DB per call (cooldown state bypass)
  - `_create_scweet()`: Her cagri icin yeni Scweet instance (aclose() sonrasi invalid olur)
  - `_cleanup_temp_db()`: Gecici SQLite DB temizligi
  - `search_tweets()`: `search()` API (v4.1+) ile `scrape()` fallback (v4.0)
  - `_normalize_tweet()`: 3 format router (GraphQL, wrapped GraphQL, TweetRecord)
  - `_normalize_graphql()`: `user_core` + `user_legacy` path destegi (yeni/eski API)
  - `_normalize_tweet_record()`: Pydantic model_dump format
  - `PERIOD_DAYS`, `TWEET_COLUMNS` sabitleri
  - Dil filtresi Twitter search syntax ile: `query lang:tr`
  - Cookies plain dict olarak gecilir (Scweet v4 format)
  - 5 dakika cache (TTL.SOCIAL_DATA)
- `twitter.py`: Yeni user-facing modul (~180 satir)
  - `search_tweets()` standalone fonksiyon
  - `TwitterMixin` class: `_get_tweet_query()` + `tweets()` metodu
  - `_build_stock_query()`: KAP sirket adi dahil sorgu olusturma
  - `_build_fund_query()`, `_build_fx_query()`, `_build_crypto_query()`
  - `FX_QUERY_MAP`, `CRYPTO_QUERY_MAP` — Turkce arama terimleri
- `ticker.py`: `TwitterMixin` eklendi, `_get_tweet_query()` override
- `fund.py`: `TwitterMixin` eklendi, `_get_tweet_query()` override
- `fx.py`: `TwitterMixin` eklendi, `_get_tweet_query()` override
- `crypto.py`: `TwitterMixin` eklendi, `_get_tweet_query()` override
- `__init__.py`: `set_twitter_auth`, `clear_twitter_auth`, `get_twitter_auth`, `search_tweets` export
- `cache.py`: `TTL.SOCIAL_DATA = 300` eklendi
- `pyproject.toml`: `twitter` optional dependency grubu eklendi (`Scweet>=4.0.0`)
- `tests/test_twitter.py`: 46 unit test (auth, query building, normalizasyon, mixin, provider, GraphQL user_core format)

---

### v0.7.5 (2026-03-01)

#### New Features
- **Fund Management Fees (Fon Yonetim Ucretleri)**: TEFAS uzerinden fon yonetim ucreti verileri
  ```python
  import borsapy as bp

  # Tum yatirim fonu ucretleri
  df = bp.management_fees()
  print(df)
  #   fund_code                              name  applied_fee  prospectus_fee  max_expense_ratio  annual_return
  # 0       AAK  AK PORTFOY KISA VADELI BONO...          1.0             2.2               3.65           45.5

  # Emeklilik fonu ucretleri
  df_emk = bp.management_fees(fund_type="EMK")

  # Kurucu filtresi
  df_akp = bp.management_fees(founder="AKP")

  # Tek fon icin
  fund = bp.Fund("AAK")
  print(fund.management_fee)
  # {'applied_fee': 1.0, 'prospectus_fee': 2.2, 'max_expense_ratio': 3.65, 'annual_return': 45.5}
  ```

  **Yeni Fonksiyon ve Property'ler:**
  | Metod/Fonksiyon | Donus | Aciklama |
  |-----------------|-------|----------|
  | `bp.management_fees(fund_type, founder)` | `DataFrame` | Tum fonlarin yonetim ucretleri |
  | `Fund.management_fee` (property) | `dict` | Tek fonun yonetim ucreti bilgisi |

  **DataFrame Sutunlari:**
  | Sutun | Tip | Aciklama |
  |-------|-----|----------|
  | `fund_code` | str | TEFAS fon kodu |
  | `name` | str | Fon tam adi |
  | `fund_category` | str | Fon kategorisi |
  | `founder_code` | str | Kurucu sirket kodu |
  | `applied_fee` | float/None | Uygulanan yillik yonetim ucreti (%) |
  | `prospectus_fee` | float/None | Izahname yonetim ucreti (%) |
  | `max_expense_ratio` | float/None | Azami toplam gider kesinti orani (%) |
  | `annual_return` | float/None | Yillik getiri (%) |

- **Fon Stopaj Oranlari (Withholding Tax Rates)**: GVK gecici 67. maddeye gore fon stopaj oranlari referans tablosu
  ```python
  import borsapy as bp

  # Tek fon icin stopaj orani
  fund = bp.Fund("AAK")
  fund.tax_category                           # "borclanma_para_maden"
  fund.withholding_tax_rate("2025-06-01")     # 0.15 (15%)
  fund.withholding_tax_rate("2025-08-01")     # 0.175 (17.5%)

  # GSYF/GYF — holding suresi ile
  fund2 = bp.Fund("GYF_CODE")
  fund2.withholding_tax_rate("2025-06-01", holding_days=800)  # 0.0 (>2 yil)
  fund2.withholding_tax_rate("2025-06-01", holding_days=300)  # 0.15 (<2 yil)

  # Standalone fonksiyon
  bp.withholding_tax_rate("AAK", "2025-06-01")  # 0.15

  # Referans tablo
  bp.withholding_tax_table()
  #   tax_category          description              <23.12.2020  ...  >=09.07.2025
  # 0  degisken_karma_doviz  Degisken, karma, ...         10.0  ...         17.5
  # 1  pay_senedi_yogun      Pay senedi yogun fon          0.0  ...          0.0
  ```

  **Yeni Fonksiyon ve Property'ler:**
  | Metod/Fonksiyon | Donus | Aciklama |
  |-----------------|-------|----------|
  | `bp.withholding_tax_rate(fund_code, purchase_date, holding_days)` | `float/None` | Fon icin stopaj orani |
  | `bp.withholding_tax_table()` | `DataFrame` | Tum stopaj oranlari referans tablosu |
  | `Fund.tax_category` (property) | `str/None` | Fonun vergi kategorisi |
  | `Fund.withholding_tax_rate(purchase_date, holding_days)` | `float/None` | Fonun stopaj orani |

  **Vergi Kategorileri:**
  | Kategori | Aciklama |
  |----------|----------|
  | `degisken_karma_doviz` | Degisken, karma, eurobond, dis borclanma, yabanci, serbest + doviz |
  | `pay_senedi_yogun` | Pay senedi yogun fon (her zaman %0) |
  | `borclanma_para_maden` | Borclanma araclari, para piyasasi, kiymetli maden, katilim |
  | `gsyf_gyf_uzun` | GSYF/GYF >2 yil (%0) |
  | `gsyf_gyf_kisa` | GSYF/GYF <2 yil |

#### Technical Changes
- `_providers/tefas.py`: `_parse_turkish_decimal()` static metod eklendi (Turkce ondalik format parse)
- `_providers/tefas.py`: `get_management_fees()` metodu eklendi (BindComparisonManagementFees API)
- `fund.py`: `Fund.management_fee` property eklendi
- `fund.py`: `management_fees()` modul-seviye fonksiyon eklendi
- `fund.py`: `Fund.tax_category` property eklendi
- `fund.py`: `Fund.withholding_tax_rate()` metodu eklendi
- `tax.py`: Yeni modul — stopaj oranlari referans tablosu, kategori mapping, oran hesaplama
- `__init__.py`: `management_fees`, `withholding_tax_rate`, `withholding_tax_table` export eklendi
- `tests/test_management_fees.py`: 22 unit + integration test
- `tests/test_tax.py`: 69 unit + 2 integration test

---

### v0.7.4 (2026-03-01)

#### New Features
- **Portfolio Rebalancing**: Hedef agirlik belirleme, sapma analizi ve otomatik dengeleme
  ```python
  import borsapy as bp

  p = bp.Portfolio()
  p.add("THYAO", shares=100, cost=280)
  p.add("GARAN", shares=200, cost=50)
  p.add("gram-altin", shares=5, asset_type="fx")

  # Hedef agirliklar belirle (0-1 olcegi, toplam ~1.0)
  p.set_target_weights({"THYAO": 0.50, "GARAN": 0.30, "gram-altin": 0.20})

  # Sapma analizi
  print(p.drift())
  #    symbol  current_weight  target_weight   drift  drift_pct
  # 0   GARAN          0.2500         0.3000 -0.0500      -5.00
  # 1   THYAO          0.7000         0.5000  0.2000      20.00
  # 2   gram-altin     0.0500         0.2000 -0.1500     -15.00

  # Dengeleme plani (esik: %2 altindaki sapmalar yoksayilir)
  plan = p.rebalance_plan(threshold=0.02)
  print(plan)  # symbol, current_shares, target_shares, delta_shares, delta_value, action

  # Dengelemeyi calistir
  p.rebalance(threshold=0.02)

  # Dry run (sadece plan, uygulama yok)
  plan = p.rebalance(threshold=0.02, dry_run=True)

  # Export/Import hedef agirliklar korunur
  data = p.to_dict()  # target_weights dahil
  p2 = bp.Portfolio.from_dict(data)
  print(p2.target_weights)  # Ayni hedefler
  ```

  **Yeni Metodlar:**
  | Metod | Donus | Aciklama |
  |-------|-------|----------|
  | `set_target_weights(weights)` | `self` | Hedef agirliklar belirle (0-1, toplam ~1.0) |
  | `target_weights` (property) | `dict` | Mevcut hedef agirliklar |
  | `drift()` | `DataFrame` | Mevcut vs hedef agirlik sapmasi |
  | `rebalance_plan(threshold)` | `DataFrame` | Dengeleme icin gerekli islemler |
  | `rebalance(threshold, dry_run)` | `DataFrame` | Dengelemeyi uygula |

- **MetaStock Gostergeleri**: 7 yeni klasik teknik gosterge
  ```python
  import borsapy as bp

  stock = bp.Ticker("THYAO")

  # Mixin shortcut (son deger)
  stock.hhv()   # 14-period en yuksek High
  stock.llv()   # 14-period en dusuk Low
  stock.mom()   # 10-period momentum (Close - Close[N])
  stock.roc()   # 10-period degisim orani (%)
  stock.wma()   # 20-period agirlikli ortalama
  stock.dema()  # 20-period cift EMA
  stock.tema()  # 20-period uclu EMA

  # Pure fonksiyonlar
  df = stock.history(period="1y")
  hhv = bp.calculate_hhv(df, period=52, column="Close")  # 52-hafta yuksek
  llv = bp.calculate_llv(df, period=52, column="Low")
  mom = bp.calculate_mom(df, period=10)
  roc = bp.calculate_roc(df, period=10)
  wma = bp.calculate_wma(df, period=20)
  dema = bp.calculate_dema(df, period=20)
  tema = bp.calculate_tema(df, period=20)

  # add_indicators ile toplu ekleme
  df = bp.add_indicators(df, ["hhv", "llv", "mom", "roc", "wma", "dema", "tema"])

  # TechnicalAnalyzer
  ta = stock.technicals(period="1y")
  ta.hhv(14)   # Series
  ta.latest    # hhv_14, llv_14, mom_10, roc_10, wma_20, dema_20, tema_20 dahil
  ```

  **Gostergeler:**
  | Gosterge | Fonksiyon | Varsayilan | Formul |
  |----------|-----------|------------|--------|
  | HHV | `calculate_hhv(df, period, column)` | 14, High | Rolling max |
  | LLV | `calculate_llv(df, period, column)` | 14, Low | Rolling min |
  | MOM | `calculate_mom(df, period)` | 10 | Close - Close[N] |
  | ROC | `calculate_roc(df, period)` | 10 | ((C - C[N]) / C[N]) * 100 |
  | WMA | `calculate_wma(df, period)` | 20 | Lineer agirlikli ortalama |
  | DEMA | `calculate_dema(df, period)` | 20 | 2*EMA - EMA(EMA) |
  | TEMA | `calculate_tema(df, period)` | 20 | 3*EMA - 3*EMA(EMA) + EMA(EMA(EMA)) |

#### Technical Changes
- `portfolio.py`: `_target_weights` state eklendi
- `portfolio.py`: `set_target_weights()`, `target_weights`, `drift()`, `rebalance_plan()`, `rebalance()` metodlari
- `portfolio.py`: `to_dict()` / `from_dict()` target_weights serializasyonu
- `technical.py`: 7 pure fonksiyon (`calculate_hhv`, `calculate_llv`, `calculate_mom`, `calculate_roc`, `calculate_wma`, `calculate_dema`, `calculate_tema`)
- `technical.py`: `TechnicalAnalyzer` sinifina 7 yeni metod + `latest` property guncellendi
- `technical.py`: `TechnicalMixin` sinifina 7 yeni mixin metod
- `technical.py`: `add_indicators()` fonksiyonuna 7 yeni gosterge destegi
- `__init__.py`: 7 yeni `calculate_*` fonksiyonu export
- `tests/test_technical.py`: 48 yeni MetaStock testi
- `tests/test_portfolio.py`: 17 yeni rebalancing testi
- `examples/portfolio_rebalancing.py`: Portfoy dengeleme ornegi
- `examples/metastock_indicators.py`: MetaStock gostergeleri ornegi

---

### v0.7.2 (2026-01-29)

#### New Features
- **Fund EMK (Emeklilik Fonu) Desteği**: `bp.Fund()` artık emeklilik fonlarını da destekliyor
  ```python
  import borsapy as bp

  # Explicit fund_type ile EMK fonu
  emk = bp.Fund("KJM", fund_type="EMK")
  print(emk.info['name'])     # KATILIM EMEKLİLİK VE HAYAT A.Ş. KIYMETLİ MADENLER...
  print(emk.history(period="1mo"))  # EMK fon geçmişi

  # Auto-detection: fund_type belirtilmezse otomatik algılanır
  emk = bp.Fund("KJM")  # Otomatik olarak EMK olduğunu algılar
  print(emk.fund_type)  # "EMK"

  # YAT (Yatırım Fonu) - varsayılan davranış değişmedi
  yat = bp.Fund("AAK")
  print(yat.fund_type)  # "YAT"
  ```

  **Fund Types:**
  | Tip | Açıklama |
  |-----|----------|
  | `YAT` | Yatırım Fonları (Investment Funds) - varsayılan |
  | `EMK` | Emeklilik Fonları (Pension Funds) |

  **Auto-Detection:**
  - `fund_type` belirtilmezse, ilk `history()` veya `allocation()` çağrısında otomatik algılanır
  - Önce YAT endpoint'i denenir, veri yoksa EMK endpoint'i denenir

#### Bug Fixes
- **Replay Mode Timezone Hatası Düzeltildi**: `replay_filtered()` metodunda timezone-aware index ile timezone-naive tarih karşılaştırması hatası düzeltildi
  ```python
  # Artık çalışıyor
  session = bp.create_replay("THYAO", period="1y")
  for candle in session.replay_filtered(
      start_date="2024-06-01",
      end_date="2024-12-31"
  ):
      print(candle['close'])
  ```

#### Technical Changes
- `fund.py`: `Fund.__init__()` metoduna `fund_type: str | None = None` parametresi eklendi
- `fund.py`: `Fund.fund_type` property eklendi (getter + auto-detection)
- `fund.py`: `Fund._detect_fund_type()` metodu eklendi (history API ile auto-detection)
- `tefas.py`: `get_fund_detail()` metoduna `fund_type` parametresi eklendi
- `tefas.py`: `get_history()` metoduna `fund_type` parametresi eklendi
- `tefas.py`: `_get_history_chunked()` metoduna `fund_type` parametresi eklendi
- `tefas.py`: `_fetch_history_chunk()` metodunda hardcoded `"YAT"` → `fund_type` parametresi
- `tefas.py`: `get_allocation()` metoduna `fund_type` parametresi eklendi
- `replay.py`: `replay_filtered()` metodunda timezone uyumluluk kontrolü eklendi

---

### v0.7.1 (2026-01-29)

#### New Features
- **Portfolio purchase_date**: Holdinglere alım tarihi eklenebilir
  ```python
  import borsapy as bp
  from datetime import date

  portfolio = bp.Portfolio()

  # Tarih ile ekleme
  portfolio.add("THYAO", shares=100, cost=280.0, purchase_date="2024-01-15")
  portfolio.add("GARAN", shares=200, cost=45.0, purchase_date=date(2024, 6, 1))
  portfolio.add("ASELS", shares=50, cost=120.0)  # Tarih verilmezse bugün

  # Holdings DataFrame'de yeni sütunlar
  print(portfolio.holdings)
  #    symbol  shares  cost  value  weight   pnl  purchase_date  holding_days
  # 0   THYAO     100   280   295    0.45  5.36    2024-01-15           380
  # 1   GARAN     200    45    52    0.35  15.5    2024-06-01           242
  # 2   ASELS      50   120   125    0.20   4.2    2026-01-29             0

  # Risk metrikleri artık holding bazlı tarih kullanır
  metrics = portfolio.risk_metrics(period="1y")
  # Her holding için sadece purchase_date sonrası veriler kullanılır

  # JSON export/import
  data = portfolio.to_dict()
  # {'holdings': [{'symbol': 'THYAO', 'shares': 100, 'cost_per_share': 280,
  #                'asset_type': 'stock', 'purchase_date': '2024-01-15'}, ...]}

  portfolio2 = bp.Portfolio.from_dict(data)
  ```

  **Desteklenen Tarih Formatları:**
  - `str`: ISO format (YYYY-MM-DD), örn: `"2024-01-15"`
  - `date`: Python date objesi, örn: `date(2024, 1, 15)`
  - `datetime`: Python datetime objesi (sadece tarih kısmı kullanılır)
  - `None`: Bugünün tarihi varsayılan olarak atanır

  **DataFrame Yeni Sütunları:**
  | Sütun | Tip | Açıklama |
  |-------|-----|----------|
  | `purchase_date` | date | Alım tarihi |
  | `holding_days` | int | Alımdan bugüne kaç gün geçti |

#### Technical Changes
- `portfolio.py`: `Holding` dataclass'a `purchase_date: date | None = None` eklendi
- `portfolio.py`: `add()` metoduna `purchase_date` parametresi eklendi (str, date, datetime destekli)
- `portfolio.py`: `holdings` property'sine `purchase_date`, `holding_days` sütunları eklendi
- `portfolio.py`: `history()` metodu artık purchase_date'e göre filtreleme yapıyor
- `portfolio.py`: `to_dict()` purchase_date'i ISO string olarak serialize ediyor
- `portfolio.py`: `from_dict()` purchase_date'i ISO string'den parse ediyor
- `tests/test_portfolio.py`: 17 yeni test eklendi (TestHolding: 2, TestPurchaseDate: 15)

---

### v0.6.3 (2026-01-25)

#### New Features
- **Supertrend Göstergesi**: Trend takip eden ATR-tabanlı teknik gösterge
  ```python
  import borsapy as bp

  stock = bp.Ticker("THYAO")

  # Mixin metodu ile son değer
  st = stock.supertrend()
  print(st['value'])       # 282.21
  print(st['direction'])   # 1 (bullish) veya -1 (bearish)
  print(st['upper'])       # 303.69 (üst band)
  print(st['lower'])       # 282.21 (alt band)

  # Custom parametreler
  st = stock.supertrend(period="6mo", atr_period=7, multiplier=2.0)

  # TechnicalAnalyzer ile tüm seriler
  ta = stock.technicals(period="1y")
  st_df = ta.supertrend()  # DataFrame: Supertrend, Direction, Upper, Lower

  # Pure function
  df = stock.history(period="1y")
  st_df = bp.calculate_supertrend(df, atr_period=10, multiplier=3.0)

  # add_indicators ile
  df_with_indicators = bp.add_indicators(df, ["supertrend"])
  print(df_with_indicators[['Close', 'Supertrend', 'Supertrend_Direction']])
  ```

  **Supertrend Formülü:**
  - ATR-tabanlı dinamik destek/direnç bantları
  - Direction: 1 = Bullish (fiyat Supertrend üzerinde), -1 = Bearish
  - Varsayılan: ATR(10), multiplier=3.0 (TradingView ile aynı)

- **Tilson T3 Göstergesi**: Triple-smoothed EMA ile düşük gecikmeli hareketli ortalama
  ```python
  import borsapy as bp

  stock = bp.Ticker("THYAO")

  # Mixin metodu ile son değer
  t3 = stock.tilson_t3()              # 296.24
  t3 = stock.tilson_t3(t3_period=8)   # Farklı period

  # TechnicalAnalyzer ile tüm seriler
  ta = stock.technicals(period="1y")
  t3_series = ta.tilson_t3(period=5, vfactor=0.7)

  # Pure function
  df = stock.history(period="1y")
  t3_series = bp.calculate_tilson_t3(df, period=5, vfactor=0.7)
  ```

  **Tilson T3 Formülü:**
  - Triple-smoothed EMA (6 ardışık EMA)
  - vfactor: Smoothing vs responsiveness kontrolü (varsayılan 0.7)
  - EMA'ya göre daha az gecikme, daha pürüzsüz çizgi

#### Improvements
- **TradingView Auth Entegrasyonu**: Tüm TradingView provider'ları artık merkezi auth kullanıyor
  - `tradingview_screener_native.py`: Auth cookie desteği eklendi (canlı veri için)
  - Tek bir `set_tradingview_auth()` çağrısı tüm TradingView modüllerini etkiliyor
- **VWAP TradingView Entegrasyonu**: `vwap()` metodu artık TradingView Scanner API kullanıyor
  - TradingView'dan alınamazsa lokal hesaplamaya fallback
  - Scanner API'ye `VWAP` ve `relative_volume_10d_calc` sütunları eklendi
- **README Güncelleme**: Tüm TradingView bölümlerine canlı veri notları eklendi
  - 8 bölümde "Canlı veri için TradingView Authentication" linki

#### Technical Changes
- `technical.py`: `calculate_supertrend()` fonksiyonu eklendi (~100 satır)
  - Wilder's smoothing ATR (TradingView ile uyumlu)
  - `TechnicalAnalyzer.supertrend()` metodu
  - `TechnicalMixin.supertrend()` metodu (lokal hesaplama)
  - `TechnicalAnalyzer.latest` property'sine supertrend eklendi
  - `add_indicators()` fonksiyonuna supertrend desteği
- `technical.py`: `calculate_tilson_t3()` fonksiyonu eklendi (~55 satır)
  - Triple-smoothed EMA with volume factor
  - `TechnicalAnalyzer.tilson_t3()` metodu
  - `TechnicalMixin.tilson_t3()` metodu (lokal hesaplama)
  - `TechnicalAnalyzer.latest` property'sine t3_5 eklendi
- `__init__.py`: `calculate_supertrend`, `calculate_tilson_t3` export eklendi
- `_providers/tradingview_screener_native.py`: `_get_auth_cookies()` metodu eklendi
- `_providers/tradingview_scanner.py`: VWAP ve relative_volume column mapping eklendi
- `technical.py`: `vwap()` metodu TradingView API + local fallback pattern'ı ile güncellendi
- `README.md`: 8 bölümde real-time data notları eklendi

---

### v0.6.1 (2026-01-24)

#### Bug Fixes
- Ruff lint hataları düzeltildi
- Cache refactor
- Eurobond date fallback eklendi

---

### v0.6.0 (2026-01-24)

#### New Features
- **Fund Portfolio Holdings**: Fon portföyündeki bireysel varlıkları (hisseler, ETF'ler, fonlar) görüntüleme
  ```python
  import borsapy as bp

  # Fon portföy dağılımı
  fund = bp.Fund("YAY")
  holdings = fund.holdings
  print(holdings)
  #    symbol          isin                          name  weight   type  country         value
  # 0     MU  US5951121038         MICRON TECHNOLOGY INC    7.28  stock  foreign  7.313887e+08
  # 1  GOOGL  US02079K3059           GOOGLE-ALPHABET INC    6.76  stock  foreign  6.786442e+08
  # 2   AVGO  US11135F1012                  BROADCOM Ltd    5.11  stock  foreign  5.126140e+08
  # ...

  # Özet bilgi
  print(f"Top holding: {holdings.iloc[0]['symbol']} ({holdings.iloc[0]['weight']:.2f}%)")
  print(f"Total weight: {holdings['weight'].sum():.2f}%")
  print(f"Holdings count: {len(holdings)}")

  # Belirli dönem için
  holdings = fund.get_holdings(period="2024-12")
  ```

  **Veri Kaynağı:** KAP "Portföy Dağılım Raporu" bildirimleri (PDF parsing)

  **DataFrame Sütunları:**
  | Sütun | Tip | Açıklama |
  |-------|-----|----------|
  | `symbol` | str | Varlık sembolü (GOOGL, MSFT, SPY) |
  | `isin` | str | ISIN kodu (US02079K3059) |
  | `name` | str | Varlık adı |
  | `weight` | float | Portföy ağırlığı (%) |
  | `type` | str | Varlık tipi: stock, etf, fund, viop_cash, term_deposit |
  | `country` | str | Ülke: foreign, TR, None |
  | `value` | float | Piyasa değeri (TL) |

  **Desteklenen Varlık Tipleri:**
  - `stock`: Yabancı ve yurtiçi hisseler
  - `etf`: Borsa Yatırım Fonları (SPY, QQQ, vb.)
  - `fund`: Fon Katılma Belgeleri
  - `viop_cash`: VİOP Nakit Teminat
  - `term_deposit`: Vadeli Mevduat
  - `reverse_repo`: Ters Repo

  **Desteklenen Fon Türleri:**
  - ✅ Yabancı Hisse Fonları (YAY, vb.) - KAP PDF'lerinde detaylı holding listesi var
  - ❌ Yurtiçi Hisse Fonları (MAC, GAF, vb.) - PDF'de sadece özet bilgi, detaylı liste yok
  - ❌ Değişken/Karma Fonlar (AAK, vb.) - farklı PDF formatı, henüz desteklenmiyor

  > **Not**: Holdings özelliği yabancı hisse fonları için optimize edilmiştir. Yurtiçi fonların KAP bildirimleri genellikle detaylı holding listesi içermez.

- **Technical Scanner (Teknik Tarama)**: Teknik koşullara göre hisse tarama
  ```python
  import borsapy as bp

  # Basit tarama
  bp.scan("XU030", "rsi < 30")                # RSI oversold
  bp.scan("XU100", "price > sma_50")          # SMA50 üzerinde
  bp.scan("XBANK", "change_percent > 3")      # %3+ yükselenler

  # Compound koşullar
  bp.scan("XU030", "rsi < 30 and volume > 1000000")

  # TechnicalScanner class
  scanner = bp.TechnicalScanner()
  scanner.set_universe("XU030")
  scanner.add_condition("rsi < 30", name="oversold")
  scanner.add_condition("volume > 1000000", name="high_vol")
  results = scanner.run()
  ```

  **Desteklenen Alanlar:**
  | Kategori | Alanlar |
  |----------|---------|
  | Fiyat | `price`, `close`, `open`, `high`, `low`, `volume`, `change_percent`, `market_cap` |
  | RSI | `rsi`, `rsi_7`, `rsi_14` |
  | SMA | `sma_5`, `sma_10`, `sma_20`, `sma_30`, `sma_50`, `sma_100`, `sma_200` |
  | EMA | `ema_5`, `ema_10`, `ema_12`, `ema_20`, `ema_26`, `ema_50`, `ema_100`, `ema_200` |
  | MACD | `macd`, `signal`, `histogram` |
  | Stochastic | `stoch_k`, `stoch_d` |
  | Diğer | `adx`, `bb_upper`, `bb_middle`, `bb_lower`, `atr`, `cci`, `wr` |

  **Desteklenen Timeframe'ler:** `1m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `1d`, `1W`, `1M`

  **Alan Karşılaştırma:**
  ```python
  bp.scan("XU030", "sma_20 > sma_50")   # SMA20 > SMA50 (golden cross durumu)
  bp.scan("XU030", "macd > signal")     # MACD bullish
  bp.scan("XU030", "close > bb_upper")  # Bollinger üst bandı üzerinde
  ```

  **Crossover Koşulları:**
  ```python
  bp.scan("XU030", "sma_20 crosses_above sma_50")  # Golden cross
  bp.scan("XU030", "sma_20 crosses_below sma_50")  # Death cross
  bp.scan("XU030", "macd crosses signal")          # MACD line crosses signal
  ```

  **Yüzde Koşulları:**
  ```python
  bp.scan("XU030", "close above_pct sma_50 1.05")  # Close, SMA50'nin %5 üzerinde
  bp.scan("XU030", "close below_pct sma_50 0.95")  # Close, SMA50'nin %5 altında
  ```

#### Technical Changes
- `_providers/tradingview_screener_native.py`: Yeni TradingView Scanner API provider (~320 satır)
  - `TVScreenerProvider` class: `tradingview-screener` paketi wrapper
  - `FIELD_MAP`: borsapy alan adları → TradingView sütun adları (35+ mapping)
  - `INTERVAL_MAP`: Timeframe → TradingView suffix (|1, |5, |15, |30, |60, |240, |1W, |1M)
  - `scan()`: TradingView Scanner API ile batch tarama
  - `_parse_condition()`: Koşul string → col() expression
  - `_parse_crossover()`: Crossover koşul parsing (previous bar [1] suffix)
  - `_get_tv_column()`: Alan adı çevirisi + interval suffix
  - `_normalize_columns()`: TradingView → borsapy sütun adı normalizasyonu
- `scanner.py`: TradingView-native backend ile yeniden yazıldı (~400 satır)
  - Lokal gösterge hesaplama kodu kaldırıldı
  - `TVScreenerProvider` singleton kullanımı
  - Geriye uyumluluk için deprecated metodlar (warnings ile)
- `condition.py`: **SİLİNDİ** (801 satır lokal parser artık gerekli değil)
- `pyproject.toml`: `tradingview-screener>=3.0.0` dependency eklendi
- `tests/test_scanner.py`: Yeniden yazıldı (~621 satır, 50 test)
- `_providers/kap_holdings.py`: Yeni KAP holdings provider (~740 satır)
  - `Holding` dataclass: symbol, isin, name, weight, type, country, value
  - `KAPHoldingsProvider` class: KAP API + PDF parsing
  - `get_fund_id()`: TEFAS kap_link → KAP objId extraction
  - `get_disclosures()`: Portföy Dağılım Raporu listesi
  - `get_holdings()`: PDF download + parsing
  - `_split_into_sections()`: Letter-prefixed section parsing (Ğ, Ş, AC, H, S)
  - `_parse_stock_section()`: Foreign/domestic stocks + ETFs
  - `_parse_fund_section()`: Fund shares (5-field and 4-field formats)
  - `_parse_cash_section()`: VİOP cash, reverse repo
  - `_parse_term_deposit_section()`: Term deposits
  - ISIN-based deduplication
  - 1 hour cache
- `fund.py`: `holdings` property ve `get_holdings()` metodu eklendi
- `pyproject.toml`: `pdfplumber>=0.11.8` dependency eklendi
- `tests/test_holdings.py`: 19 unit + integration test (~330 satır)

---

### v0.5.8 (2026-01-23)

#### New Features
- **Backtest Engine**: Strateji backtesting framework
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
  print(f"Win Rate: {result.win_rate:.1f}%")
  print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
  print(f"Max Drawdown: {result.max_drawdown:.2f}%")
  print(f"Total Trades: {result.total_trades}")

  # DataFrame export
  print(result.trades_df)      # Trade history
  print(result.equity_curve)   # Equity over time

  # Backtest class ile
  bt = bp.Backtest(
      symbol="GARAN",
      strategy=rsi_strategy,
      period="2y",
      capital=50000,
      indicators=['rsi', 'macd', 'bollinger']
  )
  result = bt.run()
  ```

  **BacktestResult Metrics:**
  - `net_profit`, `net_profit_pct`: Net kar ve yüzde
  - `total_trades`, `winning_trades`, `losing_trades`: İşlem sayıları
  - `win_rate`: Kazanç oranı (%)
  - `profit_factor`: Brüt kar / brüt zarar
  - `sharpe_ratio`, `sortino_ratio`: Risk-adjusted returns
  - `max_drawdown`: Maksimum düşüş (%)
  - `avg_trade`: Ortalama işlem karı
  - `buy_hold_return`, `vs_buy_hold`: Buy & Hold karşılaştırması
  - `trades_df`: Trade DataFrame (entry, exit, profit, duration)
  - `equity_curve`: Portföy değeri zaman serisi

  **Desteklenen Göstergeler:**
  | Gösterge | Format | Açıklama |
  |----------|--------|----------|
  | `rsi` | `rsi`, `rsi_7`, `rsi_21` | RSI (varsayılan 14) |
  | `sma` | `sma_20`, `sma_50`, `sma_200` | Simple Moving Average |
  | `ema` | `ema_12`, `ema_26`, `ema_50` | Exponential Moving Average |
  | `macd` | `macd` | MACD, Signal, Histogram |
  | `bollinger` | `bollinger` | Upper, Middle, Lower bands |
  | `atr` | `atr`, `atr_20` | Average True Range |
  | `stochastic` | `stochastic` | %K, %D |
  | `adx` | `adx` | ADX |

- **Pine Script Streaming Indicators**: TradingView Pine Script göstergeleri
  ```python
  import borsapy as bp

  stream = bp.TradingViewStream()
  stream.connect()

  # Önce chart'a abone ol
  stream.subscribe_chart("THYAO", "1m")

  # Pine gösterge ekle (TradingView hesaplama)
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

  **Desteklenen Pine Göstergeler (STD;*):**
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

  **Custom Indicator Kullanımı (Auth gerekli):**
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

- **VIOP Real-time Streaming**: VİOP vadeli işlem kontratları için gerçek zamanlı veri akışı
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

  # Gerçek zamanlı VIOP streaming
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

  **VIOP Kontrat Formatı:**
  - Base symbol + Month code + Year: `XU030DG2026`
  - Month codes: F=Jan, G=Feb, H=Mar, J=Apr, K=May, M=Jun, N=Jul, Q=Aug, U=Sep, V=Oct, X=Nov, Z=Dec

  **Desteklenen VIOP Kontratları:**
  | Tip | Örnek Base Symbol | Açıklama |
  |-----|-------------------|----------|
  | Endeks | `XU030D`, `XU100D`, `XLBNKD` | BIST endeks vadeli |
  | Döviz | `USDTRYD`, `EURTRD` | Döviz vadeli |
  | Altın | `XAUTRY`, `XAUUSD` | Altın vadeli (TRY/USD, D eki yok) |
  | Hisse | `THYAOD`, `GARAND` | Pay vadeli |

  > **Not**: Continuous kontratlar (`XU030D1!`) TradingView WebSocket'te çalışmıyor. Belirli vade kontratları kullanın (örn: `XU030DG2026`).

#### Technical Changes
- `backtest.py`: Yeni backtest modülü (~550 satır)
  - `Trade` dataclass: entry/exit bilgileri, profit hesaplama
  - `BacktestResult` dataclass: tüm metrikler (Sharpe, Sortino, max drawdown, vb.)
  - `Backtest` class: strateji çalıştırma engine
  - `backtest()` convenience function
  - Gösterge hesaplama (technical.py fonksiyonları ile)
- `_providers/pine_facade.py`: Yeni TradingView Pine Facade API provider (~150 satır)
  - `https://pine-facade.tradingview.com/pine-facade/translate/{id}/{version}` endpoint
  - STANDARD_INDICATORS mapping (20+ gösterge)
  - INDICATOR_OUTPUTS mapping (output field names)
  - LRU cache (maxsize=100)
  - Auth handling (session + signature cookies)
- `stream.py`: StudySession eklendi (~350 satır ek)
  - `PineStudy` dataclass: study configuration
  - `StudySession` class: study lifecycle management
  - `add_study()`, `remove_study()`, `get_study()`, `get_studies()`
  - `wait_for_study()`: blocking study value retrieval
  - `on_study()`, `on_any_study()` callbacks
  - TradingView `create_study`, `study_completed`, `study_data` message handling
  - Thread-safe storage with RLock
- `__init__.py`: Yeni exportlar
  - `Backtest`, `BacktestResult`, `Trade`, `backtest`
  - `search_viop`, `viop_contracts`
  - Version: 0.5.7 → 0.5.8
- `_providers/tradingview_search.py`: VIOP kontrat arama eklendi (~100 satır ek)
  - `search_viop()`: VIOP sembol arama
  - `get_viop_contracts()`: Belirli base symbol için aktif kontrat listesi
  - `VIOP_MONTH_CODES`: Ay kodu → ay adı mapping
  - `month_code_to_name()`: Ay kodu çevirici
- `search.py`: VIOP wrapper fonksiyonları eklendi
  - `search_viop()`: VIOP sembol arama (type=futures, exchange=BIST)
  - `viop_contracts()`: Kontrat listesi convenience function
- `tests/test_backtest.py`: 35+ unit test (~450 satır)
- `tests/test_pine_facade.py`: 40+ unit test (~400 satır)
- `tests/test_stream.py`: StudySession testleri eklendi (~200 test)
- `tests/test_search.py`: VIOP testleri eklendi (10 test)

---

### v0.5.7 (2026-01-22)

#### New Features
- **Search (Sembol Arama)**: TradingView symbol search API ile çoklu piyasada sembol arama
  ```python
  import borsapy as bp

  # Basit arama
  bp.search("banka")           # ['AKBNK', 'GARAN', 'ISCTR', ...]
  bp.search("enerji")          # ['AKSEN', 'ODAS', 'ZOREN', ...]
  bp.search("THY")             # ['THYAO']

  # Filtreleme
  bp.search("gold", type="forex")     # Altın pariteleri
  bp.search("BTC", type="crypto")     # Kripto
  bp.search("XU", type="index")       # Endeksler

  # Exchange filtresi
  bp.search("GARAN", exchange="BIST") # Sadece BIST

  # Detaylı sonuç
  bp.search("THYAO", full_info=True)  # Tüm metadata

  # Kısa yol fonksiyonları
  bp.search_bist("banka")      # Sadece BIST hisseleri
  bp.search_crypto("ETH")      # Sadece kripto
  bp.search_forex("USD")       # Sadece forex
  bp.search_index("XU")        # Sadece endeksler
  ```

- **Heikin Ashi Charts**: Alternatif mum grafiği hesaplama
  ```python
  import borsapy as bp

  stock = bp.Ticker("THYAO")

  # Pure function
  df = stock.history(period="1y")
  ha_df = bp.calculate_heikin_ashi(df)
  # Columns: HA_Open, HA_High, HA_Low, HA_Close, Volume

  # Convenience method
  ha_df = stock.heikin_ashi(period="1y")

  # TechnicalAnalyzer ile
  ta = stock.technicals(period="1y")
  ha_df = ta.heikin_ashi()
  ```

  **Formül:**
  ```
  HA_Close = (Open + High + Low + Close) / 4
  HA_Open  = (Prev_HA_Open + Prev_HA_Close) / 2  (ilk satır: (O+C)/2)
  HA_High  = max(High, HA_Open, HA_Close)
  HA_Low   = min(Low, HA_Open, HA_Close)
  ```

- **ChartSession (OHLCV via WebSocket)**: Gerçek zamanlı mum grafiği streaming
  ```python
  import borsapy as bp

  stream = bp.TradingViewStream()
  stream.connect()

  # Quote + Chart subscription
  stream.subscribe("THYAO")              # Anlık fiyat (mevcut)
  stream.subscribe_chart("THYAO", "1m")  # 1 dakikalık mumlar (YENİ)

  # Callback ile mum güncellemeleri
  def on_candle(symbol, interval, candle):
      print(f"{symbol} {interval}: O={candle['open']} C={candle['close']}")

  stream.on_candle("THYAO", "1m", on_candle)

  # Cached candle al
  candle = stream.get_candle("THYAO", "1m")
  # {'time': 1737123456, 'open': 285, 'high': 286, 'low': 284, 'close': 285.5, 'volume': 12345}

  # Tüm mumları al
  candles = stream.get_candles("THYAO", "1m")  # List of candles

  # İlk mum için bekle
  candle = stream.wait_for_candle("THYAO", "1m", timeout=10.0)

  stream.disconnect()
  ```

  **Desteklenen Timeframe'ler:**
  | Interval | TradingView Value |
  |----------|-------------------|
  | 1m | `'1'` |
  | 5m | `'5'` |
  | 15m | `'15'` |
  | 30m | `'30'` |
  | 1h | `'60'` |
  | 4h | `'240'` |
  | 1d | `'1D'` |
  | 1wk | `'1W'` |
  | 1mo | `'1M'` |

- **Replay Mode**: Backtesting için tarihsel veri replay
  ```python
  import borsapy as bp

  # Basit replay
  session = bp.create_replay("THYAO", period="6mo", speed=5.0)

  for candle in session.replay():
      print(f"{candle['timestamp']}: Close={candle['close']}")
      # Trading logic...

  # Callback ile
  def on_candle(c):
      print(f"Progress: {c['_index']}/{c['_total']}")

  session.on_candle(on_candle)
  list(session.replay())  # Callbacks fire automatically

  # Tarih filtresi
  for candle in session.replay_filtered(
      start_date="2024-01-01",
      end_date="2024-06-01"
  ):
      pass

  # İstatistikler
  print(session.stats())
  # {'symbol': 'THYAO', 'total_candles': 252, 'progress': 0.5, ...}
  ```

  **Candle Format:**
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

#### Technical Changes
- `_providers/tradingview_search.py`: Yeni TradingView symbol search provider (~275 satır)
  - V3 API endpoint: `symbol_search/v3/`
  - Legacy fallback: `symbol_search/`
  - Type filtering: stock, forex, crypto, index, futures, bond, fund
  - Exchange filtering: BIST, NASDAQ, NYSE, LSE, XETR, AMEX
  - 1 saatlik cache
- `search.py`: Search wrapper modülü (~150 satır)
  - `search()`, `search_bist()`, `search_crypto()`, `search_forex()`, `search_index()`
  - KAP şirket listesi ile merge (BIST sonuçları için)
  - Deduplication ve sıralama
- `charts.py`: Heikin Ashi hesaplama modülü (~100 satır)
  - `calculate_heikin_ashi(df)` pure function
  - Edge case handling (ilk satır, eksik volume)
- `stream.py`: ChartSession eklendi (~200 satır ek)
  - `_chart_session`, `_chart_data`, `_chart_callbacks` attributes
  - `subscribe_chart()`, `unsubscribe_chart()`
  - `get_candle()`, `get_candles()`, `wait_for_candle()`
  - `on_candle()`, `on_any_candle()` callbacks
  - TradingView `create_series`, `timescale_update`, `du` message handling
- `replay.py`: Yeni replay modülü (~250 satır)
  - `ReplaySession` class: Generator-based memory efficient replay
  - `create_replay()` convenience function
  - Speed control, date filtering, callback support
  - Progress tracking ve statistics
- `technical.py`: `TechnicalMixin.heikin_ashi()` metodu eklendi
- `__init__.py`: Yeni exportlar
  - `search`, `search_bist`, `search_crypto`, `search_forex`, `search_index`
  - `calculate_heikin_ashi`
  - `ReplaySession`, `create_replay`
- `tests/test_search.py`: 22 unit test
- `tests/test_charts.py`: 16 unit test
- `tests/test_replay.py`: 42 unit test
- `tests/test_stream.py`: ChartSession testleri eklendi (~35 test)

---

### v0.5.6 (2026-01-22)

#### New Features
- **TradingView Persistent WebSocket Streaming**: Düşük gecikmeli, yüksek verimli gerçek zamanlı veri akışı
  ```python
  import borsapy as bp

  # Stream oluştur ve bağlan
  stream = bp.TradingViewStream()
  stream.connect()

  # Sembollere abone ol
  stream.subscribe("THYAO")
  stream.subscribe("GARAN")
  stream.subscribe("ASELS")

  # Anlık fiyat al (cached, ~1ms)
  quote = stream.get_quote("THYAO")
  print(quote['last'])      # 299.0
  print(quote['bid'])       # 298.9
  print(quote['ask'])       # 299.1
  print(quote['volume'])    # 12345678

  # İlk quote için bekle (blocking)
  quote = stream.wait_for_quote("THYAO", timeout=5.0)

  # Callback ile real-time updates
  def on_price_update(symbol, quote):
      print(f"{symbol}: {quote['last']}")

  stream.on_quote("THYAO", on_price_update)

  # Tüm semboller için callback
  stream.on_any_quote(lambda s, q: print(f"{s}: {q['last']}"))

  # Bağlantıyı kapat
  stream.disconnect()

  # Context manager kullanımı
  with bp.TradingViewStream() as stream:
      stream.subscribe("THYAO")
      while True:
          quote = stream.get_quote("THYAO")
          # Trading logic...
  ```

#### Performance Metrics
| Metrik | Önceki (get_quote) | Yeni (TradingViewStream) |
|--------|-------------------|--------------------------|
| Latency | ~7000ms | ~50-100ms |
| Throughput | 0.1 req/s | 10-20 req/s |
| Connection | Her istekte yeni | Tek persistent |
| Data Model | Request/Response | Streaming |
| Cached Quote | N/A | <1ms |

#### TradingView Authentication (Real-time Data)
```python
import borsapy as bp

# Yöntem 1: Username/Password ile login
bp.set_tradingview_auth(
    username="user@email.com",
    password="mypassword"
)

# Yöntem 2: Mevcut session token ile
bp.set_tradingview_auth(
    session="abc123...",
    session_sign="xyz789..."
)

# Artık canlı veri (15 dakika gecikme yok)
stream = bp.TradingViewStream()
stream.connect()
stream.subscribe("THYAO")
quote = stream.wait_for_quote("THYAO")
print(quote['last'])  # Real-time fiyat

# Logout
bp.clear_tradingview_auth()
```

**Session süresi:** ~30 gün (remember=on ile)

#### Quote Fields (46 alan)
- **Fiyat**: `last`, `change`, `change_percent`, `bid`, `ask`, `bid_size`, `ask_size`, `volume`
- **OHLC**: `open`, `high`, `low`, `prev_close`
- **Fundamentals**: `market_cap`, `pe_ratio`, `eps`, `dividend_yield`, `beta`
- **52 Hafta**: `high_52_week`, `low_52_week`
- **Meta**: `description`, `currency`, `timestamp`

#### Technical Changes
- `stream.py`: Yeni TradingViewStream sınıfı (~500 satır)
  - Persistent WebSocket connection in background thread
  - Thread-safe quote caching with RLock
  - Callback pattern for real-time updates
  - Heartbeat handling (~30 saniyede bir)
  - Auto-reconnection with exponential backoff (max 30s)
  - Context manager support (`with` statement)
  - `subscribe()`, `unsubscribe()`, `get_quote()`, `wait_for_quote()`
  - `on_quote()`, `on_any_quote()` callback registration
- `_providers/tradingview.py`: TradingView authentication
  - `set_tradingview_auth()` - Login with username/password or session tokens
  - `clear_tradingview_auth()` - Clear credentials
  - `login_user()` - POST to /accounts/signin/
  - `get_user()` - Extract auth_token from HTML
  - Session cookies: sessionid, sessionid_sign
- `__init__.py`: `TradingViewStream`, `create_stream`, `set_tradingview_auth`, `clear_tradingview_auth` export eklendi
- `tests/test_stream.py`: 35+ unit test + integration test

#### Use Cases
```python
# Simple Trade Bot
stream = bp.TradingViewStream()
stream.connect()
stream.subscribe("THYAO")

prev_price = None
while True:
    quote = stream.get_quote("THYAO")
    if quote and prev_price:
        change = (quote['last'] - prev_price) / prev_price
        if change > 0.01:  # %1 artış
            print(f"BUY SIGNAL: {quote['last']}")
        elif change < -0.01:  # %1 düşüş
            print(f"SELL SIGNAL: {quote['last']}")
    prev_price = quote['last'] if quote else prev_price
    time.sleep(0.1)

# Multi-Symbol Scanner
stream = bp.TradingViewStream()
stream.connect()

for symbol in bp.Index("XU030").component_symbols:
    stream.subscribe(symbol)

def check_breakout(symbol, quote):
    # Breakout detection logic...
    pass

for symbol in stream.subscribed_symbols:
    stream.on_quote(symbol, check_breakout)

stream.wait()  # Block forever
```

---

### v0.5.5 (2026-01-22)

#### New Features
- **ETF Holders**: Uluslararası ETF'lerin BIST hisse pozisyonlarını görüntüleme
  ```python
  import borsapy as bp

  stock = bp.Ticker("ASELS")

  # ETF holder listesi (DataFrame)
  holders = stock.etf_holders
  #    symbol exchange                                      name  market_cap_usd  holding_weight_pct           issuer management      focus  expense_ratio     aum_usd
  # 0    IEMG     AMEX  iShares Core MSCI Emerging Markets ETF    118225730.76            0.090686  BlackRock, Inc.     Passive  Total Mkt           0.09  85000000000
  # 1     VWO     AMEX     Vanguard FTSE Emerging Markets ETF     85480000.00            0.060000     Vanguard Inc     Passive  Total Mkt           0.07  75000000000

  # Özet bilgi
  print(f"Total ETFs: {len(holders)}")
  print(f"Top holder: {holders.iloc[0]['name']}")
  print(f"Total weight: {holders['holding_weight_pct'].sum():.2f}%")
  ```

#### Return Format (DataFrame Columns)
| Column | Type | Description |
|--------|------|-------------|
| `symbol` | str | ETF sembol (IEMG, VWO, TUR) |
| `exchange` | str | Borsa (AMEX, NASDAQ, LSE, XETR) |
| `name` | str | ETF tam adı |
| `market_cap_usd` | float | ETF'in bu hissedeki pozisyon değeri (USD) |
| `holding_weight_pct` | float | Ağırlık yüzdesi (0.09 = %0.09) |
| `issuer` | str | İhraççı (BlackRock, Vanguard, etc.) |
| `management` | str | Yönetim stili (Passive, Active) |
| `focus` | str | Yatırım odağı (Total Market, Emerging Markets, etc.) |
| `expense_ratio` | float | Gider oranı (0.09 = %0.09) |
| `aum_usd` | float | Toplam varlık (USD) |
| `price` | float | Güncel ETF fiyatı |
| `change_pct` | float | Değişim yüzdesi |

#### Technical Changes
- `_providers/tradingview_etf.py`: Yeni TradingView ETF holder provider (~250 satır)
  - HTML scraping: `https://tr.tradingview.com/symbols/BIST-{SYMBOL}/etfs/`
  - JSON extraction from embedded script blocks
  - 1 saatlik cache (ETF pozisyonları sık değişmez)
  - Turkish → English translation (Management, Focus)
- `ticker.py`: `etf_holders` property eklendi
  - Lazy-loaded provider pattern
  - DataFrame dönüş formatı

---

### v0.5.4 (2026-01-22)

#### New Features
- **TradingView TA Signals**: TradingView Scanner API ile teknik analiz sinyalleri (BUY/SELL/NEUTRAL)
  ```python
  import borsapy as bp

  # Tek timeframe (varsayılan: günlük)
  stock = bp.Ticker("THYAO")
  signals = stock.ta_signals()
  print(signals['summary']['recommendation'])  # "STRONG_BUY", "BUY", "NEUTRAL", etc.
  print(signals['oscillators']['compute']['RSI'])  # "BUY", "SELL", "NEUTRAL"
  print(signals['moving_averages']['values']['EMA20'])  # 285.5

  # Belirli timeframe
  signals_1h = stock.ta_signals(interval="1h")

  # Tüm timeframe'ler
  all_signals = stock.ta_signals_all_timeframes()
  print(all_signals['1h']['summary']['recommendation'])

  # Index, FX, Crypto için de çalışır
  bp.Index("XU100").ta_signals()
  bp.FX("USD").ta_signals()
  bp.Crypto("BTCTRY").ta_signals()
  ```

#### Desteklenen Varlıklar
- **Ticker**: Tüm BIST hisseleri (`BIST:THYAO` → `turkey` screener)
- **Index**: Tüm BIST endeksleri (`BIST:XU100` → `turkey` screener)
- **FX**: USD, EUR, GBP, JPY + emtialar (`FX:USDTRY` → `forex` screener)
- **Crypto**: Tüm kripto paralar (`BINANCE:BTCUSDT` → `crypto` screener)

#### Desteklenen Timeframe'ler
`1m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `1d`, `1W`, `1M`

#### Return Format
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

#### Technical Changes
- `_providers/tradingview_scanner.py`: Yeni TradingView Scanner provider (~500 satır)
  - POST `https://scanner.tradingview.com/{screener}/scan`
  - 11 oscillator göstergesi: RSI, Stochastic, CCI, ADX, AO, Momentum, MACD, Stoch.RSI, W.R, BBPower, UO
  - 17 moving average: EMA/SMA (5,10,20,30,50,100,200), Ichimoku, VWMA, HullMA
  - 1 dakikalık önbellekleme
- `technical.py`: TechnicalMixin'e yeni metodlar
  - `_get_ta_symbol_info()`: Override edilmeli, (tv_symbol, screener) döndürür
  - `ta_signals(interval)`: TradingView TA sinyalleri
  - `ta_signals_all_timeframes()`: Tüm timeframe'ler için sinyaller
- `ticker.py`, `index.py`, `fx.py`, `crypto.py`: `_get_ta_symbol_info()` implementasyonları
- `tests/test_ta_signals.py`: 41 unit + integration test

---

### v0.5.3 (2026-01-20)

#### New Features
- **FX İntraday Veri Desteği**: Dakikalık ve saatlik döviz/emtia verileri TradingView üzerinden
  ```python
  usd = bp.FX("USD")

  # Dakikalık veri
  usd.history(period="1d", interval="1m")   # 1 dakikalık
  usd.history(period="1d", interval="5m")   # 5 dakikalık
  usd.history(period="1d", interval="15m")  # 15 dakikalık
  usd.history(period="1d", interval="30m")  # 30 dakikalık

  # Saatlik veri
  usd.history(period="5d", interval="1h")   # Saatlik
  usd.history(period="1mo", interval="4h")  # 4 saatlik

  # Günlük (varsayılan, canlidoviz kullanır)
  usd.history(period="1mo")                 # Günlük
  ```

#### Desteklenen İntraday Varlıklar (TradingView)
- **Dövizler**: USD, EUR, GBP, JPY (TRY çiftleri)
- **Emtialar**: ons-altin/XAU, XAG, XPT, XPD, BRENT, WTI (USD çiftleri)

> **Not**: Diğer dövizler (CHF, CAD, AUD, vb.) için TradingView'da TRY çifti bulunmadığından sadece günlük veri mevcuttur.

#### Technical Changes
- `fx.py`: TradingView symbol mapping eklendi
  - `TV_CURRENCY_MAP`: USD→FX:USDTRY, EUR→FX:EURTRY, GBP→PEPPERSTONE:GBPTRY, JPY→FX:TRYJPY
  - `TV_COMMODITY_MAP`: ons-altin→OANDA:XAUUSD, BRENT→TVC:UKOIL, WTI→TVC:USOIL
- `fx.py`: `history()` metoduna `interval` parametresi eklendi
- `fx.py`: `_get_tradingview_symbol()` helper metodu eklendi
- İntraday intervals (1m, 5m, 15m, 30m, 1h, 4h) TradingView'a yönlendiriliyor
- Günlük ve üstü intervals (1d, 1wk, 1mo) canlidoviz/dovizcom kullanmaya devam ediyor

---

### v0.5.2 (2026-01-18)

#### Bug Fixes
- **Splits (Sermaye Artırımı) Boş Dönme Sorunu Düzeltildi**: `ticker.splits` artık tüm sermaye artırımı tiplerini döndürüyor
  - `SHT_KODU=01` (Bedelli Sermaye Artırımı) eklendi
  - `SHT_KODU=02` (Bedelsiz Sermaye Artırımı) eklendi
  - Önceden sadece `03` ve `09` kabul ediliyordu, KAYSE gibi hisseler boş dönüyordu
  ```python
  # Artık çalışıyor
  kayse = bp.Ticker("KAYSE")
  print(kayse.splits)  # 324.93% bedelsiz sermaye artırımı
  ```
- **Timezone Uyumsuzluğu Düzeltildi**: `history(actions=True)` çağrısında dividends ve splits tarihleri artık doğru eşleşiyor
  - `.normalize()` yerine `.date()` karşılaştırması kullanılıyor
  - Timezone-aware ve timezone-naive tarihler artık doğru karşılaştırılıyor

#### Technical Changes
- `_providers/isyatirim.py`: `_parse_capital_increases()` metodunda SHT_KODU filtresi genişletildi (01, 02, 03, 09)
- `ticker.py`: `_add_actions_to_history()` metodunda timezone-agnostic tarih karşılaştırması

---

### v0.5.1 (2026-01-15)

#### Breaking Changes
- **TradingView Veri Kaynağı**: Paratic API dış erişime kapatıldığı için tüm fiyat verileri artık TradingView WebSocket API üzerinden geliyor
  - `Ticker.history()`, `Ticker.info`, `Ticker.fast_info` artık TradingView kullanıyor
  - `Index.history()`, `Index.info` artık TradingView kullanıyor
  - `Tickers`, `download()` fonksiyonları artık TradingView kullanıyor
  - Veri gecikmesi: ~15 dakika (TradingView free tier)

#### New Features
- **TradingView Provider**: WebSocket tabanlı yeni veri sağlayıcı
  ```python
  # Eskisi gibi çalışıyor - API değişmedi
  stock = bp.Ticker("THYAO")
  stock.history(period="1mo")
  stock.fast_info.last_price
  stock.info["last"]

  # Index de çalışıyor
  xu100 = bp.Index("XU100")
  xu100.history(period="1y")
  ```
- **Banka Finansal Tabloları**: `financial_group` parametresi ile banka mali tablolarına erişim
  ```python
  # Bankalar UFRS formatı kullanır
  banka = bp.Ticker("AKBNK")
  banka.get_balance_sheet(financial_group="UFRS")
  banka.get_income_stmt(financial_group="UFRS")
  banka.get_cashflow(financial_group="UFRS")

  # Çeyreklik banka tabloları
  banka.get_balance_sheet(quarterly=True, financial_group="UFRS")

  # Banka TTM
  banka.get_ttm_income_stmt(financial_group="UFRS")
  banka.get_ttm_cashflow(financial_group="UFRS")

  # Sınai şirketler (varsayılan XI_29)
  hisse = bp.Ticker("THYAO")
  hisse.get_balance_sheet()  # XI_29 formatı (varsayılan)
  ```

#### Technical Changes
- `_providers/tradingview.py`: Yeni TradingView WebSocket provider (~350 satır)
  - WebSocket protokolü: `wss://data.tradingview.com/socket.io/websocket`
  - `get_quote()`: Anlık fiyat, bid/ask, volume, change
  - `get_history()`: OHLCV verileri, period/interval desteği
  - Symbol format: `BIST:THYAO`, `BIST:XU100`
- `ticker.py`: Paratic → TradingView geçişi
- `index.py`: Paratic → TradingView geçişi
- `multi.py`: Paratic → TradingView geçişi
- `pyproject.toml`: `websocket-client>=1.9.0` dependency eklendi
- `ticker.py`: Finansal tablo metodları güncellendi
  - Yeni metodlar: `get_balance_sheet()`, `get_income_stmt()`, `get_cashflow()`, `get_ttm_income_stmt()`, `get_ttm_cashflow()`
  - `financial_group` parametresi: `"UFRS"` (bankalar) veya `"XI_29"` (sınai şirketler)
  - Eski property'ler geriye uyumluluk için korundu

#### Migration Notes
- API değişmedi, sadece veri kaynağı değişti
- Paratic provider tamamen kaldırıldı (`_providers/paratic.py` silindi)
- FX, Crypto, Fund modülleri etkilenmedi (farklı kaynaklar kullanıyor)

---

### v0.4.6 (2026-01-14)

#### New Features
- **TCMB Faiz Oranları**: Merkez Bankası politika faizleri ve koridor oranları
  ```python
  tcmb = bp.TCMB()
  tcmb.policy_rate              # 1 hafta repo faizi (%)
  tcmb.overnight                # {'borrowing': 36.5, 'lending': 41.0}
  tcmb.late_liquidity           # {'borrowing': 0.0, 'lending': 44.0}
  tcmb.rates                    # Tüm oranlar (DataFrame)

  # Geçmiş veriler
  tcmb.history("policy")        # 1 hafta repo geçmişi (2010+)
  tcmb.history("overnight")     # Gecelik faiz geçmişi
  tcmb.history("late_liquidity", period="1y")  # Son 1 yıl LON

  # Kısa yol
  bp.policy_rate()              # Güncel politika faizi
  ```
- **Eurobond Verileri**: Türk devlet tahvilleri (USD/EUR cinsinden)
  ```python
  # Tüm eurobondlar
  bp.eurobonds()                # DataFrame (38+ tahvil)
  bp.eurobonds(currency="USD")  # Sadece USD tahviller
  bp.eurobonds(currency="EUR")  # Sadece EUR tahviller

  # Tek tahvil
  bond = bp.Eurobond("US900123DG28")
  bond.isin                     # US900123DG28
  bond.maturity                 # datetime(2033, 1, 19)
  bond.currency                 # USD
  bond.bid_yield                # 6.55
  bond.ask_yield                # 6.24
  bond.days_to_maturity         # 2562
  bond.info                     # Tüm veriler (dict)
  ```

#### Technical Changes
- `_providers/tcmb_rates.py`: TCMB HTML scraping provider (~225 satır)
  - 3 farklı faiz tipi: policy, overnight, late_liquidity
  - Türkçe sayı formatı parse (virgül = ondalık)
  - Geçmiş veri desteği (tablo parsing)
- `_providers/ziraat_eurobond.py`: Ziraat Bank API provider (~170 satır)
  - JSON API ile HTML tablo response
  - 38+ Eurobond (34 USD + 4 EUR)
  - ISIN, maturity, bid/ask fiyat ve getiri
- `tcmb.py`: TCMB sınıfı (~205 satır)
  - `policy_rate`, `overnight`, `late_liquidity` property'leri
  - `rates` DataFrame ve `history()` metodu
- `eurobond.py`: Eurobond sınıfı (~175 satır)
  - ISIN ile lazy-loaded data
  - `eurobonds()` fonksiyonu ile tüm tahviller
- `__init__.py`: Export'lar güncellendi
  - `TCMB`, `policy_rate`, `Eurobond`, `eurobonds`
- `tests/test_tcmb.py`: 15 unit test
- `tests/test_eurobond.py`: 22 unit test

---

### v0.4.5 (2026-01-14)

#### New Features
- **Portfolio Yönetimi**: Çoklu varlık portföy yönetimi sınıfı
  ```python
  portfolio = bp.Portfolio()
  portfolio.add("THYAO", shares=100, cost=280.0)       # Hisse
  portfolio.add("gram-altin", shares=5, asset_type="fx")  # Emtia
  portfolio.add("BTCTRY", shares=0.5)                  # Kripto (auto-detect)
  portfolio.add("YAY", shares=500, asset_type="fund")  # Fon
  portfolio.set_benchmark("XU100")                     # Benchmark

  print(portfolio.holdings)    # DataFrame: symbol, shares, cost, value, weight, pnl
  print(portfolio.value)       # Toplam değer (TL)
  print(portfolio.risk_metrics())  # Sharpe, Sortino, Beta, Alpha
  ```
- **4 Varlık Tipi Desteği**: stock, fx, crypto, fund
  - **stock** (Ticker): BIST hisseleri (varsayılan)
  - **fx** (FX): 65 döviz + metaller + emtialar (otomatik algılanır)
  - **crypto** (Crypto): *TRY pattern (6+ karakter, otomatik algılanır)
  - **fund** (Fund): TEFAS fonları (asset_type="fund" gerekli)
- **Benchmark Desteği**: Index'ler (XU100, XU030, XK030) doğrudan satın alınamaz, benchmark olarak kullanılır
  ```python
  portfolio.set_benchmark("XU100")
  portfolio.beta()           # XU100'e göre beta
  portfolio.risk_metrics()['alpha']  # XU100'e göre alpha
  ```
- **Risk Metrikleri**: Fund.risk_metrics() pattern'ını takip eder
  - Annualized return, volatility
  - Sharpe ratio, Sortino ratio
  - Beta, Alpha (benchmark'a göre)
  - Max drawdown
- **Korelasyon Matrisi**: Varlıklar arası korelasyon hesaplama
  ```python
  portfolio.correlation_matrix(period="1y")
  ```
- **Import/Export**: JSON uyumlu to_dict() ve from_dict()
- **TechnicalMixin**: Portfolio sınıfı teknik analiz metodlarını da destekler (RSI, MACD, vb.)

#### Technical Changes
- `portfolio.py`: Yeni dosya (~725 satır)
  - `Holding` dataclass: symbol, shares, cost_per_share, asset_type
  - `Portfolio` class: TechnicalMixin'den miras alır
  - `_detect_asset_type()`: FX_CURRENCIES (65 döviz), FX_METALS, FX_COMMODITIES, crypto pattern
  - `_get_asset()`: asset_type'a göre Ticker/FX/Crypto/Fund instance döndürür
- `__init__.py`: Portfolio export eklendi
- `tests/test_portfolio.py`: 53 unit test (~280 satır)

---

### v0.4.1 (2026-01-14)

#### New Features
- **Teknik Analiz Göstergeleri**: 10 popüler teknik gösterge desteği
  ```python
  stock = bp.Ticker("THYAO")

  # Tekil değerler (son değer)
  stock.rsi()                    # 48.95 (RSI-14)
  stock.sma(sma_period=20)       # 277.86 (SMA-20)
  stock.ema(ema_period=12)       # 280.12 (EMA-12)
  stock.macd()                   # {'macd': 3.78, 'signal': 2.34, 'histogram': 1.44}
  stock.bollinger_bands()        # {'upper': 296.84, 'middle': 277.86, 'lower': 258.89}
  stock.atr()                    # 5.23 (ATR-14)
  stock.stochastic()             # {'k': 65.2, 'd': 58.4}
  stock.obv()                    # 12345678 (On-Balance Volume)
  stock.vwap()                   # 279.50 (Volume Weighted Average Price)
  stock.adx()                    # 25.3 (ADX-14)

  # DataFrame ile tüm göstergeler
  df = stock.history_with_indicators(period="1y")
  # Sütunlar: Open, High, Low, Close, Volume, SMA_20, EMA_12, RSI_14, MACD, ...

  # TechnicalAnalyzer ile tam seriler
  ta = stock.technicals(period="1y")
  ta.rsi()                       # pd.Series (252 değer)
  ta.macd()                      # pd.DataFrame (MACD, Signal, Histogram)
  ta.latest                      # {'rsi_14': 48.95, 'sma_20': 277.86, ...}

  # FX, Crypto, Index için de çalışır
  bp.FX("USD").rsi()
  bp.Crypto("BTCTRY").macd()
  bp.Index("XU100").bollinger_bands()

  # Standalone fonksiyonlar
  from borsapy import calculate_rsi, calculate_macd, add_indicators
  df = bp.download("THYAO", period="1y")
  rsi = calculate_rsi(df)
  df_with_all = add_indicators(df)
  ```

#### Technical Changes
- `technical.py`: Yeni teknik analiz modülü
  - Pure fonksiyonlar: `calculate_sma`, `calculate_ema`, `calculate_tilson_t3`, `calculate_rsi`, `calculate_macd`, `calculate_bollinger_bands`, `calculate_atr`, `calculate_stochastic`, `calculate_obv`, `calculate_vwap`, `calculate_adx`, `calculate_supertrend`
  - `TechnicalAnalyzer` class: DataFrame wrapper
  - `TechnicalMixin` class: Asset sınıflarına mixin
  - `add_indicators()`: DataFrame'e gösterge sütunları ekleme
- `ticker.py`, `index.py`, `crypto.py`, `fx.py`: `TechnicalMixin` eklendi
- `__init__.py`: Teknik analiz fonksiyonları export edildi
- `tests/test_technical.py`: 35 unit test eklendi

---

### v0.4.0 (2026-01-13)

#### New Features
- **65 Döviz Desteği**: canlidoviz.com API ile 65 farklı döviz için `history()` ve `current` desteği
  ```python
  # Majör dövizler
  bp.FX("USD").history(period="1mo")  # ABD Doları
  bp.FX("EUR").history(period="1mo")  # Euro
  bp.FX("GBP").history(period="1mo")  # İngiliz Sterlini
  bp.FX("CHF").history(period="1mo")  # İsviçre Frangı
  bp.FX("CAD").history(period="1mo")  # Kanada Doları
  bp.FX("AUD").history(period="1mo")  # Avustralya Doları

  # Diğer dövizler (toplam 65)
  bp.FX("CNY").history(period="1mo")  # Çin Yuanı
  bp.FX("RUB").history(period="1mo")  # Rus Rublesi
  bp.FX("SAR").history(period="1mo")  # Suudi Arabistan Riyali
  # ... ve 56 döviz daha
  ```
- **Banka Bazlı Döviz Geçmişi**: CHF, CAD, AUD için banka bazlı geçmiş desteği
  ```python
  # CHF banka geçmişi (9 banka)
  chf = bp.FX("CHF")
  chf.institution_history("akbank", period="1mo")
  chf.institution_history("ziraat", period="1mo")

  # CAD banka geçmişi (5 banka)
  cad = bp.FX("CAD")
  cad.institution_history("akbank", period="1mo")

  # AUD banka geçmişi (5 banka)
  aud = bp.FX("AUD")
  aud.institution_history("isbank", period="1mo")
  ```
- **Emtia Desteği**: BRENT petrol ve USD bazlı değerli metaller
  ```python
  bp.FX("BRENT").history(period="1mo")    # Brent Petrol (USD)
  bp.FX("XAG-USD").history(period="1mo")  # Gümüş Ons (USD)
  bp.FX("XPT-USD").history(period="1mo")  # Platin Spot (USD)
  bp.FX("XPD-USD").history(period="1mo")  # Paladyum Spot (USD)
  ```

#### Technical Changes
- `canlidoviz.py`: 65 döviz ID'si eklendi (CURRENCY_IDS)
  - Majör: USD, EUR, GBP, CHF, CAD, AUD, JPY, NZD, SGD, HKD, TWD
  - Avrupa: DKK, SEK, NOK, PLN, CZK, HUF, RON, BGN, HRK, RSD, BAM, MKD, ALL, MDL, UAH, BYR, ISK
  - Ortadoğu/Afrika: AED, SAR, QAR, KWD, BHD, OMR, JOD, IQD, IRR, LBP, SYP, EGP, LYD, TND, DZD, MAD, ZAR, ILS
  - Asya/Pasifik: CNY, INR, PKR, LKR, IDR, MYR, THB, PHP, KRW, KZT, AZN, GEL
  - Amerika: MXN, BRL, ARS, CLP, COP, PEN, UYU, CRC
  - Diğer: RUB, DVZSP1 (Sepet Kur)
- `canlidoviz.py`: Banka bazlı döviz ID'leri eklendi
  - BANK_CHF_IDS (9 banka)
  - BANK_CAD_IDS (5 banka)
  - BANK_AUD_IDS (5 banka)
  - BANK_JPY_IDS (6 banka)
  - BANK_RUB_IDS (10 banka)
  - BANK_SAR_IDS (12 banka)
  - BANK_AED_IDS (4 banka)
  - BANK_CNY_IDS (3 banka)
- `canlidoviz.py`: Emtia ID'leri eklendi
  - ENERGY_IDS: BRENT=266
  - COMMODITY_IDS: XAG-USD=267, XPT-USD=268, XPD-USD=269
- `canlidoviz.py`: `get_bank_rates()` HTML scraping metodu eklendi (alternatif kaynak)
- `fx.py`: `_get_item_id()` tüm yeni döviz ve emtiaları destekliyor

---

### v0.3.5 (2026-01-13)

#### Bug Fixes
- **Token-free FX data**: canlidoviz.com entegrasyonu ile döviz/metal verileri artık token gerektirmiyor
  - `history()`, `current` metodları canlidoviz.com API kullanıyor
  - doviz.com token expiration (401 Unauthorized) sorunu çözüldü
  - USD, EUR, GBP tam destekli (canlidoviz API)
  - CHF, CAD, AUD, JPY için bank_rates ortalaması kullanılıyor (fallback)
  - Tüm metaller (gram-altin, ceyrek-altin, yarim-altin, tam-altin, cumhuriyet-altin, ons-altin, gram-gumus) destekleniyor
  - `institution_history()` dövizler için canlidoviz, metaller için henüz desteklenmiyor
  - HTML scraping metodları (bank_rates, institution_rates) hala doviz.com kullanıyor (token gerektirmiyor)

#### Technical Changes
- `canlidoviz.py`: Yeni token-free provider
  - Doğru currency ID'leri: USD=1, EUR=50, GBP=100
  - Doğru metal ID'leri: gram-altin=32, ceyrek-altin=11, yarim-altin=47, tam-altin=14, ons-altin=81, gram-gumus=64
  - Bank-specific USD/EUR/GBP ID'leri (institution_history için)
- `fx.py`: Router mantığı
  - `_use_canlidoviz()`: Hangi provider'ı kullanacağına karar veriyor
  - `_current_from_bank_rates()`: API desteklenmeyen dövizler için bank_rates ortalaması
- `dovizcom.py`: Sadece HTML scraping (bank_rates, institution_rates) ve energy/fuel assets için

---

### v0.3.4 (2026-01-12)

#### Bug Fixes
- **Fix 401 Unauthorized for currency institution_history**: Origin header `kur.doviz.com` olarak düzeltildi

---

### v0.3.2 (2025-01-12)

#### New Features
- **`amount` field**: TL bazında işlem hacmi (`fast_info.amount`, `info['amount']`)
- **Doğru lot hacmi**: `volume` artık TL hacminden hesaplanıyor (Paratic'in hatalı `v` değeri yerine)
- **Banka kurları**: `FX.bank_rates` ve `FX.bank_rate(bank)` ile 36+ bankanın döviz kurları
  ```python
  usd = bp.FX("USD")
  usd.bank_rates        # Tüm bankaların alış/satış kurları (DataFrame)
  usd.bank_rate("akbank")  # Tek banka kuru (dict)
  bp.banks()            # Desteklenen banka listesi
  ```
- **Değerli metal kurum fiyatları**: `FX.institution_rates` ve `FX.institution_rate()` ile kuyumcu/banka altın/gümüş/platin fiyatları
  ```python
  gold = bp.FX("gram-altin")
  gold.institution_rates              # Tüm kurumların fiyatları (DataFrame)
  gold.institution_rate("akbank")     # Tek kurum fiyatı (dict)
  bp.metal_institutions()             # Desteklenen emtialar
  # Desteklenen emtialar: gram-altin, gram-gumus, ons-altin, gram-platin, gram-paladyum
  ```
- **Kurum bazlı geçmiş fiyatlar**: `FX.institution_history()` ile kurum bazlı geçmiş (metal + döviz)
  ```python
  # Metal geçmişi
  gold = bp.FX("gram-altin")
  gold.institution_history("akbank", period="1mo")     # Akbank 1 aylık gram altın
  gold.institution_history("kapalicarsi", period="3mo") # Kapalıçarşı 3 aylık

  # Döviz geçmişi
  usd = bp.FX("USD")
  usd.institution_history("akbank", period="1mo")      # Akbank 1 aylık USD
  usd.institution_history("garanti-bbva", period="5d") # Garanti 5 günlük

  # 27 kurum destekleniyor (bankalar + kuyumcular)
  # Kuyumcular (kapalicarsi, harem, altinkaynak) OHLC verir
  # Bankalar (akbank, garanti) sadece Close verir
  ```
- **Fon varlık dağılımı**: `Fund.allocation`, `Fund.allocation_history()` ve `Fund.info['allocation']`
  ```python
  fund = bp.Fund("AAK")
  fund.info['allocation']                # info içinde (ekstra API çağrısı yok)
  fund.allocation                        # Son 7 günlük dağılım (ayrı API)
  fund.allocation_history(period="3mo")  # Son 3 ay (max ~100 gün)
  # asset_type: Türkçe (Hisse Senedi, Ters-Repo, etc.)
  # asset_name: İngilizce (Stocks, Reverse Repo, etc.)
  # weight: Ağırlık (%)
  ```
- **Zenginleştirilmiş Fund.info**: ISIN, komisyonlar, kategori sıralaması, günlük/haftalık getiri
  ```python
  fund.info['isin']           # ISIN kodu
  fund.info['daily_return']   # Günlük getiri
  fund.info['weekly_return']  # Haftalık getiri
  fund.info['category_rank']  # Kategori sırası (örn: 20/181)
  fund.info['entry_fee']      # Giriş komisyonu
  fund.info['exit_fee']       # Çıkış komisyonu
  ```
- **Fon tarama ve karşılaştırma**: `screen_funds()` ve `compare_funds()` fonksiyonları
  ```python
  # Fon tarama - getiri kriterlerine göre filtrele
  bp.screen_funds(fund_type="YAT", min_return_1y=50)  # >%50 1Y getiri
  bp.screen_funds(fund_type="EMK", min_return_ytd=20) # Emeklilik fonları

  # Fon karşılaştırma - yan yana analiz
  result = bp.compare_funds(["AAK", "TTE", "AFO"])
  result['funds']      # Fon detayları listesi
  result['rankings']   # Sıralamalar (by_return_1y, by_size, by_risk_asc)
  result['summary']    # Özet (avg_return_1y, best/worst, total_size)
  ```
- **Ekonomik Takvim**: `EconomicCalendar` sınıfı ve `economic_calendar()` fonksiyonu
  ```python
  cal = bp.EconomicCalendar()
  cal.events(period="1w")                    # Bu hafta
  cal.events(country="TR", importance="high") # Sadece önemli TR olayları
  cal.today()                                # Bugünkü olaylar
  cal.this_week()                            # Bu hafta
  bp.economic_calendar(period="1mo", country="TR")  # Kısa yol
  ```
- **Tahvil/Bono**: `Bond` sınıfı ve `bonds()`, `risk_free_rate()` fonksiyonları
  ```python
  bond = bp.Bond("10Y")           # 10 yıllık tahvil
  bond.yield_rate                 # Faiz oranı (örn: 28.03)
  bond.yield_decimal              # Ondalık (örn: 0.2803)
  bp.bonds()                      # Tüm tahvil faizleri (DataFrame)
  bp.risk_free_rate()             # 10Y faiz (DCF hesaplamaları için)
  ```
- **Endeks Bileşenleri**: `Index.components` ve `Index.component_symbols` ile endeks içindeki hisseler
  ```python
  # Endeks bileşenlerini listele
  xu030 = bp.Index("XU030")
  xu030.components           # [{'symbol': 'AKBNK', 'name': 'AKBANK'}, ...]
  xu030.component_symbols    # ['AKBNK', 'ASELS', 'BIMAS', ...]
  len(xu030.components)      # 30

  # Katılım endeksleri
  xk030 = bp.Index("XK030")
  xk030.components           # Katılım 30 bileşenleri

  # Tüm endeksler (79 endeks)
  bp.indices()               # Popüler endeksler listesi
  bp.indices(detailed=True)  # [{'symbol': 'XU100', 'name': 'BIST 100', 'count': 100}, ...]
  bp.all_indices()           # BIST'teki tüm 79 endeks
  ```
- **Hisse Tarama**: `Screener` sınıfı ve `screen_stocks()` fonksiyonu
  ```python
  # Basit kullanım
  bp.screen_stocks(template="high_dividend")
  bp.screen_stocks(market_cap_min=1000, pe_max=15)

  # Fluent API
  screener = bp.Screener()
  screener.add_filter("market_cap", min=1000)
  screener.add_filter("dividend_yield", min=3)
  screener.set_sector("Bankacılık")
  results = screener.run()

  # Yardımcı fonksiyonlar
  bp.screener_criteria()          # Mevcut filtre kriterleri
  bp.sectors()                    # Sektör listesi
  bp.stock_indices()              # Endeks listesi (BIST30, BIST100, etc.)
  ```
- **Fund uzun period desteği**: `Fund.history()` artık 3y, 5y, max periodlarını destekliyor
  ```python
  fund = bp.Fund("YAY")
  fund.history(period="1y")   # 252 veri noktası
  fund.history(period="3y")   # 752 veri noktası
  fund.history(period="5y")   # 1255 veri noktası
  fund.history(period="max")  # 5 yıla kadar tüm veriler
  ```
- **Fund risk metrikleri**: `Fund.sharpe_ratio()` ve `Fund.risk_metrics()` metodları
  ```python
  fund = bp.Fund("YAY")
  fund.sharpe_ratio()           # 1Y Sharpe (10Y tahvil faizi ile)
  fund.sharpe_ratio(period="3y") # 3Y Sharpe

  # Tüm risk metrikleri
  metrics = fund.risk_metrics(period="1y")
  metrics['annualized_return']    # Yıllık getiri (%)
  metrics['annualized_volatility'] # Yıllık volatilite (%)
  metrics['sharpe_ratio']         # Sharpe oranı
  metrics['sortino_ratio']        # Sortino oranı (downside risk)
  metrics['max_drawdown']         # Maksimum düşüş (%)
  ```
- **Değerli metal history desteği**: `gram-gumus`, `ons-altin`, `gram-platin`, `gram-paladyum` için history desteği eklendi
  ```python
  # Yeni desteklenen metaller
  bp.FX("gram-gumus").history(period="1mo")    # Gram gümüş geçmişi
  bp.FX("ons-altin").history(period="1mo")     # Ons altın geçmişi
  bp.FX("gram-platin").history(period="1mo")   # Gram platin geçmişi
  bp.FX("gram-paladyum").history(period="1mo") # Gram paladyum geçmişi

  # Current fiyatlar da çalışıyor
  bp.FX("gram-platin").current   # {'symbol': 'gram-platin', 'last': 3182.18, ...}
  ```
- **API Dokümantasyonu**: pdoc ile otomatik API referans dokümantasyonu
  ```bash
  # GitHub Pages: https://saidsurucu.github.io/borsa-py/
  uv run pdoc borsapy -o docs  # HTML çıktı
  uv run pdoc borsapy          # Canlı önizleme (localhost:8080)
  ```

#### Bug Fixes
- Paratic API'nin yanlış lot hacmi (`v` field) sorunu düzeltildi - artık `amount / last` formülüyle hesaplanıyor
- TEFAS WAF bloklama sorunu çözüldü - 90 günden uzun istekler artık chunked requests ile yapılıyor

#### Technical Changes
- `paratic.py`: `get_quote()` metoduna `amount` eklendi, `volume` hesaplama mantığı güncellendi
- `ticker.py`: `FastInfo` ve `EnrichedInfo` sınıflarına `amount` alanı eklendi
- `dovizcom.py`: Banka kurları için `get_bank_rates()`, `get_banks()` metodları eklendi (BeautifulSoup + regex)
- `fx.py`: `bank_rates` property, `bank_rate()` metodu ve `banks()` fonksiyonu eklendi
- `__init__.py`: `banks()` fonksiyonu export edildi
- `tefas.py`: `ASSET_TYPE_MAPPING`, `ASSET_NAME_STANDARDIZATION` ve `get_allocation()` metodu eklendi
- `tefas.py`: `get_fund_detail()` zenginleştirildi (allocation, ISIN, komisyon, kategori sıralaması, günlük/haftalık getiri)
- `tefas.py`: `screen_funds()` ve `compare_funds()` metodları eklendi (BindComparisonFundReturns API)
- `fund.py`: `allocation` property, `allocation_history()`, `screen_funds()`, `compare_funds()` eklendi
- `dovizcom_calendar.py`: Ekonomik takvim provider'ı eklendi (doviz.com/calendar API)
- `dovizcom_tahvil.py`: Tahvil faizleri provider'ı eklendi (doviz.com/tahvil HTML scraping)
- `isyatirim_screener.py`: Hisse tarama provider'ı eklendi (İş Yatırım getScreenerDataNEW API)
- `calendar.py`: `EconomicCalendar` sınıfı ve `economic_calendar()` fonksiyonu eklendi
- `bond.py`: `Bond` sınıfı, `bonds()` ve `risk_free_rate()` fonksiyonları eklendi
- `screener.py`: `Screener` sınıfı, `screen_stocks()`, `screener_criteria()`, `sectors()`, `stock_indices()` eklendi
- `tefas.py`: Chunked requests desteği eklendi (WAF bypass için 90 günlük parçalar, rate limiting gecikmesi)
- `fund.py`: `sharpe_ratio()` ve `risk_metrics()` metodları eklendi (Sharpe, Sortino, max drawdown, volatility)
- `dovizcom.py`: `METAL_SLUGS`, `get_metal_institution_rates()`, `get_metal_institutions()` metodları eklendi (altin.doviz.com HTML scraping)
- `fx.py`: `institution_rates` property, `institution_rate()` metodu ve `metal_institutions()` fonksiyonu eklendi
- `__init__.py`: `metal_institutions()` fonksiyonu export edildi
- `dovizcom.py`: `HISTORY_API_SLUGS` mapping ve yeni metal slug'ları SUPPORTED_ASSETS'e eklendi (gram-gumus, ons-altin, gram-platin, gram-paladyum)
- `dovizcom.py`: `INSTITUTION_IDS` mapping (27 kurum) ve `get_metal_institution_history()` metodu eklendi (kurum bazlı geçmiş fiyat)
- `fx.py`: `institution_history()` metodu eklendi (kurum bazlı metal geçmişi)
- `bist_index.py`: Endeks bileşenleri provider'ı eklendi (BIST CSV: hisse_endeks_ds.csv)
- `index.py`: `INDICES` genişletildi (katılım, tematik endeksler), `Index.components`, `Index.component_symbols` property'leri eklendi
- `index.py`: `indices(detailed=True)` ve `all_indices()` fonksiyonları eklendi
- `__init__.py`: `all_indices()` fonksiyonu export edildi

---

## Future Plans

### Eksik TradingView Özellikleri

**Alternatif Chart Tipleri:**
- Renko Charts (box-based)
- Kagi Charts (reversal-based)
- Line Break Charts
- Point & Figure Charts
- Range Charts

**Gösterge Arama:**
- `searchIndicator()` - TradingView gösterge kütüphanesinde arama
- `getIndicator()` - Gösterge detayları ve Pine Script kodu
- Private/Invite-only Indicators (auth ile)

**Diğer:**
- `getDrawings()` - Chart üzerindeki kullanıcı çizimlerini alma
- Pine Script Permission Management

**TradingView API Özellik Karşılaştırması:**

| Quote Fields | TradingView | borsapy | Durum |
|--------------|-------------|---------|-------|
| `lp` (last price) | ✅ | ✅ | `last` |
| `bid`, `ask`, `bid_size`, `ask_size` | ✅ | ✅ | Var |
| `volume` | ✅ | ✅ | Var |
| `ch`, `chp` (change) | ✅ | ✅ | `change`, `change_percent` |
| `open_price`, `high_price`, `low_price` | ✅ | ✅ | `open`, `high`, `low` |
| `prev_close_price` | ✅ | ✅ | `prev_close` |
| `market_cap_basic` | ✅ | ✅ | `market_cap` |
| `earnings_per_share_basic_ttm` | ✅ | ✅ | `eps` |
| `price_earnings_ttm` | ✅ | ✅ | `pe_ratio` |
| `dividends_yield` | ✅ | ✅ | `dividend_yield` |
| `beta_1_year` | ✅ | ✅ | `beta` |

| Chart Data | TradingView | borsapy | Durum |
|------------|-------------|---------|-------|
| OHLCV candles | ✅ | ✅ | `subscribe_chart()` |
| Multiple timeframes | ✅ | ✅ | 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1wk, 1mo |
| Heikin Ashi | ✅ | ✅ | `calculate_heikin_ashi()` |
| Renko, Kagi, PnF | ✅ | ❌ | **Eksik** |

| Technical Analysis | TradingView | borsapy | Durum |
|--------------------|-------------|---------|-------|
| `getTA()` - Oscillators/MA | ✅ | ✅ | `ta_signals()` |
| Built-in Indicators | ✅ | ✅ | `rsi()`, `macd()`, `sma()`, vb. |
| Market Search | ✅ | ✅ | `search()`, `search_bist()` |
| Screener/Scanner | ✅ | ⚠️ | İş Yatırım var, TradingView yok |

**Eksik özellikler:**
1. Renko, Kagi, Point & Figure chart tipleri
2. TradingView Screener API (İş Yatırım alternatifi mevcut)

---

### Colendi Trading Entegrasyonu (Al/Sat)

**Ne:** Colendi Menkul Değerler API ile hisse/vadeli al-sat.

**Referans:** https://github.com/BoraDurkun/Colendi-API-Python-Wrapper

**Özellikler:**
- Hisse emri: oluştur / değiştir / iptal
- Vadeli işlem emri: oluştur / değiştir / iptal
- Portföy: bakiye, pozisyonlar, emir listesi
- WebSocket: canlı piyasa verisi

**Auth Flow:**
```
1. send_otp(username, password) → SMS kodu gönderilir
2. login(token, otp) → JWT token alınır
3. Her istek HMAC-SHA256 imzalı: "{client_key}|{path}|{body}|{timestamp}"
4. Session 60 saniyede bir refresh
```

**API Endpoints:**
```
Base URL: https://api.codyalgo.com:11443
WebSocket: wss://api.codyalgo.com:11443/ws

Portfolio:
  POST /get_subaccounts
  POST /get_account_summary
  POST /get_cash_balance

Stock:
  POST /get_stock_create_order   (direction: 1=BUY, 2=SELL)
  POST /get_stock_replace_order
  POST /get_stock_delete_order
  POST /get_stock_order_list
  POST /get_stock_positions

Futures:
  POST /get_future_create_order
  POST /get_future_replace_order
  POST /get_future_delete_order
  POST /get_future_order_list
```

**Kullanım (hedef):**
```python
import borsapy as bp

# Colendi auth (premium)
broker = bp.Broker(
    license_key="BORSAPY-PRO-XXXX",
    api_key="colendi_api_key",
    api_secret="colendi_secret",
    username="internet_banking_user",
    password="internet_banking_pass"
)

# SMS OTP gelecek
broker.request_otp()
broker.verify_otp("123456")

# Trading
broker.portfolio()                    # Portföy özeti
broker.balance()                      # Nakit bakiye
broker.positions()                    # Açık pozisyonlar

broker.buy("THYAO", quantity=100, price=285.50)   # Limit emir
broker.sell("THYAO", quantity=50, price=290.00)
broker.cancel_order(order_id="...")

# Vadeli
broker.buy_future("F_XU0300225", quantity=1, price=9500)
```

**Premium Model:** TradingView auth ile aynı - Go binary içinde lisans kontrolü.

**Yasal durum:** Kullanıcı kendi broker hesabını kullanıyor → sorun yok.

---

## Data Sources
| Module | Source | API |
|--------|--------|-----|
| Ticker | TradingView + İş Yatırım | WebSocket (OHLCV), MaliTablo (financials) |
| ISIN | isinturkiye.com.tr | 3-step: KAP→ihracKod→ISIN |
| Analyst Targets | hedeffiyat.com.tr | HTML scraping |
| FX | canlidoviz.com + doviz.com | canlidoviz (65 döviz, metaller), doviz.com (bank_rates HTML) |
| Crypto | BtcTurk | Public API + Graph API |
| Fund | TEFAS | gov.tr API (SSL disabled) |
| Inflation | TCMB | Scraping + Calculator API |
| Companies | KAP | Excel export |
| Calendar | doviz.com | Bearer token + HTML parsing |
| Bond | doviz.com | HTML scraping (/tahvil) |
| TCMB | tcmb.gov.tr | HTML scraping (faiz oranları) |
| Eurobond | ziraatbank.com.tr | JSON API (GetZBBonoTahvilOran) |
| EVDS | TCMB EVDS3 | v3 backend (`/igmevdsms-dis/*`); REST GET (key) + anonim SPA endpoints |
| Screener | İş Yatırım | getScreenerDataNEW JSON API |
| Index | BIST + TradingView | hisse_endeks_ds.csv (components), WebSocket (OHLCV) |
| ETF Holders | TradingView | HTML scraping (symbols/BIST-{}/etfs) |
| Twitter/X | Scweet (optional) | Twitter GraphQL API (cookie auth) |

## Project Structure
```
borsapy/
├── __init__.py         # Exports: Ticker, FX, Crypto, Fund, Inflation, companies, etc.
├── ticker.py           # BIST stock data
├── fx.py               # Forex/commodities
├── crypto.py           # Cryptocurrency
├── fund.py             # Mutual funds
├── inflation.py        # TCMB inflation data
├── evds.py             # TCMB EVDS3 (145 categories, full macro series)
├── market.py           # companies(), search_companies()
├── bond.py             # Government bond yields
├── tcmb.py             # TCMB interest rates
├── eurobond.py         # Turkish Eurobonds
├── calendar.py         # Economic calendar
├── screener.py         # Stock screener
├── stream.py           # TradingView WebSocket streaming (real-time)
├── twitter.py          # Twitter/X tweet search (TwitterMixin, query builders)
├── cache.py            # TTL-based in-memory cache
├── exceptions.py       # Custom exceptions
└── _providers/         # Internal API clients
    ├── base.py         # BaseProvider with httpx client
    ├── tradingview.py  # TradingView WebSocket (OHLCV + quotes)
    ├── isyatirim.py    # Financial statements (lazy-loaded)
    ├── isyatirim_screener.py  # Stock screener (İş Yatırım)
    ├── canlidoviz.py   # Forex/commodities (token-free, 65 currencies)
    ├── dovizcom.py     # Forex HTML scraping (bank_rates, institution_rates)
    ├── dovizcom_calendar.py   # Economic calendar (doviz.com)
    ├── dovizcom_tahvil.py     # Bond yields (doviz.com)
    ├── tcmb_rates.py   # TCMB interest rates (tcmb.gov.tr)
    ├── ziraat_eurobond.py  # Eurobonds (ziraatbank.com.tr)
    ├── btcturk.py      # Crypto ticker + OHLCV
    ├── tefas.py        # Mutual fund data
    ├── tcmb.py         # Inflation data
    ├── kap.py          # BIST company list
    ├── isin.py         # ISIN codes (isinturkiye.com.tr)
    ├── hedeffiyat.py   # Analyst price targets
    ├── tradingview_etf.py  # ETF holders (TradingView HTML scraping)
    ├── evds.py         # EVDS3 backend (catalog + REST data + chunking)
    └── twitter.py      # Twitter/X via Scweet (optional dep)
```

## Key Design Decisions
1. **Sync HTTP**: All providers use sync httpx (converted from async borsa-mcp)
2. **Singleton Providers**: Each provider has `get_*_provider()` singleton function
3. **TTL Cache**: Different TTLs for different data types (see cache.py)
4. **yfinance API Style**: `.info`, `.history()`, `.balance_sheet` properties
5. **English Field Names**: API compatibility (but Turkish data sources)
6. **EnrichedInfo Class**: Lazy-loading dict-like info with yfinance aliases (regularMarketPrice → last)
7. **TTM Calculation**: `ttm_income_stmt`, `ttm_cashflow` sum last 4 quarters automatically

## Testing
```bash
uv run python -c "import borsapy as bp; print(bp.Ticker('THYAO').info)"
```

## Common Issues
- TEFAS requires SSL verification disabled (`self._client.verify = False`)
- TEFAS WAF blocks requests >90-100 days (chunked requests implemented)
- doviz.com uses Bearer token (fallback token in code)
- KAP Excel has header row that needs filtering ("BIST KODU", "Kod")
- TCMB API returns numbers in format "444,399.15" (comma=thousands)

## Release & PyPI Publish

### Yeni Versiyon Yayınlama
1. `borsapy/__init__.py` ve `pyproject.toml` içindeki version'ı güncelle
2. `uv run pdoc borsapy -o docs` ile dokümantasyonu güncelle
3. Değişiklikleri commit et ve push et
4. `gh release create vX.Y.Z --title "..." --notes "..."` ile release oluştur
5. GitHub Actions workflow otomatik olarak PyPI'a publish eder

### PyPI Publish Hatası Çözümü
Eğer release oluşturulduktan SONRA pyproject.toml versiyonu güncellendiyse, workflow eski versiyonla build eder ve PyPI "file already exists" hatası verir.

**Çözüm**: Release'i silip tekrar oluştur:
```bash
# Release ve tag'i sil
gh release delete vX.Y.Z --yes
git push origin --delete vX.Y.Z

# Tekrar oluştur
gh release create vX.Y.Z --title "..." --notes "..."
```

### Önemli Notlar
- **Her iki dosyada da versiyon güncellenmeli**: `__init__.py` VE `pyproject.toml`
- Release oluşturmadan ÖNCE tüm versiyon güncellemeleri commit edilmeli
- Workflow `.github/workflows/publish.yml` dosyasında tanımlı

## Adding New Providers
1. Create `_providers/new_provider.py` extending `BaseProvider`
2. Add singleton `get_new_provider()` function
3. Create user-facing class in `borsapy/new_module.py`
4. Export from `__init__.py`

---

## yfinance Feature Parity Tracking

**KURAL**: Her yeni özellik eklendikten sonra bu liste güncellenmelidir!

### ✅ Mevcut Özellikler (Ticker)
- [x] symbol, info, fast_info
- [x] history()
- [x] dividends, splits, actions
- [x] balance_sheet, quarterly_balance_sheet
- [x] income_stmt, quarterly_income_stmt
- [x] cashflow, quarterly_cashflow
- [x] major_holders
- [x] recommendations
- [x] news (KAP disclosures)
- [x] calendar (expected disclosures)
- [x] etf_holders (TradingView HTML scraping)

### ✅ Mevcut Sınıflar/Fonksiyonlar
- [x] Ticker
- [x] Tickers
- [x] download()
- [x] Index, indices()
- [x] companies(), search_companies()
- [x] FX (borsapy-only)
- [x] Crypto (borsapy-only)
- [x] Fund (borsapy-only)
- [x] Portfolio (borsapy-only, çoklu varlık portföy yönetimi + risk metrikleri)
- [x] Inflation (borsapy-only)
- [x] VIOP (borsapy-only, vadeli işlem + opsiyon)
- [x] search_funds(), screen_funds(), compare_funds() (borsapy-only, TEFAS fon tarama/karşılaştırma)
- [x] Bond, bonds(), risk_free_rate() (borsapy-only, tahvil faizleri)
- [x] TCMB, policy_rate() (borsapy-only, merkez bankası faiz oranları)
- [x] Eurobond, eurobonds() (borsapy-only, Türk devlet eurobondları)
- [x] EconomicCalendar, economic_calendar() (borsapy-only, ekonomik takvim)
- [x] Screener, screen_stocks() (borsapy-only, hisse tarama)
- [x] TradingViewStream, create_stream() (borsapy-only, persistent WebSocket streaming)
- [x] set_tradingview_auth(), clear_tradingview_auth() (borsapy-only, TradingView Pro real-time access)
- [x] search(), search_bist(), search_crypto(), search_forex(), search_index() (borsapy-only, TradingView symbol search)
- [x] ReplaySession, create_replay() (borsapy-only, backtesting için historical replay)
- [x] search_tweets(), set_twitter_auth() (borsapy-only, Twitter/X tweet arama, optional dep)
- [x] EVDS, EVDSSeries (borsapy-only, TCMB Elektronik Veri Dağıtım Sistemi v3 — 145 kategori, on binlerce makro seri)
- [x] EVDS().categories, datagroups, series_in_group, search, search_server, series, dashboard, dashboard_by_id, home_page_dashboards, datagroup_data, announcements (11 metod)
- [x] EVDSSeries.code, info, range, native_frequency, datagroup, history(period/start/end/frequency/aggregation/formula/decimals/decimal_separator)
- [x] evds_series(), evds_download(), evds_categories(), evds_search() (borsapy-only, EVDS shortcut'lar)
- [x] set_evds_key(), get_evds_key(), clear_evds_key() (borsapy-only, EVDS API key yönetimi — ücretsiz key https://evds3.tcmb.gov.tr)
- [x] EVDS auto-chunking (1000-obs limiti aşan sorgular client-side bölünüp birleştirilir)
- [x] EVDS end=None → 01-01-2999 always-current sentinel
- [x] EVDS frequency normalizasyonu (legacy v2 9/13/16/18 ↔ v3 1..8)
- [x] EVDS dot↔underscore kod dönüşümü (kullanıcı her iki formatı verebilir)
- [x] EVDS CSV/XML output_format desteği (provider seviye)
- [x] EVDS resmi REST katalog yedekleri (get_categories_rest, get_datagroups_rest, get_series_list_rest)

### ✅ Yeni Eklenen - Yüksek Öncelik (Tamamlandı)
- [x] isin (ISIN kodu - isinturkiye.com.tr)
- [x] analyst_price_targets (hedeffiyat.com.tr)
- [x] earnings_dates (calendar'dan türetildi)
- [x] history(actions=True) (Dividends + Stock Splits sütunları)

### ✅ Yeni Eklenen - Orta Öncelik (Tamamlandı)
- [x] ttm_income_stmt, ttm_cashflow (son 4 çeyrek toplamı)

### ✅ Yeni Eklenen - Düşük Öncelik (Tamamlandı)
- [x] VIOP class (vadeli işlemler + opsiyonlar, İş Yatırım HTML scraping)

### ✅ Fund Sınıfı Yeni Özellikler
- [x] Fund.allocation - Portföy varlık dağılımı (son 7 gün)
- [x] Fund.allocation_history(period) - Geçmiş varlık dağılımı (max ~100 gün)
- [x] Fund.info['allocation'] - Varlık dağılımı info içinde (extra API çağrısı yok)
- [x] Fund.info['isin'] - ISIN kodu
- [x] Fund.info['weekly_return'] - Haftalık getiri
- [x] Fund.info['category_rank'] - Kategori sıralaması
- [x] Fund.info['entry_fee'], Fund.info['exit_fee'] - Komisyon oranları
- [x] screen_funds() - Fon tarama (fund_type, min_return_1y, min_return_ytd, vb.)
- [x] compare_funds() - Fon karşılaştırma (rankings, summary, max 10 fon)
- [x] Fund.history(period="3y/5y/max") - Uzun period desteği (chunked requests ile WAF bypass)
- [x] Fund.sharpe_ratio() - Sharpe oranı hesaplama (10Y tahvil faizi ile)
- [x] Fund.risk_metrics() - Risk metrikleri (Sharpe, Sortino, max drawdown, volatility)
- [x] Fund.management_fee - Fon yönetim ücreti bilgisi (applied_fee, prospectus_fee, max_expense_ratio)
- [x] management_fees() - Tüm fonların yönetim ücretleri (DataFrame)
- [x] Fund.tax_category - Fonun vergi kategorisi (TEFAS kategori mapping)
- [x] Fund.withholding_tax_rate() - Fon stopaj oranı (alım tarihine göre)
- [x] withholding_tax_rate() - Standalone stopaj oranı hesaplama
- [x] withholding_tax_table() - Stopaj oranları referans tablosu

### ✅ Teknik Analiz Özellikleri (Yeni)
- [x] TechnicalAnalyzer class - DataFrame wrapper for technical analysis
- [x] TechnicalMixin - Ticker, Index, Crypto, FX sınıflarına mixin
- [x] calculate_sma() - Simple Moving Average
- [x] calculate_ema() - Exponential Moving Average
- [x] calculate_rsi() - Relative Strength Index
- [x] calculate_macd() - MACD (line, signal, histogram)
- [x] calculate_bollinger_bands() - Bollinger Bands (upper, middle, lower)
- [x] calculate_atr() - Average True Range
- [x] calculate_stochastic() - Stochastic Oscillator (%K, %D)
- [x] calculate_obv() - On-Balance Volume
- [x] calculate_vwap() - Volume Weighted Average Price
- [x] calculate_adx() - Average Directional Index
- [x] calculate_supertrend() - Supertrend (trend-following, ATR-based)
- [x] calculate_tilson_t3() - Tilson T3 (triple-smoothed EMA)
- [x] add_indicators() - DataFrame'e tüm göstergeleri ekleme
- [x] Ticker.rsi(), .sma(), .ema(), .macd(), .bollinger_bands(), .atr(), .stochastic(), .obv(), .vwap(), .adx()
- [x] Ticker.supertrend() - Supertrend göstergesi (value, direction, upper, lower)
- [x] Ticker.tilson_t3() - Tilson T3 (triple-smoothed EMA)
- [x] Ticker.technicals() - TechnicalAnalyzer döndürür
- [x] Ticker.history_with_indicators() - Göstergeli DataFrame döndürür
- [x] calculate_heikin_ashi() - Heikin Ashi mum hesaplama
- [x] Ticker.heikin_ashi() - Heikin Ashi DataFrame döndürür
- [x] TechnicalAnalyzer.heikin_ashi() - Analyzer'dan Heikin Ashi
- [x] TechnicalAnalyzer.supertrend() - Supertrend DataFrame döndürür
- [x] TechnicalAnalyzer.tilson_t3() - T3 Series döndürür
- [x] calculate_hhv() - Highest High Value (MetaStock)
- [x] calculate_llv() - Lowest Low Value (MetaStock)
- [x] calculate_mom() - Momentum (MetaStock)
- [x] calculate_roc() - Rate of Change (MetaStock)
- [x] calculate_wma() - Weighted Moving Average (MetaStock)
- [x] calculate_dema() - Double Exponential Moving Average (MetaStock)
- [x] calculate_tema() - Triple Exponential Moving Average (MetaStock)
- [x] Portfolio.set_target_weights() - Portföy hedef ağırlıkları
- [x] Portfolio.drift() - Sapma analizi
- [x] Portfolio.rebalance_plan() - Dengeleme planı
- [x] Portfolio.rebalance() - Otomatik dengeleme

### ✅ TradingView TA Signals (Yeni)
- [x] TradingViewScannerProvider - TradingView Scanner API provider
- [x] ta_signals(interval) - TradingView BUY/SELL/NEUTRAL sinyalleri (11 oscillator + 17 MA)
- [x] ta_signals_all_timeframes() - Tüm 9 timeframe için sinyaller
- [x] Ticker._get_ta_symbol_info() - BIST:SYMBOL + turkey screener
- [x] Index._get_ta_symbol_info() - BIST:SYMBOL + turkey screener
- [x] FX._get_ta_symbol_info() - exchange:SYMBOL + forex screener
- [x] Crypto._get_ta_symbol_info() - BINANCE:BASEUSDT + crypto screener

### ✅ TradingView WebSocket Streaming (Yeni)
- [x] TradingViewStream class - Persistent WebSocket connection
- [x] create_stream() - Factory function
- [x] connect(), disconnect() - Connection lifecycle
- [x] subscribe(), unsubscribe() - Symbol subscription
- [x] get_quote() - Cached quote retrieval (~1μs)
- [x] wait_for_quote() - Blocking first quote
- [x] on_quote(), on_any_quote() - Callback registration
- [x] Auto-reconnection with exponential backoff
- [x] Heartbeat handling (~30s)
- [x] Context manager support (`with` statement)
- [x] Thread-safe quote caching with RLock
- [x] 46 quote fields (price, OHLC, fundamentals, meta)
- [x] subscribe_chart(), unsubscribe_chart() - OHLCV candle subscription
- [x] get_candle(), get_candles() - Cached candle retrieval
- [x] wait_for_candle() - Blocking first candle
- [x] on_candle(), on_any_candle() - Candle update callbacks
- [x] 9 timeframe support (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1wk, 1mo)

### ✅ TradingView Authentication (Yeni)
- [x] set_tradingview_auth(username, password) - Login with credentials
- [x] set_tradingview_auth(session, session_sign) - Login with session tokens
- [x] clear_tradingview_auth() - Logout
- [x] login_user() - TradingView login API
- [x] get_user() - Get user info and auth_token
- [x] Real-time data access (no 15min delay with Pro account)
- [x] Session persistence (~30 days with remember=on)

### ✅ Replay Mode (Yeni)
- [x] ReplaySession class - Generator-based historical replay
- [x] create_replay() - Factory function with auto data loading
- [x] replay() - Generator yielding candles
- [x] replay_filtered() - Date range filtering
- [x] on_candle() - Callback registration
- [x] stats() - Replay statistics
- [x] Speed control (1x, 10x, 100x, etc.)
- [x] Progress tracking (_index, _total, _progress)

### ✅ Twitter/X Tweet Arama (Yeni)
- [x] set_twitter_auth() — Cookie-based auth (auth_token + ct0)
- [x] clear_twitter_auth(), get_twitter_auth() — Auth yonetimi
- [x] search_tweets() — Standalone tweet arama fonksiyonu
- [x] TwitterMixin — Asset class'lara tweets() metodu ekleyen mixin
- [x] Ticker.tweets() — Hisse tweetleri ($THYAO OR #THYAO OR "TURK HAVA YOLLARI")
- [x] Fund.tweets() — Fon tweetleri (#AAK OR "fon adi")
- [x] FX.tweets() — Doviz/emtia tweetleri (Turkce arama terimleri dahil)
- [x] Crypto.tweets() — Kripto tweetleri ($BTC OR #Bitcoin)
- [x] Custom query override (tweets(query="..."))
- [x] Period support (1d, 7d, 1mo, since/until)
- [x] Language filter (lang="tr")
- [x] Tweet normalization (GraphQL → flat dict, 15 sutun)
- [x] Optional dependency (pip install borsapy[twitter])

### ❌ Eksik Özellikler - Orta Öncelik
- [ ] insider_transactions, insider_purchases
- [~] institutional_holders (veri kaynağı yok - MKK kurumsal/bireysel ayrımı yok)

### ❌ Eksik Özellikler - Düşük Öncelik
- [ ] sustainability (ESG)
- [x] recommendations_summary (hedeffiyat.com.tr bireysel analist tavsiyelerinden)
- [ ] upgrades_downgrades

### ✅ Tamamlanan info Alanları
- [x] marketCap, trailingPE, priceToBook
- [x] dividendYield, exDividendDate
- [x] fiftyTwoWeekHigh, fiftyTwoWeekLow
- [x] enterpriseToEbitda, netDebt
- [x] sharesOutstanding, floatShares, foreignRatio
- [x] fiftyDayAverage, twoHundredDayAverage
- [x] yfinance aliases (regularMarketPrice, currentPrice, etc.)
- [x] longBusinessSummary (KAP Faaliyet Konusu)

### ✅ Tamamlanan info Alanları (Yeni)
- [x] sector, industry, website (KAP şirket bilgileri sayfasından)
- [x] amount (TL bazında hacim, borsapy-only)

### ❌ Eksik Sınıflar
- [ ] Sector
- [ ] Industry
- [ ] Market (open/close status)
- [x] Screener/EquityQuery (İş Yatırım API ile)

---

## Feature Implementation Rules

1. **yfinance Parity**: Her yeni Ticker özelliği eklendiğinde yukarıdaki listeyi güncelle
2. **Checklist Format**: `- [x]` tamamlandı, `- [ ]` eksik
3. **Priority Order**: Yüksek → Orta → Düşük sırasıyla uygula
4. **Commit Rule**: Özellik tamamlandığında CLAUDE.md'deki checkbox'ı da işaretle
