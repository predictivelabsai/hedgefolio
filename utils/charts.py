"""Plotly figure builders for Hedgefolio.

Returns Plotly figure JSON (layout + traces) that the browser renders client-side
via Plotly.js. Reuses the same data-access helpers as the streamlit pages.
Missing-table / empty-dataset errors bubble up as `None` so the UI can show a
friendly "no data yet" panel instead of a 500.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import pandas as pd
import plotly.express as px

from utils.db_queries import (
    get_fund_concentration,
    get_fund_holdings,
    get_popular_securities,
    get_security_type_distribution,
)

logger = logging.getLogger(__name__)


def _fig_json(fig) -> str:
    return json.dumps(fig.to_plotly_json(), default=str)


def _safe(fn):
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            logger.warning("chart builder failed (%s): %s", fn.__name__, e)
            return None
    wrapper.__name__ = fn.__name__
    return wrapper


@_safe
def portfolio_treemap_json(fund_name: str, limit: int = 25) -> Optional[str]:
    holdings = get_fund_holdings(fund_name, limit=2000)
    if holdings.empty:
        return None
    top = (
        holdings.groupby(["NAMEOFISSUER", "TITLEOFCLASS"])
        .agg({"VALUE": "sum", "SSHPRNAMT": "sum"})
        .reset_index()
        .sort_values("VALUE", ascending=False)
        .head(limit)
    )
    total = top["VALUE"].sum() or 1
    top["portfolio_pct"] = top["VALUE"] / total * 100
    top["label"] = top.apply(
        lambda r: f"{r['NAMEOFISSUER'][:30]}<br>{r['portfolio_pct']:.1f}%", axis=1
    )
    fig = px.treemap(
        top,
        path=["TITLEOFCLASS", "label"],
        values="VALUE",
        color="portfolio_pct",
        color_continuous_scale="Blues",
        title=f"Portfolio Treemap — {fund_name} (Top {limit})",
    )
    fig.update_layout(
        height=620,
        margin=dict(t=50, l=10, r=10, b=10),
        coloraxis_colorbar=dict(title="Portfolio %", thickness=15, len=0.5),
    )
    fig.update_traces(textfont_size=10, textposition="middle center", texttemplate="%{label}")
    return _fig_json(fig)


@_safe
def popular_securities_bar_json(top_n: int = 15) -> Optional[str]:
    df = get_popular_securities(top_n)
    if df.empty:
        return None
    df = df.sort_values("Total Value")
    fig = px.bar(
        df,
        x="Total Value",
        y="Security",
        orientation="h",
        title=f"Top {top_n} Securities Across All Funds",
        color="Fund Count",
        color_continuous_scale="Viridis",
        labels={"Total Value": "Total Value ($)", "Security": "Security Name"},
    )
    fig.update_layout(height=600, margin=dict(t=50, l=10, r=10, b=10))
    return _fig_json(fig)


@_safe
def fund_concentration_pie_json(top_n: int = 10) -> Optional[str]:
    df = get_fund_concentration(top_n)
    if df.empty or df["TABLEVALUETOTAL"].sum() <= 0:
        return None
    fig = px.pie(
        df,
        values="TABLEVALUETOTAL",
        names="FILINGMANAGER_NAME",
        title=f"Top {top_n} Funds — Market Share",
        hole=0.3,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(height=600, margin=dict(t=50, l=10, r=10, b=10))
    return _fig_json(fig)


@_safe
def security_type_bar_json(limit: int = 20) -> Optional[str]:
    df = get_security_type_distribution()
    if df.empty:
        return None
    df = df.head(limit).sort_values("Count")
    fig = px.bar(
        df,
        x="Count",
        y="Type",
        orientation="h",
        title="Distribution of Security Types",
        color="Count",
        color_continuous_scale="Teal",
    )
    fig.update_layout(height=600, margin=dict(t=50, l=10, r=10, b=10))
    return _fig_json(fig)
