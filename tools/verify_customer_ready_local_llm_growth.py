"""Static verifier for ENGEL_CUSTOMER_READY_LOCAL_LLM_GROWTH_V1.

This is a doc/data check only. It does NOT:
  - download models
  - install packages
  - call any model server
  - start any runtime
  - make network calls
  - mutate any of the files it inspects

It DOES:
  - validate the required files exist under D:\\b.WorkSpace
  - validate JSON parses + required flags are all `false`
  - validate candidate files carry their `candidate_only` footers
  - count the conversation examples (must be >= 30)
  - check that every required conversation flow exists by name
  - confirm the demo script exists and is non-trivial
  - confirm the rubric threshold is >= 30
  - scan all customer-ready files for forbidden robotic phrases,
    skipping content inside marked <!-- BAD-EXAMPLE --> blocks
  - confirm no forbidden runtime/build/install language was added

Exit code 0 on PASS, non-zero on FAIL.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # D:\b.WorkSpace
MEMORY = ROOT / "memory"
REPORTS = ROOT / "reports" / "codex_bridge"
TOOLS = ROOT / "tools"


# ────────────────────────── required artifacts ──────────────────────────

REQUIRED_FILES = {
    "contract":     MEMORY / "ENGEL_CUSTOMER_READY_LOCAL_LLM_GROWTH_CONTRACT_V1.json",
    "style":        MEMORY / "ENGEL_CUSTOMER_READY_CONVERSATION_STYLE_V1.md",
    "knowledge":    MEMORY / "ENGEL_CUSTOMER_READY_KNOWLEDGE_BASE_CANDIDATES_V1.md",
    "memory":       MEMORY / "ENGEL_CUSTOMER_READY_MEMORY_CANDIDATES_V1.md",
    "flows":        MEMORY / "ENGEL_CUSTOMER_READY_CONVERSATION_FLOWS_V1.md",
    "examples":     MEMORY / "ENGEL_CUSTOMER_READY_CONVERSATION_EXAMPLES_V1.md",
    "demo":         MEMORY / "ENGEL_CUSTOMER_READY_DEMO_SCRIPT_V1.md",
    "rubric":       MEMORY / "ENGEL_CUSTOMER_READY_CONVERSATION_RUBRIC_V1.json",
    "verifier":     TOOLS  / "verify_customer_ready_local_llm_growth.py",
    "report":       REPORTS / "ENGEL_CUSTOMER_READY_LOCAL_LLM_GROWTH_V1.md",
}


# ────────────────────────── contract flag rules ──────────────────────────

CONTRACT_FALSE_FLAGS = [
    "runtime_enabled",
    "inference_enabled",
    "training_enabled",
    "fine_tuning_enabled",
    "provider_calls_enabled",
    "trusted_memory_write_enabled",
    "autonomous_learning_enabled",
]

CONTRACT_TRUE_FLAGS = [
    "memory_candidates_only",
    "knowledge_candidates_only",
    "human_review_required",
    "all_outputs_untrusted_until_verified",
]


# ───────────────────────── forbidden text scan ──────────────────────────

# These phrases must NOT appear in customer-ready files outside marked
# BAD-EXAMPLE blocks. Case-insensitive substring match.
FORBIDDEN_PHRASES = [
    "as an ai language model",
    "certainly, i can assist",
    "please provide more information",
    "i am unable to",
]

# Block markers that the scanner skips.
BAD_BLOCK_OPEN = "<!-- BAD-EXAMPLE -->"
BAD_BLOCK_CLOSE = "<!-- /BAD-EXAMPLE -->"

# Files we scan for forbidden phrases.
SCAN_FILES = [
    "style", "knowledge", "memory", "flows", "examples", "demo",
]

# Forbidden runtime/build language (anything that suggests this pass
# actually started a model or installed something). Matched case-insensitive.
FORBIDDEN_RUNTIME_LANGUAGE = [
    r"\bollama serve\b",
    r"\bollama run\b",
    r"\bllama-server\b",
    r"\bpip install\b",        # Bare install command, not just "pip install graphifyy" in a quote
    r"\bnpm install\b",
    r"\bcargo build\b",
    r"\bpyinstaller\b",
    r"\bmodel start\b",
    r"\btraining started\b",
    r"\bfine[- ]tuning started\b",
]
# Allow-list specific phrases that are pattern-matched but legitimate
# (e.g. style guide referencing "pip install graphifyy" inside an inline
# `code` span to teach the customer how to install something). We treat
# any line containing one of these allow tokens as exempt from the
# runtime-language scan.
RUNTIME_ALLOW_TOKENS = [
    "pip install graphifyy",         # mentioned only as a literal command example
    "pip install discord.py",        # historical reference only
    "models install whisper",        # an Engel chat command, not a system install
    "models install piper",          # same
    "tts use ",                      # Engel chat command
    "stt use ",                      # Engel chat command
    "browser ai connect ",           # Engel chat command
    "ephify build",                  # Engel chat command
    "say hello",                     # voice demo line
    "voice on",                      # Engel chat command
    "voice off",                     # Engel chat command
]


# ───────────────────────── candidate footer rules ────────────────────────

CANDIDATE_FOOTERS = [
    "trust_status: candidate_only",
    "can_apply_now: false",
    "requires_human_review: true",
]

CANDIDATE_FILES = ["knowledge", "memory"]
CANDIDATE_FOOTER_MIN_OCCURRENCES = 8  # Each file has many sections; at least 8 footers required


# ───────────────────────── flows required entries ────────────────────────

REQUIRED_FLOW_TITLES = [
    "first-time customer onboarding",
    "what is engel",
    "why should i buy this",
    "is it private",
    "can it run locally",
    "can it help me build an app",
    "can it remember things",
    "can it connect to my phone",
    "can it work on other devices",
    "what are remote queens",
    "what if engel makes a mistake",
    "can engel improve itself",
    "what's ready now",
    "how do i start",
]


# ───────────────────────── helpers ─────────────────────────

class Result:
    def __init__(self) -> None:
        self.passes: list[str] = []
        self.fails: list[str] = []

    def ok(self, msg: str) -> None:
        self.passes.append(msg)

    def fail(self, msg: str) -> None:
        self.fails.append(msg)

    def _ascii(self, s: str) -> str:
        return s.encode("ascii", "replace").decode("ascii")

    def report(self) -> int:
        print("=" * 72)
        print("ENGEL_CUSTOMER_READY_LOCAL_LLM_GROWTH_V1 -- verifier")
        print("=" * 72)
        for line in self.passes:
            print(f"  PASS  {self._ascii(line)}")
        for line in self.fails:
            print(f"  FAIL  {self._ascii(line)}")
        print("-" * 72)
        print(f"Total: {len(self.passes)} pass | {len(self.fails)} fail")
        if self.fails:
            print("RESULT: FAIL")
            return 1
        print("RESULT: PASS")
        return 0


def strip_bad_blocks(text: str) -> str:
    """Remove the contents of every <!-- BAD-EXAMPLE --> ... <!-- /BAD-EXAMPLE --> block."""
    pattern = re.compile(re.escape(BAD_BLOCK_OPEN) + r".*?" + re.escape(BAD_BLOCK_CLOSE), re.DOTALL)
    return pattern.sub("", text)


def line_is_runtime_exempt(line: str) -> bool:
    low = line.lower()
    for token in RUNTIME_ALLOW_TOKENS:
        if token.lower() in low:
            return True
    return False


# ───────────────────────── checks ─────────────────────────

def check_files_exist(result: Result) -> dict:
    paths: dict = {}
    for key, path in REQUIRED_FILES.items():
        if path.exists() and path.is_file():
            result.ok(f"required file exists: {path.relative_to(ROOT)}")
            paths[key] = path
        else:
            result.fail(f"required file MISSING: {path}")
            paths[key] = None
    return paths


def check_contract(result: Result, contract_path: Path | None) -> None:
    if contract_path is None or not contract_path.exists():
        return
    try:
        data = json.loads(contract_path.read_text(encoding="utf-8"))
    except Exception as exc:
        result.fail(f"contract JSON does not parse: {exc}")
        return
    result.ok("contract JSON parses cleanly")
    for flag in CONTRACT_FALSE_FLAGS:
        if data.get(flag) is False:
            result.ok(f"contract flag {flag} = false")
        else:
            result.fail(f"contract flag {flag} should be false, got {data.get(flag)!r}")
    for flag in CONTRACT_TRUE_FLAGS:
        if data.get(flag) is True:
            result.ok(f"contract flag {flag} = true")
        else:
            result.fail(f"contract flag {flag} should be true, got {data.get(flag)!r}")
    if data.get("status") != "scaffold_only":
        result.fail(f"contract status should be 'scaffold_only', got {data.get('status')!r}")
    else:
        result.ok("contract status = scaffold_only")


def check_rubric(result: Result, rubric_path: Path | None) -> None:
    if rubric_path is None or not rubric_path.exists():
        return
    try:
        data = json.loads(rubric_path.read_text(encoding="utf-8"))
    except Exception as exc:
        result.fail(f"rubric JSON does not parse: {exc}")
        return
    result.ok("rubric JSON parses cleanly")
    thresholds = data.get("thresholds", {})
    total_min = thresholds.get("total_score_minimum")
    if isinstance(total_min, int) and total_min >= 30:
        result.ok(f"rubric total_score_minimum = {total_min} (>= 30)")
    else:
        result.fail(f"rubric total_score_minimum must be >= 30, got {total_min!r}")
    if thresholds.get("no_critical_failures") is True:
        result.ok("rubric no_critical_failures = true")
    else:
        result.fail("rubric no_critical_failures must be true")
    dims = data.get("scoring_dimensions", {})
    required_dims = [
        "natural_flow", "warmth", "clarity", "specificity", "customer_value",
        "low_robotic_phrasing", "context_awareness", "safety_without_stiffness",
        "concise_next_step", "recovery_from_uncertainty",
        "no_fake_capabilities", "no_unsafe_action",
    ]
    for dim in required_dims:
        if dim in dims:
            result.ok(f"rubric dimension present: {dim}")
        else:
            result.fail(f"rubric dimension MISSING: {dim}")


def check_candidate_footers(result: Result, paths: dict) -> None:
    for key in CANDIDATE_FILES:
        p = paths.get(key)
        if p is None or not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        missing = []
        for footer in CANDIDATE_FOOTERS:
            if footer not in text:
                missing.append(footer)
        if missing:
            result.fail(f"{p.name}: candidate footer line missing → {missing}")
            continue
        # Count occurrences of the trust_status line (proxy for #sections).
        occurrences = text.count("trust_status: candidate_only")
        if occurrences >= CANDIDATE_FOOTER_MIN_OCCURRENCES:
            result.ok(f"{p.name}: candidate footers present in {occurrences} sections")
        else:
            result.fail(f"{p.name}: only {occurrences} candidate footers, need >= {CANDIDATE_FOOTER_MIN_OCCURRENCES}")


def check_examples_count(result: Result, examples_path: Path | None) -> None:
    if examples_path is None or not examples_path.exists():
        return
    text = examples_path.read_text(encoding="utf-8")
    # Each example begins with "### Example N · ..."
    example_headings = re.findall(r"^### Example \d+ ·", text, flags=re.MULTILINE)
    n = len(example_headings)
    if n >= 30:
        result.ok(f"conversation examples: {n} (>= 30)")
    else:
        result.fail(f"conversation examples: {n}, need at least 30")


def check_flows_present(result: Result, flows_path: Path | None) -> None:
    if flows_path is None or not flows_path.exists():
        return
    text = flows_path.read_text(encoding="utf-8").lower()
    missing = []
    for title in REQUIRED_FLOW_TITLES:
        if title not in text:
            missing.append(title)
    if missing:
        result.fail(f"flows file missing required scenarios: {missing}")
    else:
        result.ok(f"flows file contains all {len(REQUIRED_FLOW_TITLES)} required scenarios")


def check_demo_script(result: Result, demo_path: Path | None) -> None:
    if demo_path is None or not demo_path.exists():
        return
    text = demo_path.read_text(encoding="utf-8")
    word_count = len(text.split())
    if word_count >= 300:
        result.ok(f"demo script length: {word_count} words (>= 300)")
    else:
        result.fail(f"demo script too short: {word_count} words, need >= 300")
    required_sections = [
        "opening", "what engel is", "customer", "local",
        "mobile", "remote queen", "safety", "next-step",
        "limitation", "closing",
    ]
    low = text.lower()
    missing = [s for s in required_sections if s not in low]
    if missing:
        result.fail(f"demo script missing required sections: {missing}")
    else:
        result.ok("demo script contains all required sections")


def check_forbidden_phrases(result: Result, paths: dict) -> None:
    any_violations = False
    for key in SCAN_FILES:
        p = paths.get(key)
        if p is None or not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        scrubbed = strip_bad_blocks(text).lower()
        for phrase in FORBIDDEN_PHRASES:
            if phrase in scrubbed:
                result.fail(f"{p.name}: forbidden phrase outside BAD-EXAMPLE block → {phrase!r}")
                any_violations = True
    if not any_violations:
        result.ok("no forbidden robotic phrases outside BAD-EXAMPLE blocks")


def check_no_runtime_language(result: Result, paths: dict) -> None:
    any_violations = False
    for key in SCAN_FILES + ["contract", "rubric"]:
        p = paths.get(key)
        if p is None or not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        scrubbed = strip_bad_blocks(text)
        for line in scrubbed.splitlines():
            if line_is_runtime_exempt(line):
                continue
            for pattern in FORBIDDEN_RUNTIME_LANGUAGE:
                if re.search(pattern, line, flags=re.IGNORECASE):
                    result.fail(
                        f"{p.name}: forbidden runtime/build language present → "
                        f"pattern {pattern!r} on line {line.strip()[:80]!r}"
                    )
                    any_violations = True
                    break
    if not any_violations:
        result.ok("no forbidden runtime/build/install language found")


def check_report_exists_and_says_no_runtime(result: Result, report_path: Path | None) -> None:
    if report_path is None or not report_path.exists():
        return
    text = report_path.read_text(encoding="utf-8").lower()
    if "no model was trained" in text or "no model is running" in text or "no inference" in text or "scaffold only" in text:
        result.ok("report explicitly states no model was trained/run/improved")
    else:
        result.fail("report must explicitly state no model was trained, run, or improved")


# ───────────────────────── main ─────────────────────────

def main() -> int:
    result = Result()

    paths = check_files_exist(result)
    check_contract(result, paths.get("contract"))
    check_rubric(result, paths.get("rubric"))
    check_candidate_footers(result, paths)
    check_examples_count(result, paths.get("examples"))
    check_flows_present(result, paths.get("flows"))
    check_demo_script(result, paths.get("demo"))
    check_forbidden_phrases(result, paths)
    check_no_runtime_language(result, paths)
    check_report_exists_and_says_no_runtime(result, paths.get("report"))

    return result.report()


if __name__ == "__main__":
    sys.exit(main())
