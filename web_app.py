"""Hedgefolio — FastHTML 3-pane agentic chat UI.

Chat-driven everywhere: the five common analyses (activist filings,
portfolio holdings, popular securities, top funds, security-type breakdown)
are shortcuts in the left nav that pre-fill the chat input and submit. The
agent streams the answer back as markdown (tables, no static Plotly pages).

Layout:
  Left  — brand, new-chat, 5 shortcut buttons, recent conversations, subscribe
  Center — AG-UI chat (WebSocket-streamed via LangGraph astream_events v2)
  Right  — live tool-call trace

Run:
  python web_app.py                # listens on PORT (default 5011)
  uvicorn web_app:app --port 5011  # alternative
"""

from __future__ import annotations

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
    H2,
    H3,
    H4,
    Input,
    NotStr,
    P,
    Script,
    Span,
    Style,
    Title,
    fast_app,
    serve,
)

from utils.agent import build_agent
from utils.agui import list_conversations, setup_agui
from utils.db_queries import (
    check_database_connection,
    get_subscriber_count,
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
    ],
)

if langgraph_agent is not None:
    agui = setup_agui(app, langgraph_agent)
else:
    agui = None


# ---------------------------------------------------------------------------
# Shortcuts — one chat prompt per left-nav button. The agent resolves these
# against its tools and streams back a markdown table.
# ---------------------------------------------------------------------------

SHORTCUTS = [
    {
        "key":    "activist",
        "label":  "Activist Filings",
        "desc":   "Latest Schedule 13D filings",
        "prompt": "Show me the 20 most recent Schedule 13D activist filings from the last 14 days. Include the form type, filer, subject company, filing date, and a link.",
    },
    {
        "key":    "holdings",
        "label":  "Top Holdings",
        "desc":   "Bridgewater's portfolio",
        "prompt": "Show me the top 20 holdings of Bridgewater Associates, with ticker-equivalent name, value, shares, and portfolio percentage.",
    },
    {
        "key":    "popular",
        "label":  "Popular Securities",
        "desc":   "Most widely-held stocks",
        "prompt": "What are the 20 most popular securities across all hedge funds? Include total value, total shares, and how many funds hold each one.",
    },
    {
        "key":    "top-funds",
        "label":  "Top Funds by AUM",
        "desc":   "Largest hedge funds",
        "prompt": "Who are the top 15 hedge funds by portfolio value? Include AUM and total positions.",
    },
    {
        "key":    "types",
        "label":  "Security Types",
        "desc":   "Instrument breakdown",
        "prompt": "What is the distribution of security types across all 13F holdings? Show the top 15 classes by position count and percentage.",
    },
]


# ---------------------------------------------------------------------------
# Layout CSS
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

.shortcut-btn {
  text-align: left;
  width: 100%;
  padding: 0.55rem 0.7rem;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  font-family: inherit;
  font-size: 0.85rem;
  color: #1e293b;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}
.shortcut-btn:hover {
  background: #eff6ff;
  border-color: #93c5fd;
  color: #1e40af;
}
.shortcut-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.shortcut-btn .label { font-weight: 600; font-size: 0.85rem; }
.shortcut-btn .desc  { font-size: 0.7rem; color: #64748b; }
.shortcut-btn:hover .desc { color: #475569; }

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

/* Shortcut button handler: pre-fill chat input and submit. If the chat isn't
   mounted yet (very first paint), stash the prompt in a cookie and reload to
   the chat URL — the server will pick it up and auto-submit. */
function runShortcut(prompt) {
    if (window._aguiProcessing) return;
    function doSubmit() {
        var ta = document.getElementById('chat-input');
        var fm = document.getElementById('chat-form');
        if (ta && fm) {
            // Dismiss welcome hero if visible.
            var welcome = document.getElementById('welcome-screen');
            if (welcome) welcome.remove();
            ta.value = prompt;
            ta.focus();
            fm.requestSubmit();
            return true;
        }
        return false;
    }
    if (doSubmit()) return;
    // Fallback: retry briefly in case the chat widget is still mounting.
    var tries = 0;
    var iv = setInterval(function() {
        tries++;
        if (doSubmit() || tries > 40) clearInterval(iv);
    }, 50);
}
"""


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def _left_pane(session):
    shortcuts = Div(
        H4("Shortcuts"),
        *[
            Button(
                Span(sc["label"], cls="label"),
                Span(sc["desc"], cls="desc"),
                cls="shortcut-btn",
                onclick=f"runShortcut({sc['prompt']!r})",
                data_shortcut_key=sc["key"],
                type="button",
            )
            for sc in SHORTCUTS
        ],
        cls="sidebar-section",
    )

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
        Button("+ New chat", cls="new-chat-btn",
               onclick="window.location.href='/?new=1'", type="button"),
        shortcuts,
        convs_section,
        subscribe,
    ]
    if sub_count_html is not None:
        parts.append(sub_count_html)
    parts.append(Div("Powered by xAI Grok · SEC 13F + 13D/G data", cls="sidebar-footer"))
    return Div(*parts, cls="left-pane", id="left-pane")


def _right_pane():
    return Div(
        Div(
            H3("Thinking trace"),
            Div(
                Button("Clear", cls="close-trace-btn",
                       onclick="clearTrace()",
                       style="margin-right: 0.5rem; font-size: 0.7rem;",
                       type="button"),
                Button("×", cls="close-trace-btn", onclick="toggleRightPane()", type="button"),
                style="display: flex; align-items: center;",
            ),
            cls="right-header",
        ),
        Div(
            Div(
                Div("Tool calls and reasoning will appear here during agent runs.",
                    style="color: #475569; font-style: italic;"),
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


@rt("/")
def home(session, new: str = "", thread: str = ""):
    if agui is None:
        return (
            Title("Hedgefolio"),
            Div(H2("Chat unavailable"),
                P("Set XAI_API_KEY in .env and restart."))
        )
    tid = _session_thread_id(session, new=new, thread=thread)
    return (
        Title("Hedgefolio"),
        Style(LAYOUT_CSS),
        Div(
            _left_pane(session),
            Div(
                Div(
                    H2("Hedgefolio"),
                    Button("Trace", cls="toggle-trace-btn",
                           onclick="toggleRightPane()", type="button"),
                    cls="center-header",
                ),
                Div(Div(agui.chat(tid), cls="center-chat"), id="center-body", cls="center-body"),
                cls="center-pane",
            ),
            _right_pane(),
            cls="app-layout",
        ),
        Script(LAYOUT_JS),
    )


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


@rt("/health")
def health():
    db_ok = False
    try:
        db_ok = check_database_connection()
    except Exception:
        db_ok = False
    return {"status": "ok", "db": db_ok, "agent": agui is not None}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5011"))
    serve(host="0.0.0.0", port=port, reload=os.getenv("RELOAD", "false").lower() == "true")
