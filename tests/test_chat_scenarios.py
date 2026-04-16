"""End-to-end chat scenario tests.

These simulate a user typing a question into the AG-UI chat. They drive the
same LangGraph agent the WebSocket handler uses via `astream_events(v2)`,
collect which tools the agent chose, and verify the final markdown answer.

Skipped when XAI_API_KEY is absent or when the relevant DB tables are empty.
"""

from __future__ import annotations

import asyncio
import os

import pytest


def _api_available() -> bool:
    return bool(os.getenv("XAI_API_KEY"))


async def _run_chat(message: str) -> tuple[list[str], str]:
    """Send `message` to the agent and collect tool calls + streamed text."""
    from langchain_core.messages import HumanMessage
    from utils.agent import build_agent

    agent = build_agent()
    tools_called: list[str] = []
    response = ""
    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=message)]},
        version="v2",
    ):
        kind = event.get("event")
        if kind == "on_tool_start":
            tools_called.append(event.get("name", ""))
        elif kind == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                response += chunk.content
    return tools_called, response


@pytest.mark.slow
def test_43_chat_laurion_capital_performance(has_13f_data):
    """'What is the performance of Laurion Capital?' — should resolve the
    fund and answer with its holdings/portfolio profile."""
    if not _api_available():
        pytest.skip("XAI_API_KEY not set")
    if not has_13f_data:
        pytest.skip("no 13F data")
    tools_called, response = asyncio.run(
        _run_chat("What is the performance of Laurion Capital?")
    )
    # Should have called a fund lookup tool (search_funds or get_fund_holdings)
    assert any(t in tools_called for t in
               ("search_funds", "get_fund_holdings", "get_fund_concentration")), \
           f"expected a fund tool call, got {tools_called}"
    # Response should mention Laurion
    assert "Laurion" in response or "LAURION" in response.upper(), \
           f"response missing Laurion: {response[:200]}"


@pytest.mark.slow
def test_44_chat_situational_awareness_holdings(has_13f_data):
    """'What are the largest holdings of Situational Awareness?' — should
    call get_fund_holdings and return a markdown table of positions."""
    if not _api_available():
        pytest.skip("XAI_API_KEY not set")
    if not has_13f_data:
        pytest.skip("no 13F data")
    tools_called, response = asyncio.run(
        _run_chat("What are the largest holdings of Situational Awareness?")
    )
    assert "get_fund_holdings" in tools_called or "search_funds" in tools_called, \
           f"expected a fund-lookup tool, got {tools_called}"
    # Response should either list holdings (markdown table) or clearly
    # explain that the fund wasn't found.
    assert "Situational" in response or "not found" in response.lower() \
           or "no fund" in response.lower() or "|" in response, \
           f"unexpected response: {response[:300]}"


@pytest.mark.slow
def test_45_chat_top_funds_by_aum(has_13f_data):
    """'Who are the top 5 hedge funds by AUM?' — must call get_top_funds."""
    if not _api_available():
        pytest.skip("XAI_API_KEY not set")
    if not has_13f_data:
        pytest.skip("no 13F data")
    tools_called, response = asyncio.run(
        _run_chat("Who are the top 5 hedge funds by AUM?")
    )
    assert "get_top_funds" in tools_called, \
           f"expected get_top_funds, got {tools_called}"
    # Markdown table
    assert "|" in response


@pytest.mark.slow
def test_46_chat_who_owns_nvidia(has_13f_data):
    """'Which funds hold NVIDIA?' — must call search_securities."""
    if not _api_available():
        pytest.skip("XAI_API_KEY not set")
    if not has_13f_data:
        pytest.skip("no 13F data")
    tools_called, response = asyncio.run(_run_chat("Which hedge funds hold NVIDIA?"))
    assert "search_securities" in tools_called, \
           f"expected search_securities, got {tools_called}"
    assert "NVIDIA" in response.upper()


@pytest.mark.slow
def test_47_chat_recent_activist_filings(has_activist_data):
    """'What 13D filings happened this week?' — must call the activist tool."""
    if not _api_available():
        pytest.skip("XAI_API_KEY not set")
    if not has_activist_data:
        pytest.skip("no activist data")
    tools_called, response = asyncio.run(
        _run_chat("What 13D activist filings have been filed in the last 7 days? Show 5.")
    )
    assert "get_recent_activist_filings" in tools_called, \
           f"expected activist tool, got {tools_called}"
    assert "SCHEDULE 13D" in response or "13D" in response


@pytest.mark.slow
def test_48_chat_search_activist_by_filer(has_activist_data):
    """Chat should route 'has Icahn filed anything?' to search_activist_filings."""
    if not _api_available():
        pytest.skip("XAI_API_KEY not set")
    if not has_activist_data:
        pytest.skip("no activist data")
    tools_called, response = asyncio.run(
        _run_chat("Has Elliott Investment Management filed any 13D recently?")
    )
    # Could be either tool — both are valid routes
    assert any(t in tools_called for t in
               ("search_activist_filings", "get_recent_activist_filings")), \
           f"expected an activist tool, got {tools_called}"
    assert len(response) > 20
