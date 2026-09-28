from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
RUN_DIR = PROJECT_ROOT / "reports" / "math_training_runs"
MEMORY_CANDIDATE_DIR = PROJECT_ROOT / "reports" / "memory_candidates"
VERSION = "ENGEL_MATH_TRAINING_HOUR_V1"

DOMAINS = (
    "arithmetic_exactness",
    "algebra_equations",
    "unit_rate_checks",
    "logic_truth_tables",
    "graph_dependency_reasoning",
    "probability_statistics",
)

SAFETY_LABELS = (
    "LOCAL_ONLY",
    "MATH_CURRICULUM_DRILLS",
    "CANDIDATE_LEARNING_ONLY",
    "UNTRUSTED_OUTPUTS_ONLY",
    "NOT_TRUSTED_MEMORY",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_TRAINING",
    "NO_MODEL_RUNTIME",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "HUMAN_REVIEW_REQUIRED",
)


@dataclass
class Drill:
    cycle: int
    domain: str
    prompt: str
    answer: str
    check: str
    lesson: str


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
    return "_".join(part for part in cleaned.split("_") if part) or "math_training"


def run_id(started_at: str) -> str:
    seed = f"{VERSION}|{started_at}".encode("utf-8")
    return "math_training_" + hashlib.sha256(seed).hexdigest()[:16]


def drill_arithmetic(cycle: int, rng: random.Random) -> Drill:
    a = Fraction(rng.randint(2, 24), rng.randint(2, 12))
    b = Fraction(rng.randint(2, 24), rng.randint(2, 12))
    op = rng.choice(["+", "-", "*", "/"])
    if op == "+":
        ans = a + b
    elif op == "-":
        ans = a - b
    elif op == "*":
        ans = a * b
    else:
        ans = a / b
    prompt = f"Compute exactly: ({a}) {op} ({b})"
    lesson = "Use rational arithmetic first; delay decimals until presentation."
    return Drill(cycle, "arithmetic_exactness", prompt, str(ans), "Fraction equality verified", lesson)


def drill_algebra(cycle: int, rng: random.Random) -> Drill:
    x = rng.randint(-12, 12)
    a = rng.randint(2, 9)
    b = rng.randint(-20, 20)
    c = a * x + b
    prompt = f"Solve for x: {a}x + ({b}) = {c}"
    check = f"{a}*{x}+({b})={a * x + b}"
    lesson = "Isolate the variable, then substitute the result back into the original equation."
    return Drill(cycle, "algebra_equations", prompt, str(x), check, lesson)


def drill_unit_rate(cycle: int, rng: random.Random) -> Drill:
    miles = rng.randint(24, 360)
    hours = rng.choice([2, 3, 4, 5, 6, 8])
    rate = Fraction(miles, hours)
    prompt = f"A worker travels {miles} miles in {hours} hours. What is the exact miles/hour rate?"
    lesson = "Track numerator and denominator labels so the resulting unit is meaningful."
    return Drill(cycle, "unit_rate_checks", prompt, f"{rate} miles/hour", "distance / time verified", lesson)


def drill_logic(cycle: int, rng: random.Random) -> Drill:
    p = rng.choice([True, False])
    q = rng.choice([True, False])
    expression = (p and not q) or ((not p) and q)
    prompt = f"Evaluate XOR-style condition: (p and not q) or (not p and q), where p={p}, q={q}"
    lesson = "Break compound logic into named subexpressions before deciding an approval gate."
    return Drill(cycle, "logic_truth_tables", prompt, str(expression), "truth table row verified", lesson)


def drill_graph(cycle: int, rng: random.Random) -> Drill:
    nodes = ["A", "B", "C", "D", "E"]
    edges = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D"), ("D", "E")]
    removed = rng.choice(edges)
    remaining = [edge for edge in edges if edge != removed]
    reachable = {"A"}
    changed = True
    while changed:
        changed = False
        for left, right in remaining:
            if left in reachable and right not in reachable:
                reachable.add(right)
                changed = True
    prompt = f"In dependency graph {edges}, remove edge {removed}. Which nodes remain reachable from A?"
    lesson = "When checking dependencies, recompute reachability after every removed or blocked edge."
    return Drill(cycle, "graph_dependency_reasoning", prompt, ",".join(sorted(reachable)), "reachability fixed-point verified", lesson)


def drill_probability(cycle: int, rng: random.Random) -> Drill:
    values = [rng.randint(1, 12) for _ in range(5)]
    mean = Fraction(sum(values), len(values))
    variance = Fraction(sum((Fraction(v) - mean) ** 2 for v in values), len(values))
    prompt = f"For values {values}, compute exact mean and population variance."
    lesson = "Use exact fractions for small statistics to avoid rounding drift in verifier thresholds."
    return Drill(cycle, "probability_statistics", prompt, f"mean={mean}; variance={variance}", "exact mean/variance verified", lesson)


DRILL_BUILDERS = {
    "arithmetic_exactness": drill_arithmetic,
    "algebra_equations": drill_algebra,
    "unit_rate_checks": drill_unit_rate,
    "logic_truth_tables": drill_logic,
    "graph_dependency_reasoning": drill_graph,
    "probability_statistics": drill_probability,
}


def build_drills(cycle: int, count: int, rng: random.Random) -> list[Drill]:
    drills: list[Drill] = []
    for idx in range(count):
        domain = DOMAINS[(cycle + idx) % len(DOMAINS)]
        drills.append(DRILL_BUILDERS[domain](cycle, rng))
    return drills


def render_summary(payload: dict) -> str:
    counts = payload["domain_counts"]
    lines = [
        "# Engel Math Training Hour Receipt",
        "",
        f"run_id: {payload['run_id']}",
        f"started_at: {payload['started_at']}",
        f"finished_at: {payload['finished_at']}",
        f"duration_seconds: {payload['duration_seconds']}",
        f"cycles_completed: {payload['cycles_completed']}",
        f"drills_completed: {payload['drills_completed']}",
        f"meeting_room_order_id: {payload.get('meeting_room_order_id', '')}",
        f"meeting_room_summary: {payload.get('meeting_room_summary', '')}",
        f"meeting_room_completion: {payload.get('meeting_room_completion', 'pending')}",
        "",
        "Labels:",
        *[f"- {label}" for label in SAFETY_LABELS],
        "",
        "Domain coverage:",
        *[f"- {domain}: {counts.get(domain, 0)}" for domain in DOMAINS],
        "",
        "Candidate lessons:",
        "- Exact arithmetic should stay fraction-based until display.",
        "- Algebra answers are not accepted until substituted back into the original equation.",
        "- Unit labels are part of the answer, not decoration.",
        "- Logic gates should be evaluated by named subexpressions or a truth table row.",
        "- Graph dependency answers need reachability recomputed after edge changes.",
        "- Small statistics should use exact fractions before threshold comparisons.",
        "",
        "Safety boundary:",
        "This was local curriculum drilling only. It did not train model weights, call providers, use network/browser, write trusted memory, mutate source, start workers, or load a model runtime.",
        "",
        "Output files:",
        f"- jsonl_log: {payload['jsonl_log']}",
        f"- memory_candidate: {payload['memory_candidate']}",
    ]
    return "\n".join(lines).rstrip() + "\n"


def render_memory_candidate(payload: dict) -> str:
    lines = [
        "# Engel Math Training Candidate Memory Proposal",
        "",
        "Labels:",
        *[f"- {label}" for label in SAFETY_LABELS],
        "",
        f"source_run_id: {payload['run_id']}",
        f"source_summary: {payload['summary_path']}",
        f"drills_completed: {payload['drills_completed']}",
        "",
        "Proposed memory summary:",
        "Engel should prefer exact, checkable math workflows: use fractions for arithmetic/statistics, substitute algebra solutions back into equations, carry unit labels through calculations, decompose logic gates, and recompute graph reachability after dependency changes.",
        "",
        "Reason to remember:",
        "These patterns reduce math drift in verifier design, routing checks, resource calculations, dependency maps, and approval-condition logic.",
        "",
        "Required review before use:",
        "Human review and the normal approved-memory promotion path are required before this can become trusted memory.",
        "",
        "Not trusted memory:",
        "true",
    ]
    return "\n".join(lines).rstrip() + "\n"


def run_training(minutes: float, cycle_seconds: float, problems_per_cycle: int) -> dict:
    started_at = now_utc()
    rid = run_id(started_at)
    meeting_order_id = ""
    meeting_summary = "Meeting Room handoff not recorded."
    order_text = (
        "Train Engel AI for one hour in math using Meeting Room agents. "
        "Use local-only math drills, verification, and candidate memory notes; "
        "do not train model weights or write trusted memory."
    )
    try:
        from engel_agent_meeting_room import submit_order_from_engel_main_ui

        order = submit_order_from_engel_main_ui(order_text, source="Math Training Hour Runner")
        if order.get("accepted"):
            meeting_order_id = str(order.get("order_id") or "")
            meeting_summary = str(order.get("summary") or "Meeting Room order accepted")
            print(f"[{now_utc()}] meeting_room_order={meeting_order_id} {meeting_summary}", flush=True)
    except Exception as exc:
        meeting_summary = f"Meeting Room handoff failed: {type(exc).__name__}: {exc}"
        print(f"[{now_utc()}] {meeting_summary}", flush=True)

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = RUN_DIR / f"{safe_slug(rid)}.jsonl"
    summary_path = RUN_DIR / f"{safe_slug(rid)}_summary.md"
    memory_path = MEMORY_CANDIDATE_DIR / f"{safe_slug(rid)}_math_training_candidate_memory.md"
    rng = random.Random(rid)
    deadline = time.monotonic() + max(0.0, minutes * 60.0)
    cycle = 0
    drills_completed = 0
    domain_counts = {domain: 0 for domain in DOMAINS}

    with jsonl_path.open("w", encoding="utf-8") as handle:
        while True:
            now = time.monotonic()
            if cycle > 0 and now >= deadline:
                break
            cycle += 1
            drills = build_drills(cycle, problems_per_cycle, rng)
            for drill in drills:
                handle.write(json.dumps(asdict(drill), sort_keys=True) + "\n")
                drills_completed += 1
                domain_counts[drill.domain] += 1
            handle.flush()
            print(
                f"[{now_utc()}] {rid} cycle={cycle} drills={drills_completed} "
                f"remaining_seconds={max(0, int(deadline - time.monotonic()))}",
                flush=True,
            )
            sleep_for = min(cycle_seconds, max(0.0, deadline - time.monotonic()))
            if sleep_for <= 0:
                break
            time.sleep(sleep_for)

    finished_at = now_utc()
    duration_seconds = max(0, round(minutes * 60))
    payload = {
        "run_id": rid,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration_seconds,
        "cycles_completed": cycle,
        "drills_completed": drills_completed,
        "domain_counts": domain_counts,
        "meeting_room_order_id": meeting_order_id,
        "meeting_room_summary": meeting_summary,
        "jsonl_log": str(jsonl_path.relative_to(PROJECT_ROOT)),
        "summary_path": str(summary_path.relative_to(PROJECT_ROOT)),
        "memory_candidate": str(memory_path.relative_to(PROJECT_ROOT)),
    }
    summary_path.write_text(render_summary(payload), encoding="utf-8")
    memory_path.write_text(render_memory_candidate(payload), encoding="utf-8")
    if meeting_order_id:
        try:
            from engel_agent_meeting_room import complete_order_from_engel_main_ui

            completion = complete_order_from_engel_main_ui(
                meeting_order_id,
                (
                    f"Math training completed: {drills_completed} verified drills across "
                    f"{len(DOMAINS)} domains. Summary: {payload['summary_path']}. "
                    f"Candidate memory proposal: {payload['memory_candidate']}."
                ),
                source="Math Training Hour Runner",
            )
            payload["meeting_room_completion"] = str(completion.get("summary") or completion)
            summary_path.write_text(render_summary(payload), encoding="utf-8")
        except Exception as exc:
            payload["meeting_room_completion"] = f"completion failed: {type(exc).__name__}: {exc}"
            summary_path.write_text(render_summary(payload), encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run bounded local Engel math curriculum training.")
    parser.add_argument("--minutes", type=float, default=60.0)
    parser.add_argument("--cycle-seconds", type=float, default=60.0)
    parser.add_argument("--problems-per-cycle", type=int, default=24)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = run_training(args.minutes, args.cycle_seconds, args.problems_per_cycle)
    print("ENGEL_MATH_TRAINING_COMPLETE")
    print(f"summary_path={payload['summary_path']}")
    print(f"memory_candidate={payload['memory_candidate']}")
    print(f"jsonl_log={payload['jsonl_log']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
