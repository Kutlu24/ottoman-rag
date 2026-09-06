"""Sentetik veriyle uctan uca duman testi: chunk_page -> index_chunks -> search.

Gercek Kraken/Transkribus calismasi beklemeden, provenance-aware chunking +
embedding + vektor arama zincirinin dogru calistigini dogrular.

Calistirma:
    conda activate ottoman-rag
    python -m ingestion.smoke_test
"""

from __future__ import annotations

from ottoman_rag_common.geometry import BoundingBox, Point
from ottoman_rag_common.htr import HtrPageResult, HtrRun, Line
from ottoman_rag_common.provenance import ManuscriptRef, PageRef

from search_server import vector_store
from search_server.embeddings import embed_texts

from .chunker import chunk_page


def _line(i: int, text: str) -> Line:
    y = 100.0 * i
    poly = [Point(x=50, y=y), Point(x=800, y=y), Point(x=800, y=y + 40), Point(x=50, y=y + 40)]
    return Line(id=f"line_{i}", text=text, confidence=0.92, polygon=poly, bbox=BoundingBox.from_points(poly))


def main() -> None:
    htr_run = HtrRun(
        htr_run_id="smoke-test-run-1",
        backend="transkribus",
        model_name="Ottoman Fatwa Manuscripts",
        model_ref="169801",
        cer_estimate=5.94,
    )

    lines = [
        _line(0, "Bu bir Osmanlıca el yazması fetva metninin ilk satırıdır."),
        _line(1, "İkinci satırda konuyla ilgili hüküm devam etmektedir."),
        _line(2, "Üçüncü satır kaynak gösterme ve şahitlik üzerinedir."),
    ]

    htr_result = HtrPageResult(
        image_path="data/raw_images/ms1234_fol012r.jpg",
        image_width=900,
        image_height=1400,
        htr_run=htr_run,
        lines=lines,
    )

    manuscript = ManuscriptRef(
        manuscript_id="ms-1234",
        title="Fetava Mecmuası (örnek)",
        repository="Süleymaniye Kütüphanesi",
        shelfmark="Ayasofya 1234",
        date="18. yüzyıl",
    )
    page = PageRef(
        page_id="ms-1234-fol012r",
        manuscript_id="ms-1234",
        folio_label="12r",
        image_path=htr_result.image_path,
        image_width=htr_result.image_width,
        image_height=htr_result.image_height,
    )

    chunks = chunk_page(htr_result, manuscript, page, max_chars=200)
    print(f"[1/3] {len(chunks)} chunk üretildi (provenance dahil).")
    for c in chunks:
        print(f"  - chunk_id={c.chunk_id[:8]}... line_ids={c.provenance.line_ids} "
              f"citation={c.provenance.citation_label!r}")

    vectors = embed_texts([c.text for c in chunks], is_query=False)
    vector_store.upsert_chunks(chunks, vectors)
    print(f"[2/3] {len(chunks)} chunk Chroma'ya yazıldı.")

    query = "Şahitlik ile ilgili hüküm nedir?"
    [query_vec] = embed_texts([query], is_query=True)
    results = vector_store.query(query_vec, top_k=2, manuscript_id="ms-1234")

    print(f"[3/3] Sorgu: {query!r}")
    for r in results:
        print(
            f"  -> {r['citation_label']} | satır(lar)={r['line_ids']} | "
            f"mesafe={r['distance']:.4f} | metin={r['text'][:80]!r}"
        )


if __name__ == "__main__":
    main()
