from __future__ import annotations

import asyncio
import base64
import os
import re
import secrets
import subprocess
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from ottoman_rag_common.htr import HtrPageResult
from ottoman_rag_common.provenance import ManuscriptRef, PageRef
from PIL import Image
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from ingestion.chunker import chunk_page

from . import store
from .config import (
    BASIC_AUTH_PASSWORD,
    BASIC_AUTH_USER,
    CHROMA_DB_DIR,
    EMBEDDING_MODEL_NAME,
    HTR_KRAKEN_DIR,
    HTR_KRAKEN_PYTHON,
    HTR_MODE,
    KRAKEN_DEFAULT_MODEL,
    KRAKEN_MODEL_DIR,
    PROJECT_ROOT,
    RAW_IMAGES_DIR,
    REMOTE_HTR_API_KEY,
    REMOTE_HTR_URL,
    SEARCH_HTTP_PORT,
    SEARCH_HTTP_URL,
    SEARCH_SERVER_DIR,
)
from .mcp_clients import McpClientManager
from .rag import AskResponse, answer_question

_SAFE_STEM = re.compile(r"[^a-zA-Z0-9_-]+")
_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"

mcp_manager = McpClientManager()
search_http_client: httpx.AsyncClient | None = None
_search_process: subprocess.Popen | None = None
_htr_kraken_lock = asyncio.Lock()


async def _start_search_http_server() -> subprocess.Popen:
    """search-server'i MCP stdio degil duz HTTP olarak baslatir - bkz.
    config.py'deki SEARCH_HTTP_PORT yorumu (embed_texts, MCP stdio
    transport'unda dogrulanamayan bir sebeple kilitleniyordu)."""
    env = {
        "CHROMA_DB_DIR": CHROMA_DB_DIR,
        "EMBEDDING_MODEL_NAME": EMBEDDING_MODEL_NAME,
        "HF_HUB_OFFLINE": "1",
        "HF_HUB_DISABLE_PROGRESS_BARS": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "ANONYMIZED_TELEMETRY": "False",
    }
    full_env = {**os.environ, **env}
    full_env.pop("SSL_CERT_FILE", None)  # bkz. http_app.py docstring
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "search_server.http_app:app", "--host", "127.0.0.1", "--port", str(SEARCH_HTTP_PORT)],
        cwd=str(SEARCH_SERVER_DIR),
        env=full_env,
    )
    # Hazir olana kadar bekle - ilk embedding modeli yuklemesi birkaç
    # saniye surebilir, ama HTTP sunucusunun kendisi hemen ayaga kalkar.
    async with httpx.AsyncClient() as probe:
        for _ in range(60):
            try:
                r = await probe.get(f"{SEARCH_HTTP_URL}/health", timeout=2.0)
                if r.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1.0)
        else:
            raise RuntimeError(f"search-server HTTP {SEARCH_HTTP_URL}/health 60 saniyede ayağa kalkmadı")
    return proc


async def _ensure_htr_kraken_started() -> None:
    """htr-kraken'i lifespan'da degil, ilk yerel HTR ihtiyacinda baslatir.

    Render'in 512MB ucretsiz tier'inda, search-server (embedding, kendi
    PyTorch yigini) ve htr-kraken (kraken, AYRI bir PyTorch yigini) ikisi de
    lifespan'da acilista baslatilinca container OOM'a giriyordu - iki tam
    torch surumu ayni container'da ayni anda RAM'de. Bu tek basina yetmedi:
    /ingest'in yerel-HTR yolu kraken'i baslattiginda, search-server HALA
    calisiyor oluyor ve ayni OOM iki sürecin yan yana durmasindan kaynaklanan
    ayni sorunu /ingest sirasinda yeniden yaratiyordu. Cozum: /ingest'in
    yerel-HTR yolu artik search-server'i GECICI olarak durdurup kraken'i
    baslatiyor, HTR bitince kraken'i kapatip search-server'i (embedding icin
    gerekli) geri baslatiyor - bkz. ingest() icindeki durdur/baslat sirasi.
    Bu fonksiyon sadece kraken'i baslatir; search-server'in durdurulmasi
    cagiran tarafin sorumlulugundadir.
    """
    async with _htr_kraken_lock:
        if mcp_manager.is_started("htr-kraken"):
            return
        await mcp_manager.start(
            "htr-kraken",
            command=HTR_KRAKEN_PYTHON,
            args=["-m", "htr_server.server"],
            cwd=str(HTR_KRAKEN_DIR),
            env={"KRAKEN_MODEL_DIR": KRAKEN_MODEL_DIR, "KRAKEN_DEFAULT_MODEL": KRAKEN_DEFAULT_MODEL},
        )


async def _stop_search_http_server() -> None:
    """search-server alt surecini gecici olarak kapatir (RAM'i kraken'e
    birakmak icin) - bkz. _ensure_htr_kraken_started docstring'i.
    search_http_client nesnesi (httpx.AsyncClient) kapatilmiyor; sadece
    arkasindaki surec durup _start_search_http_server ile ayni portta
    yeniden baslatiliyor, boylece client tekrar olusturmaya gerek yok."""
    global _search_process
    if _search_process is not None:
        _search_process.terminate()
        await asyncio.to_thread(_search_process.wait)
        _search_process = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global search_http_client, _search_process
    _search_process = await _start_search_http_server()
    search_http_client = httpx.AsyncClient(base_url=SEARCH_HTTP_URL, timeout=120.0)

    # htr-kraken ARTIK burada eagerly baslatilmiyor - bkz.
    # _ensure_htr_kraken_started docstring'i. /ingest'in yerel-HTR yolu onu
    # ilk kullanimda kendisi baslatir.
    try:
        yield
    finally:
        await mcp_manager.stop_all()
        await search_http_client.aclose()
        if _search_process is not None:
            _search_process.terminate()


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """HTTP Basic Auth ile tum uygulamayi (API + statik frontend) korur.

    BASIC_AUTH_USER bos ise (varsayilan, yerel gelistirme) auth tamamen
    devre disi kalir. Production'da (HF Spaces secrets) doldurulmasi
    zorunlu - ANTHROPIC_API_KEY gercek para harcadigindan herkese acik,
    korumasiz birakilmamali.
    """

    async def dispatch(self, request: Request, call_next):
        if not BASIC_AUTH_USER:
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
                user, _, password = decoded.partition(":")
            except Exception:
                user, password = "", ""
            if secrets.compare_digest(user, BASIC_AUTH_USER) and secrets.compare_digest(
                password, BASIC_AUTH_PASSWORD
            ):
                return await call_next(request)

        return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="ottoman-rag"'})


app = FastAPI(title="Osmanlıca El Yazması RAG API", lifespan=lifespan)

app.add_middleware(BasicAuthMiddleware)

# Dev ortamında frontend (Vite, :5173) farklı origin'den backend'e (:8000)
# istek atar; production'da frontend ayni origin'den (statik dosya olarak)
# servis edildigi icin CORS devreye girmez, bu yuzden dev origin'lerini
# sabit birakmak zararsiz.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str
    manuscript_id: str | None = None
    top_k: int = 5
    language: str = "tr"  # "tr" | "en" - cevabin uretilecegi dil


@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest) -> AskResponse:
    return await answer_question(
        search_http_client, req.question, req.manuscript_id, req.top_k, req.language
    )


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


class UploadImageResponse(BaseModel):
    image_path: str
    image_width: int
    image_height: int


@app.post("/upload-image", response_model=UploadImageResponse)
async def upload_image(file: UploadFile) -> UploadImageResponse:
    """Bir sayfa görüntüsünü sunucuya kaydeder; frontend'in "Yeni Sayfa
    Ekle" formu bunu kullanır. Dönen image_path, /ingest'e verilecek yerel
    yoldur."""
    original = Path(file.filename or "sayfa")
    ext = original.suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Desteklenmeyen dosya türü: {ext or '(yok)'}. İzin verilenler: {sorted(_ALLOWED_EXTENSIONS)}",
        )

    safe_stem = _SAFE_STEM.sub("_", original.stem).strip("_") or "sayfa"
    filename = f"{safe_stem}_{uuid.uuid4().hex[:8]}{ext}"

    RAW_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_IMAGES_DIR / filename
    content = await file.read()
    dest.write_bytes(content)

    with Image.open(dest) as img:
        width, height = img.size

    return UploadImageResponse(image_path=str(dest), image_width=width, image_height=height)


class IngestRequest(BaseModel):
    manuscript: ManuscriptRef
    page: PageRef
    kraken_model: str | None = None
    max_chars: int = 400
    # "local" (bu makinede CPU) | "remote" (GPU'lu uzak sunucu). Bos
    # birakilirsa sunucunun HTR_MODE ortam degiskeni (varsayilan "local")
    # kullanilir - boylece arastirmaci her yukleme icin secebilir.
    htr_backend: str | None = None


class IngestResponse(BaseModel):
    chunks_indexed: int


async def _run_htr_remote(image_path: str, model_name: str | None) -> HtrPageResult:
    if not REMOTE_HTR_URL:
        raise HTTPException(
            status_code=400,
            detail="Uzak HTR seçildi ama REMOTE_HTR_URL yapılandırılmamış (.env).",
        )
    headers = {"x-api-key": REMOTE_HTR_API_KEY} if REMOTE_HTR_API_KEY else {}
    async with httpx.AsyncClient(timeout=600) as client:
        with open(image_path, "rb") as f:
            files = {"file": (Path(image_path).name, f, "application/octet-stream")}
            data = {"model_name": model_name} if model_name else {}
            resp = await client.post(
                f"{REMOTE_HTR_URL}/run-htr", files=files, data=data, headers=headers
            )
        if resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Uzak HTR sunucusu hata döndürdü ({resp.status_code}): {resp.text}",
            )
        return HtrPageResult.model_validate(resp.json())


@app.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest) -> IngestResponse:
    """Bir sayfayı transkribe edip provenance koruyarak indeksler.

    HTR, htr_backend'e göre yerelde (Kraken, CPU, MCP alt süreci) ya da
    uzak bir GPU sunucusunda (bkz. mcp-servers/remote-htr-server) çalışır.

    Not: yerel modda models/ altında bir .mlmodel dosyası olmadan çalışmaz
    (bkz. kök README - OpenITI Ottoman base modeli). Transkribus üzerinden
    ingestion henüz bu uç noktaya bağlanmadı.
    """
    global _search_process
    store.upsert_manuscript(req.manuscript)
    store.upsert_page(req.page)

    backend_choice = req.htr_backend or HTR_MODE
    if backend_choice == "remote":
        htr_result = await _run_htr_remote(req.page.image_path, req.kraken_model)
    else:
        # search-server ve kraken'in PyTorch yiginlari Render'in 512MB
        # tier'inda AYNI ANDA sigmiyor (bkz. _ensure_htr_kraken_started
        # docstring'i) - search-server'i gecici kapatip kraken'e yer aciyoruz,
        # HTR bitince embedding/indexleme icin geri baslatiyoruz.
        await _stop_search_http_server()
        try:
            await _ensure_htr_kraken_started()
            htr_client = mcp_manager.get("htr-kraken")
            raw_result = await htr_client.call_tool(
                "run_htr",
                {"image_path": req.page.image_path, "model_name": req.kraken_model},
                timeout=600,  # Kraken CPU'da yavas olabilir; sunucuyu sonsuza kadar kilitlemesin
            )
            htr_result = HtrPageResult.model_validate(raw_result)
        finally:
            await mcp_manager.stop("htr-kraken")
            _search_process = await _start_search_http_server()

    chunks = chunk_page(htr_result, req.manuscript, req.page, max_chars=req.max_chars)

    resp = await search_http_client.post(
        "/index_chunks", json={"chunks": [c.model_dump(mode="json") for c in chunks]}
    )
    resp.raise_for_status()
    return IngestResponse(chunks_indexed=resp.json()["indexed"])


# Statik frontend build'i (varsa) en sonda mount edilir - butun API
# rotalarindan SONRA tanimlanmali ki once onlar eslessin. HF Spaces gibi
# tek-port ortamlarda frontend'i ayri bir Node sureciyle degil, dogrudan
# bu FastAPI uygulamasindan servis ederiz (bkz. Dockerfile).
if FRONTEND_DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST_DIR), html=True), name="frontend")
