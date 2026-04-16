"""End-to-end regression tests for the 5 left-nav shortcuts.

Each shortcut is a pre-canned prompt wired into ``web_app.SHORTCUTS``. When
the user clicks the button the text is fed into the chat input; the agent
must route it to the correct tool and stream back a markdown answer with
specific content.

These are live LLM tests — they hit xAI Grok — so they're skipped when
``XAI_API_KEY`` is absent. They're the highest-value regression guard
because they cover the wiring AND the prompt engineering AND the tool
implementations in one pass.
"""

from __future__ import annotations

import asyncio
import os
from typing import Iterable

import pytest


def _api_available() -> bool:
    return bool(os.getenv("XAI_API_KEY"))


def _prompt_for(key: str) -> str:
    from web_app import SHORTCUTS
    for sc in SHORTCUTS:
        if sc["key"] == key:
            return sc["prompt"]
    raise KeyError(key)


async def _run(prompt: str) -> tuple[list[str], str]:
    """Drive the agent with `prompt` and capture tools + streamed answer."""
    from langchain_core.messages import HumanMessage
    from utils.agent import build_agent

    agent = build_agent()
    tools_called: list[str] = []
    response = ""
    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=prompt)]},
        version="v2",
    ):
        k = event.get("event")
        if k == "on_tool_start":
            tools_called.append(event.get("name", ""))
        elif k == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                response += chunk.content
    return tools_called, response


def _assert_markdown_table(response: str, *, min_rows: int = 5):
    """A markdown table has | separators and enough pipe-bearing lines."""
    pipe_lines = [ln for ln in response.splitlines() if ln.count("|") >= 3]
    assert len(pipe_lines) >= min_rows + 2, (
        f"expected ≥ {min_rows + 2} table lines (header + separator + rows), "
        f"got {len(pipe_lines)}. Response: {response[:500]}"
    )


def _assert_any_tool(tools_called: Iterable[str], expected: Iterable[str]):
    expected_set = set(expected)
    called_set = set(tools_called)
    assert expected_set & called_set, (
        f"no expected tool was called. expected any of {expected_set}, "
        f"got {called_set}"
    )


# ---------------------------------------------------------------------------
# SHORTCUT 1 — Activist Filings
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_49_shortcut_activist_filings(has_activist_data):
    if not _api_available():
        pytest.skip("XAI_API_KEY not set")
    if not has_activist_data:
        pytest.skip("no activist data")
    tools, response = asyncio.run(_run(_prompt_for("activist")))
    _assert_any_tool(tools, {"get_recent_activist_filings", "search_activist_filings"})
    _assert_markdown_table(response, min_rows=10)
    # Should mention SCHEDULE 13D in the response (directly or in rows)
    assert "SCHEDULE 13D" in response or "13D" in response, \
        f"expected 13D references in response. Got: {response[:500]}"


# ---------------------------------------------------------------------------
# SHORTCUT 2 — Top Holdings (Bridgewater)
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_50_shortcut_top_holdings(has_13f_data):
    if not _api_available():
        pytest.skip("XAI_API_KEY not set")
    if not has_13f_data:
        pytest.skip("no 13F data")
    tools, response = asyncio.run(_run(_prompt_for("holdings")))
    _assert_any_tool(tools, {"get_fund_holdings", "search_funds"})
    _assert_markdown_table(response, min_rows=10)
    assert "bridgewater" in response.lower(), \
        f"expected Bridgewater in response. Got: {response[:500]}"
    # Portfolio % column was requested
    assert "%" in response


# ---------------------------------------------------------------------------
# SHORTCUT 3 — Popular Securities
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_51_shortcut_popular_securities(has_13f_data):
    if not _api_available():
        pytest.skip("XAI_API_KEY not set")
    if not has_13f_data:
        pytest.skip("no 13F data")
    tools, response = asyncio.run(_run(_prompt_for("popular")))
    _assert_any_tool(tools, {"get_popular_securities"})
    _assert_markdown_table(response, min_rows=10)
    # Should include fund count column or language
    assert "fund" in response.lower() or "count" in response.lower()


# ---------------------------------------------------------------------------
# SHORTCUT 4 — Top Funds by AUM
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_52_shortcut_top_funds(has_13f_data):
    if not _api_available():
        pytest.skip("XAI_API_KEY not set")
    if not has_13f_data:
        pytest.skip("no 13F data")
    tools, response = asyncio.run(_run(_prompt_for("top-funds")))
    _assert_any_tool(tools, {"get_top_funds", "get_fund_concentration"})
    _assert_markdown_table(response, min_rows=10)
    # Large-T / -B / -M money strings from the tool formatter
    assert any(suffix in response for suffix in ("$", "B", "T", "M"))


# ---------------------------------------------------------------------------
# SHORTCUT 5 — Security Types
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_53_shortcut_security_types(has_13f_data):
    if not _api_available():
        pytest.skip("XAI_API_KEY not set")
    if not has_13f_data:
        pytest.skip("no 13F data")
    tools, response = asyncio.run(_run(_prompt_for("types")))
    _assert_any_tool(tools, {"get_security_type_distribution"})
    _assert_markdown_table(response, min_rows=5)
    # Common equity label that will appear in the breakdown
    assert "COM" in response or "common" in response.lower()


# ---------------------------------------------------------------------------
# Unit-level guards — catch breakage without the LLM roundtrip
# ---------------------------------------------------------------------------

def test_54_all_shortcut_keys_unique():
    from web_app import SHORTCUTS
    keys = [sc["key"] for sc in SHORTCUTS]
    assert len(keys) == len(set(keys)), f"duplicate shortcut keys: {keys}"


def test_55_each_shortcut_has_required_fields():
    from web_app import SHORTCUTS
    for sc in SHORTCUTS:
        assert sc["key"] and isinstance(sc["key"], str)
        assert sc["label"] and isinstance(sc["label"], str)
        assert sc["desc"] and isinstance(sc["desc"], str)
        assert sc["prompt"] and isinstance(sc["prompt"], str)
        assert len(sc["prompt"]) >= 20, "prompts must be descriptive"


def test_56_security_type_tool_directly(has_13f_data):
    """Unit-level check — the underlying tool function works even if the
    agent test is skipped for lack of an API key."""
    from utils.agent_tools import get_security_type_distribution
    if not has_13f_data:
        pytest.skip("no 13F data")
    out = get_security_type_distribution(limit=10)
    assert "security types" in out.lower()
    assert "|" in out  # markdown table


def test_57_security_type_tool_percentages_sum_plausibly(has_13f_data):
    """Sanity check — percentages in the output should be plausible (each
    between 0 and 100)."""
    import re
    from utils.agent_tools import get_security_type_distribution
    if not has_13f_data:
        pytest.skip("no 13F data")
    out = get_security_type_distribution(limit=15)
    pcts = [float(x) for x in re.findall(r"(\d+\.\d)%", out)]
    assert pcts, "no percentages found in output"
    assert all(0 <= p <= 100 for p in pcts), f"bad pcts: {pcts}"


def test_58_agent_registers_security_type_tool():
    from utils.agent import TOOLS
    names = {t.name for t in TOOLS}
    assert "get_security_type_distribution" in names
