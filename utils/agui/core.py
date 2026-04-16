"""AG-UI core for Hedgefolio: 3-pane chat with LangGraph streaming.

Adapted from the alpatrade AG-UI port (MIT). Removes the long-running
StreamingCommand plumbing — hedgefolio tools are short and synchronous, so
only the AI streaming path is kept. LangGraph `astream_events(v2)` drives
token-by-token streaming into the chat pane while tool-call traces stream
into the right-hand pane.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict

from fasthtml.common import (
    Button,
    Div,
    Form,
    Hidden,
    NotStr,
    Pre,
    Script,
    Span,
    Style,
    Textarea,
)

from .chat_store import (
    list_conversations,
    load_conversation_messages,
    save_conversation,
    save_message,
)
from .styles import get_chat_styles

logger = logging.getLogger(__name__)


_SCROLL_CHAT_JS = (
    "var m=document.getElementById('chat-messages');"
    "if(m)m.scrollTop=m.scrollHeight;"
)
_GUARD_ENABLE_JS = "window._aguiProcessing=true;"
_GUARD_DISABLE_JS = "window._aguiProcessing=false;"


# ---------------------------------------------------------------------------
# UI renderer
# ---------------------------------------------------------------------------

class UI:
    """Renders chat components for a given thread."""

    def __init__(self, thread_id: str, autoscroll: bool = True):
        self.thread_id = thread_id
        self.autoscroll = autoscroll

    def _clear_input(self):
        return self._render_input_form(oob_swap=True)

    def _render_messages(self, messages: list[dict], oob: bool = False):
        attrs = {"id": "chat-messages", "cls": "chat-messages"}
        if oob:
            attrs["hx_swap_oob"] = "outerHTML"
        return Div(*[self._render_message(m) for m in messages], **attrs)

    def _render_message(self, message: dict):
        role = message.get("role", "assistant")
        cls = "chat-user" if role == "user" else "chat-assistant"
        mid = message.get("message_id", str(uuid.uuid4()))
        content_id = f"msg-content-{mid}"
        if role == "user":
            return Div(
                Div(message.get("content", ""), cls="chat-message-content"),
                cls=f"chat-message {cls}",
                id=mid,
            )
        # Assistant messages get markdown rendering.
        return Div(
            Div(message.get("content", ""), cls="chat-message-content marked", id=content_id),
            cls=f"chat-message {cls}",
            id=mid,
        )

    def _render_input_form(self, oob_swap: bool = False):
        container_attrs = {"cls": "chat-input", "id": "chat-input-container"}
        if oob_swap:
            container_attrs["hx_swap_oob"] = "outerHTML"

        return Div(
            Div(id="suggestion-buttons"),
            Div(id="chat-status", cls="chat-status"),
            Form(
                Hidden(name="thread_id", value=self.thread_id),
                Textarea(
                    id="chat-input",
                    name="msg",
                    placeholder="Ask about a fund, a holding, or F13 filings...\nShift+Enter for new line",
                    autofocus=True,
                    autocomplete="off",
                    cls="chat-input-field",
                    rows="2",
                    onkeydown="handleKeyDown(this, event)",
                    oninput="autoResize(this)",
                ),
                Button(
                    "Send",
                    type="submit",
                    cls="chat-input-button",
                    onclick="if(window._aguiProcessing){event.preventDefault();return false;}",
                ),
                cls="chat-input-form",
                id="chat-form",
                ws_send=True,
            ),
            Div(
                Span("Enter", cls="kbd"), " to send  ",
                Span("Shift+Enter", cls="kbd"), " new line",
                cls="input-hint",
            ),
            **container_attrs,
        )

    def _render_welcome(self):
        _ICON_CHAT = (
            '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>'
        )
        _ICON_CHART = (
            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M18 20V10M12 20V4M6 20v-6"/></svg>'
        )
        _ICON_SEARCH = (
            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>'
        )
        _ICON_BOOK = (
            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>'
            '<path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>'
        )
        _ICON_TREE = (
            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>'
            '<rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>'
        )

        cards = [
            ("Fund performance",    "Check a fund's portfolio profile",                "What is the performance of Laurion Capital?",              "#3b82f6", _ICON_CHART),
            ("Largest holdings",    "Top positions for a specific fund",               "What are the largest holdings of Situational Awareness?",  "#6366f1", _ICON_TREE),
            ("Who owns a stock",    "Find which hedge funds hold a security",          "Which hedge funds hold NVIDIA?",                           "#8b5cf6", _ICON_SEARCH),
            ("Recent activists",    "Latest Schedule 13D filings (last 7 days)",       "Show me the 10 most recent 13D activist filings.",         "#ef4444", _ICON_BOOK),
            ("Popular trades",      "Most widely-held securities across all funds",    "What are the 10 most popular securities right now?",       "#10b981", _ICON_TREE),
            ("F13 filing docs",     "Ask how 13F fields and deadlines work",           "What is INVESTMENTDISCRETION in a 13F filing?",            "#f59e0b", _ICON_BOOK),
        ]

        card_els = []
        for title, desc, cmd, color, icon_svg in cards:
            card_els.append(
                Div(
                    Div(NotStr(icon_svg), cls="welcome-card-icon",
                        style=f"background:{color}15;color:{color}"),
                    Div(title, cls="welcome-card-title"),
                    Div(desc, cls="welcome-card-desc"),
                    cls="welcome-card",
                    onclick=(
                        "if(window._aguiProcessing)return;"
                        "var ta=document.getElementById('chat-input');"
                        "var fm=document.getElementById('chat-form');"
                        f"if(ta&&fm){{ta.value={cmd!r};fm.requestSubmit();}}"
                    ),
                )
            )

        return Div(
            Div(
                Div(NotStr(_ICON_CHAT), cls="welcome-icon"),
                Div("Hedgefolio", cls="welcome-title"),
                Div("Invest like a hedge fund manager", cls="welcome-subtitle"),
                Div(*card_els, cls="welcome-grid"),
                cls="welcome-hero",
            ),
            id="welcome-screen",
        )

    def chat(self, **kwargs):
        components = [
            get_chat_styles(),
            Div(
                self._render_welcome(),
                id="chat-messages",
                cls="chat-messages",
                hx_get=f"/agui/messages/{self.thread_id}",
                hx_trigger="load",
                hx_swap="outerHTML",
            ),
            self._render_input_form(),
            Script(_CHAT_JS),
        ]
        if self.autoscroll:
            components.append(Script(_AUTOSCROLL_JS))

        components.append(Div(id="agui-js", style="display:none"))

        return Div(
            *components,
            hx_ext="ws",
            ws_connect=f"/agui/ws/{self.thread_id}",
            cls="chat-container welcome-active",
            **kwargs,
        )


_CHAT_JS = """
(function() {
    function checkWelcome() {
        var container = document.querySelector('.chat-container');
        var welcome = document.getElementById('welcome-screen');
        if (container) {
            if (welcome) container.classList.add('welcome-active');
            else container.classList.remove('welcome-active');
        }
    }
    checkWelcome();
    var container = document.querySelector('.chat-container');
    if (container) {
        var observer = new MutationObserver(checkWelcome);
        observer.observe(container, {childList: true, subtree: true});
    }
})();

function autoResize(textarea) {
    textarea.style.height = 'auto';
    var maxH = 12 * 16;
    var h = Math.min(textarea.scrollHeight, maxH);
    textarea.style.height = h + 'px';
    textarea.style.overflowY = textarea.scrollHeight > maxH ? 'auto' : 'hidden';
}
function handleKeyDown(textarea, event) {
    autoResize(textarea);
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        if (window._aguiProcessing) return;
        var form = textarea.closest('form');
        if (form && textarea.value.trim()) form.requestSubmit();
    }
}

function tableToCSV(table) {
    var rows = [];
    table.querySelectorAll('tr').forEach(function(tr) {
        var cells = [];
        tr.querySelectorAll('th, td').forEach(function(td) {
            var val = td.textContent.trim().replace(/"/g, '""');
            cells.push('"' + val + '"');
        });
        rows.push(cells.join(','));
    });
    return rows.join('\\n');
}

function enhanceTables(container) {
    container.querySelectorAll('table').forEach(function(table) {
        if (table.dataset.enhanced) return;
        table.dataset.enhanced = '1';
        var toolbar = document.createElement('div');
        toolbar.className = 'table-toolbar';
        var copyBtn = document.createElement('button');
        copyBtn.textContent = 'Copy CSV';
        copyBtn.className = 'table-action-btn';
        copyBtn.onclick = function() {
            var csv = tableToCSV(table);
            navigator.clipboard.writeText(csv).then(function() {
                copyBtn.textContent = 'Copied!';
                setTimeout(function(){ copyBtn.textContent = 'Copy CSV'; }, 1500);
            });
        };
        var dlBtn = document.createElement('button');
        dlBtn.textContent = 'Download CSV';
        dlBtn.className = 'table-action-btn';
        dlBtn.onclick = function() {
            var csv = tableToCSV(table);
            var blob = new Blob([csv], {type: 'text/csv'});
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.download = 'hedgefolio-data.csv';
            a.click();
            URL.revokeObjectURL(url);
        };
        toolbar.appendChild(copyBtn);
        toolbar.appendChild(dlBtn);
        table.parentNode.insertBefore(toolbar, table);
    });
}

function postRenderEnhance(el) { enhanceTables(el); }

function renderMarkdown(elementId) {
    setTimeout(function() {
        var el = document.getElementById(elementId);
        if (el && window.marked && el.classList.contains('marked')) {
            var txt = el.textContent || el.innerText;
            if (txt.trim()) {
                el.innerHTML = marked.parse(txt);
                el.classList.remove('marked');
                el.classList.add('marked-done');
                delete el.dataset.rendering;
                postRenderEnhance(el);
            }
        }
    }, 100);
}

if (window.marked) {
    new MutationObserver(function() {
        document.querySelectorAll('.marked').forEach(function(el) {
            var parent = el.parentElement;
            if (parent) {
                var cursor = parent.querySelector('.chat-streaming');
                if (cursor && cursor.textContent) return;
            }
            var txt = el.textContent || el.innerText;
            if (txt.trim() && !el.dataset.rendering) {
                el.dataset.rendering = '1';
                setTimeout(function() {
                    if (!el.classList.contains('marked')) { delete el.dataset.rendering; return; }
                    var finalTxt = el.textContent || el.innerText;
                    if (finalTxt.trim()) {
                        el.innerHTML = marked.parse(finalTxt);
                        el.classList.remove('marked');
                        el.classList.add('marked-done');
                        postRenderEnhance(el);
                    }
                    delete el.dataset.rendering;
                }, 150);
            }
        });
    }).observe(document.body, {childList: true, subtree: true});
}
"""


_AUTOSCROLL_JS = """
(function() {
    var obs = new MutationObserver(function() {
        var m = document.getElementById('chat-messages');
        if (m) m.scrollTop = m.scrollHeight;
    });
    var t = document.getElementById('chat-messages');
    if (t) obs.observe(t, {childList: true, subtree: true});
})();
"""


# ---------------------------------------------------------------------------
# Thread
# ---------------------------------------------------------------------------

class AGUIThread:
    def __init__(self, thread_id: str, langgraph_agent, user_id: str | None = None):
        self.thread_id = thread_id
        self._agent = langgraph_agent
        self._user_id = user_id
        self._messages: list[dict] = []
        self._connections: Dict[str, Any] = {}
        self.ui = UI(self.thread_id, autoscroll=True)
        self._suggestions: list[str] = []
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        self._loaded = True
        try:
            self._messages = load_conversation_messages(self.thread_id)
        except Exception:
            logger.exception("Failed to load history for %s", self.thread_id)

    def subscribe(self, connection_id: str, send):
        self._connections[connection_id] = send

    def unsubscribe(self, connection_id: str):
        self._connections.pop(connection_id, None)

    async def send(self, element):
        for _, send_fn in list(self._connections.items()):
            try:
                await send_fn(element)
            except Exception:
                logger.exception("WS send failed")

    async def _send_js(self, js_code: str):
        await self.send(Div(Script(js_code), id="agui-js", hx_swap_oob="innerHTML"))

    async def set_suggestions(self, suggestions: list[str]):
        self._suggestions = suggestions[:4]
        if self._suggestions:
            el = Div(
                *[
                    Button(
                        Span(s), Span("\u2192", cls="arrow"),
                        onclick=(
                            "if(window._aguiProcessing)return;"
                            "var ta=document.getElementById('chat-input');"
                            "var fm=document.getElementById('chat-form');"
                            f"if(ta&&fm){{ta.value={s!r};fm.requestSubmit();}}"
                        ),
                        cls="suggestion-btn",
                    )
                    for s in self._suggestions
                ],
                id="suggestion-buttons",
                hx_swap_oob="outerHTML",
            )
        else:
            el = Div(id="suggestion-buttons", hx_swap_oob="outerHTML")
        await self.send(el)

    async def _refresh_conv_list(self):
        await self.send(
            Div(id="conv-list", hx_get="/agui-conv/list",
                hx_trigger="load", hx_swap="innerHTML", hx_swap_oob="outerHTML")
        )

    async def _handle_message(self, msg: str, session):
        self._ensure_loaded()
        await self._send_js(_GUARD_ENABLE_JS)
        await self._send_js(
            "var w=document.getElementById('welcome-screen');if(w)w.remove();"
            "var c=document.querySelector('.chat-container');if(c)c.classList.remove('welcome-active');"
        )
        await self.set_suggestions([])
        await self._handle_ai_run(msg, session)

    async def _handle_ai_run(self, msg: str, session):
        from langchain_core.messages import AIMessage, HumanMessage

        _open_trace = (
            "var l=document.querySelector('.app-layout');"
            "if(l&&!l.classList.contains('right-open'))l.classList.add('right-open');"
            "setTimeout(function(){var tc=document.getElementById('trace-content');"
            "if(tc)tc.scrollTop=tc.scrollHeight;},100);"
        )

        user_mid = str(uuid.uuid4())
        asst_mid = str(uuid.uuid4())
        content_id = f"message-content-{asst_mid}"

        self._messages.append({"role": "user", "content": msg, "message_id": user_mid})
        try:
            title = msg[:80] if len(self._messages) == 1 else None
            save_conversation(self.thread_id, user_id=self._user_id, title=title)
        except Exception:
            logger.exception("save_conversation failed")
        try:
            save_message(self.thread_id, "user", msg, user_mid)
        except Exception:
            logger.exception("save_message(user) failed")

        await self.send(
            Div(
                Div(Div(msg, cls="chat-message-content"),
                    cls="chat-message chat-user", id=user_mid),
                id="chat-messages", hx_swap_oob="beforeend",
            )
        )

        await self.send(self.ui._clear_input())
        await self._send_js(
            "var b=document.querySelector('.chat-input-button'),t=document.getElementById('chat-input');"
            "if(b){b.disabled=true;b.classList.add('sending')}"
            "if(t){t.disabled=true;t.placeholder='Thinking...'}"
        )

        await self.send(
            Div(
                Div(
                    Div(
                        Span("", id=content_id),
                        Span("", cls="chat-streaming", id=f"streaming-{asst_mid}"),
                        cls="chat-message-content",
                    ),
                    cls="chat-message chat-assistant",
                    id=f"message-{asst_mid}",
                ),
                id="chat-messages", hx_swap_oob="beforeend",
            )
        )

        run_trace_id = str(uuid.uuid4())
        await self.send(
            Div(
                Div(Span("AI run started", cls="trace-label"),
                    cls="trace-entry trace-run-start",
                    id=f"trace-run-{run_trace_id}"),
                Script(_open_trace),
                id="trace-content", hx_swap_oob="beforeend",
            )
        )

        lc_messages = []
        for m in self._messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            else:
                lc_messages.append(AIMessage(content=content))

        full_response = ""
        try:
            async for event in self._agent.astream_events(
                {"messages": lc_messages}, version="v2"
            ):
                kind = event.get("event", "")
                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        token = chunk.content
                        full_response += token
                        await self.send(Span(token, id=content_id, hx_swap_oob="beforeend"))
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "tool")
                    tool_run_id = event.get("run_id", "")[:8]
                    inputs = event.get("data", {}).get("input", {})
                    detail = ", ".join(f"{k}={v}" for k, v in (inputs or {}).items())
                    await self.send(
                        Div(
                            Div(
                                Span(f"Tool: {tool_name}", cls="trace-label"),
                                Span(detail or "running...", cls="trace-detail"),
                                cls="trace-entry trace-tool-active",
                                id=f"trace-tool-{tool_run_id}",
                            ),
                            Script(_open_trace),
                            id="trace-content", hx_swap_oob="beforeend",
                        )
                    )
                    await self.send(
                        Div(
                            Div(Div(f"Running {tool_name}...", cls="chat-message-content"),
                                cls="chat-message chat-tool",
                                id=f"tool-{tool_run_id}"),
                            id="chat-messages", hx_swap_oob="beforeend",
                        )
                    )
                elif kind == "on_tool_end":
                    tool_run_id = event.get("run_id", "")[:8]
                    await self.send(
                        Div(
                            Div("Done", cls="chat-message-content"),
                            cls="chat-message chat-tool",
                            id=f"tool-{tool_run_id}",
                            hx_swap_oob="outerHTML",
                        )
                    )
                    await self.send(
                        Div(
                            Span("Tool complete", cls="trace-label"),
                            cls="trace-entry trace-tool-done",
                            id=f"trace-tool-{tool_run_id}",
                            hx_swap_oob="outerHTML",
                        )
                    )
        except Exception as e:
            error_msg = str(e)
            logger.exception("AI run error: %s", error_msg)
            full_response += f"\n\n**Error:** {error_msg}"
            await self.send(Span(f"\n\n**Error:** {error_msg}", id=content_id, hx_swap_oob="beforeend"))
            await self.send(
                Div(
                    Div(
                        Span("Error", cls="trace-label"),
                        Span(error_msg[:200], cls="trace-detail"),
                        cls="trace-entry trace-error",
                    ),
                    id="trace-content", hx_swap_oob="beforeend",
                )
            )

        await self.send(Span("", id=f"streaming-{asst_mid}", hx_swap_oob="outerHTML"))
        await self._send_js(
            f"var el=document.getElementById('{content_id}');"
            f"if(el)el.classList.add('marked');"
            f"renderMarkdown('{content_id}');"
        )
        await self.send(
            Div(
                Div(Span("Run finished", cls="trace-label"), cls="trace-entry trace-run-end"),
                id="trace-content", hx_swap_oob="beforeend",
            )
        )

        self._messages.append({"role": "assistant", "content": full_response, "message_id": asst_mid})
        try:
            save_message(self.thread_id, "assistant", full_response, asst_mid)
        except Exception:
            logger.exception("save_message(assistant) failed")

        await self._refresh_conv_list()
        await self.send(self.ui._clear_input())
        await self._send_js(
            _GUARD_DISABLE_JS
            + "var b=document.querySelector('.chat-input-button'),t=document.getElementById('chat-input');"
            "if(b){b.disabled=false;b.classList.remove('sending')}"
            "if(t){t.disabled=false;t.placeholder='Ask about a fund, a holding, or F13 filings...';t.focus()}"
        )
        await self._send_js(_SCROLL_CHAT_JS)


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

class AGUISetup:
    def __init__(self, app, langgraph_agent):
        self.app = app
        self._agent = langgraph_agent
        self._threads: Dict[str, AGUIThread] = {}
        self._setup_routes()

    def _setup_routes(self):
        @self.app.get("/agui/ui/{thread_id}/chat")
        async def agui_chat_ui(thread_id: str, session):
            session["thread_id"] = thread_id
            return self.thread(thread_id, session).ui.chat()

        @self.app.ws(
            "/agui/ws/{thread_id}",
            conn=self._on_conn,
            disconn=self._on_disconn,
        )
        async def agui_ws(thread_id: str, msg: str, session):
            await self._threads[thread_id]._handle_message(msg, session)

        @self.app.route("/agui/messages/{thread_id}")
        def agui_messages(thread_id: str, session):
            thread = self.thread(thread_id, session)
            thread._ensure_loaded()
            if thread._messages:
                return thread.ui._render_messages(thread._messages)
            return Div(thread.ui._render_welcome(), id="chat-messages", cls="chat-messages")

    def thread(self, thread_id: str, session=None) -> AGUIThread:
        if thread_id not in self._threads:
            user_id = None
            if session and session.get("user"):
                user_id = session["user"].get("user_id")
            self._threads[thread_id] = AGUIThread(
                thread_id=thread_id,
                langgraph_agent=self._agent,
                user_id=user_id,
            )
        return self._threads[thread_id]

    def _on_conn(self, ws, send, session):
        tid = session.get("thread_id", "default")
        self.thread(tid, session).subscribe(str(id(ws)), send)

    def _on_disconn(self, ws, session):
        tid = session.get("thread_id", "default")
        if tid in self._threads:
            self._threads[tid].unsubscribe(str(id(ws)))

    def chat(self, thread_id: str):
        return Div(
            hx_get=f"/agui/ui/{thread_id}/chat",
            hx_trigger="load",
            hx_swap="innerHTML",
        )


def setup_agui(app, langgraph_agent) -> AGUISetup:
    return AGUISetup(app, langgraph_agent)
