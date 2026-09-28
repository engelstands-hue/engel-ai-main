#!/usr/bin/env python3
"""Verify the build-lane usability gate accepts compact protocol-correct
multi-file replies (2026-07-28 fix) without loosening its stub protections.

Root fixture is the exact failure shape from receipts
ENGEL_MAIN_SERVER_BUILD_LANE_20260728T{002909,003851}*.json: a structured
("large job") build whose reply used FILE: markers + closed bare fences but
was ~700 chars, below the old len>=2000 substantiality floor.
"""
from __future__ import annotations

import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
for entry in (str(ROOT), str(TOOLS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from engel_main_server_chat_http_service import (  # noqa: E402
    _build_lane_extracted_project_files_substantial,
    _build_lane_reply_usable,
)

CHECKS: list[tuple[str, bool]] = []


def check(name: str, ok: bool) -> None:
    CHECKS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


STRUCTURED_PROMPT = (
    "Generate the project files. This is a large job for the Engel build lane.\n"
    "Use FILE: markers with fenced contents."
)
SMALL_PROMPT = "Generate the project files for this small helper."

COMPACT_TWO_FILE_REPLY = """FILE: fibonacci.py
```
def fibonacci(n):
    \"\"\"Generate the first n Fibonacci numbers.\"\"\"
    fib_sequence = [0, 1]
    while len(fib_sequence) < n:
        fib_sequence.append(fib_sequence[-1] + fib_sequence[-2])
    return fib_sequence[:n]


if __name__ == "__main__":
    print(fibonacci(12))
```

FILE: test_fibonacci.py
```
from fibonacci import fibonacci


def test_first_twelve():
    assert fibonacci(12)[-1] == 89
    assert len(fibonacci(12)) == 12
```
"""

STUB_BODY_REPLY = """FILE: fibonacci.py
```
def fibonacci(n):
    return list(range(n))
```

FILE: test_fibonacci.py
```
pass
```
"""

NO_MARKER_REPLY = (
    "```python\n# fibonacci.py\ndef fibonacci(n):\n    return list(range(n))\n```\n"
    "```python\n# test_fibonacci.py\ndef test():\n    pass\n```\n"
)

LONG_TWO_MARKER_REPLY = (
    "FILE: app.py\n```\n" + "\n".join(f"VALUE_{i} = {i}" for i in range(80))
    + "\n```\n\nFILE: test_app.py\n```\nfrom app import VALUE_1\n\n"
    "def test_value():\n    assert VALUE_1 == 1\n```\n"
)


def main() -> int:
    # 1. the exact regression shape now passes
    check("compact_two_file_structured_usable",
          _build_lane_reply_usable(STRUCTURED_PROMPT, COMPACT_TWO_FILE_REPLY))
    check("compact_two_file_extractor_substantial",
          _build_lane_extracted_project_files_substantial(COMPACT_TWO_FILE_REPLY))

    # 2. stub protection retained: one-line/pass bodies do not count
    check("stub_bodies_still_rejected",
          not _build_lane_reply_usable(STRUCTURED_PROMPT, STUB_BODY_REPLY))

    # 3. (2026-07-28 salvage) the round-1 coder shape - fences headed by
    #    `# filename` comments, no FILE: markers - now extracts and passes.
    check("comment_filename_salvage_usable",
          _build_lane_reply_usable(STRUCTURED_PROMPT, NO_MARKER_REPLY))
    from engel_main_local_model_worker import _extract_project_files
    salvaged = _extract_project_files(NO_MARKER_REPLY, "entry.py")
    check("salvage_extracts_two_named_files",
          set(salvaged) == {"fibonacci.py", "test_fibonacci.py"})

    # 3b. salvage is all-or-nothing: one unnamed fence aborts it, so code
    #     examples in prose never become project files.
    mixed = NO_MARKER_REPLY + "```python\nprint('just an example')\n```\n"
    check("mixed_fences_do_not_salvage",
          not _build_lane_reply_usable(STRUCTURED_PROMPT, mixed))

    # 3c. salvage edge cases (2026-07-28 second pass): CRLF replies still
    #     salvage; a shebang head is a script body, not a filename, and
    #     aborts; duplicate filename heads collapse to the last body.
    crlf_reply = NO_MARKER_REPLY.replace("\n", "\r\n")
    crlf_files = _extract_project_files(crlf_reply, "entry.py")
    check("crlf_salvage_extracts",
          set(crlf_files) == {"fibonacci.py", "test_fibonacci.py"})
    shebang = ("```python\n#!/usr/bin/env python\nprint('a')\nprint('b')\n```\n"
               "```python\n# test_x.py\nimport x\n\ndef test():\n    pass\n```\n")
    check("shebang_head_aborts_salvage",
          not _build_lane_reply_usable(STRUCTURED_PROMPT, shebang))
    # Duplicate filename heads collapse to ONE unique name, which fails the
    # >=2-files salvage floor - ambiguous output falls through to the
    # conservative single-fence default-entry path instead of guessing.
    dup = ("```python\n# app.py\nprint('first')\nprint('one')\n```\n"
           "```python\n# app.py\nprint('second')\nprint('two')\n```\n")
    dup_files = _extract_project_files(dup, "entry.py")
    check("duplicate_heads_do_not_salvage",
          list(dup_files) == ["entry.py"])

    # 4. previously-accepted shapes unchanged
    check("long_two_marker_still_usable",
          _build_lane_reply_usable(STRUCTURED_PROMPT, LONG_TWO_MARKER_REPLY))
    check("small_job_single_fence_still_usable",
          _build_lane_reply_usable(
              SMALL_PROMPT,
              "```python\nprint('hello')\nprint('world')\n```",
          ))

    # 5. plan/review JSON stages unchanged
    check("plan_stage_json_usable",
          _build_lane_reply_usable(
              "Plan this Engel build now.",
              '{"files": [{"path": "a.py"}]}',
          ))
    check("review_stage_verdict_usable",
          _build_lane_reply_usable(
              "Review this completed Engel build.",
              '{"verdict": "pass"}',
          ))
    check("empty_reply_rejected",
          not _build_lane_reply_usable(STRUCTURED_PROMPT, "   "))

    failed = [name for name, ok in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
