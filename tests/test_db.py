"""DB / schema regression tests."""

from __future__ import annotations

import pytest
from sqlalchemy import text


def test_01_db_reachable(db_pool, db_ok):
    with db_pool.get_session() as s:
        val = s.execute(text("SELECT 1")).scalar()
    assert val == 1


def test_02_hedgefolio_schema_exists(db_pool, db_ok):
    with db_pool.get_session() as s:
        rows = s.execute(
            text("SELECT schema_name FROM information_schema.schemata "
                 "WHERE schema_name IN ('hedgefolio', 'hedgefolio_rag')")
        ).fetchall()
    names = {r[0] for r in rows}
    assert "hedgefolio" in names
    assert "hedgefolio_rag" in names


def test_03_core_13f_tables_exist(db_pool, db_ok):
    with db_pool.get_session() as s:
        rows = s.execute(
            text("SELECT table_name FROM information_schema.tables "
                 "WHERE table_schema = 'hedgefolio' ORDER BY table_name")
        ).fetchall()
    tables = {r[0] for r in rows}
    for expected in {"submission", "coverpage", "summarypage", "infotable",
                     "activist_filing", "chat_conversations", "chat_messages",
                     "company_ticker"}:
        assert expected in tables, f"missing table: {expected}"


def test_04_13f_row_counts_consistent(db_pool, has_13f_data):
    if not has_13f_data:
        pytest.skip("no 13F data loaded")
    with db_pool.get_session() as s:
        subs = s.execute(text("SELECT COUNT(*) FROM hedgefolio.submission")).scalar()
        covs = s.execute(text("SELECT COUNT(*) FROM hedgefolio.coverpage")).scalar()
        info = s.execute(text("SELECT COUNT(*) FROM hedgefolio.infotable")).scalar()
    assert subs > 0
    assert covs > 0
    assert info > 0
    # Every infotable row must point at a real submission.
    with db_pool.get_session() as s:
        orphan = s.execute(
            text(
                """
                SELECT COUNT(*) FROM hedgefolio.infotable i
                LEFT JOIN hedgefolio.submission s
                       ON s.accession_number = i.accession_number
                WHERE s.accession_number IS NULL
                """
            )
        ).scalar()
    assert orphan == 0


def test_05_activist_table_populated_or_empty(db_pool, has_activist_data):
    # Not failing on empty — just asserts the column types and index when
    # there's at least one row.
    if not has_activist_data:
        pytest.skip("no activist filings loaded")
    with db_pool.get_session() as s:
        row = s.execute(
            text(
                """
                SELECT form_type, filer_name, filing_date
                FROM hedgefolio.activist_filing
                ORDER BY filing_date DESC LIMIT 1
                """
            )
        ).fetchone()
    assert row is not None
    assert row[0].startswith("SCHEDULE 13")
    assert row[1], "filer_name should not be empty"


def test_06_rag_documents_ingested(db_pool, has_rag_data):
    if not has_rag_data:
        pytest.skip("no RAG docs ingested")
    with db_pool.get_session() as s:
        n_docs = s.execute(text("SELECT COUNT(*) FROM hedgefolio_rag.documents")).scalar()
        n_chunks = s.execute(text("SELECT COUNT(*) FROM hedgefolio_rag.chunks")).scalar()
    assert n_docs > 0
    assert n_chunks >= n_docs


def test_07_rag_fts_index_usable(db_pool, has_rag_data):
    """FTS index built with gin(to_tsvector) actually answers queries."""
    if not has_rag_data:
        pytest.skip("no RAG docs ingested")
    with db_pool.get_session() as s:
        hits = s.execute(
            text(
                """
                SELECT COUNT(*) FROM hedgefolio_rag.chunks
                WHERE to_tsvector('english', content)
                      @@ plainto_tsquery('english', 'INVESTMENTDISCRETION')
                """
            )
        ).scalar()
    assert hits > 0, "FTS on RAG chunks should return results for known keyword"
