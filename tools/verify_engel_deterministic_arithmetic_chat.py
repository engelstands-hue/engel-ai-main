#!/usr/bin/env python3
"""Verify conversational arithmetic stays deterministic without broadening scope."""

from __future__ import annotations

import engel_main_server_chat_http_service as service


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    conversational = "Hi Engel. What is 2 + 2? Answer in one short sentence."
    require(
        service._prompt_is_simple_arithmetic_chat(conversational),
        "conversational arithmetic was not recognized",
    )
    require(
        service._safe_arithmetic_answer(conversational) == "2 + 2 = 4",
        "conversational arithmetic did not use the deterministic answer",
    )
    require(
        service._safe_arithmetic_answer("Call me at 555-1234") is None,
        "phone number was misclassified as subtraction",
    )
    require(
        service._safe_arithmetic_answer("Compare the 2020-2021 results") is None,
        "date range was misclassified as subtraction",
    )
    require(
        service._safe_arithmetic_answer("Ticket 100-50 is delayed") is None,
        "ticket identifier was misclassified as subtraction",
    )
    print("PASS: conversational arithmetic is deterministic and identifiers stay excluded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
