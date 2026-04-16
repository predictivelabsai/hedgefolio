"""Shared fixtures for the hedgefolio regression test suite.

Most tests are data-dependent. They skip automatically if the relevant table
is empty, so the suite can run against a fresh DB without failing — the
failures you really want to catch are wiring/import errors and schema drift,
not "no 13F data yet".
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Ensure the repo root is on sys.path so `import utils...` works from any dir.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env before any util imports (they call load_dotenv() themselves,
# but being explicit here keeps test behavior predictable).
load_dotenv(ROOT / ".env")


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def db_pool():
    from utils.db_pool import get_pool
    if not os.getenv("DB_URL"):
        pytest.skip("DB_URL not set")
    return get_pool()


@pytest.fixture(scope="session")
def db_ok(db_pool):
    """Ensures DB is reachable; returns True or skips the whole session."""
    from sqlalchemy import text
    try:
        with db_pool.get_session() as s:
            s.execute(text("SELECT 1")).scalar()
    except Exception as e:
        pytest.skip(f"DB unreachable: {e}")
    return True


def _count(db_pool, table_fqn: str) -> int:
    """Row count of a fully-qualified table; -1 if the table doesn't exist."""
    from sqlalchemy import text
    try:
        with db_pool.get_session() as s:
            return s.execute(text(f"SELECT COUNT(*) FROM {table_fqn}")).scalar() or 0
    except Exception:
        return -1


@pytest.fixture(scope="session")
def has_13f_data(db_pool, db_ok) -> bool:
    return _count(db_pool, "hedgefolio.infotable") > 0


@pytest.fixture(scope="session")
def has_activist_data(db_pool, db_ok) -> bool:
    return _count(db_pool, "hedgefolio.activist_filing") > 0


@pytest.fixture(scope="session")
def has_rag_data(db_pool, db_ok) -> bool:
    return _count(db_pool, "hedgefolio_rag.chunks") > 0


# ---------------------------------------------------------------------------
# Web test client (Starlette is the underlying framework for FastHTML)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def web_client():
    from starlette.testclient import TestClient

    # Import the app lazily so pytest collection doesn't fail when env is weird.
    os.environ.setdefault("JWT_SECRET", "test-jwt-secret-please-ignore")
    import web_app
    return TestClient(web_app.app)
