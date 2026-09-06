from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from ottoman_rag_common.provenance import Chunk

from . import vector_store
from .embeddings import embed_texts

mcp = FastMCP("search-server")


@mcp.tool()
def index_chunks(chunks: list[Chunk]) -> int:
    """Verilen chunk'ları embed edip vektör veritabanına yazar.

    Returns:
        İşlenen chunk sayısı.
    """
    if not chunks:
        return 0
    vectors = embed_texts([c.text for c in chunks], is_query=False)
    vector_store.upsert_chunks(chunks, vectors)
    return len(chunks)


@mcp.tool()
def search(query: str, top_k: int = 5, manuscript_id: str | None = None) -> list[dict]:
    """Soruyla en alakalı chunk'ları, provenance (yazma/sayfa/satır/bbox) bilgisiyle döndürür.

    Args:
        query: Araştırmacının doğal dil sorusu.
        top_k: Döndürülecek chunk sayısı.
        manuscript_id: Verilirse aramayı tek bir yazma eserle sınırlar.
    """
    [query_vec] = embed_texts([query], is_query=True)
    return vector_store.query(query_vec, top_k=top_k, manuscript_id=manuscript_id)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
