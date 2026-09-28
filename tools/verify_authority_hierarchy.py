#!/usr/bin/env python3
"""
verify_authority_hierarchy.py

Read-only verifier for Engel authority order:

    Josh > Guardian > Engel/runtime

This verifier checks current steering docs for the explicit hierarchy and
flags nearby unsafe authority inversions only. It does not modify files,
call providers/network, start workers, mutate queues, write trusted memory,
or touch ALIVE_STATE.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()

FILES_TO_CHECK = [
    ROOT / "AGENTS.md",
    ROOT / "memory" / "ENGEL_CORE_DIRECTION_AND_SAFETY_CONSTITUTION_V1.md",
    ROOT / "memory" / "PROJECT_MEMORY_INDEX_V2V.md",
    ROOT / "memory" / "ENGEL_COMMANDS.md",
]

# (2026-07-28) The static system prompt was RETIRED with the
# "retired_static_sources_20260624" goal state; the served prompt now lives in
# code (train/serve-aligned _BASE_SYSTEM_PROMPT). Keep scanning the legacy
# file for authority inversions IF it ever reappears, but its absence is the
# expected state, not a failure.
OPTIONAL_LEGACY_FILES = [
    ROOT / "prompts" / "ENGEL_SYSTEM.md",
]

REQUIRED_CANONICAL_PHRASES = [
    "Josh > Guardian > Engel/runtime",
]

REQUIRED_CONCEPT_PATTERNS = [
    r"Josh.{0,120}(final|highest).{0,120}authority",
    r"Guardian.{0,120}(safety|governance|review).{0,120}(layer|gate|gatekeeper).{0,120}below\s+Josh",
    r"Engel/runtime|Engel runtime",
    r"(Engel/runtime|Engel runtime|Engel/runtime systems).{0,160}(below|remain below).{0,80}both",
]

# Tight phrasing avoids false positives on safe text such as "above Engel/runtime"
# or the substring "runtime" inside "Engel/runtime".
_STANDALONE_RUNTIME = r"(?<!Engel/)runtime\b"

FORBIDDEN_NEARBY_PATTERNS = [
    r"Guardian\s*>\s*Josh",
    r"Engel\s*>\s*Guardian",
    r"Engel/runtime\s*>\s*Guardian",
    r"runtime\s*>\s*Guardian",
    r"Engel\s*>\s*Josh",
    r"Engel/runtime\s*>\s*Josh",
    r"runtime\s*>\s*Josh",
    r"Guardian.{1,200}\babove\s+Josh\b",
    r"Guardian.{1,200}\b(override|overrule)\s+Josh\b",
    r"Guardian\s+and\s+Josh",
    r"Josh\s+and\s+Guardian",
    r"Guardian/Josh",
    r"Josh/Guardian",
    r"Guardian\s*\+\s*Josh",
    r"Josh\s*\+\s*Guardian",
    r"\bEngel(?:/runtime)?\b.{1,200}\babove\s+Guardian\b",
    r"\bEngel(?:/runtime)?\b.{1,200}\babove\s+Josh\b",
    rf"{_STANDALONE_RUNTIME}.{{1,200}}\babove\s+Guardian\b",
    rf"{_STANDALONE_RUNTIME}.{{1,200}}\babove\s+Josh\b",
    r"\bEngel(?:/runtime)?\b.{1,200}\bbypass\s+Guardian\b",
    r"\bEngel(?:/runtime)?\b.{1,200}\bbypass\s+Josh\b",
    rf"{_STANDALONE_RUNTIME}.{{1,200}}\bbypass\s+Guardian\b",
    rf"{_STANDALONE_RUNTIME}.{{1,200}}\bbypass\s+Josh\b",
    r"autonomy.{1,200}\bcross\b.{1,200}\bgates?\b.{1,200}\bwithout\b.{1,200}\bJosh\b",
    rf"{_STANDALONE_RUNTIME}.{{1,200}}\bcross\b.{{1,200}}\bgates?\b.{{1,200}}\bwithout\b.{{1,200}}\bJosh\b",
]


def read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def check_required_files() -> tuple[dict[Path, str], list[str]]:
    failures: list[str] = []
    file_texts: dict[Path, str] = {}

    for path in FILES_TO_CHECK:
        try:
            file_texts[path] = read_text(path)
            print(f"[authority] read: {path.relative_to(ROOT)}")
        except FileNotFoundError as exc:
            failures.append(str(exc))

    for path in OPTIONAL_LEGACY_FILES:
        try:
            if path.exists():
                file_texts[path] = path.read_text(encoding="utf-8", errors="replace")
                print(f"[authority] read (legacy, optional): {path.relative_to(ROOT)}")
            else:
                print(f"[authority] retired static source absent as expected: "
                      f"{path.relative_to(ROOT)}")
        except OSError as exc:
            failures.append(f"optional legacy file unreadable: {path} ({exc})")

    return file_texts, failures


def check_required_phrases(all_text: str) -> list[str]:
    failures: list[str] = []

    for phrase in REQUIRED_CANONICAL_PHRASES:
        if phrase not in all_text:
            failures.append(f"Missing required canonical phrase: {phrase}")

    return failures


def check_required_concepts(all_text: str) -> list[str]:
    failures: list[str] = []
    text = compact(all_text)

    for pattern in REQUIRED_CONCEPT_PATTERNS:
        if not re.search(pattern, text, flags=re.IGNORECASE):
            failures.append(f"Missing required authority concept pattern: {pattern}")

    return failures


def check_forbidden_patterns(file_texts: dict[Path, str]) -> list[str]:
    failures: list[str] = []

    for path, raw_text in file_texts.items():
        text = compact(raw_text)

        for pattern in FORBIDDEN_NEARBY_PATTERNS:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                failures.append(
                    f"Forbidden authority wording found in {path.relative_to(ROOT)}: "
                    f"pattern={pattern!r}, match={match.group(0)!r}"
                )

    return failures


def main() -> int:
    print("[authority] Engel authority hierarchy verifier")
    print("[authority] Expected hierarchy: Josh > Guardian > Engel/runtime")
    print("[authority] Mode: read-only")

    file_texts, failures = check_required_files()

    if file_texts:
        all_text = "\n\n".join(file_texts.values())
        failures.extend(check_required_phrases(all_text))
        failures.extend(check_required_concepts(all_text))
        failures.extend(check_forbidden_patterns(file_texts))

    if failures:
        print("\n[authority] FAIL")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("\n[authority] PASS")
    print("[authority] Josh remains final human authority.")
    print("[authority] Guardian remains safety/governance layer below Josh.")
    print("[authority] Engel/runtime remains below the Josh-first, Guardian-second gates.")
    print("[authority] No forbidden authority inversion wording found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
