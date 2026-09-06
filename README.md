# Osmanlıca El Yazması RAG Sistemi

Osmanlıca el yazması metinleri okuyabilen açık kaynak HTR modellerini MCP sunucuları
olarak entegre eden, RAG tabanlı bir arama sistemi. Araştırmacı bir soru sorduğunda,
cevabı kaynak metindeki ilgili satır(lar) görüntü üzerinde highlight edilmiş şekilde
görebilir.

## Mimari

İki ayrı HTR backend'i MCP sunucusu olarak entegre ediyoruz:

- **`htr-kraken-server`** (bu repoda, `mcp-servers/htr-server/`) — self-hosted, açık
  kaynak Kraken motoru. Offline çalışır, kendi verinizle fine-tune edilebilir.
- **`transkribus`** ([`@lazyants/transkribus-mcp-server`](https://github.com/lazyants/transkribus-mcp-server),
  hazır npm paketi) — Transkribus'un herkese açık, halihazırda eğitilmiş modellerine
  (ör. `OttomanTurkish_Print_1`, %7,20 CER) API üzerinden erişir. Lisansı FSL-1.1-MIT
  (2 yıl sonra MIT'e dönüşüyor, ticari olmayan/araştırma kullanımı serbest).

```
[Görüntü] -> htr-kraken-server (Kraken)  \
          -> transkribus (Transkribus API) -> PAGE XML (bbox + metin + conf)
          -> ingestion/chunker -> search-mcp-server (embedding + vektör DB)
          -> RAG orchestrator (Claude API, her iki MCP sunucusuna da bağlı client)
          -> backend (FastAPI) -> frontend (React, highlight overlay)
```

Orchestrator, sayfa/model bazında hangi backend'in kullanılacağına karar verebilir
(örn. Transkribus'ta halihazırda iyi bir Osmanlıca modeli varsa onu, yoksa/offline
gerekiyorsa Kraken'i kullanır); ikisinin çıktısı da aynı `HtrPageResult` şekline
(satır + bbox + metin + confidence) normalize edilir.

## Klasör yapısı

- `packages/ottoman_rag_common/` — tüm servislerde paylaşılan provenance/HTR şemaları
  (`geometry`, `htr`, `provenance` — bkz. aşağıdaki tasarım notu)
- `mcp-servers/htr-server/` — Kraken tabanlı HTR MCP sunucusu (satır bbox + metin üretir)
- `mcp-servers/search-server/` — embedding + Chroma vektör arama MCP sunucusu
- `.mcp.json` — `htr-kraken`, `transkribus`, `search-server` MCP sunucularının bağlantı tanımı
- `ingestion/` — HTR çıktısını (her iki backend'den) provenance koruyarak chunk'layıp
  vektör DB'ye yazan pipeline (`chunker.py`, duman testi: `smoke_test.py`)
- `training/` — Kraken modelini kendi/MAKHZAN verisiyle fine-tune etme script'leri
- `backend/` — FastAPI + RAG orchestrator
- `frontend/` — React tabanlı araştırmacı arayüzü
- `data/` — ham görüntüler, PAGE XML çıktıları, Chroma verisi, dev veritabanı

## Pipeline ve provenance-aware retrieval tasarımı

Akış: **Image → HTR → transcription → chunking → embedding → vector database →
retrieval → LLM → cited answer.** Projenin temel hedefi bu akış boyunca
**manuscript provenance**'ın (hangi yazma, hangi sayfa/folio, hangi satır,
hangi HTR modeliyle üretildi) hiç kaybolmamasını sağlamak — böylece RAG
cevabı, kaynak görüntüde tam olarak hangi satırların highlight edileceğini
ve tam bir bilimsel atıfı (repository, shelfmark, folio) her zaman
üretebilir.

Bunu şu şekilde uyguladık (`packages/ottoman_rag_common/provenance.py`):

- **Chunk kendi provenance'ını taşır** (loose coupling değil): her `Chunk`
  nesnesi `manuscript_id`, `page_id`, kaynak `line_ids` ve bunlarla birebir
  eşleşen `bboxes` listesini, hangi `HtrRun` (backend + model + CER) ile
  üretildiğini içerir.
- **Hibrit depolama:** vektör DB'nin (Chroma) metadata alanında yalnızca
  retrieval-zamanı filtreleme ve highlight için gereken alanlar tutulur;
  yazmanın tam katalog kaydı (Step 3'te) ayrı bir metadata store'da tek
  doğruluk kaynağı olarak duracak. `citation_label` bu kayıttan önceden
  hesaplanıp chunk'a "cache'lenmiş" bir görüntü alanı olarak taşınır — bu
  sayede retrieval ekstra join gerektirmeden doğrudan atıf üretebilir.
- **Model/versiyon izlenebilirliği:** `HtrRun.htr_run_id`/`model_ref` sayesinde
  hangi transkripsiyonun hangi modelden (ve dolayısıyla ne CER ile) geldiği
  her zaman biliniyor; ileride daha iyi bir model ile yeniden transkribe
  edildiğinde eski/yeni chunk'lar birbirine karışmaz.

`ingestion/chunker.py` satırları ardışık pencereleme ile (varsayılan ~400
karakter) chunk'lara böler; `mcp-servers/search-server` bu chunk'ları
`intfloat/multilingual-e5-base` ile embed edip Chroma'ya yazar ve arama
sonucunda aynı provenance alanlarını döndürür. `ingestion/smoke_test.py`,
gerçek bir HTR çalıştırması olmadan bu zinciri sentetik veriyle uçtan uca
doğrular.

## HTR modelleri

İki backend paralel kullanılıyor:

1. **Transkribus** — halka açık, hazır eğitilmiş modeller. `@lazyants/transkribus-mcp-server`
   üzerinden, hesap bilgileriyle (`.env`'deki `TRANSKRIBUS_USER`/`TRANSKRIBUS_PASSWORD`)
   erişilir. Platforma bağlı, self-host edilemez.
   - **El yazması (varsayılan):** `Ottoman Fatwa Manuscripts` — htrId `169801`,
     PyLaia tabanlı, 72 sayfa/2888 satır ile eğitilmiş, **%5,94 CER**. Gerçek el
     yazması üzerinde iyi sonuç veriyor, Kraken fine-tuning beklemeden kullanılabilir.
   - **Basılı/matbu metin:** `OttomanTurkish_Print_1` — htrId `52502`, %7,2 CER,
     386 sayfa/23.758 satır (Digital Ottoman Corpora ekibi tarafından yayınlandı).
2. **Kraken** ([kraken.re](https://kraken.re)) — tam açık kaynak, self-hosted.
   [OpenITI'nin Ottoman baskı base modeli](https://zenodo.org/records/7050342)
   başlangıç noktası; Transkribus modelleri yetersiz kaldığı senaryolarda veya
   tamamen offline çalışmak gerektiğinde
   [OpenITI MAKHZAN](https://openhumanitiesdata.metajnl.com/articles/10.5334/johd.465)
   (açık, üyelik gerektirmeyen ground-truth veri seti — hem basılı hem el yazması
   içeriyor) ile `training/` altında fine-tune edilecek.

### Araştırılan diğer kaynaklar

| Kaynak | Açık kaynak mı? | Üyelik? | Karar |
|---|---|---|---|
| OTRN (Uni Vienna) | Model/API/veri seti sunmuyor, araştırmacı ağı | Kişisel başvuru gerekiyor (ad, akademik bağlantı, motivasyon) | Teknik entegrasyon noktası değil — dahil edilmedi |
| Digital Ottoman Corpora | — | — | `OttomanTurkish_Print_1` modelini üreten ekip, ayrı bir entegrasyon değil |
| Osmanlica.com | Hayır, kapalı/ticari servis | Ücretsiz katman günlük 10 kredi, sonrası ücretli | Opsiyonel 3. backend olarak eklenebilir, varsayılan mimaride yok |

## Durum

- [x] Step 1a — `mcp-servers/htr-server` iskeleti (Kraken backend)
- [x] Step 1b — `.mcp.json`'a `transkribus-mcp-server` entegrasyonu
- [x] Step 2 — `packages/ottoman_rag_common` (provenance şeması) +
      `ingestion/chunker.py` + `mcp-servers/search-server` — canlı ortamda
      doğrulandı (sentetik veriyle uçtan uca)
- [x] Step 3 — `backend/` (FastAPI + RAG orchestrator + SQLite metadata store) —
      gerçek `uvicorn` sunucusu + gerçek MCP (stdio) client bağlantısıyla
      doğrulandı; `/ask` sadece `ANTHROPIC_API_KEY` eksikliğinden bekleneni
      verdi, retrieval zinciri tam çalışıyor
- [ ] Step 4 — `frontend/` (viewer + highlight overlay)
- [ ] Step 5 — `training/` (Kraken fine-tuning, opsiyonel)

## Ortam kurulumu

```
conda create -n ottoman-rag python=3.11
conda activate ottoman-rag
pip install -e packages/ottoman_rag_common
pip install -e mcp-servers/htr-server
pip install -e mcp-servers/search-server
pip install -e ingestion
pip install -e backend

# duman testi (Kraken/Transkribus gerekmez, sentetik veriyle uçtan uca doğrular)
python -m ingestion.smoke_test

# backend'i çalıştırma (.env'de ANTHROPIC_API_KEY dolu olmalı)
cd backend/src
uvicorn backend.main:app --reload
```

**Not (çözüldü):** `mcp` paketinin en güncel sürümü (2.x) `FastMCP`'yi
`MCPServer` olarak yeniden adlandırdı ve API'yi değiştirdi; bu proje henüz
yaygın olarak desteklenmeyen bu değişikliği takip etmek yerine `mcp<2.0.0`'a
sabitlendi. Ayrıca `.env`'deki göreli yollar (`CHROMA_DB_DIR` vb.), her MCP
sunucusu kendi `cwd`'siyle ayrı bir subprocess olarak başladığından
`backend/src/backend/config.py` içinde her zaman proje köküne göre mutlak
yola çevriliyor.
