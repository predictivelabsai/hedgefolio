"""SQLAlchemy connection pool for Hedgefolio.

Wraps the DB_URL env var with a pooled engine plus a session context manager.
The existing SQLAlchemy session helpers in `db_util` / `db_queries` remain
untouched for backwards compatibility — this pool is used by the AG-UI chat
store, the RAG retriever, and the FastHTML web app routes.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

logger = logging.getLogger(__name__)


class DatabasePool:
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv("DB_URL")
        if not self.database_url:
            raise ValueError("DB_URL is not set")
        self.engine = create_engine(
            self.database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
        self._session_factory = sessionmaker(bind=self.engine)

    @contextmanager
    def get_session(self) -> Session:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self):
        self.engine.dispose()


_pool: Optional[DatabasePool] = None


def get_pool() -> DatabasePool:
    global _pool
    if _pool is None:
        _pool = DatabasePool()
    return _pool
