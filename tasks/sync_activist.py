#!/usr/bin/env python3
"""Sync recent Schedule 13D / 13G filings from SEC EDGAR.

Run daily (cron) to ingest yesterday's activist / beneficial-ownership
filings. Also pulls the last N days on first run so a fresh deploy has a
useful backfill.

    python tasks/sync_activist.py                 # last 14 days
    python tasks/sync_activist.py --days 60       # last 60 days (initial)
    python tasks/sync_activist.py --enrich 200    # also resolve issuer headers
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.activist import enrich_subjects, sync_days


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14, help="How many calendar days back to fetch")
    ap.add_argument("--enrich", type=int, default=0,
                    help="After sync, fetch issuer headers for this many un-enriched rows")
    args = ap.parse_args()

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    logging.info("Syncing last %s days of SC 13D/G filings …", args.days)
    result = sync_days(days=args.days)
    logging.info("  filings_ingested=%s days_fetched=%s", result["filings_ingested"], result["days_fetched"])

    if args.enrich:
        logging.info("Enriching issuer headers (limit=%s) …", args.enrich)
        er = enrich_subjects(limit=args.enrich)
        logging.info("  enriched=%s of %s candidates", er["enriched"], er["total"])


if __name__ == "__main__":
    main()
