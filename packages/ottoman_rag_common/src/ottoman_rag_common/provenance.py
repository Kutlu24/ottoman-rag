from __future__ import annotations

from pydantic import BaseModel

from .geometry import BoundingBox
from .htr import HtrRun


class ManuscriptRef(BaseModel):
    """Yazma eserin katalog bilgisi - tek doğruluk kaynağı bu değil, bir
    metadata store'da (Step 3) tutulacak; bu sadece chunk'lara taşınan özet."""

    manuscript_id: str
    title: str | None = None
    repository: str | None = None  # ör. "Süleymaniye Kütüphanesi"
    shelfmark: str | None = None  # ör. "Ayasofya 1234"
    date: str | None = None
    collection: str | None = None
    notes: str | None = None


class PageRef(BaseModel):
    page_id: str
    manuscript_id: str
    folio_label: str | None = None  # ör. "12r"
    image_path: str
    image_width: int | None = None
    image_height: int | None = None


class ChunkProvenance(BaseModel):
    """Bir chunk'ın hangi yazma/sayfa/satırlardan geldiğinin tam izi.

    line_ids ve bboxes aynı sırada, birebir eşleşir: chunk birden fazla satırı
    kapsıyorsa highlight overlay bu listedeki her bbox'ı ayrı ayrı çizer.
    """

    manuscript_id: str
    page_id: str
    folio_label: str | None = None
    line_ids: list[str]
    bboxes: list[BoundingBox]
    htr_run: HtrRun
    citation_label: str | None = None  # ör. "Süleymaniye Ktp., Ayasofya 1234, fol. 12r"


class Chunk(BaseModel):
    chunk_id: str
    text: str
    provenance: ChunkProvenance
