"""Build the Hedgefolio LangGraph agent backed by xAI Grok (OpenAI-compatible)."""

from __future__ import annotations

import os

from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from utils.agent_tools import (
    ask_f13_docs,
    get_fund_concentration,
    get_fund_holdings,
    get_market_overview,
    get_popular_securities,
    get_recent_activist_filings,
    get_top_funds,
    search_activist_filings,
    search_funds,
    search_securities,
)


SYSTEM_PROMPT = (
    "You are Hedgefolio, an AI assistant for hedge-fund-level equity research. "
    "You have tools backed by a live SEC 13F filings database covering hundreds of "
    "funds and hundreds of thousands of individual holdings, plus a RAG knowledge "
    "base of the official F13 filing format. "
    "Always use your tools when the user asks about a specific fund, a specific "
    "security, market-wide concentration, or the 13F schema. Never invent holdings "
    "or dollar amounts — retrieve them via tools. "
    "Respond in concise markdown with tables where appropriate. "
    "When the user asks a definitional question about 13F filings (fields, "
    "methodology, deadlines), call `ask_f13_docs`. "
    "When the user asks about a fund's portfolio, call `get_fund_holdings` with "
    "the fund name. When they ask 'who owns X' / 'which funds hold X', call "
    "`search_securities` with the security or ticker. For leaderboards, use "
    "`get_top_funds` or `get_popular_securities`."
)


TOOLS = [
    StructuredTool.from_function(
        get_market_overview,
        name="get_market_overview",
        description="Return an overview of the 13F dataset: total funds, total holdings, total AUM, and unique securities.",
    ),
    StructuredTool.from_function(
        search_funds,
        name="search_funds",
        description="Search hedge funds whose name matches a query. Returns fund name, AUM, and position count.",
    ),
    StructuredTool.from_function(
        get_top_funds,
        name="get_top_funds",
        description="Get the top N hedge funds by portfolio value. Call with top_n=<int>, e.g. 20.",
    ),
    StructuredTool.from_function(
        get_fund_holdings,
        name="get_fund_holdings",
        description=(
            "Return the top holdings for a named fund. Pass the fund name (partial match "
            "works, e.g. 'Bridgewater'). limit defaults to 20."
        ),
    ),
    StructuredTool.from_function(
        search_securities,
        name="search_securities",
        description=(
            "Search for a security by name or ticker and return the aggregate position "
            "across all funds plus the list of funds holding it."
        ),
    ),
    StructuredTool.from_function(
        get_popular_securities,
        name="get_popular_securities",
        description="Return the most popular securities across all funds, ranked by total value.",
    ),
    StructuredTool.from_function(
        get_fund_concentration,
        name="get_fund_concentration",
        description="Return the largest funds by portfolio value to illustrate market concentration.",
    ),
    StructuredTool.from_function(
        ask_f13_docs,
        name="ask_f13_docs",
        description=(
            "Query the F13 filings knowledge base (SEC Form 13F readme + schema) for "
            "definitions, field meanings, deadlines, and methodology. Pass the user's "
            "question verbatim."
        ),
    ),
    StructuredTool.from_function(
        get_recent_activist_filings,
        name="get_recent_activist_filings",
        description=(
            "Return the most recent Schedule 13D / 13G beneficial-ownership filings "
            "from SEC EDGAR. 13D = activist investor intending to influence management; "
            "13G = passive >5% stakeholder. Args: days=14, limit=25, activist_only=True. "
            "Updated daily — use this to see what activists are accumulating right now."
        ),
    ),
    StructuredTool.from_function(
        search_activist_filings,
        name="search_activist_filings",
        description=(
            "Search Schedule 13D/G filings by filer or subject company name (partial "
            "match). Use when the user asks 'what has Icahn / Elliott / Carl filed?' "
            "or 'who filed a 13D on <company>?'."
        ),
    ),
]


def build_agent():
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "XAI_API_KEY is not set. Add it to .env to enable the chat agent."
        )
    model_name = os.getenv("GROK_MODEL", "grok-4-fast-reasoning")
    llm = ChatOpenAI(
        api_key=api_key,
        base_url="https://api.x.ai/v1",
        model=model_name,
        temperature=0.3,
        streaming=True,
    )
    return create_react_agent(model=llm, tools=TOOLS, prompt=SYSTEM_PROMPT)
