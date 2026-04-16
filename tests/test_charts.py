"""Plotly chart JSON builders must produce valid figure objects."""

from __future__ import annotations

import json

import pytest


def _assert_fig(fig_json: str):
    assert isinstance(fig_json, str)
    payload = json.loads(fig_json)
    assert "data" in payload
    assert isinstance(payload["data"], list)
    assert "layout" in payload


def test_19_portfolio_treemap(has_13f_data):
    from utils.charts import portfolio_treemap_json
    if not has_13f_data:
        pytest.skip("no 13F data")
    from utils.db_queries import get_fund_names
    names = get_fund_names()
    # Find something that has holdings — use the first fund alphabetically.
    pick = names[0] if names else "BRIDGEWATER ASSOCIATES, LP"
    out = portfolio_treemap_json(pick, limit=10)
    # Some small funds may return None — just assert the function doesn't blow up
    # and any non-None output parses.
    if out is not None:
        _assert_fig(out)


def test_20_popular_securities_bar(has_13f_data):
    from utils.charts import popular_securities_bar_json
    if not has_13f_data:
        pytest.skip("no 13F data")
    out = popular_securities_bar_json(top_n=10)
    assert out is not None
    _assert_fig(out)


def test_21_fund_concentration_pie(has_13f_data):
    from utils.charts import fund_concentration_pie_json
    if not has_13f_data:
        pytest.skip("no 13F data")
    out = fund_concentration_pie_json(top_n=5)
    assert out is not None
    _assert_fig(out)


def test_22_security_type_bar(has_13f_data):
    from utils.charts import security_type_bar_json
    if not has_13f_data:
        pytest.skip("no 13F data")
    out = security_type_bar_json()
    assert out is not None
    _assert_fig(out)
