"""Chroma tabanli, provenance metadata'sini koruyan vektor deposu.

Tasarim: vektor DB'nin metadata alaninda SADECE retrieval-zamani filtreleme
ve highlight icin gereken alanlar tutulur (manuscript_id, page_id, line_ids,
bboxes, htr backend/model, citation_label). Yazmanin tam katalog kaydi
(repository, tarih, koleksiyon aciklamasi vb.) ayri bir metadata store'da
(Step 3'te backend/ icinde) tek dogruluk kaynagi olarak duracak; buradaki
citation_label onceden hesaplanip "cache'lenmis" bir goruntu alanidir.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import chromadb

from ottoman_rag_common.provenance import Chunk

_DB_DIR = Path(
    os.environ.get(
        "CHROMA_DB_DIR",
        Path(__file__).resolve().parents[4] / "data" / "chroma",
    )
)
_COLLECTION_NAME = "ottoman_manuscripts"

_client: chromadb.ClientAPI | None = None
_collection = None


def get_collection():
    global _client, _collection
    if _collection is None:
        _DB_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(_DB_DIR))
        _collection = _client.get_or_create_collection(_COLLECTION_NAME)
    return _collection


def _to_metadata(chunk: Chunk) -> dict:
    p = chunk.provenance
    return {
        "manuscript_id": p.manuscript_id,
        "page_id": p.page_id,
        "folio_label": p.folio_label or "",
        "line_ids": json.dumps(p.line_ids),
        "bboxes": json.dumps([b.model_dump() for b in p.bboxes]),
        "htr_backend": p.htr_run.backend,
        "htr_model_name": p.htr_run.model_name,
        "citation_label": p.citation_label or "",
    }


def upsert_chunks(chunks: list[Chunk], embeddings: list[list[float]]) -> None:
    if not chunks:
        return
    collection = get_collection()
    collection.upsert(
        ids=[c.chunk_id for c in chunks],
        embeddings=embeddings,
        documents=[c.text for c in chunks],
        metadatas=[_to_metadata(c) for c in chunks],
    )


def query(query_embedding: list[float], top_k: int = 5, manuscript_id: str | None = None) -> list[dict]:
    collection = get_collection()
    where = {"manuscript_id": manuscript_id} if manuscript_id else None
    result = collection.query(query_embeddings=[query_embedding], n_results=top_k, where=where)

    out: list[dict] = []
    ids = result.get("ids", [[]])[0]
    for i, chunk_id in enumerate(ids):
        meta = result["metadatas"][0][i]
        out.append(
            {
                "chunk_id": chunk_id,
                "text": result["documents"][0][i],
                "distance": result["distances"][0][i],
                "manuscript_id": meta["manuscript_id"],
                "page_id": meta["page_id"],
                "folio_label": meta["folio_label"],
                "line_ids": json.loads(meta["line_ids"]),
                "bboxes": json.loads(meta["bboxes"]),
                "htr_backend": meta["htr_backend"],
                "htr_model_name": meta["htr_model_name"],
                "citation_label": meta["citation_label"],
            }
        )
    return out
