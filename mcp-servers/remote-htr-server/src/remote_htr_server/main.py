"""Kraken HTR'i GPU'lu bir makinede (Google Cloud Run + GPU, universite
sunucusu, kendi GPU'lu makineniz vb.) calistirip HTTP uzerinden sunan
referans servis.

htr-server (mcp-servers/htr-server) ile ayni kraken_runner.run_kraken()
fonksiyonunu kullanir - tek fark burada calistirma HTTP uzerinden (MCP
stdio degil, cunku aginin karsi ucundaki bir makineye baglanmak icin
stdio subprocess modeli calismaz) ve device varsayilani "cuda:0"dir.

Calistirma:
    KRAKEN_MODEL_DIR=./models KRAKEN_DEVICE=cuda:0 REMOTE_HTR_API_KEY=... \
      uvicorn remote_htr_server.main:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import os
import secrets
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from htr_server.kraken_runner import KrakenError, run_kraken

API_KEY = os.environ.get("REMOTE_HTR_API_KEY", "")
MODEL_DIR = Path(os.environ.get("KRAKEN_MODEL_DIR", "./models"))
DEFAULT_MODEL = os.environ.get("KRAKEN_DEFAULT_MODEL", "")
DEFAULT_DEVICE = os.environ.get("KRAKEN_DEVICE", "cuda:0")

app = FastAPI(title="Uzak HTR Sunucusu (GPU)")


def _check_auth(x_api_key: str | None) -> None:
    # API_KEY bos ise (yerel/kapali agda test) auth devre disi; gercek bir
    # GPU sunucusuna (internete acik) deploy ederken MUTLAKA doldurulmali.
    if API_KEY and not (x_api_key and secrets.compare_digest(x_api_key, API_KEY)):
        raise HTTPException(status_code=401, detail="Geçersiz veya eksik API anahtarı")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "default_device": DEFAULT_DEVICE, "model_dir": str(MODEL_DIR)}


@app.post("/run-htr")
async def run_htr_endpoint(
    file: UploadFile = File(...),
    model_name: str | None = Form(None),
    device: str | None = Form(None),
    x_api_key: str | None = Header(None),
) -> dict:
    _check_auth(x_api_key)

    chosen_model = model_name or DEFAULT_MODEL
    if not chosen_model:
        raise HTTPException(status_code=400, detail="model_name verilmedi ve KRAKEN_DEFAULT_MODEL yok")
    model_path = MODEL_DIR / chosen_model
    if not model_path.exists():
        raise HTTPException(status_code=404, detail=f"Model bulunamadı: {model_path}")

    suffix = Path(file.filename or "page.jpg").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        result = run_kraken(tmp_path, str(model_path), device=device or DEFAULT_DEVICE)
        return result.model_dump(mode="json")
    except KrakenError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)
