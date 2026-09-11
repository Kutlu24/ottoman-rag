from __future__ import annotations

import asyncio

from mcp.server.fastmcp import FastMCP
from ottoman_rag_common.provenance import Chunk

from . import vector_store
from .embeddings import embed_texts

mcp = FastMCP("search-server")


def _index_chunks_sync(chunks: list[Chunk]) -> int:
    if not chunks:
        return 0
    vectors = embed_texts([c.text for c in chunks], is_query=False)
    vector_store.upsert_chunks(chunks, vectors)
    return len(chunks)


def _search_sync(query: str, top_k: int, manuscript_id: str | None) -> list[dict]:
    [query_vec] = embed_texts([query], is_query=True)
    return vector_store.query(query_vec, top_k=top_k, manuscript_id=manuscript_id)


# index_chunks/search'un asil isi (embed_texts -> ~20s+ CPU-bound model
# yukleme+encode, ardindan chromadb okuma/yazma) senkron ve bloklayici.
# Dogrudan bir @mcp.tool() fonksiyonu icinde cagrilirsa, FastMCP'nin tek
# asyncio event loop'unu tamamen tikar - MCP stdio transport'u o sure
# boyunca hicbir mesaj okuyup yazamaz, ve gozlemlenen davranis bu: cagri
# sessizce dakikalarca (gercek suresinden cok daha uzun) asilir, sonunda
# istemci tarafinda zaman asimina ugrar. asyncio.to_thread ile isi ayri
# bir thread'e tasimak event loop'u serbest birakiyor. (2026-09, gercek
# hata: index_chunks VE salt-okunur search, ikisi de ayni sekilde
# kilitleniyordu - "sadece yazma yolu" degil, HER embed_texts cagrisi.)
@mcp.tool()
async def index_chunks(chunks: list[Chunk]) -> int:
    """Verilen chunk'ları embed edip vektör veritabanına yazar.

    Returns:
        İşlenen chunk sayısı.
    """
    return await asyncio.to_thread(_index_chunks_sync, chunks)


@mcp.tool()
async def search(query: str, top_k: int = 5, manuscript_id: str | None = None) -> list[dict]:
    """Soruyla en alakalı chunk'ları, provenance (yazma/sayfa/satır/bbox) bilgisiyle döndürür.

    Args:
        query: Araştırmacının doğal dil sorusu.
        top_k: Döndürülecek chunk sayısı.
        manuscript_id: Verilirse aramayı tek bir yazma eserle sınırlar.
    """
    return await asyncio.to_thread(_search_sync, query, top_k, manuscript_id)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
