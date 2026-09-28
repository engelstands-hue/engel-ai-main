#!/usr/bin/env python3
"""Disabled historical refactoring template.

This file used to contain a copy-paste provider-driven refactoring example.
It is kept only as an explicit tombstone so old references do not turn into a
live provider/API path. Use Engel's guarded code companion and REPS flows for
real refactor work.
"""

from __future__ import annotations


MESSAGE = """Refactoring Queen is retired.

Current route:
- use Engel code companion / REPS review flow
- keep source edits scoped and verifier-covered
- do not run provider/API refactor agents from this historical template
"""


def main() -> int:
    print(MESSAGE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
