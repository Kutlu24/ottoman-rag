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

- `mcp-servers/htr-server/` — Kraken tabanlı HTR MCP sunucusu (satır bbox + metin üretir)
- `mcp-servers/search-server/` — embedding + vektör arama MCP sunucusu
- `.mcp.json` — `htr-kraken` ve `transkribus` MCP sunucularının bağlantı tanımı
- `ingestion/` — HTR çıktısını (her iki backend'den) chunk'layıp vektör DB'ye yazan pipeline
- `training/` — Kraken modelini kendi/MAKHZAN verisiyle fine-tune etme script'leri
- `backend/` — FastAPI + RAG orchestrator
- `frontend/` — React tabanlı araştırmacı arayüzü
- `data/` — ham görüntüler, PAGE XML çıktıları, dev veritabanı

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
- [ ] Step 2 — `ingestion/` + `mcp-servers/search-server`
- [ ] Step 3 — `backend/` (FastAPI + RAG orchestrator)
- [ ] Step 4 — `frontend/` (viewer + highlight overlay)
- [ ] Step 5 — `training/` (Kraken fine-tuning, opsiyonel)
