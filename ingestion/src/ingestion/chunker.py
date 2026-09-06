"""HTR satirlarini, provenance korunarak RAG chunk'larina bolen modul.

Tasarim karari: chunk'in kendisi provenance'i tasir (loose coupling degil).
Her chunk manuscript_id + page_id + kaynak line_id'leri + o satirlarin
bbox'larini + hangi HTR modeliyle uretildigini (htr_run) icerir. Boylece
retrieval sonucundan dogrudan "hangi yazma, hangi sayfa, hangi satirlar"
bilgisine ve highlight icin gereken bbox'lara ulasilir; ayri bir join
gerekmez (bkz. README - provenance-aware retrieval tasarim notu).
"""

from __future__ import annotations

import uuid

from ottoman_rag_common.geometry import BoundingBox
from ottoman_rag_common.htr import HtrPageResult
from ottoman_rag_common.provenance import Chunk, ChunkProvenance, ManuscriptRef, PageRef


def _citation_label(manuscript: ManuscriptRef, page: PageRef) -> str:
    parts = [p for p in (manuscript.repository, manuscript.shelfmark) if p]
    label = ", ".join(parts) if parts else manuscript.manuscript_id
    if page.folio_label:
        label += f", fol. {page.folio_label}"
    return label


def chunk_page(
    htr_result: HtrPageResult,
    manuscript: ManuscriptRef,
    page: PageRef,
    max_chars: int = 400,
) -> list[Chunk]:
    """Sayfa satırlarını ardışık pencereleme ile chunk'lara böler.

    Satırlar sırayla biriktirilir; toplam karakter sayısı max_chars'ı
    aştığında yeni chunk başlar. Böylece embedding için yeterli bağlam
    korunurken her chunk'ın kaynak satırlarının (dolayısıyla bbox'larının)
    izi kaybolmaz.
    """
    citation = _citation_label(manuscript, page)
    chunks: list[Chunk] = []

    buffer_text: list[str] = []
    buffer_line_ids: list[str] = []
    buffer_bboxes: list[BoundingBox] = []
    buffer_len = 0

    def flush() -> None:
        nonlocal buffer_text, buffer_line_ids, buffer_bboxes, buffer_len
        if not buffer_text:
            return
        chunks.append(
            Chunk(
                chunk_id=str(uuid.uuid4()),
                text=" ".join(buffer_text).strip(),
                provenance=ChunkProvenance(
                    manuscript_id=manuscript.manuscript_id,
                    page_id=page.page_id,
                    folio_label=page.folio_label,
                    line_ids=list(buffer_line_ids),
                    bboxes=list(buffer_bboxes),
                    htr_run=htr_result.htr_run,
                    citation_label=citation,
                ),
            )
        )
        buffer_text, buffer_line_ids, buffer_bboxes, buffer_len = [], [], [], 0

    for line in htr_result.lines:
        if not line.text.strip():
            continue
        if buffer_len + len(line.text) > max_chars and buffer_text:
            flush()
        buffer_text.append(line.text)
        buffer_line_ids.append(line.id)
        buffer_bboxes.append(line.bbox)
        buffer_len += len(line.text)

    flush()
    return chunks
