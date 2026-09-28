#!/usr/bin/env python3
"""Gate for the chat comparison tool (engel_chat_compare.py).

Runs the tool's offline selftest: payload safety (chat_only always true, training
opt-out declared), llama-cli transcript parsing, and thinking-block stripping. No
network and no model load - the live halves are exercised by real comparison runs,
whose receipts land in /opt/engel/reports/chat_compare/ on CT246.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import engel_chat_compare  # noqa: E402


def main() -> int:
    return engel_chat_compare.selftest()


if __name__ == "__main__":
    raise SystemExit(main())
