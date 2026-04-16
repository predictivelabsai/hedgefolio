"""End-to-end agent integration tests.

These hit the xAI API so they're skipped when XAI_API_KEY isn't set.
They're also marked "slow" since a real streaming run takes 5-15 seconds.
"""

from __future__ import annotations

import asyncio
import os

import pytest


def _api_available() -> bool:
    return bool(os.getenv("XAI_API_KEY"))


def test_40_agent_builds_without_error():
    if not _api_available():
        pytest.skip("XAI_API_KEY not set")
    from utils.agent import build_agent
    agent = build_agent()
    # CompiledStateGraph has astream_events
    assert hasattr(agent, "astream_events")


def test_41_agent_registers_all_tools():
    if not _api_available():
        pytest.skip("XAI_API_KEY not set")
    from utils.agent import TOOLS
    names = {t.name for t in TOOLS}
    expected = {
        "get_market_overview", "search_funds", "get_top_funds",
        "get_fund_holdings", "search_securities", "get_popular_securities",
        "get_fund_concentration", "ask_f13_docs",
        "get_recent_activist_filings", "search_activist_filings",
    }
    missing = expected - names
    assert not missing, f"missing tools: {missing}"


@pytest.mark.slow
def test_42_agent_calls_rag_tool(has_rag_data):
    """Ask a definitional question that should route to `ask_f13_docs`."""
    if not _api_available():
        pytest.skip("XAI_API_KEY not set")
    if not has_rag_data:
        pytest.skip("RAG not ingested")
    from utils.agent import build_agent
    from langchain_core.messages import HumanMessage

    async def run():
        agent = build_agent()
        tools_called: list[str] = []
        response = ""
        async for event in agent.astream_events(
            {"messages": [HumanMessage(content="What is INVESTMENTDISCRETION in a 13F filing?")]},
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

    tools_called, response = asyncio.run(run())
    assert "ask_f13_docs" in tools_called
    assert len(response) > 20
