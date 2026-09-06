"""Yazma eseri katalog kaydinin (manuscript/page) tek dogruluk kaynagi.

search-server'daki vektor DB metadata'si (citation_label vb.) bu tablolardan
onceden hesaplanip chunk'lara "cache'lenir" (bkz. ingestion/chunker.py);
burasi ise tam kaydin (repository, tarih, koleksiyon notlari, gorsel yolu)
kalici olarak tutuldugu yerdir.
"""

from __future__ import annotations

import sqlite3

from ottoman_rag_common.provenance import ManuscriptRef, PageRef

from .config import METADATA_DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS manuscripts (
    manuscript_id TEXT PRIMARY KEY,
    title TEXT,
    repository TEXT,
    shelfmark TEXT,
    date TEXT,
    collection TEXT,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS pages (
    page_id TEXT PRIMARY KEY,
    manuscript_id TEXT NOT NULL REFERENCES manuscripts(manuscript_id),
    folio_label TEXT,
    image_path TEXT NOT NULL,
    image_width INTEGER,
    image_height INTEGER
);
"""


def _connect() -> sqlite3.Connection:
    METADATA_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(METADATA_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def upsert_manuscript(m: ManuscriptRef) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO manuscripts
                 (manuscript_id, title, repository, shelfmark, date, collection, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(manuscript_id) DO UPDATE SET
                 title=excluded.title,
                 repository=excluded.repository,
                 shelfmark=excluded.shelfmark,
                 date=excluded.date,
                 collection=excluded.collection,
                 notes=excluded.notes""",
            (m.manuscript_id, m.title, m.repository, m.shelfmark, m.date, m.collection, m.notes),
        )


def get_manuscript(manuscript_id: str) -> ManuscriptRef | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM manuscripts WHERE manuscript_id = ?", (manuscript_id,)
        ).fetchone()
        return ManuscriptRef(**dict(row)) if row else None


def upsert_page(p: PageRef) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO pages
                 (page_id, manuscript_id, folio_label, image_path, image_width, image_height)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(page_id) DO UPDATE SET
                 manuscript_id=excluded.manuscript_id,
                 folio_label=excluded.folio_label,
                 image_path=excluded.image_path,
                 image_width=excluded.image_width,
                 image_height=excluded.image_height""",
            (p.page_id, p.manuscript_id, p.folio_label, p.image_path, p.image_width, p.image_height),
        )


def get_page(page_id: str) -> PageRef | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM pages WHERE page_id = ?", (page_id,)).fetchone()
        return PageRef(**dict(row)) if row else None
