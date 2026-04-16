#!/usr/bin/env python3
"""Download the latest SEC Form 13F quarterly dataset and load it into the DB.

SEC publishes rolling 3-month Form 13F data sets at
``https://www.sec.gov/files/structureddata/data/form-13f-data-sets/``.
File naming is ``01<mon><yyyy>-<DD><mon><yyyy>_form13f.zip`` where the window
starts on the first of the month and ends on the last day of the third month.

This script:
  1. Probes the SEC URL space for the most recent available window.
  2. Downloads the zip into ``data/downloads/`` (with a User-Agent, as SEC
     requires for any automated fetch).
  3. Unpacks the TSVs + chunks into ``data/``.
  4. Runs the SQLAlchemy loaders from ``utils.db_util.load_all_data``.
  5. Prints row counts so you can confirm the ingest.

Intended to be run offline / from cron — it takes ~10-30 minutes end-to-end
for a full quarter depending on how big INFOTABLE is.
"""

from __future__ import annotations

import calendar
import logging
import os
import shutil
import sys
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Optional

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from utils.db_pool import get_pool
from utils.db_util import DB_SCHEMA, create_tables, get_engine, load_all_data

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

SEC_BASE = "https://www.sec.gov/files/structureddata/data/form-13f-data-sets"
USER_AGENT = os.getenv(
    "SEC_USER_AGENT",
    "Hedgefolio/0.1 (kaljuvee@gmail.com)",
)
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOWNLOAD_DIR = DATA_DIR / "downloads"


# ---------------------------------------------------------------------------
# URL enumeration
# ---------------------------------------------------------------------------

def _last_day(y: int, m: int) -> int:
    return calendar.monthrange(y, m)[1]


def _window_url(start: date) -> tuple[str, str]:
    """Return (filename, url) for the 3-month window starting on ``start``."""
    assert start.day == 1
    y1, m1 = start.year, start.month
    m3 = m1 + 2
    y3 = y1
    if m3 > 12:
        m3 -= 12
        y3 += 1
    end = date(y3, m3, _last_day(y3, m3))
    mon_s = calendar.month_abbr[m1].lower()
    mon_e = calendar.month_abbr[m3].lower()
    name = f"01{mon_s}{y1}-{end.day:02d}{mon_e}{y3}_form13f.zip"
    return name, f"{SEC_BASE}/{name}"


def _quarter_starts(n: int = 12) -> Iterable[date]:
    """Yield the first-of-month start dates for SEC 13F windows, newest first."""
    today = date.today()
    m = ((today.month - 1) // 3) * 3 + 1  # current quarter start
    y = today.year
    # Walk back: SEC windows are Mar/Jun/Sep/Dec starts.
    starts: list[date] = []
    candidates = [(y, 12), (y, 9), (y, 6), (y, 3),
                  (y - 1, 12), (y - 1, 9), (y - 1, 6), (y - 1, 3),
                  (y - 2, 12), (y - 2, 9), (y - 2, 6), (y - 2, 3)]
    # Filter to windows whose END date is not in the future.
    for (yy, mm) in candidates:
        end_month = mm + 2
        end_year = yy
        if end_month > 12:
            end_month -= 12
            end_year += 1
        end = date(end_year, end_month, _last_day(end_year, end_month))
        if end <= today:
            starts.append(date(yy, mm, 1))
    # Newest first, limit.
    return starts[:n]


def find_latest_url(session: requests.Session) -> tuple[str, str]:
    """HEAD-probe SEC windows newest→oldest and return the first 200."""
    for start in _quarter_starts():
        name, url = _window_url(start)
        r = session.head(url, allow_redirects=True, timeout=30)
        if r.status_code == 200:
            logger.info("Latest available window: %s (%s bytes)", name,
                        r.headers.get("Content-Length", "?"))
            return name, url
    raise RuntimeError("No recent SEC 13F dataset found")


# ---------------------------------------------------------------------------
# Download + extract
# ---------------------------------------------------------------------------

def download(url: str, dest: Path, session: requests.Session) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    logger.info("Downloading %s → %s", url, dest)
    with session.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        last_report = time.time()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                if not chunk:
                    continue
                f.write(chunk)
                done += len(chunk)
                now = time.time()
                if now - last_report > 5:
                    pct = (done / total * 100) if total else 0
                    logger.info("  ... %.1f%% (%d / %d MB)",
                                pct, done // (1 << 20), total // (1 << 20))
                    last_report = now
    tmp.rename(dest)
    logger.info("Download complete: %s (%d MB)", dest, dest.stat().st_size // (1 << 20))


def extract(zip_path: Path, target: Path) -> list[Path]:
    target.mkdir(parents=True, exist_ok=True)
    logger.info("Extracting %s → %s", zip_path, target)
    extracted: list[Path] = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            # Flatten nested paths: keep only the basename.
            out_path = target / Path(info.filename).name
            with zf.open(info) as src, open(out_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted.append(out_path)
            logger.info("  wrote %s (%d MB)", out_path.name,
                        out_path.stat().st_size // (1 << 20))
    return extracted


# ---------------------------------------------------------------------------
# DB load
# ---------------------------------------------------------------------------

def verify_counts() -> dict[str, int]:
    tables = ["submission", "coverpage", "summarypage", "signature",
              "othermanager", "othermanager2", "infotable", "company_ticker"]
    pool = get_pool()
    counts: dict[str, int] = {}
    with pool.get_session() as s:
        for t in tables:
            try:
                counts[t] = s.execute(
                    text(f"SELECT COUNT(*) FROM {DB_SCHEMA}.{t}")
                ).scalar() or 0
            except Exception as e:  # noqa: BLE001
                logger.warning("count %s failed: %s", t, e)
                counts[t] = -1
    return counts


def load_to_db() -> None:
    logger.info("Creating tables if absent …")
    create_tables(get_engine())
    logger.info("Loading data from %s into schema %s …", DATA_DIR, DB_SCHEMA)
    load_all_data(str(DATA_DIR))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(url_override: Optional[str] = None, *, skip_download: bool = False,
         skip_load: bool = False) -> None:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/zip, */*",
    })

    if skip_download:
        logger.info("--skip-download: reusing existing files in %s", DATA_DIR)
    else:
        if url_override:
            name = Path(url_override).name
            url = url_override
            logger.info("Using explicit URL: %s", url)
        else:
            name, url = find_latest_url(session)
        zip_path = DOWNLOAD_DIR / name
        if zip_path.exists() and zip_path.stat().st_size > 1_000_000:
            logger.info("Reusing cached zip: %s", zip_path)
        else:
            download(url, zip_path, session)
        extract(zip_path, DATA_DIR)

    if skip_load:
        logger.info("--skip-load: stopping before DB ingest")
        return

    load_to_db()
    counts = verify_counts()
    logger.info("Row counts per table:")
    for t, c in counts.items():
        logger.info("  %-16s %10d", t, c)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="Explicit SEC 13F zip URL to use")
    ap.add_argument("--skip-download", action="store_true",
                    help="Skip download; reuse data/*.tsv already on disk")
    ap.add_argument("--skip-load", action="store_true",
                    help="Skip the DB load phase (download + extract only)")
    args = ap.parse_args()
    main(url_override=args.url, skip_download=args.skip_download,
         skip_load=args.skip_load)
