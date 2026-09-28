#!/usr/bin/env python3
"""Stamp Wiki One Journal after landing CODE. Requires --wiki-read."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engel_wiki_one import stamp_journal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Stamp Wiki One Journal after CODE")
    parser.add_argument("--wiki-read", action="store_true", help="assert wiki/ONE.md was read")
    parser.add_argument("--lane", required=True)
    parser.add_argument("--worker", required=True)
    parser.add_argument("--organs", required=True, help="comma-separated organ ids")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--files", default="", help="semicolon-separated relative paths")
    parser.add_argument("--receipt", default="")
    args = parser.parse_args()
    result = stamp_journal(
        lane=args.lane,
        worker=args.worker,
        organs=[part.strip() for part in args.organs.split(",") if part.strip()],
        summary=args.summary,
        files=[part.strip() for part in args.files.replace(",", ";").split(";") if part.strip()],
        receipt=args.receipt,
        wiki_read=bool(args.wiki_read),
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
