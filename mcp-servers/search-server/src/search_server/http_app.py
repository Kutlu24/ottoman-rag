"""HTTP arayuzu (MCP stdio yerine) - search-server'in embed_texts cagrisi
MCP'nin stdio alt-surec transport'u uzerinden calistirildiginda (backend'den
tamamen izole edilmis bir testte bile) her seferinde sessizce kilitleniyordu
(2026-09; muhtemelen PyTorch/sentence-transformers'in Windows'ta pipe'lanmis
stdio ile bir etkilesim sorunu - kesin kok neden dogrulanamadi, birden fazla
gercek duzeltme denendi: SSL sertifika yolu, HF_HUB_OFFLINE, tqdm/ilerleme
cubugu kapatma, chromadb telemetry kapatma, asyncio.to_thread, OMP/MKL
thread sinirlamasi - hicbiri kokten cozmedi).

Ayni is mantigi (embeddings.py, vector_store.py) duz bir HTTP servisi olarak
sarmalandiginda calisiyor - stdio degil TCP soket kullanildigi icin ayni
sorun ortaya cikmiyor. server.py'deki MCP tool tanimlari kaldirilmadi (ileride
kendi gelistirilen HTR modeli MCP uzerinden entegre edilecegi zaman ayni
desen kullanilacak), sadece su an backend bu HTTP arayuzunu cagiriyor.
"""

from __future__ import annotations

from fastapi import FastAPI
from ottoman_rag_common.provenance import Chunk
from pydantic import BaseModel

from . import vector_store
from .embeddings import embed_texts

app = FastAPI(title="search-server (HTTP)")


class IndexChunksRequest(BaseModel):
    chunks: list[Chunk]


class IndexChunksResponse(BaseModel):
    indexed: int


@app.post("/index_chunks", response_model=IndexChunksResponse)
def index_chunks(req: IndexChunksRequest) -> IndexChunksResponse:
    if not req.chunks:
        return IndexChunksResponse(indexed=0)
    vectors = embed_texts([c.text for c in req.chunks], is_query=False)
    vector_store.upsert_chunks(req.chunks, vectors)
    return IndexChunksResponse(indexed=len(req.chunks))


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    manuscript_id: str | None = None


@app.post("/search", response_model=list[dict])
def search(req: SearchRequest) -> list[dict]:
    [query_vec] = embed_texts([req.query], is_query=True)
    return vector_store.query(query_vec, top_k=req.top_k, manuscript_id=req.manuscript_id)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
