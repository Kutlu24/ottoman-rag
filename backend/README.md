# backend

FastAPI servisi + RAG orchestrator. Araştırmacının sorusunu alır, `search-server`
MCP sunucusundan provenance'lı chunk'ları getirir, Claude API'ye (zorunlu tool-use
ile) yapılandırılmış bir "hangi pasajdan alıntı yaptın" cevabı ürettirir ve
sonucu (cevap + kaynak yazma/sayfa/satır/bbox) döndürür.

## Kurulum

```
pip install -e ../packages/ottoman_rag_common
pip install -e .
```

`.env` dosyasında `ANTHROPIC_API_KEY` dolu olmalı (proje kökündeki `.env`,
otomatik yüklenir).

## Çalıştırma

```
cd src
uvicorn backend.main:app --reload
```

Açılışta `search-server`'ı (ve `htr-kraken` MCP sunucusunu) subprocess olarak
başlatıp bağlantıyı canlı tutar; kapanışta düzgünce sonlandırır.

## Uç noktalar

- `POST /ask` — `{question, manuscript_id?, top_k?}` → `{answer, citations}`.
  Her `citation`: `manuscript_id`, `page_id`, `citation_label`, `line_ids`,
  `bboxes`, `image_path` içerir — frontend bunu doğrudan highlight overlay
  için kullanabilir.
- `POST /manuscripts`, `GET /manuscripts/{id}` — yazma katalog kaydı (tek
  doğruluk kaynağı; `search-server`'daki `citation_label` buradan üretilir).
- `POST /pages`, `GET /pages/{id}/image` — sayfa kaydı ve ham görüntü servisi.
- `POST /ingest` — bir sayfa görüntüsünü Kraken ile transkribe edip
  chunk'layıp indeksler (Transkribus üzerinden ingestion, MCP sunucusunun
  300 tool'undan doğru olanların keşfi henüz yapılmadı — bkz. kök README
  "Durum" bölümü).
