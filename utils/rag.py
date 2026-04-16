"""F13 filings RAG — schema bootstrap, ingestion, and retrieval.

Uses Postgres full-text search (`to_tsvector`) for a zero-dependency retriever.
The LangGraph agent calls `search_f13_docs()` to answer questions about the
structure, fields, and methodology of SEC Form 13F filings. Source documents
live in /home/julian/dev/plai/hedgefolio/data (FORM13F_readme.htm +
FORM13F_metadata.json).
"""

from __future__ import annotations

import json
import logging
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import List

from sqlalchemy import text

from utils.db_pool import get_pool

logger = logging.getLogger(__name__)

RAG_SCHEMA = "hedgefolio_rag"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCHEMA_SQL = Path(__file__).resolve().parent.parent / "sql" / "rag_schema.sql"


def ensure_schema() -> None:
    """Create the hedgefolio_rag schema/tables if they are missing."""
    pool = get_pool()
    sql = SCHEMA_SQL.read_text()
    with pool.get_session() as s:
        s.execute(text(sql))


# ---------------------------------------------------------------------------
# HTML stripping — lightweight, no BeautifulSoup dependency.
# ---------------------------------------------------------------------------

class _HTMLToText(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in ("p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip:
            return
        if data.strip():
            self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def html_to_text(html: str) -> str:
    parser = _HTMLToText()
    parser.feed(html)
    return parser.get_text()


# ---------------------------------------------------------------------------
# Chunking — roughly 1500 chars per chunk with 200 char overlap. Simple and
# good enough for the size of the F13 readme.
# ---------------------------------------------------------------------------

def chunk_text(text_body: str, chunk_size: int = 1500, overlap: int = 200) -> List[str]:
    chunks: list[str] = []
    paragraphs = re.split(r"\n\s*\n", text_body)
    buf = ""
    for p in paragraphs:
        if not p.strip():
            continue
        if len(buf) + len(p) + 2 <= chunk_size:
            buf = f"{buf}\n\n{p}" if buf else p
        else:
            if buf:
                chunks.append(buf.strip())
            if len(p) > chunk_size:
                # paragraph is too big; split hard
                for i in range(0, len(p), chunk_size - overlap):
                    chunks.append(p[i : i + chunk_size].strip())
                buf = ""
            else:
                buf = p
    if buf:
        chunks.append(buf.strip())
    return chunks


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def _upsert_document(session, source: str, title: str, doc_type: str, url: str | None, metadata: dict | None) -> int:
    row = session.execute(
        text(
            f"""
            INSERT INTO {RAG_SCHEMA}.documents (source, title, doc_type, url, metadata)
            VALUES (:source, :title, :doc_type, :url, CAST(:metadata AS JSONB))
            ON CONFLICT (source) DO UPDATE
                SET title = EXCLUDED.title,
                    doc_type = EXCLUDED.doc_type,
                    url = EXCLUDED.url,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
            RETURNING id
            """
        ),
        {
            "source": source,
            "title": title,
            "doc_type": doc_type,
            "url": url,
            "metadata": json.dumps(metadata or {}),
        },
    ).fetchone()
    return int(row[0])


def _replace_chunks(session, document_id: int, chunks: list[str]) -> None:
    session.execute(
        text(f"DELETE FROM {RAG_SCHEMA}.chunks WHERE document_id = :did"),
        {"did": document_id},
    )
    for idx, chunk in enumerate(chunks):
        session.execute(
            text(
                f"""
                INSERT INTO {RAG_SCHEMA}.chunks (document_id, chunk_index, content, token_count)
                VALUES (:did, :idx, :content, :tokens)
                """
            ),
            {
                "did": document_id,
                "idx": idx,
                "content": chunk,
                "tokens": max(1, len(chunk) // 4),
            },
        )


def ingest_readme() -> int:
    path = DATA_DIR / "FORM13F_readme.htm"
    if not path.exists():
        logger.warning("FORM13F_readme.htm not found at %s", path)
        return 0
    html = path.read_text(errors="ignore")
    body = html_to_text(html)
    chunks = chunk_text(body)
    pool = get_pool()
    with pool.get_session() as s:
        doc_id = _upsert_document(
            s,
            source="FORM13F_readme.htm",
            title="SEC Form 13F — Dataset Readme",
            doc_type="readme",
            url="https://www.sec.gov/dera/data/form-13f",
            metadata={"chunks": len(chunks)},
        )
        _replace_chunks(s, doc_id, chunks)
    logger.info("Ingested FORM13F_readme.htm → %s chunks", len(chunks))
    return len(chunks)


def ingest_metadata() -> int:
    path = DATA_DIR / "FORM13F_metadata.json"
    if not path.exists():
        return 0
    meta = json.loads(path.read_text())
    lines: list[str] = ["# SEC Form 13F — Table Schema"]
    for table in meta.get("tables", []):
        url = table.get("url", "")
        lines.append(f"\n## Table: {url}")
        ts = table.get("tableSchema", {})
        pk = ts.get("primaryKey")
        if pk:
            lines.append(f"Primary key: {pk}")
        for col in ts.get("columns", []):
            name = col.get("name")
            desc = col.get("dc:description", "").strip()
            dtype = col.get("datatype", {})
            base = dtype.get("base", "") if isinstance(dtype, dict) else dtype
            required = " (required)" if col.get("required") else ""
            lines.append(f"- **{name}** ({base}){required}: {desc}")
    body = "\n".join(lines)
    chunks = chunk_text(body, chunk_size=2000, overlap=150)
    pool = get_pool()
    with pool.get_session() as s:
        doc_id = _upsert_document(
            s,
            source="FORM13F_metadata.json",
            title="SEC Form 13F — Table & Column Schema",
            doc_type="schema",
            url=None,
            metadata={"chunks": len(chunks), "tables": len(meta.get("tables", []))},
        )
        _replace_chunks(s, doc_id, chunks)
    logger.info("Ingested FORM13F_metadata.json → %s chunks", len(chunks))
    return len(chunks)


def ingest_all() -> dict:
    ensure_schema()
    return {
        "readme_chunks": ingest_readme(),
        "metadata_chunks": ingest_metadata(),
    }


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def search_f13_docs(query: str, limit: int = 5) -> str:
    """Search F13 filing docs and return the top chunks formatted as markdown."""
    if not query or not query.strip():
        return "Please provide a search query."
    pool = get_pool()
    try:
        with pool.get_session() as s:
            rows = s.execute(
                text(
                    f"""
                    SELECT d.title, d.source, c.content,
                           ts_rank_cd(to_tsvector('english', c.content),
                                      plainto_tsquery('english', :q)) AS rank
                    FROM {RAG_SCHEMA}.chunks c
                    JOIN {RAG_SCHEMA}.documents d ON d.id = c.document_id
                    WHERE to_tsvector('english', c.content) @@ plainto_tsquery('english', :q)
                    ORDER BY rank DESC
                    LIMIT :lim
                    """
                ),
                {"q": query, "lim": limit},
            ).fetchall()
    except Exception as e:
        return f"RAG error: {e}. The index may not be built — run `python tasks/setup_rag.py`."

    if not rows:
        return f"No matches found in the F13 knowledge base for **{query}**."

    out = [f"**F13 Docs — top {len(rows)} result(s) for `{query}`:**"]
    for i, r in enumerate(rows, 1):
        title, source, content, _ = r
        snippet = content.strip()
        if len(snippet) > 900:
            snippet = snippet[:900].rstrip() + "…"
        out.append(f"\n### {i}. {title}\n_source: `{source}`_\n\n{snippet}")
    return "\n".join(out)
