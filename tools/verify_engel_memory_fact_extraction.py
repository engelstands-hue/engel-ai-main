#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from engel_main_server_chat_http_service import _extract_fact_clause, _saved_facts


def main() -> int:
    prompt = (
        "I care about drawings that anticipate the build, not drawings that only "
        "look finished. Remember that distinction."
    )
    fact = _extract_fact_clause(prompt)
    assert fact.startswith("I care about drawings that anticipate the build"), fact
    assert fact != "distinction", fact
    assert _extract_fact_clause("Remember that I prefer direct answers.") == (
        "I prefer direct answers"
    )
    assert "distinction" not in {
        str(item.get("fact") or "").casefold() for item in _saved_facts()
    }
    print("VERIFY_ENGEL_MEMORY_FACT_EXTRACTION: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
