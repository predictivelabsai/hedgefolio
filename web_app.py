"""Hedgefolio — FastHTML 3-pane agentic chat UI.

Layout:
  Left pane:    Brand + new chat + recent conversations + charts navigation
                + email subscribe form.
  Center pane:  Either the AG-UI chat (default) or an interactive Plotly chart
                page loaded via HTMX.
  Right pane:   Thinking trace / tool-call stream.

Run:
  python web_app.py                # listens on PORT (default 5011)
  uvicorn web_app:app --port 5011  # alternative
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid as _uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.absolute()))

from dotenv import load_dotenv

load_dotenv()

from fasthtml.common import (
    A,
    Button,
    Div,
    Form,
    H1,
    H2,
    H3,
    H4,
    Hidden,
    Input,
    Label,
    NotStr,
    Option,
    P,
    Script,
    Select,
    Span,
    Style,
    Title,
    fast_app,
    serve,
)

from utils.agent import build_agent
from utils.agui import list_conversations, setup_agui
from utils.charts import (
    fund_concentration_pie_json,
    popular_securities_bar_json,
    portfolio_treemap_json,
    security_type_bar_json,
)
from utils.db_queries import (
    check_database_connection,
    get_fund_names,
    get_subscriber_count,
    get_summary_stats,
    subscribe_user,
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LangGraph agent
# ---------------------------------------------------------------------------

try:
    langgraph_agent = build_agent()
    logger.info("LangGraph agent initialized")
except Exception as exc:  # pragma: no cover
    langgraph_agent = None
    logger.error("Failed to build LangGraph agent: %s", exc)


# ---------------------------------------------------------------------------
# FastHTML app
# ---------------------------------------------------------------------------

app, rt = fast_app(
    exts="ws",
    secret_key=os.getenv("JWT_SECRET", os.urandom(32).hex()),
    hdrs=[
        Script(src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"),
        Script(src="https://cdn.plot.ly/plotly-2.35.2.min.js"),
    ],
)

if langgraph_agent is not None:
    agui = setup_agui(app, langgraph_agent)
else:
    agui = None


# ---------------------------------------------------------------------------
# Layout CSS — 3-pane grid
# ---------------------------------------------------------------------------

LAYOUT_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f8fafc;
  color: #1e293b;
  height: 100vh;
  overflow: hidden;
}

.app-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  height: 100vh;
  transition: grid-template-columns 0.3s ease;
}

.app-layout .right-pane { display: none; }
.app-layout.right-open { grid-template-columns: 260px 1fr 380px; }
.app-layout.right-open .right-pane { display: flex; }

.left-pane {
  background: #ffffff;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding: 1rem;
  gap: 1rem;
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #e2e8f0;
}

.brand {
  font-size: 1.25rem;
  font-weight: 700;
  color: #1e293b;
  text-decoration: none;
}
.brand:hover { color: #3b82f6; }

.chat-badge {
  font-size: 0.6rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  background: #3b82f6;
  color: white;
  padding: 0.15rem 0.4rem;
  border-radius: 0.25rem;
}

.new-chat-btn {
  width: 100%;
  padding: 0.5rem;
  background: transparent;
  border: 1px dashed #cbd5e1;
  border-radius: 0.5rem;
  color: #3b82f6;
  font-family: inherit;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s;
}
.new-chat-btn:hover { background: #eff6ff; border-color: #93c5fd; }

.sidebar-section { display: flex; flex-direction: column; gap: 0.3rem; }
.sidebar-section h4 {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: #64748b;
  margin-bottom: 0.25rem;
}

.sidebar-section a, .sidebar-nav a {
  color: #475569;
  text-decoration: none;
  font-size: 0.85rem;
  padding: 0.4rem 0.6rem;
  border-radius: 0.375rem;
  transition: all 0.15s;
  cursor: pointer;
  display: block;
}
.sidebar-section a:hover, .sidebar-nav a:hover {
  background: #f1f5f9;
  color: #1e293b;
}
.sidebar-section a.active, .sidebar-nav a.active {
  background: #eff6ff;
  color: #3b82f6;
  font-weight: 600;
}

.conv-section {
  min-height: 120px;
  max-height: 30vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}
.conv-item {
  display: block;
  font-size: 0.8rem;
  padding: 0.5rem 0.6rem;
  color: #475569;
  text-decoration: none;
  border-radius: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.conv-item:hover { background: #f1f5f9; color: #1e293b; }
.conv-active { background: #eff6ff; border-left: 2px solid #3b82f6; color: #1e293b; }
.conv-empty { font-style: italic; color: #94a3b8; font-size: 0.75rem; padding: 0.5rem; }

.subscribe-form {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.75rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
}
.subscribe-form input {
  width: 100%;
  padding: 0.45rem 0.6rem;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 0.375rem;
  font-family: inherit;
  font-size: 0.8rem;
}
.subscribe-form input:focus { outline: none; border-color: #3b82f6; }
.subscribe-form button {
  padding: 0.45rem;
  background: #3b82f6;
  color: #fff;
  border: none;
  border-radius: 0.375rem;
  font-family: inherit;
  font-size: 0.8rem;
  cursor: pointer;
}
.subscribe-form button:hover { background: #2563eb; }
.subscribe-status { font-size: 0.75rem; min-height: 1rem; }
.subscribe-status.ok { color: #16a34a; }
.subscribe-status.err { color: #dc2626; }

.sidebar-footer {
  margin-top: auto;
  font-size: 0.7rem;
  color: #94a3b8;
  text-align: center;
  padding-top: 0.5rem;
  border-top: 1px solid #e2e8f0;
}

.center-pane {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f8fafc;
  overflow: hidden;
}

.center-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: #ffffff;
  border-bottom: 1px solid #e2e8f0;
  min-height: 3rem;
}
.center-header h2 {
  font-size: 0.95rem;
  font-weight: 600;
  color: #1e293b;
}

.toggle-trace-btn {
  padding: 0.3rem 0.7rem;
  background: transparent;
  color: #64748b;
  border: 1px solid #e2e8f0;
  border-radius: 0.375rem;
  font-family: inherit;
  font-size: 0.75rem;
  cursor: pointer;
}
.toggle-trace-btn:hover { background: #f1f5f9; color: #3b82f6; border-color: #3b82f6; }

.center-body {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.center-body > div {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
}
.center-chat .chat-container {
  height: 100%; flex: 1; border: none; border-radius: 0; background: #f8fafc;
  display: flex; flex-direction: column;
}
.center-chat .chat-messages { background: #f8fafc; flex: 1; }
.center-chat .chat-input { background: #f8fafc; border-top: 1px solid #e2e8f0; }
.center-chat .chat-input-form { background: #ffffff; border-color: #e2e8f0; }

.chart-page {
  padding: 1.25rem 1.5rem;
  overflow-y: auto;
  background: #f8fafc;
  flex: 1;
}
.chart-page h1 { font-size: 1.25rem; margin-bottom: 0.5rem; }
.chart-page .subtitle { color: #64748b; font-size: 0.85rem; margin-bottom: 1rem; }
.chart-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 0.75rem;
  padding: 1rem;
  margin-bottom: 1rem;
}
.chart-placeholder { min-height: 620px; }

.metric-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1rem;
}
.metric-tile {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 0.75rem;
  padding: 0.75rem 1rem;
}
.metric-tile .label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}
.metric-tile .value {
  font-size: 1.25rem;
  font-weight: 700;
  color: #1e293b;
  margin-top: 0.25rem;
}

.fund-picker {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.fund-picker select, .fund-picker input[type=search] {
  padding: 0.5rem 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  background: #fff;
  font-size: 0.85rem;
}
.fund-picker select { flex: 0 0 auto; }
.fund-picker button {
  padding: 0.5rem 0.9rem;
  background: #3b82f6;
  color: #fff;
  border: none;
  border-radius: 0.5rem;
  font-family: inherit;
  font-size: 0.85rem;
  cursor: pointer;
}
.fund-picker button:hover { background: #2563eb; }

.chart-page table { border: 1px solid #e2e8f0; border-radius: 0.5rem; }
.chart-page table th {
  background: #f1f5f9;
  color: #475569;
  text-align: left;
  font-weight: 600;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 0.5rem 0.6rem;
  border-bottom: 1px solid #e2e8f0;
}
.chart-page table td {
  padding: 0.45rem 0.6rem;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: top;
}
.chart-page table tbody tr:hover { background: #f8fafc; }
.chart-page table a { color: #3b82f6; text-decoration: none; font-family: ui-monospace,monospace; font-size: 0.75rem; }
.chart-page table a:hover { text-decoration: underline; }

.badge-red { display: inline-block; background: #fef2f2; color: #991b1b; padding: 0.15rem 0.5rem; border-radius: 0.75rem; font-size: 0.7rem; font-weight: 600; }
.badge-blue { display: inline-block; background: #dbeafe; color: #1e40af; padding: 0.15rem 0.5rem; border-radius: 0.75rem; font-size: 0.7rem; font-weight: 600; }

.right-pane {
  background: #ffffff;
  border-left: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.right-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #e2e8f0;
}
.right-header h3 { font-size: 0.85rem; font-weight: 600; color: #1e293b; }
.close-trace-btn {
  background: none; border: none; color: #64748b; cursor: pointer;
  font-size: 1rem; padding: 0.2rem; border-radius: 0.25rem;
}
.close-trace-btn:hover { color: #1e293b; background: #f1f5f9; }
.right-content {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
}

.trace-entry {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.5rem 0.75rem;
  margin-bottom: 0.5rem;
  border-left: 3px solid #e2e8f0;
  border-radius: 0 0.25rem 0.25rem 0;
  background: #f1f5f9;
  font-size: 0.8rem;
}
.trace-label { color: #94a3b8; font-weight: 500; }
.trace-detail { color: #64748b; font-size: 0.75rem; font-family: ui-monospace, monospace; word-break: break-all; }
.trace-run-start { border-left-color: #3b82f6; }
.trace-run-start .trace-label { color: #3b82f6; }
.trace-run-end { border-left-color: #16a34a; }
.trace-run-end .trace-label { color: #16a34a; }
.trace-tool-active { border-left-color: #d97706; }
.trace-tool-active .trace-label { color: #d97706; }
.trace-tool-done { border-left-color: #16a34a; }
.trace-tool-done .trace-label { color: #16a34a; }
.trace-error { border-left-color: #dc2626; }
.trace-error .trace-label { color: #dc2626; }
#trace-content { font-size: 0.8rem; color: #94a3b8; overflow-y: auto; flex: 1; }

@media (max-width: 900px) {
  .app-layout { grid-template-columns: 1fr !important; }
  .left-pane { display: none; }
  .right-pane { display: none; }
}
"""


LAYOUT_JS = """
function toggleRightPane() {
    var layout = document.querySelector('.app-layout');
    if (layout) layout.classList.toggle('right-open');
}
function clearTrace() {
    var tc = document.getElementById('trace-content');
    if (tc) tc.innerHTML = '<div style="color:#475569;font-style:italic">Tool calls and reasoning will appear here.</div>';
}
function renderPlotly(divId, figJson) {
    if (!window.Plotly) { console.error('Plotly not loaded'); return; }
    var target = document.getElementById(divId);
    if (!target || !figJson) return;
    try {
        var fig = typeof figJson === 'string' ? JSON.parse(figJson) : figJson;
        Plotly.newPlot(target, fig.data || [], fig.layout || {}, {responsive: true, displayModeBar: false});
    } catch (e) {
        target.innerHTML = '<div style="padding:2rem;color:#dc2626">Chart error: ' + e.message + '</div>';
    }
}
"""


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

NAV_LINKS = [
    ("chat",          "Chat",                "/"),
    ("activist",      "Activist Filings",    "/activist"),
    ("treemap",       "Portfolio Treemap",   "/charts/treemap"),
    ("popular",       "Popular Securities",  "/charts/popular"),
    ("concentration", "Fund Concentration",  "/charts/concentration"),
    ("types",         "Security Types",      "/charts/types"),
]


def _left_pane(session, active: str = "chat"):
    items = []
    for key, label, href in NAV_LINKS:
        cls = "active" if active == key else ""
        # HTMX swap the center-pane body only.
        items.append(
            A(
                label,
                href=href,
                cls=cls,
                hx_get=href,
                hx_target="#center-body",
                hx_swap="innerHTML",
                hx_push_url="true",
            )
        )

    nav = Div(H4("Navigate"), *items, cls="sidebar-section")

    convs_section = Div(
        H4("Recent conversations"),
        Div(
            id="conv-list",
            hx_get="/agui-conv/list",
            hx_trigger="load",
            hx_swap="innerHTML",
        ),
        cls="conv-section",
    )

    subscribe = Div(
        H4("Stay updated"),
        Form(
            Input(type="email", name="email", placeholder="you@example.com", required=True),
            Button("Subscribe", type="submit"),
            Div(id="subscribe-status", cls="subscribe-status"),
            hx_post="/subscribe",
            hx_target="#subscribe-status",
            hx_swap="innerHTML",
            cls="subscribe-form",
        ),
        cls="sidebar-section",
    )

    try:
        count = get_subscriber_count()
        sub_count_html = Div(f"{count:,} subscribers", cls="sidebar-footer") if count else None
    except Exception:
        sub_count_html = None

    parts = [
        Div(A("Hedgefolio", href="/", cls="brand"), Span("AI", cls="chat-badge"), cls="sidebar-header"),
        Button("+ New chat", cls="new-chat-btn", onclick="window.location.href='/?new=1'"),
        nav,
        convs_section,
        subscribe,
    ]
    if sub_count_html is not None:
        parts.append(sub_count_html)
    parts.append(Div("Powered by xAI Grok · SEC 13F data", cls="sidebar-footer"))
    return Div(*parts, cls="left-pane", id="left-pane")


def _right_pane():
    return Div(
        Div(
            H3("Thinking trace"),
            Div(
                Button("Clear", cls="close-trace-btn",
                       onclick="clearTrace()",
                       style="margin-right: 0.5rem; font-size: 0.7rem;"),
                Button("×", cls="close-trace-btn", onclick="toggleRightPane()"),
                style="display: flex; align-items: center;",
            ),
            cls="right-header",
        ),
        Div(
            Div(
                Div(
                    "Tool calls and reasoning will appear here during agent runs.",
                    style="color: #475569; font-style: italic;",
                ),
                id="trace-content",
            ),
            cls="right-content",
        ),
        cls="right-pane",
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def _session_thread_id(session, new: str = "", thread: str = "") -> str:
    if new == "1":
        tid = str(_uuid.uuid4())
        session["thread_id"] = tid
        return tid
    if thread:
        session["thread_id"] = thread
        return thread
    tid = session.get("thread_id")
    if not tid:
        tid = str(_uuid.uuid4())
        session["thread_id"] = tid
    return tid


def _page_shell(session, body, title_suffix: str, active: str):
    return (
        Title(f"Hedgefolio{(' — ' + title_suffix) if title_suffix else ''}"),
        Style(LAYOUT_CSS),
        Div(
            _left_pane(session, active=active),
            Div(
                Div(
                    H2("Hedgefolio"),
                    Button("Trace", cls="toggle-trace-btn", onclick="toggleRightPane()"),
                    cls="center-header",
                ),
                Div(body, id="center-body", cls="center-body"),
                cls="center-pane",
            ),
            _right_pane(),
            cls="app-layout",
        ),
        Script(LAYOUT_JS),
    )


def _chat_body(session, new: str = "", thread: str = ""):
    if agui is None:
        return Div(
            Div(
                H1("Chat unavailable"),
                P("The LangGraph agent could not be initialized. Set XAI_API_KEY in .env and restart."),
                cls="chart-page",
            )
        )
    tid = _session_thread_id(session, new=new, thread=thread)
    return Div(agui.chat(tid), cls="center-chat")


@rt("/")
def get(session, new: str = "", thread: str = ""):
    body = _chat_body(session, new=new, thread=thread)
    return _page_shell(session, body, title_suffix="Chat", active="chat")


# Convenience: also serve partials for HTMX swapping.
@rt("/partials/chat")
def partials_chat(session, new: str = "", thread: str = ""):
    return _chat_body(session, new=new, thread=thread)


# ---------------------------------------------------------------------------
# Chart pages
# ---------------------------------------------------------------------------

def _no_data_card() -> Div:
    return Div(
        H3("No 13F data loaded yet"),
        P(
            "The hedgefolio tables are empty. Run the data sync task to download "
            "SEC 13F filings and populate the database:",
            style="color:#64748b;margin-bottom:0.5rem;",
        ),
        P(NotStr("<code>python tasks/setup_data.py</code>"),
          style="font-family:ui-monospace,monospace;background:#f1f5f9;padding:0.5rem 0.75rem;border-radius:0.5rem;"),
        cls="chart-card",
    )


def _metric_tiles():
    try:
        stats = get_summary_stats()
    except Exception as e:
        logger.info("metric tiles unavailable: %s", e)
        return _no_data_card()
    return Div(
        Div(Div("Total Funds", cls="label"), Div(f"{stats['total_funds']:,}", cls="value"), cls="metric-tile"),
        Div(Div("Total Holdings", cls="label"), Div(f"{stats['total_holdings']:,}", cls="value"), cls="metric-tile"),
        Div(Div("Total AUM", cls="label"),
            Div(f"${stats['total_aum'] / 1e12:.2f}T" if stats['total_aum'] > 1e12 else f"${stats['total_aum'] / 1e9:.2f}B", cls="value"),
            cls="metric-tile"),
        Div(Div("Unique Securities", cls="label"), Div(f"{stats['unique_securities']:,}", cls="value"), cls="metric-tile"),
        cls="metric-row",
    )


def _render_plotly_card(title: str, fig_json: str | None, div_id: str, empty_msg: str):
    if not fig_json:
        return Div(H3(title), P(empty_msg, style="color:#94a3b8"), cls="chart-card")
    safe_payload = json.dumps(fig_json)
    return Div(
        H3(title),
        Div(id=div_id, cls="chart-placeholder"),
        Script(f"renderPlotly({div_id!r}, {safe_payload});"),
        cls="chart-card",
    )


def _treemap_body(fund: str = ""):
    try:
        funds = get_fund_names()
    except Exception as e:
        logger.info("fund list unavailable: %s", e)
        return Div(H1("Portfolio Treemap"), _no_data_card(), cls="chart-page")
    if not funds:
        return Div(H1("Portfolio Treemap"), _no_data_card(), cls="chart-page")
    # Default to Bridgewater-like fund
    default = next((f for f in funds if "BRIDGEWATER" in (f or "").upper()), funds[0])
    selected = fund or default

    picker_opts = [
        Option(f, value=f, selected=(f == selected)) for f in funds[:500]
    ]
    picker = Div(
        Form(
            Label("Fund:"),
            Select(
                *picker_opts,
                name="fund",
                onchange="this.form.requestSubmit()",
            ),
            hx_get="/charts/treemap",
            hx_target="#center-body",
            hx_swap="innerHTML",
            cls="fund-picker",
        ),
    )

    fig_json = portfolio_treemap_json(selected, limit=25)
    return Div(
        H1("Portfolio Treemap"),
        P(f"Top 25 holdings for {selected}", cls="subtitle"),
        picker,
        _render_plotly_card(f"Holdings — {selected}", fig_json, "treemap-fig",
                            "No holdings data available for this fund."),
        cls="chart-page",
    )


@rt("/charts/treemap")
def charts_treemap(session, fund: str = ""):
    # Support both full page load (direct nav) and HTMX partial.
    body = _treemap_body(fund=fund)
    # If HTMX, return the body only.
    return body


@rt("/charts/popular")
def charts_popular(session):
    fig = popular_securities_bar_json(top_n=20)
    return Div(
        H1("Most Popular Securities"),
        P("Holdings aggregated across every hedge fund in the dataset.", cls="subtitle"),
        _metric_tiles(),
        _render_plotly_card("Top 20 Securities by Total Value", fig, "popular-fig",
                            "No data available."),
        cls="chart-page",
    )


@rt("/charts/concentration")
def charts_concentration(session):
    fig = fund_concentration_pie_json(top_n=10)
    return Div(
        H1("Fund Concentration"),
        P("Market share of the top hedge funds by portfolio value.", cls="subtitle"),
        _metric_tiles(),
        _render_plotly_card("Top 10 Funds — Market Share", fig, "concentration-fig",
                            "No data available."),
        cls="chart-page",
    )


@rt("/charts/types")
def charts_types(session):
    fig = security_type_bar_json()
    return Div(
        H1("Security Type Distribution"),
        P("What kinds of instruments hedge funds hold the most of.", cls="subtitle"),
        _render_plotly_card("Security Types", fig, "types-fig", "No data available."),
        cls="chart-page",
    )


# ---------------------------------------------------------------------------
# Activist filings (Schedule 13D / 13G)
# ---------------------------------------------------------------------------

def _activist_body(form_filter: str = "all", days: int = 14, q: str = ""):
    try:
        from utils.activist import activist_stats, recent_filings, search_activist
    except Exception as e:
        logger.exception("activist module import failed")
        return Div(H1("Activist Filings"), P(f"Error: {e}"), cls="chart-page")

    try:
        stats = activist_stats(days=days)
    except Exception as e:
        logger.info("activist stats unavailable: %s", e)
        return Div(
            H1("Activist Filings"),
            Div(
                H3("Activist filings index not built yet"),
                P("Run:", style="color:#64748b;margin-bottom:0.5rem;"),
                P(NotStr("<code>python tasks/sync_activist.py --days 30 --enrich 500</code>"),
                  style="font-family:ui-monospace,monospace;background:#f1f5f9;padding:0.5rem 0.75rem;border-radius:0.5rem;"),
                cls="chart-card",
            ),
            cls="chart-page",
        )

    activist_only = form_filter == "13d"
    if q:
        rows = search_activist(q, limit=200)
    else:
        rows = recent_filings(limit=200, activist_only=activist_only, days=days)

    # Filter/search form
    filter_opts = [
        Option("13D + 13G", value="all", selected=(form_filter == "all")),
        Option("13D only (activist)", value="13d", selected=(form_filter == "13d")),
    ]
    days_opts = [
        Option(f"Last {n} days", value=str(n), selected=(days == n))
        for n in (7, 14, 30, 60, 90)
    ]
    controls = Form(
        Label("Forms:"),
        Select(*filter_opts, name="form_filter"),
        Label("Window:"),
        Select(*days_opts, name="days"),
        Label("Search:"),
        Input(type="search", name="q", value=q or "",
              placeholder="Filer or subject (Icahn, NVIDIA…)",
              style="flex:1;padding:0.45rem 0.6rem;border:1px solid #e2e8f0;border-radius:0.5rem;"),
        Button("Apply", type="submit"),
        hx_get="/activist",
        hx_target="#center-body",
        hx_swap="innerHTML",
        cls="fund-picker",
        style="flex-wrap:wrap;gap:0.5rem;",
    )

    tiles = Div(
        Div(Div("13D filings", cls="label"),
            Div(f"{stats['cnt_13d']}", cls="value"),
            cls="metric-tile"),
        Div(Div("13D amendments", cls="label"),
            Div(f"{stats['cnt_13d_a']}", cls="value"),
            cls="metric-tile"),
        Div(Div("13G filings", cls="label"),
            Div(f"{stats['cnt_13g']}", cls="value"),
            cls="metric-tile"),
        Div(Div("13G amendments", cls="label"),
            Div(f"{stats['cnt_13g_a']}", cls="value"),
            cls="metric-tile"),
        Div(Div("Unique filers", cls="label"),
            Div(f"{stats['unique_filers']}", cls="value"),
            cls="metric-tile"),
        Div(Div("Most recent", cls="label"),
            Div(str(stats["most_recent"] or "—"), cls="value", style="font-size:0.9rem"),
            cls="metric-tile"),
        cls="metric-row",
    )

    # Build the filings table
    if not rows:
        table = Div(
            H3("No filings in this window"),
            P("Adjust the filter or run the daily sync to backfill more days.",
              style="color:#64748b"),
            cls="chart-card",
        )
    else:
        header_row = NotStr(
            "<thead><tr>"
            "<th>Date</th><th>Form</th><th>Filer</th>"
            "<th>Subject</th><th>Link</th>"
            "</tr></thead>"
        )
        body_rows = []
        for r in rows:
            date_s = r["filing_date"].isoformat() if r["filing_date"] else ""
            form = r["form_type"]
            # Classic activist 13D gets a colored badge.
            badge_cls = "badge-red" if "13D" in form else "badge-blue"
            filer = (r["filer_name"] or "").replace("<", "&lt;")
            subject = (r["subject_name"] or "—").replace("<", "&lt;")
            link = (
                f'<a href="{r["filing_url"]}" target="_blank" rel="noreferrer">'
                f'{r["accession_number"]}</a>'
            ) if r["filing_url"] else ""
            body_rows.append(
                f"<tr>"
                f"<td>{date_s}</td>"
                f"<td><span class='{badge_cls}'>{form}</span></td>"
                f"<td>{filer}</td>"
                f"<td>{subject}</td>"
                f"<td>{link}</td>"
                f"</tr>"
            )
        table = Div(
            H3(f"{len(rows)} filings"),
            NotStr(
                "<table style='width:100%;border-collapse:collapse;font-size:0.85rem'>"
                + str(header_row)
                + "<tbody>"
                + "".join(body_rows)
                + "</tbody></table>"
            ),
            cls="chart-card",
            style="overflow-x:auto",
        )

    return Div(
        H1("Activist Filings"),
        P(
            "Live tracker of SEC Schedule 13D and 13G filings — the reports "
            "filed by investors when they cross the 5% ownership threshold. "
            "13D signals activist intent (willing to influence management); "
            "13G is the passive variant.",
            cls="subtitle",
        ),
        controls,
        tiles,
        table,
        cls="chart-page",
    )


@rt("/activist")
def activist_view(session, form_filter: str = "all", days: int = 14, q: str = ""):
    return _activist_body(form_filter=form_filter, days=int(days or 14), q=q or "")


# Also support full-page direct navigation to chart pages (not just HTMX swaps).
@rt("/charts/treemap/full")
def charts_treemap_full(session, fund: str = ""):
    return _page_shell(session, _treemap_body(fund=fund), title_suffix="Treemap", active="treemap")


# ---------------------------------------------------------------------------
# Conversation list (sidebar)
# ---------------------------------------------------------------------------

@rt("/agui-conv/list")
def get_conv_list(session):
    current_tid = session.get("thread_id", "")
    user_id = session.get("user", {}).get("user_id") if session.get("user") else None
    try:
        convs = list_conversations(user_id=user_id, limit=20)
    except Exception:
        convs = []
    if not convs:
        return Div(Span("No conversations yet", cls="conv-empty"))
    items = []
    for c in convs:
        tid = c["thread_id"]
        title = (c.get("title") or c.get("first_msg") or "New chat")[:40]
        cls = "conv-item"
        if tid == current_tid:
            cls += " conv-active"
        items.append(A(title, href=f"/?thread={tid}", cls=cls, title=c.get("title") or ""))
    return Div(*items)


# ---------------------------------------------------------------------------
# Email subscribe
# ---------------------------------------------------------------------------

@rt("/subscribe")
def post_subscribe(session, email: str = ""):
    from utils.email_util import POSTMARK_API_KEY, send_welcome_email, validate_email

    email = (email or "").strip()
    if not email or not validate_email(email):
        return Span("Please enter a valid email.", cls="err")
    result = subscribe_user(email)
    if not result.get("success"):
        return Span(result.get("message", "Error"), cls="err")
    if result.get("is_new") and POSTMARK_API_KEY:
        try:
            send_welcome_email(email)
        except Exception:
            pass
    return Span(result.get("message", "Subscribed!"), cls="ok")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@rt("/health")
def health():
    db_ok = False
    try:
        db_ok = check_database_connection()
    except Exception:
        db_ok = False
    return {"status": "ok", "db": db_ok, "agent": agui is not None}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5011"))
    serve(host="0.0.0.0", port=port, reload=os.getenv("RELOAD", "false").lower() == "true")
