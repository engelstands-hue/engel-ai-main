#!/usr/bin/env python3
"""Build Engel's Meeting Room registry from the agency-agents catalog."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engel_agency_agents_registry import (  # noqa: E402
    AGENT_CARD_ROOT,
    REGISTRY_PATH,
    REPORT_PATH,
    build_registry,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root",
        default=None,
        help="Path to agency-agents-main root. Defaults to ENGEL_AGENCY_AGENTS_ROOT or the known D: path.",
    )
    parser.add_argument(
        "--no-copy-cards",
        action="store_true",
        help="Only rebuild JSON/report; do not refresh copied agent cards.",
    )
    args = parser.parse_args()

    payload = build_registry(args.source_root, copy_cards=not args.no_copy_cards)
    print("ENGEL_AGENCY_AGENTS_REGISTRY_BUILD_PASS")
    print(f"agents={payload.get('agent_count', 0)}")
    print(f"divisions={payload.get('division_count', 0)}")
    print(f"registry={REGISTRY_PATH}")
    print(f"cards={AGENT_CARD_ROOT}")
    print(f"report={REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
