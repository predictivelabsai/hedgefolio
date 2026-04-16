"""RAG retrieval + HTML→text + chunking tests."""

from __future__ import annotations

import pytest


def test_36_html_to_text_strips_tags():
    from utils.rag import html_to_text
    html = "<html><body><h1>Title</h1><p>Hello <b>world</b></p><script>evil()</script></body></html>"
    out = html_to_text(html)
    assert "Title" in out
    assert "Hello" in out
    assert "world" in out
    assert "evil" not in out  # <script> stripped


def test_37_chunk_text_respects_size():
    from utils.rag import chunk_text
    body = ("Para one.\n\n" * 50) + "Para two.\n\n" + ("x" * 5000)
    chunks = chunk_text(body, chunk_size=1500, overlap=200)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= 1500 + 200  # some overlap leeway


def test_38_search_f13_docs_returns_known_terms(has_rag_data):
    from utils.rag import search_f13_docs
    if not has_rag_data:
        pytest.skip("RAG not ingested")
    out = search_f13_docs("CUSIP")
    assert "CUSIP" in out.upper()


def test_39_search_f13_docs_no_match(has_rag_data):
    from utils.rag import search_f13_docs
    if not has_rag_data:
        pytest.skip("RAG not ingested")
    out = search_f13_docs("zzzzzyyyxxxwww_does_not_exist_anywhere")
    assert "No matches" in out or "no matches" in out.lower()
