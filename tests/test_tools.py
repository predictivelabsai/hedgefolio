"""Agent tool-function regression tests.

Each tool returns a markdown string; we assert structure + presence of real
data when tables are populated.
"""

from __future__ import annotations

import pytest


def test_08_get_market_overview(has_13f_data):
    from utils.agent_tools import get_market_overview
    out = get_market_overview()
    assert isinstance(out, str)
    assert "Hedge Fund Market Overview" in out
    if has_13f_data:
        assert "Total Funds" in out
        assert "Total Holdings" in out


def test_09_search_funds(has_13f_data):
    from utils.agent_tools import search_funds
    if not has_13f_data:
        pytest.skip("no 13F data")
    out = search_funds("VANGUARD", limit=5)
    assert "VANGUARD" in out.upper()


def test_10_get_top_funds(has_13f_data):
    from utils.agent_tools import get_top_funds
    if not has_13f_data:
        pytest.skip("no 13F data")
    out = get_top_funds(top_n=10)
    # Should be a markdown table with 10 rows + header + separator.
    data_lines = [ln for ln in out.splitlines() if ln.startswith("| ")]
    # header + separator + 10 rows
    assert len(data_lines) >= 10


def test_11_get_fund_holdings(has_13f_data):
    from utils.agent_tools import get_fund_holdings
    if not has_13f_data:
        pytest.skip("no 13F data")
    out = get_fund_holdings("Bridgewater", limit=10)
    assert "bridgewater" in out.lower()
    assert "Portfolio %" in out


def test_12_search_securities(has_13f_data):
    from utils.agent_tools import search_securities
    if not has_13f_data:
        pytest.skip("no 13F data")
    out = search_securities("NVIDIA", limit=10)
    assert "NVIDIA" in out.upper()


def test_13_get_popular_securities(has_13f_data):
    from utils.agent_tools import get_popular_securities
    if not has_13f_data:
        pytest.skip("no 13F data")
    out = get_popular_securities(top_n=10)
    assert "most popular securities" in out.lower()


def test_14_get_fund_concentration(has_13f_data):
    from utils.agent_tools import get_fund_concentration
    if not has_13f_data:
        pytest.skip("no 13F data")
    out = get_fund_concentration(top_n=5)
    assert "funds by portfolio value" in out.lower()


def test_15_get_recent_activist_filings(has_activist_data):
    from utils.agent_tools import get_recent_activist_filings
    if not has_activist_data:
        pytest.skip("no activist data")
    out = get_recent_activist_filings(days=30, limit=10, activist_only=False)
    assert "SCHEDULE" in out
    assert "Date" in out


def test_16_search_activist_filings(has_activist_data):
    from utils.agent_tools import search_activist_filings
    if not has_activist_data:
        pytest.skip("no activist data")
    # Try a very generic token that should hit many filers.
    out = search_activist_filings("LLC", limit=5)
    assert "LLC" in out.upper()


def test_17_ask_f13_docs(has_rag_data):
    from utils.agent_tools import ask_f13_docs
    if not has_rag_data:
        pytest.skip("RAG not ingested")
    out = ask_f13_docs("What does INVESTMENTDISCRETION mean?")
    assert "F13" in out or "13F" in out.upper() or "INVESTMENTDISCRETION" in out.upper()


def test_18_tool_error_handling_returns_string():
    """Tools must never raise to the caller — they must return a string."""
    from utils.agent_tools import get_fund_holdings
    out = get_fund_holdings("__definitely_not_a_real_fund__xyzzy__", limit=5)
    assert isinstance(out, str)
    assert len(out) > 0
