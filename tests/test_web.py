"""HTTP endpoint regression tests (starlette TestClient against web_app.app)."""

from __future__ import annotations

import uuid

import pytest


def test_23_health_endpoint(web_client):
    r = web_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] is True
    # agent True depends on XAI_API_KEY; we assert key exists rather than value
    assert "agent" in body


def test_24_home_page_renders(web_client):
    r = web_client.get("/")
    assert r.status_code == 200
    assert b"Hedgefolio" in r.content
    assert b"app-layout" in r.content
    # Left nav must include both chat + activist + charts links
    assert b"Activist Filings" in r.content
    assert b"Portfolio Treemap" in r.content


def test_25_activist_page_renders(web_client, has_activist_data):
    r = web_client.get("/activist")
    assert r.status_code == 200
    # Page always renders — it shows a "not built yet" card if no data.
    assert b"Activist Filings" in r.content
    if has_activist_data:
        # Some badge should be present; 13D badge class lives on .badge-red
        assert b"SCHEDULE 13" in r.content


def test_26_activist_filter_13d(web_client, has_activist_data):
    if not has_activist_data:
        pytest.skip("no activist data")
    r = web_client.get("/activist?form_filter=13d&days=30")
    assert r.status_code == 200
    assert b"SCHEDULE 13D" in r.content


def test_27_activist_search(web_client, has_activist_data):
    if not has_activist_data:
        pytest.skip("no activist data")
    r = web_client.get("/activist?q=LLC")
    assert r.status_code == 200
    assert b"LLC" in r.content.upper()


def test_28_chart_pages_render(web_client):
    for path in ("/charts/popular", "/charts/concentration",
                 "/charts/types", "/charts/treemap"):
        r = web_client.get(path)
        assert r.status_code == 200, f"{path} returned {r.status_code}"


def test_29_subscribe_invalid_email(web_client):
    r = web_client.post("/subscribe", data={"email": "not-an-email"})
    assert r.status_code == 200
    assert b"valid email" in r.content.lower()


def test_30_agui_chat_ui_fragment(web_client):
    tid = str(uuid.uuid4())
    r = web_client.get(f"/agui/ui/{tid}/chat")
    assert r.status_code == 200
    # Chat widget should bring in the WebSocket connect attribute.
    assert b"ws-connect" in r.content or b"chat-container" in r.content


def test_31_agui_messages_empty_thread(web_client):
    tid = str(uuid.uuid4())
    r = web_client.get(f"/agui/messages/{tid}")
    assert r.status_code == 200
    # Empty thread returns the welcome hero.
    assert b"Hedgefolio" in r.content


def test_32_conv_list(web_client):
    r = web_client.get("/agui-conv/list")
    assert r.status_code == 200


def test_33_welcome_has_six_cards(web_client):
    """Fresh chat should show 6 suggestion cards in the welcome hero."""
    import uuid
    tid = str(uuid.uuid4())
    r = web_client.get(f"/agui/messages/{tid}")
    assert r.status_code == 200
    n = r.content.count(b"welcome-card-title")
    assert n == 6, f"expected 6 welcome cards, got {n}"
    # And the prompts we advertise are all present
    assert b"Laurion Capital" in r.content
    assert b"Situational Awareness" in r.content
    assert b"NVIDIA" in r.content
    assert b"13D" in r.content
