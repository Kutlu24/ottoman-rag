from ottoman_rag_common.geometry import BoundingBox, Point
from ottoman_rag_common.htr import HtrPageResult, HtrRun, Line
from ottoman_rag_common.provenance import ManuscriptRef, PageRef

from ingestion.chunker import chunk_page

MS = ManuscriptRef(manuscript_id="ms1", repository="Süleymaniye Kütüphanesi", shelfmark="Ayasofya 1234")
PAGE = PageRef(page_id="p1", manuscript_id="ms1", folio_label="12r", image_path="p1.png")
RUN = HtrRun(htr_run_id="r1", backend="kraken", model_name="m")


def _line(i: int, text: str) -> Line:
    box = BoundingBox(x_min=0, y_min=i * 10, x_max=100, y_max=i * 10 + 8)
    pts = [Point(x=0, y=i * 10), Point(x=100, y=i * 10 + 8)]
    return Line(id=f"l{i}", text=text, polygon=pts, bbox=box)


def _result(*texts: str) -> HtrPageResult:
    return HtrPageResult(image_path="p1.png", lines=[_line(i, t) for i, t in enumerate(texts)], htr_run=RUN)


def test_short_page_becomes_one_chunk_with_all_lines():
    chunks = chunk_page(_result("bir", "iki", "üç"), MS, PAGE)
    assert len(chunks) == 1
    assert chunks[0].text == "bir iki üç"
    assert chunks[0].provenance.line_ids == ["l0", "l1", "l2"]


def test_splits_when_max_chars_exceeded_and_keeps_line_bbox_alignment():
    chunks = chunk_page(_result("a" * 30, "b" * 30, "c" * 30), MS, PAGE, max_chars=50)
    assert [c.provenance.line_ids for c in chunks] == [["l0"], ["l1"], ["l2"]]
    for c in chunks:
        assert len(c.provenance.line_ids) == len(c.provenance.bboxes)


def test_blank_lines_are_skipped():
    chunks = chunk_page(_result("x", "   ", "y"), MS, PAGE)
    assert chunks[0].provenance.line_ids == ["l0", "l2"]


def test_empty_page_yields_no_chunks():
    assert chunk_page(_result(), MS, PAGE) == []


def test_oversized_single_line_is_not_dropped():
    chunks = chunk_page(_result("z" * 500), MS, PAGE, max_chars=50)
    assert len(chunks) == 1 and len(chunks[0].text) == 500


def test_citation_label_and_htr_run_travel_with_chunk():
    p = chunk_page(_result("x"), MS, PAGE)[0].provenance
    assert p.citation_label == "Süleymaniye Kütüphanesi, Ayasofya 1234, fol. 12r"
    assert p.htr_run.htr_run_id == "r1"


def test_citation_label_falls_back_to_manuscript_id():
    ms = ManuscriptRef(manuscript_id="ms9")
    page = PageRef(page_id="p", manuscript_id="ms9", image_path="x.png")
    assert chunk_page(_result("x"), ms, page)[0].provenance.citation_label == "ms9"


def test_chunk_ids_are_unique():
    chunks = chunk_page(_result("a" * 30, "b" * 30), MS, PAGE, max_chars=40)
    assert len({c.chunk_id for c in chunks}) == len(chunks)
