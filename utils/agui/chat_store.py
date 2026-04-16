"""Chat persistence for Hedgefolio — conversations + messages in Postgres."""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy import text

from utils.db_pool import get_pool

logger = logging.getLogger(__name__)

SCHEMA = "hedgefolio"


def save_conversation(thread_id: str, user_id: Optional[str] = None,
                      title: Optional[str] = None) -> None:
    """Upsert a conversation. If title is None, only update updated_at."""
    with get_pool().get_session() as s:
        if title is not None:
            s.execute(
                text(
                    f"""
                    INSERT INTO {SCHEMA}.chat_conversations (thread_id, user_id, title)
                    VALUES (CAST(:tid AS UUID), :uid, :title)
                    ON CONFLICT (thread_id) DO UPDATE
                        SET title = :title, updated_at = NOW()
                    """
                ),
                {"tid": thread_id, "uid": user_id, "title": title},
            )
        else:
            s.execute(
                text(
                    f"""
                    INSERT INTO {SCHEMA}.chat_conversations (thread_id, user_id, title)
                    VALUES (CAST(:tid AS UUID), :uid, 'New chat')
                    ON CONFLICT (thread_id) DO UPDATE SET updated_at = NOW()
                    """
                ),
                {"tid": thread_id, "uid": user_id},
            )


def save_message(thread_id: str, role: str, content: str,
                 message_id: Optional[str] = None,
                 metadata: Optional[dict] = None) -> None:
    mid = message_id or str(uuid.uuid4())
    with get_pool().get_session() as s:
        s.execute(
            text(
                f"""
                INSERT INTO {SCHEMA}.chat_messages (thread_id, message_id, role, content, metadata)
                VALUES (CAST(:tid AS UUID), CAST(:mid AS UUID), :role, :content, CAST(:meta AS JSONB))
                ON CONFLICT (message_id) DO NOTHING
                """
            ),
            {
                "tid": thread_id,
                "mid": mid,
                "role": role,
                "content": content,
                "meta": None if metadata is None else __import__("json").dumps(metadata),
            },
        )


def load_conversation_messages(thread_id: str) -> list[dict]:
    with get_pool().get_session() as s:
        rows = s.execute(
            text(
                f"""
                SELECT message_id, role, content, metadata, created_at
                FROM {SCHEMA}.chat_messages
                WHERE thread_id = CAST(:tid AS UUID)
                ORDER BY created_at ASC
                """
            ),
            {"tid": thread_id},
        ).fetchall()
    return [
        {
            "message_id": str(r[0]),
            "role": r[1],
            "content": r[2],
            "metadata": r[3],
            "created_at": r[4],
        }
        for r in rows
    ]


def list_conversations(user_id: Optional[str] = None, limit: int = 20) -> list[dict]:
    with get_pool().get_session() as s:
        if user_id:
            rows = s.execute(
                text(
                    f"""
                    SELECT c.thread_id, c.title, c.updated_at,
                           (SELECT content FROM {SCHEMA}.chat_messages m
                             WHERE m.thread_id = c.thread_id AND m.role = 'user'
                             ORDER BY m.created_at ASC LIMIT 1) AS first_msg
                    FROM {SCHEMA}.chat_conversations c
                    WHERE c.user_id = :uid
                    ORDER BY c.updated_at DESC
                    LIMIT :lim
                    """
                ),
                {"uid": user_id, "lim": limit},
            ).fetchall()
        else:
            rows = s.execute(
                text(
                    f"""
                    SELECT c.thread_id, c.title, c.updated_at,
                           (SELECT content FROM {SCHEMA}.chat_messages m
                             WHERE m.thread_id = c.thread_id AND m.role = 'user'
                             ORDER BY m.created_at ASC LIMIT 1) AS first_msg
                    FROM {SCHEMA}.chat_conversations c
                    WHERE c.user_id IS NULL
                    ORDER BY c.updated_at DESC
                    LIMIT :lim
                    """
                ),
                {"lim": limit},
            ).fetchall()
    return [
        {
            "thread_id": str(r[0]),
            "title": r[1],
            "updated_at": r[2],
            "first_msg": r[3],
        }
        for r in rows
    ]


def delete_conversation(thread_id: str) -> None:
    with get_pool().get_session() as s:
        s.execute(
            text(f"DELETE FROM {SCHEMA}.chat_conversations WHERE thread_id = CAST(:tid AS UUID)"),
            {"tid": thread_id},
        )
