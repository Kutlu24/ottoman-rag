# search-server

Provenance-korumalı chunk'ları embed edip Chroma vektör veritabanına yazan ve
soru geldiğinde en alakalı chunk'ları (kaynak yazma/sayfa/satır/bbox bilgisiyle
birlikte) döndüren MCP sunucusu.

## Kurulum

```
pip install -e ../../packages/ottoman_rag_common
pip install -e .
```

## Embedding modeli

`intfloat/multilingual-e5-base` — açık kaynak, çok dilli, self-hosted (ilk
çalıştırmada HuggingFace'ten otomatik indirilir). E5 modelleri sorgu ve
pasajları farklı önekle bekler (`query: ` / `passage: `), bu `embeddings.py`
içinde otomatik uygulanıyor.

## Tool'lar

- `index_chunks(chunks)` — `ottoman_rag_common.provenance.Chunk` listesini
  embed edip Chroma'ya yazar.
- `search(query, top_k=5, manuscript_id=None)` — soruya en yakın chunk'ları,
  `manuscript_id`, `page_id`, `line_ids`, `bboxes`, `citation_label` gibi
  provenance alanlarıyla birlikte döndürür.

## Veri konumu

Chroma verisi `CHROMA_DB_DIR` env değişkeninde belirtilen klasörde (varsayılan:
proje kökü `data/chroma/`) diskte tutulur.
