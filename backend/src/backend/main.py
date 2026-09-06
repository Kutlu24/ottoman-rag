from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from ottoman_rag_common.htr import HtrPageResult
from ottoman_rag_common.provenance import ManuscriptRef, PageRef
from pydantic import BaseModel

from ingestion.chunker import chunk_page

from . import store
from .config import (
    CHROMA_DB_DIR,
    EMBEDDING_MODEL_NAME,
    HTR_KRAKEN_DIR,
    KRAKEN_DEFAULT_MODEL,
    KRAKEN_MODEL_DIR,
    SEARCH_SERVER_DIR,
)
from .mcp_clients import McpClientManager
from .rag import AskResponse, answer_question

mcp_manager = McpClientManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mcp_manager.start(
        "search",
        command="python",
        args=["-m", "search_server.server"],
        cwd=str(SEARCH_SERVER_DIR),
        env={"CHROMA_DB_DIR": CHROMA_DB_DIR, "EMBEDDING_MODEL_NAME": EMBEDDING_MODEL_NAME},
    )
    await mcp_manager.start(
        "htr-kraken",
        command="python",
        args=["-m", "htr_server.server"],
        cwd=str(HTR_KRAKEN_DIR),
        env={"KRAKEN_MODEL_DIR": KRAKEN_MODEL_DIR, "KRAKEN_DEFAULT_MODEL": KRAKEN_DEFAULT_MODEL},
    )
    try:
        yield
    finally:
        await mcp_manager.stop_all()


app = FastAPI(title="Osmanlıca El Yazması RAG API", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str
    manuscript_id: str | None = None
    top_k: int = 5


@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest) -> AskResponse:
    return await answer_question(mcp_manager, req.question, req.manuscript_id, req.top_k)


@app.post("/manuscripts", response_model=ManuscriptRef)
def create_manuscript(manuscript: ManuscriptRef) -> ManuscriptRef:
    store.upsert_manuscript(manuscript)
    return manuscript


@app.get("/manuscripts/{manuscript_id}", response_model=ManuscriptRef)
def get_manuscript(manuscript_id: str) -> ManuscriptRef:
    manuscript = store.get_manuscript(manuscript_id)
    if manuscript is None:
        raise HTTPException(status_code=404, detail="Yazma bulunamadı")
    return manuscript


@app.post("/pages", response_model=PageRef)
def create_page(page: PageRef) -> PageRef:
    store.upsert_page(page)
    return page


@app.get("/pages/{page_id}/image")
def get_page_image(page_id: str) -> FileResponse:
    page = store.get_page(page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Sayfa bulunamadı")
    return FileResponse(page.image_path)


class IngestRequest(BaseModel):
    manuscript: ManuscriptRef
    page: PageRef
    kraken_model: str | None = None
    max_chars: int = 400


class IngestResponse(BaseModel):
    chunks_indexed: int


@app.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest) -> IngestResponse:
    """Kraken ile bir sayfayı transkribe edip provenance koruyarak indeksler.

    Not: models/ altında bir .mlmodel dosyası olmadan çalışmaz (bkz. kök
    README - OpenITI Ottoman base modeli). Transkribus üzerinden ingestion
    henüz bu uç noktaya bağlanmadı.
    """
    store.upsert_manuscript(req.manuscript)
    store.upsert_page(req.page)

    htr_client = mcp_manager.get("htr-kraken")
    raw_result = await htr_client.call_tool(
        "run_htr", {"image_path": req.page.image_path, "model_name": req.kraken_model}
    )
    htr_result = HtrPageResult.model_validate(raw_result)

    chunks = chunk_page(htr_result, req.manuscript, req.page, max_chars=req.max_chars)

    search_client = mcp_manager.get("search")
    indexed = await search_client.call_tool(
        "index_chunks", {"chunks": [c.model_dump(mode="json") for c in chunks]}
    )
    return IngestResponse(chunks_indexed=indexed)
