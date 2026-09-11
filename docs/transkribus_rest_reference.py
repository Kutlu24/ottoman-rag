"""Transkribus legacy TrpServer REST API icin dogrulanmis, calisan referans kod.

Bu dosya calistirilan bir modul DEGIL - backend'e henuz baglanmadi (bkz. README
Step 8). Layout Analysis (satir segmentasyonu) adimi Transkribus'un sunucu
tarafinda bozuk oldugu icin tam bir OCR sonucu uretmiyor. Asagidaki iki akis
GERCEK hesapla, gercek gorunutuyle dogrulandi ve calisiyor:

1) upload_image_to_transkribus() - gorsel yukleme (eski zip yontemi 404,
   yerine bu /uploads akisi geciyor)
2) run_pylaia_recognition() - PyLaia tanima job'u basariyla calisiyor, ama
   segmentasyon olmadan BOS sonuc donduruyor (Transkribus'ta once Layout
   Analysis gerekiyor, o da su an /LA/analyze'da HTTP 500 ile bozuk).

Transkribus tarafi duzelirse (legacy /LA/analyze veya yeni Metagrapho
/processing/v1/processes API'si), bu iki fonksiyonu baz alarak htr_backend
"transkribus" secenegini backend/src/backend/main.py'ye eklemek yeterli olur.
"""
from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

BASE = "https://transkribus.eu/TrpServer/rest"


def login(client: httpx.Client, user: str, password: str) -> None:
    resp = client.post("/auth/login", data={"user": user, "pw": password})
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    session_id = next(e.text for e in root.iter() if e.tag.rsplit("}", 1)[-1] == "sessionId")
    client.cookies.set("JSESSIONID", session_id)


def upload_image_to_transkribus(
    client: httpx.Client, coll_id: int, image_path: Path, title: str
) -> int:
    """Gorseli yeni bir dokuman olarak yukler, docId dondurur.

    Dogrulanmis akis (docId 18693058, coll 2501806 ile test edildi):
    POST /uploads?collId=... -> uploadId -> PUT /uploads/{uploadId} (multipart)
    -> GET /jobs/{jobId} (poll) -> docId.
    """
    body = {
        "md": {"title": title},
        "pageList": {"pages": [{"fileName": image_path.name, "pageNr": 1}]},
    }
    resp = client.post("/uploads", params={"collId": coll_id}, json=body)
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    upload_id = next(e.text for e in root.iter() if e.tag.rsplit("}", 1)[-1] == "uploadId")

    with open(image_path, "rb") as f:
        files = {"img": (image_path.name, f, "application/octet-stream")}
        resp = client.put(f"/uploads/{upload_id}", files=files)
    resp.raise_for_status()

    job_id = None
    for _ in range(20):
        resp = client.get(f"/uploads/{upload_id}")
        data = resp.json()
        job_id = data.get("jobId")
        if job_id:
            break
        time.sleep(2)
    if not job_id:
        raise RuntimeError("upload jobId alinamadi")

    for _ in range(20):
        resp = client.get(f"/jobs/{job_id}")
        job = resp.json()
        if job.get("state") == "FINISHED" and job.get("success"):
            return job["docId"]
        if job.get("state") == "FAILED":
            raise RuntimeError(f"upload job basarisiz: {job}")
        time.sleep(2)
    raise RuntimeError("upload job zaman asimina ugradi")


def run_pylaia_recognition(client: httpx.Client, coll_id: int, model_id: int, doc_id: int) -> str:
    """PyLaia tanima job'unu baslatir. NOT: onceden Layout Analysis (satir
    segmentasyonu) yapilmis olmasi gerekir, aksi halde bos sonuc doner -
    ve /LA/analyze su an Transkribus sunucusunda bozuk (HTTP 500)."""
    params = {"id": doc_id, "pages": "1"}
    resp = client.post(f"/pylaia/{coll_id}/{model_id}/recognition", params=params, json={})
    resp.raise_for_status()
    return resp.text.strip()  # jobId


# Herkese acik Osmanlica modelleri (app.transkribus.org/models?search=ottoman
# uzerinden, 2026-09-06 tarihinde dogrulandi):
OTTOMAN_MODELS = {
    461445: {"name": "Manuscrita cursiva XVIII", "languages": "tr-ottoman, es", "cer": 2.59},
    457745: {"name": "Dabbas 1706-1711", "languages": "ar", "cer": 3.62},
    169801: {"name": "Ottoman Fatwa Manuscript", "languages": "tr-ottoman", "cer": 5.94},
    57485: {"name": "OttomanTurkish_Print_v2", "languages": "tr-ottoman", "cer": 7.60},
    52502: {"name": "OttomanTurkish_Print_1", "languages": "tr-ottoman", "cer": 7.20},
    56496: {"name": "OttomanTurkish_generic", "languages": "tr-ottoman", "cer": 11.60},
}
