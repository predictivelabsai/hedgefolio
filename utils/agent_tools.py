"""LangGraph tool functions for the Hedgefolio AG-UI agent.

Each function returns a markdown string (tables, bullets) ready for display.
They wrap the existing `utils.db_queries` helpers so the streamlit pages and
the agent share a single data-access layer.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _fmt_money(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if abs(v) >= 1e12:
        return f"${v / 1e12:.2f}T"
    if abs(v) >= 1e9:
        return f"${v / 1e9:.2f}B"
    if abs(v) >= 1e6:
        return f"${v / 1e6:.2f}M"
    if abs(v) >= 1e3:
        return f"${v / 1e3:.1f}K"
    return f"${v:,.0f}"


# ---------------------------------------------------------------------------
# Summary / market overview
# ---------------------------------------------------------------------------

def get_market_overview() -> str:
    """Return an overview of the entire 13F dataset: funds, holdings, AUM, unique securities."""
    try:
        from utils.db_queries import get_summary_stats
        stats = get_summary_stats()
        return (
            "**Hedge Fund Market Overview**\n\n"
            "| Metric | Value |\n"
            "|--------|-------|\n"
            f"| Total Funds | {stats['total_funds']:,} |\n"
            f"| Total Holdings | {stats['total_holdings']:,} |\n"
            f"| Total AUM | {_fmt_money(stats['total_aum'])} |\n"
            f"| Unique Securities | {stats['unique_securities']:,} |\n"
        )
    except Exception as e:
        return f"Error fetching market overview: {e}"


# ---------------------------------------------------------------------------
# Fund lookups
# ---------------------------------------------------------------------------

def search_funds(query: str, limit: int = 15) -> str:
    """Search hedge funds whose name contains the query. Returns a markdown table."""
    try:
        from utils.db_queries import search_funds as _search
        rows = _search(query, limit=limit)
        if not rows:
            return f"No funds found matching '{query}'."
        md = "| Fund | Portfolio Value | Positions | Accession |\n"
        md += "|------|-----------------|-----------|-----------|\n"
        for r in rows:
            md += (
                f"| {r['name']} | {_fmt_money(r['portfolio_value'])} | "
                f"{r['positions'] or '—'} | `{r['accession_number']}` |\n"
            )
        return md
    except Exception as e:
        return f"Error searching funds: {e}"


def get_top_funds(top_n: int = 20) -> str:
    """Return the top N funds by portfolio value as a markdown table."""
    try:
        from utils.db_queries import get_top_funds as _top
        df = _top(top_n)
        if df.empty:
            return "No funds found."
        md = "| # | Fund | Portfolio Value | Positions |\n"
        md += "|---|------|-----------------|-----------|\n"
        for i, (_, r) in enumerate(df.iterrows(), 1):
            md += (
                f"| {i} | {r['Fund Name']} | "
                f"{_fmt_money(r['Portfolio Value'])} | "
                f"{int(r['Total Positions']) if r['Total Positions'] else '—'} |\n"
            )
        return md
    except Exception as e:
        return f"Error fetching top funds: {e}"


def get_fund_holdings(fund_name: str, limit: int = 20) -> str:
    """Return top holdings for a named fund. Partial matches are resolved to the closest fund."""
    try:
        from utils.db_queries import get_fund_holdings as _holdings
        from utils.db_queries import get_fund_names
        # Resolve fuzzy match
        names = [n for n in get_fund_names() if fund_name.upper() in (n or "").upper()]
        resolved = names[0] if names else fund_name
        df = _holdings(resolved, limit=limit)
        if df.empty:
            return f"No holdings found for fund '{fund_name}' (resolved as '{resolved}')."
        md = f"**Top {len(df)} holdings for {resolved}**\n\n"
        md += "| # | Security | Type | Value | Shares | Portfolio % |\n"
        md += "|---|----------|------|-------|--------|-------------|\n"
        for i, (_, r) in enumerate(df.iterrows(), 1):
            md += (
                f"| {i} | {r['NAMEOFISSUER']} | {r['TITLEOFCLASS']} | "
                f"{_fmt_money(r['VALUE'])} | "
                f"{int(r['SSHPRNAMT']):,} | "
                f"{float(r.get('portfolio_pct', 0)):.2f}% |\n"
            )
        return md
    except Exception as e:
        return f"Error fetching fund holdings: {e}"


# ---------------------------------------------------------------------------
# Security lookups
# ---------------------------------------------------------------------------

def search_securities(query: str, limit: int = 15) -> str:
    """Search which funds hold a security by name/ticker and return aggregated positions."""
    try:
        from utils.db_queries import search_securities as _search
        sec_df, fund_df = _search(query, limit=limit)
        if sec_df.empty:
            return f"No securities found matching '{query}'."
        md = f"**Securities matching '{query}'**\n\n"
        md += "| Security | Type | Total Value | Total Shares | Fund Count |\n"
        md += "|----------|------|-------------|--------------|------------|\n"
        for _, r in sec_df.iterrows():
            md += (
                f"| {r['Security']} | {r['Type']} | "
                f"{_fmt_money(r['Total Value'])} | "
                f"{int(r['Total Shares']):,} | "
                f"{int(r['Fund Count'])} |\n"
            )
        if not fund_df.empty:
            md += "\n**Funds holding this security**\n\n"
            md += "| Fund | Position Value | Shares Held |\n"
            md += "|------|----------------|-------------|\n"
            for _, r in fund_df.head(limit).iterrows():
                md += (
                    f"| {r['Fund Name']} | "
                    f"{_fmt_money(r['Position Value'])} | "
                    f"{int(r['Shares Held']):,} |\n"
                )
        return md
    except Exception as e:
        return f"Error searching securities: {e}"


def get_popular_securities(top_n: int = 20) -> str:
    """Return the most popular securities across all funds, ranked by total value."""
    try:
        from utils.db_queries import get_popular_securities as _pop
        df = _pop(top_n)
        if df.empty:
            return "No securities found."
        md = f"**Top {len(df)} most popular securities**\n\n"
        md += "| # | Security | Type | Total Value | Fund Count |\n"
        md += "|---|----------|------|-------------|------------|\n"
        for i, (_, r) in enumerate(df.iterrows(), 1):
            md += (
                f"| {i} | {r['Security']} | {r['Type']} | "
                f"{_fmt_money(r['Total Value'])} | "
                f"{int(r['Fund Count'])} |\n"
            )
        return md
    except Exception as e:
        return f"Error fetching popular securities: {e}"


def get_fund_concentration(top_n: int = 15) -> str:
    """Return the largest funds by portfolio value to show market concentration."""
    try:
        from utils.db_queries import get_fund_concentration as _conc
        df = _conc(top_n)
        if df.empty:
            return "No fund concentration data."
        md = f"**Top {len(df)} funds by portfolio value**\n\n"
        md += "| # | Fund | Portfolio Value | Positions |\n"
        md += "|---|------|-----------------|-----------|\n"
        for i, (_, r) in enumerate(df.iterrows(), 1):
            val = r["TABLEVALUETOTAL"]
            positions = r["TABLEENTRYTOTAL"]
            md += (
                f"| {i} | {r['FILINGMANAGER_NAME']} | "
                f"{_fmt_money(val)} | "
                f"{int(positions) if positions else '—'} |\n"
            )
        return md
    except Exception as e:
        return f"Error fetching fund concentration: {e}"


# ---------------------------------------------------------------------------
# Activist filings (Schedule 13D / 13G)
# ---------------------------------------------------------------------------

def _fmt_filings(rows: list, include_subject: bool = True) -> str:
    if not rows:
        return "No matching filings."
    hdr = "| Date | Form | Filer"
    if include_subject:
        hdr += " | Subject"
    hdr += " | Link |\n"
    sep = "|------|------|-------"
    if include_subject:
        sep += "|---------"
    sep += "|------|\n"
    md = hdr + sep
    for r in rows:
        date_s = r["filing_date"].isoformat() if r["filing_date"] else ""
        filer = (r["filer_name"] or "?")[:50]
        subject = (r["subject_name"] or "") if include_subject else ""
        subject = subject[:50]
        link = f"[view]({r['filing_url']})" if r["filing_url"] else ""
        if include_subject:
            md += f"| {date_s} | {r['form_type']} | {filer} | {subject} | {link} |\n"
        else:
            md += f"| {date_s} | {r['form_type']} | {filer} | {link} |\n"
    return md


def get_recent_activist_filings(days: int = 14, limit: int = 25,
                                activist_only: bool = True) -> str:
    """Return the most recent Schedule 13D / 13G filings.

    Args:
        days: How many calendar days back to include.
        limit: Maximum number of rows to return.
        activist_only: If True, only 13D / 13D/A (classic "activist"); False
            also includes 13G / 13G/A (passive >5% holders).
    """
    try:
        from utils.activist import activist_stats, recent_filings
        rows = recent_filings(limit=limit, activist_only=activist_only, days=days)
        stats = activist_stats(days=days)
        header = (
            f"**Recent activist/beneficial-ownership filings** "
            f"(last {days} days, "
            f"13D: {stats['cnt_13d']} + amendments {stats['cnt_13d_a']}, "
            f"13G: {stats['cnt_13g']} + amendments {stats['cnt_13g_a']}, "
            f"{stats['unique_filers']} unique filers)\n\n"
        )
        return header + _fmt_filings(rows)
    except Exception as e:
        return f"Error fetching activist filings: {e}"


def search_activist_filings(query: str, limit: int = 25) -> str:
    """Search activist / beneficial-ownership filings by filer or subject name.

    Args:
        query: Partial name (filer or subject). Example: 'ICAHN', 'ELLIOTT',
            'Apple', 'NVIDIA'.
    """
    try:
        from utils.activist import search_activist
        rows = search_activist(query, limit=limit)
        if not rows:
            return f"No activist filings match '{query}'."
        return f"**Activist filings matching '{query}'**\n\n" + _fmt_filings(rows)
    except Exception as e:
        return f"Error searching activist filings: {e}"


# ---------------------------------------------------------------------------
# F13 RAG
# ---------------------------------------------------------------------------

def ask_f13_docs(question: str, limit: int = 4) -> str:
    """Search the F13 filings knowledge base and return relevant passages."""
    try:
        from utils.rag import search_f13_docs
        return search_f13_docs(question, limit=limit)
    except Exception as e:
        return f"Error querying F13 docs: {e}"
