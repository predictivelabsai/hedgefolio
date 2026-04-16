"""Schedule 13D/13G activist-filing tracker.

Data source: SEC EDGAR daily index files.
    https://www.sec.gov/Archives/edgar/daily-index/YYYY/QTRQ/form.YYYYMMDD.idx

The index lists every filing for the day in fixed-width columns:
    [Form Type: 17][Company Name: 62][CIK: 12][Date Filed: 12][File Name: rest]

We harvest only SC 13D, SC 13D/A, SC 13G, SC 13G/A — beneficial-ownership
reports for >5% stakes. 13D is the classic "activist" flavor (intends to
influence management). 13G is the passive-holder variant.

Enrichment is a separate step: after indexing the filer, we can fetch each
filing's SGML header to populate the subject company (the issuer the filer
has accumulated). That takes one HTTP request per filing, so it runs on a
separate pass governed by `enrich_subjects()`.
"""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import date, timedelta
from typing import Iterable, Iterator, Optional

import requests
from sqlalchemy import text

from utils.db_pool import get_pool

logger = logging.getLogger(__name__)

USER_AGENT = os.getenv(
    "SEC_USER_AGENT",
    "Hedgefolio/0.1 (kaljuvee@gmail.com)",
)

# Activist (13D) + passive (13G) schedules.
# EDGAR daily indices label these "SCHEDULE 13D", "SCHEDULE 13G", etc.
# (The "SC 13D" shorthand is used in some other SEC contexts, but not here.)
ACTIVIST_FORMS = {
    "SCHEDULE 13D", "SCHEDULE 13D/A",
    "SCHEDULE 13G", "SCHEDULE 13G/A",
}

IDX_URL = "https://www.sec.gov/Archives/edgar/daily-index/{year}/QTR{q}/form.{yyyymmdd}.idx"
ARCHIVE_URL = "https://www.sec.gov/Archives/{path}"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"})
    return s


# ---------------------------------------------------------------------------
# Index parser
# ---------------------------------------------------------------------------

_DASH_RE = re.compile(r"^-{10,}$")


def _parse_index_lines(text_body: str) -> Iterator[tuple[str, str, str, date, str]]:
    """Yield (form_type, company, cik, filing_date, path) for each row."""
    past_header = False
    for raw in text_body.splitlines():
        if not past_header:
            if _DASH_RE.match(raw.strip()):
                past_header = True
            continue
        if not raw.strip():
            continue
        # Line shorter than expected? skip.
        if len(raw) < 50:
            continue
        form_type = raw[:17].strip()
        if form_type not in ACTIVIST_FORMS:
            continue
        company = raw[17:79].strip()
        cik = raw[79:91].strip()
        date_str = raw[91:103].strip()
        path = raw[103:].strip()
        try:
            fd = date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
        except (ValueError, IndexError):
            continue
        yield form_type, company, cik, fd, path


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

_INSERT_SQL = text(
    """
    INSERT INTO hedgefolio.activist_filing
        (accession_number, form_type, is_amendment, is_activist,
         filer_cik, filer_name, filing_date, filing_url, index_path)
    VALUES (:acc, :form, :amend, :activist, :cik, :name, :fd, :url, :path)
    ON CONFLICT (accession_number) DO UPDATE SET
        form_type = EXCLUDED.form_type,
        is_amendment = EXCLUDED.is_amendment,
        is_activist = EXCLUDED.is_activist,
        filer_cik = EXCLUDED.filer_cik,
        filer_name = EXCLUDED.filer_name,
        filing_date = EXCLUDED.filing_date,
        filing_url = EXCLUDED.filing_url,
        index_path = EXCLUDED.index_path,
        updated_at = NOW()
    """
)


def _accession_from_path(path: str) -> Optional[str]:
    """Extract the 20-char accession from a path like
    ``edgar/data/1128250/0001140361-26-014708.txt``.
    """
    base = path.rsplit("/", 1)[-1]
    if base.endswith(".txt"):
        base = base[:-4]
    if re.fullmatch(r"\d{10}-\d{2}-\d{6}", base):
        return base
    return None


def _upsert_filings(rows: Iterable[tuple[str, str, str, date, str]]) -> int:
    inserted = 0
    pool = get_pool()
    with pool.get_session() as s:
        for form_type, company, cik, fd, path in rows:
            acc = _accession_from_path(path)
            if not acc:
                continue
            is_amend = form_type.endswith("/A")
            is_activist = "13D" in form_type
            url = ARCHIVE_URL.format(path=path)
            s.execute(
                _INSERT_SQL,
                {
                    "acc": acc,
                    "form": form_type,
                    "amend": is_amend,
                    "activist": is_activist,
                    "cik": cik,
                    "name": company[:250],
                    "fd": fd,
                    "url": url,
                    "path": path,
                },
            )
            inserted += 1
    return inserted


# ---------------------------------------------------------------------------
# Daily sync
# ---------------------------------------------------------------------------

def sync_days(days: int = 14, session: Optional[requests.Session] = None) -> dict:
    """Ingest the last N days of EDGAR daily indices.

    Returns a dict with filings_ingested and days_fetched.
    """
    sess = session or _session()
    today = date.today()
    total = 0
    fetched_days = 0
    for delta in range(days):
        d = today - timedelta(days=delta)
        # Skip weekends (EDGAR daily index only exists on business days).
        if d.weekday() >= 5:
            continue
        q = (d.month - 1) // 3 + 1
        url = IDX_URL.format(year=d.year, q=q, yyyymmdd=d.strftime("%Y%m%d"))
        try:
            r = sess.get(url, timeout=30)
        except requests.RequestException as e:
            logger.warning("daily index fetch failed for %s: %s", d, e)
            continue
        if r.status_code in (403, 404):
            # SEC returns 403 for days whose index has not been generated yet
            # (today-of, before EOD) and 404 for pure gaps.
            logger.info("no daily index for %s (status %s)", d, r.status_code)
            continue
        if r.status_code >= 400:
            logger.warning("daily index %s returned %s", d, r.status_code)
            continue
        rows = list(_parse_index_lines(r.text))
        n = _upsert_filings(rows)
        total += n
        fetched_days += 1
        logger.info("  %s → %s activist filings", d, n)
        # Be kind to SEC.
        time.sleep(0.2)
    return {"filings_ingested": total, "days_fetched": fetched_days}


# ---------------------------------------------------------------------------
# Subject enrichment
# ---------------------------------------------------------------------------

_SUBJECT_RE = re.compile(
    r"SUBJECT COMPANY:.*?COMPANY CONFORMED NAME:\s*(.+?)\s*(?:\r?\n)"
    r".*?CENTRAL INDEX KEY:\s*(\d+)",
    re.DOTALL,
)


def _fetch_subject(accession: str, path: str, sess: requests.Session) -> Optional[tuple[str, str]]:
    url = ARCHIVE_URL.format(path=path)
    try:
        r = sess.get(url, timeout=30, stream=True)
        r.raise_for_status()
    except requests.RequestException as e:
        logger.warning("fetch %s failed: %s", url, e)
        return None
    # Only read the header region — the SGML wrapper is at the top of the .txt.
    buf = []
    total = 0
    for chunk in r.iter_content(chunk_size=8192, decode_unicode=True):
        if not isinstance(chunk, str):
            chunk = chunk.decode("utf-8", errors="replace")
        buf.append(chunk)
        total += len(chunk)
        if total > 200_000 or "</SEC-HEADER>" in "".join(buf[-3:]):
            break
    header = "".join(buf)
    m = _SUBJECT_RE.search(header)
    if not m:
        return None
    return m.group(1).strip()[:250], m.group(2).strip().zfill(10)


def enrich_subjects(limit: int = 100, sleep: float = 0.25) -> dict:
    """Populate subject_name / subject_cik for filings that lack them."""
    pool = get_pool()
    with pool.get_session() as s:
        rows = s.execute(
            text(
                """
                SELECT accession_number, index_path
                FROM hedgefolio.activist_filing
                WHERE subject_name IS NULL
                ORDER BY filing_date DESC
                LIMIT :lim
                """
            ),
            {"lim": limit},
        ).fetchall()
    if not rows:
        return {"enriched": 0, "total": 0}
    sess = _session()
    enriched = 0
    pool = get_pool()
    with pool.get_session() as s:
        for acc, path in rows:
            got = _fetch_subject(acc, path, sess)
            if not got:
                time.sleep(sleep)
                continue
            sub_name, sub_cik = got
            s.execute(
                text(
                    """
                    UPDATE hedgefolio.activist_filing
                    SET subject_name = :name, subject_cik = :cik, updated_at = NOW()
                    WHERE accession_number = :acc
                    """
                ),
                {"name": sub_name, "cik": sub_cik, "acc": acc},
            )
            enriched += 1
            time.sleep(sleep)
    return {"enriched": enriched, "total": len(rows)}


# ---------------------------------------------------------------------------
# Queries (used by web routes + agent tools)
# ---------------------------------------------------------------------------

def recent_filings(limit: int = 50, activist_only: bool = False, days: int = 30) -> list[dict]:
    pool = get_pool()
    where = ["filing_date >= CURRENT_DATE - make_interval(days => :days)"]
    params = {"lim": limit, "days": int(days)}
    if activist_only:
        where.append("is_activist = TRUE")
    with pool.get_session() as s:
        rows = s.execute(
            text(
                f"""
                SELECT accession_number, form_type, filing_date,
                       filer_name, filer_cik,
                       subject_name, subject_cik, filing_url
                FROM hedgefolio.activist_filing
                WHERE {' AND '.join(where)}
                ORDER BY filing_date DESC, accession_number DESC
                LIMIT :lim
                """
            ),
            params,
        ).fetchall()
    return [
        {
            "accession_number": r[0],
            "form_type": r[1],
            "filing_date": r[2],
            "filer_name": r[3],
            "filer_cik": r[4],
            "subject_name": r[5],
            "subject_cik": r[6],
            "filing_url": r[7],
        }
        for r in rows
    ]


def search_activist(query: str, limit: int = 50) -> list[dict]:
    pool = get_pool()
    q = f"%{query}%"
    with pool.get_session() as s:
        rows = s.execute(
            text(
                """
                SELECT accession_number, form_type, filing_date,
                       filer_name, filer_cik, subject_name, subject_cik, filing_url
                FROM hedgefolio.activist_filing
                WHERE filer_name ILIKE :q OR subject_name ILIKE :q
                ORDER BY filing_date DESC
                LIMIT :lim
                """
            ),
            {"q": q, "lim": limit},
        ).fetchall()
    return [
        {
            "accession_number": r[0],
            "form_type": r[1],
            "filing_date": r[2],
            "filer_name": r[3],
            "filer_cik": r[4],
            "subject_name": r[5],
            "subject_cik": r[6],
            "filing_url": r[7],
        }
        for r in rows
    ]


def activist_stats(days: int = 30) -> dict:
    pool = get_pool()
    with pool.get_session() as s:
        row = s.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (WHERE form_type = 'SCHEDULE 13D') AS cnt_13d,
                    COUNT(*) FILTER (WHERE form_type = 'SCHEDULE 13D/A') AS cnt_13d_a,
                    COUNT(*) FILTER (WHERE form_type = 'SCHEDULE 13G') AS cnt_13g,
                    COUNT(*) FILTER (WHERE form_type = 'SCHEDULE 13G/A') AS cnt_13g_a,
                    COUNT(DISTINCT filer_cik) AS unique_filers,
                    MAX(filing_date) AS most_recent
                FROM hedgefolio.activist_filing
                WHERE filing_date >= CURRENT_DATE - make_interval(days => :days)
                """
            ),
            {"days": int(days)},
        ).fetchone()
    return {
        "cnt_13d": row[0] or 0,
        "cnt_13d_a": row[1] or 0,
        "cnt_13g": row[2] or 0,
        "cnt_13g_a": row[3] or 0,
        "unique_filers": row[4] or 0,
        "most_recent": row[5],
        "days": days,
    }
