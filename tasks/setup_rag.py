"""Bootstrap the hedgefolio_rag schema and ingest F13 reference docs."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.rag import ingest_all


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    result = ingest_all()
    print(f"RAG ingestion complete: {result}")


if __name__ == "__main__":
    main()
