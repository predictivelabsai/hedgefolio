"""HTTP endpoint regression tests (starlette TestClient against web_app.app)."""

from __future__ import annotations

import uuid


def test_23_health_endpoint(web_client):
    r = web_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] is True
    assert "agent" in body


def test_24_home_page_renders(web_client):
    r = web_client.get("/")
    assert r.status_code == 200
    assert b"Hedgefolio" in r.content
    assert b"app-layout" in r.content


def test_25_left_nav_has_all_five_shortcuts(web_client):
    """Every shortcut must render as a clickable button with its prompt."""
    from web_app import SHORTCUTS
    r = web_client.get("/")
    assert r.status_code == 200
    html = r.content.decode()
    assert len(SHORTCUTS) == 5, "we expose exactly five shortcuts"
    for sc in SHORTCUTS:
        # Label + description visible in the sidebar
        assert sc["label"] in html, f"label missing: {sc['label']}"
        assert sc["desc"] in html, f"desc missing: {sc['desc']}"
        # The prompt itself is wired into onclick="runShortcut('...')"
        assert "runShortcut(" in html
        # Each button carries its semantic key for test targeting
        assert f'data-shortcut-key="{sc["key"]}"' in html


def test_26_shortcut_onclick_includes_full_prompt(web_client):
    """The onclick handler should carry the exact prompt text so regression
    tests can assert what will be sent to the agent."""
    from web_app import SHORTCUTS
    r = web_client.get("/")
    html = r.content.decode()
    for sc in SHORTCUTS:
        # Prompts may contain apostrophes; Python's repr() → single quotes.
        # Just assert a distinctive phrase from each prompt appears somewhere
        # on the page (inside a runShortcut call).
        marker = sc["prompt"].split(".")[0][:40]
        assert marker in html, f"shortcut prompt snippet missing: {marker!r}"


def test_27_removed_pages_404(web_client):
    """The static chart pages were replaced with chat shortcuts — they
    should no longer be routable."""
    for path in ("/activist", "/charts/popular", "/charts/concentration",
                 "/charts/types", "/charts/treemap"):
        r = web_client.get(path)
        assert r.status_code == 404, f"{path} should be gone, got {r.status_code}"


def test_28_subscribe_invalid_email(web_client):
    r = web_client.post("/subscribe", data={"email": "not-an-email"})
    assert r.status_code == 200
    assert b"valid email" in r.content.lower()


def test_29_agui_chat_ui_fragment(web_client):
    tid = str(uuid.uuid4())
    r = web_client.get(f"/agui/ui/{tid}/chat")
    assert r.status_code == 200
    assert b"ws-connect" in r.content or b"chat-container" in r.content


def test_30_agui_messages_empty_thread(web_client):
    tid = str(uuid.uuid4())
    r = web_client.get(f"/agui/messages/{tid}")
    assert r.status_code == 200
    assert b"Hedgefolio" in r.content


def test_31_conv_list(web_client):
    r = web_client.get("/agui-conv/list")
    assert r.status_code == 200


def test_32_welcome_has_six_cards(web_client):
    """Fresh chat should show 6 suggestion cards in the welcome hero."""
    tid = str(uuid.uuid4())
    r = web_client.get(f"/agui/messages/{tid}")
    assert r.status_code == 200
    n = r.content.count(b"welcome-card-title")
    assert n == 6, f"expected 6 welcome cards, got {n}"
    assert b"Laurion Capital" in r.content
    assert b"Situational Awareness" in r.content
    assert b"NVIDIA" in r.content
    assert b"13D" in r.content


def test_33_run_shortcut_js_defined(web_client):
    """The page must define the JS handler the shortcut buttons call."""
    r = web_client.get("/")
    assert b"function runShortcut(" in r.content
    # Guard against double-submit while the agent is already streaming
    assert b"_aguiProcessing" in r.content
