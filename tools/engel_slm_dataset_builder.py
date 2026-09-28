#!/usr/bin/env python3
"""Build supervised datasets for Engel's SLM roster from Engel's OWN receipts.

Engel already labels its own work: every chat receipt records the style-gate check
results, the semantic-quality verdict, which lane served the turn, and whether the
reply needed repair. That is thousands of free supervised examples, so the SLMs here
are trained on Engel's real behaviour rather than synthetic prompts.

Runs where the corpora live (CT246 /opt/engel by default). Emits one JSONL per
dataset plus a manifest with class balance, because a dataset whose balance nobody
measured is how you ship a classifier that always predicts the majority class.

Datasets (canonical metadata: tools/engel_slm_roster.py)
  intent_router     prompt -> chat | build | training_job | meeting_room
  route_governor    bounded Governor features -> suggested local lane
  style_checks      (prompt, reply) -> multi-label failing checks
  reply_grader      (prompt, reply) -> needed_repair | clean
  train_admit       (prompt, reply) -> admit | reject
  failure_triage    (goal, error, diagnostic) -> repair_succeeded | repair_failed
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterator

import engel_slm_roster as roster
import engel_prompt_training_quarantine as prompt_quarantine
from engel_build_training_dataset import (
    CORPUS_ROOT_ENV,
    PACKS_DIR_ENV,
    PACK_REQUIRED_FIELDS,
    PACK_ROW_SCHEMA,
    assess_prompt_training_pack_row,
    normalize_training_targets,
    verify_training_corpus_root,
)

DEFAULT_ROOT = Path("/opt/engel")

CLEAN_STATUSES = {
    "large local chat replied",
    "quick casual model replied",
    "trained lora local chat replied",
    "deep local specialist replied",
    "sparse moe expert lane replied",
    "code lane model replied",
}
REPAIR_STATUSES = {
    "chat replied after local style repair",
    "chat style check failed",
    "large local chat replied after semantic repair",
    "local model replied with quality warning",
    "chat quality gate blocked unsafe drafts",
    "local quality check failed",
}

# Synthetic/negative-test markers: deliberate fixtures must never become "live
# breakage" training signal (the health check learned this the hard way).
# Prompt-training packs (2026-08-01): every graded prompt-training turn now emits a
# row carrying the runner's authoritative admit verdict, admitted AND rejected alike.
# The rejects are the whole point -- a roster model that only ever saw admitted text
# could not learn the boundary it exists to draw.
PACK_SUBDIR = ("memory", "training", "packs")
PACK_GLOB = "ENGEL_PROMPT_TRAINING_PACK_*.jsonl"
GOVERNOR_ROW_SCHEMA = "engel_governor_decision_v1"
FORGE_ROW_SCHEMA = "engel_forge_outcome_v1"
TRAIN_ADMIT_QUARANTINE: list[dict[str, Any]] = []


def _iter_receipts(root: Path, limit: int) -> Iterator[dict[str, Any]]:
    receipts = root / "reports" / "engel_standalone_chat_llm" / "chat_receipts"
    if not receipts.is_dir():
        return
    paths = sorted(receipts.glob("*.json"))
    if limit > 0:
        paths = paths[-limit:]
    for path in paths:
        try:
            if path.stat().st_size > 400_000:
                continue
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            data["_path"] = str(path)
            yield data


def _training_packs_dir(root: Path, packs_dir: Path | None = None) -> Path:
    if packs_dir is not None:
        return packs_dir
    env = str(os.environ.get(PACKS_DIR_ENV) or "").strip()
    return Path(env) if env else root.joinpath(*PACK_SUBDIR)


def _iter_training_packs(
    root: Path,
    limit: int,
    packs_dir: Path | None = None,
    quarantine_dir: Path | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield prompt-training pack rows, newest packs last.

    The LATEST receipt in that directory is a `.json` summary, not JSONL, so the glob
    is suffix-specific rather than filtered afterwards -- a half-parsed summary silently
    contributing zero rows is the kind of quiet miss that makes a dataset look thin for
    no visible reason. `limit` counts PACK FILES (one file = one training session), not
    rows: sessions are the unit an operator thinks in when they say "just the last few".
    """
    packs = _training_packs_dir(root, packs_dir)
    if not packs.is_dir():
        return
    paths = sorted(packs.glob(PACK_GLOB))
    if limit > 0:
        paths = paths[-limit:]
    quarantine_root = quarantine_dir or prompt_quarantine.DEFAULT_QUARANTINE_DIR
    for path in paths:
        loaded = prompt_quarantine.load_pack(path, quarantine_root)
        if loaded.get("blockers"):
            raise RuntimeError(
                f"prompt-training quarantine verification failed for {path.name}: "
                + " | ".join(str(item) for item in loaded["blockers"][:3])
            )
        for parsed in loaded.get("rows") or []:
            if parsed.get("quarantined") is True:
                continue
            row = parsed.get("row")
            if not isinstance(row, dict):
                continue
            schema = str(row.get("schema") or "")
            if schema != PACK_ROW_SCHEMA or not PACK_REQUIRED_FIELDS.issubset(row):
                continue
            row["_path"] = str(path)
            yield row


def _iter_jsonl(path: Path, schema: str) -> Iterator[dict[str, Any]]:
    if not path.is_file():
        return
    try:
        handle = path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict) or str(row.get("schema") or "") != schema:
                continue
            row["_path"] = str(path)
            yield row


def _text(value: Any, limit: int = 4000) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _prompt_of(receipt: dict[str, Any]) -> str:
    return _text(receipt.get("prompt") or receipt.get("prompt_redacted"))


def _reply_of(receipt: dict[str, Any]) -> str:
    # raw_first_reply is the model's ORIGINAL draft -- the thing the gate judged.
    # Preferring the repaired text would teach the grader to score post-repair
    # output and it would never learn what a failing draft looks like.
    return _text(
        receipt.get("raw_first_reply")
        or receipt.get("local_semantic_repair_original_reply")
        or receipt.get("assistant_reply")
        or receipt.get("reply_redacted")
    )


def build_reply_grader(receipts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for receipt in receipts:
        status = str(receipt.get("status") or "").strip().casefold()
        prompt, reply = _prompt_of(receipt), _reply_of(receipt)
        if not prompt or not reply:
            continue
        if status in CLEAN_STATUSES:
            label = "clean"
        elif status in REPAIR_STATUSES:
            label = "needed_repair"
        else:
            continue
        # A first draft that the style scorer itself failed is needed_repair even if
        # the final status looks clean after a successful repair.
        first = receipt.get("first_style_score") or {}
        if first.get("ok") is False:
            label = "needed_repair"
        rows.append(
            {
                "prompt": prompt,
                "reply": reply,
                "label": label,
                "status": status,
                "source": receipt.get("_path", ""),
            }
        )
    return rows


def build_style_checks(receipts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for receipt in receipts:
        score = receipt.get("first_style_score") or receipt.get("style_score") or {}
        checks = score.get("checks") if isinstance(score.get("checks"), dict) else None
        if not checks:
            continue
        prompt, reply = _prompt_of(receipt), _reply_of(receipt)
        if not prompt or not reply:
            continue
        failing = sorted(k for k, v in checks.items() if v is False)
        rows.append(
            {
                "prompt": prompt,
                "reply": reply,
                "failing_checks": failing,
                "ok": not failing,
                "source": receipt.get("_path", ""),
            }
        )
    return rows


def build_intent_router(receipts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Label the action lane each prompt actually took -- the ground truth the
    keyword intent gates keep getting wrong."""
    rows = []
    for receipt in receipts:
        prompt = _prompt_of(receipt)
        if not prompt:
            continue
        provider = str(receipt.get("selected_provider") or "").casefold()
        if receipt.get("conical_job_id") or receipt.get("build_lane_used") is True:
            label = "build"
        elif provider == "training_control" or "training package" in str(
            receipt.get("status") or ""
        ).casefold():
            label = "training_job"
        elif receipt.get("meeting_room_order_id") or receipt.get(
            "agent_meeting_room_used"
        ) is True:
            label = "meeting_room"
        else:
            label = "chat"
        rows.append({"prompt": prompt, "label": label, "source": receipt.get("_path", "")})
    return rows


def build_route_governor(
    receipts: list[dict[str, Any]], governor_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Build the missing Governor T1 route corpus without learning authority.

    The input contains only the route feature allowlist from engel_slm_roster;
    rule_id, reason, approval/gate values, and the outcome itself never enter the
    features. Exact duplicates are collapsed so a repeated training fixture cannot
    make a lookup table look like evidence.
    """
    candidates: list[tuple[dict[str, Any], str, str]] = []
    for receipt in receipts:
        record = receipt.get("governor_route_decision")
        if not isinstance(record, dict):
            continue
        verdict = record.get("verdict")
        if not isinstance(verdict, dict) or verdict.get("decision") != "route":
            continue
        candidates.append(
            (record.get("features") or {}, str(verdict.get("outcome") or ""), receipt.get("_path", ""))
        )
    for record in governor_rows:
        verdict = record.get("verdict")
        if not isinstance(verdict, dict) or verdict.get("decision") != "route":
            continue
        candidates.append(
            (record.get("features") or {}, str(verdict.get("outcome") or ""), record.get("_path", ""))
        )

    allowed = set(roster.task_spec("route_governor").labels)
    seen: set[tuple[str, str]] = set()
    rows: list[dict[str, Any]] = []
    for features, label, source in candidates:
        canonical = roster.canonical_route_features(features)
        signature = (roster.route_feature_text(canonical), label)
        if not canonical or label not in allowed or signature in seen:
            continue
        seen.add(signature)
        rows.append({"features": canonical, "label": label, "source": source})
    return rows


def build_failure_triage(forge_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Use observed repair outcomes, replacing the old circular receipt labels.

    The former dataset labeled an error from the same status/error strings supplied
    as input and was correctly rejected for leakage. Code Forge records the missing
    ground truth: whether the *next* bounded round actually fixed that failure.
    """
    seen: set[tuple[str, str, str, str]] = set()
    rows: list[dict[str, Any]] = []
    for item in forge_rows:
        fixed = item.get("fixed_by_next")
        if not isinstance(fixed, bool):
            continue
        goal = _text(item.get("goal"), 1000)
        error_class = _text(item.get("error_class"), 64)
        diagnostic = _text(item.get("error_tail"), 1200)
        if not goal or not error_class or error_class == "none":
            continue
        label = "repair_succeeded" if fixed else "repair_failed"
        signature = (goal, error_class, diagnostic, label)
        if signature in seen:
            continue
        seen.add(signature)
        rows.append(
            {
                "goal": goal,
                "error_class": error_class,
                "diagnostic": diagnostic,
                "label": label,
                "source": item.get("_path", ""),
            }
        )
    return rows


def build_train_admit(
    pack_rows: list[dict[str, Any]],
    *,
    corpus_root: Path | str | None = None,
    training_target: str = "slm",
    target_stats: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """(prompt, reply) -> admit | reject under current downstream policy.

    The historical pack verdict remains audit evidence, but it is not authoritative.
    Current provenance, action-lane, discipline, and AEC claim-support rules are
    re-derived.  Rows whose exclusion depends on hidden/session context (action lanes,
    duplicates, failed turns) are skipped rather than mislabeled as reply-quality rejects.

    `base_prompt` is deliberately the input, not `delivered_prompt`. The delivered text
    carries the level wrapper and the answer contract, which are identical across every
    turn in a session -- training on it would hand the classifier a session fingerprint
    instead of the ask, and the leakage detector would be right to reject the result.

    Exact prompt/reply pairs with conflicting historical or current labels are quarantined
    as ambiguous evidence. Repeated pairs with one stable label are collapsed to one row,
    preventing row-level train/test leakage later in the SLM trainer.
    """
    selected_target = normalize_training_targets(training_target)
    if selected_target != ("slm",):
        raise ValueError("the SLM dataset builder only consumes prompt rows targeting slm")
    stats = target_stats if target_stats is not None else {}
    stats.clear()
    stats.update(
        {
            "training_target": "slm",
            "rows_seen": 0,
            "rows_explicitly_targeting": 0,
            "rows_excluded_missing_or_malformed": 0,
            "rows_excluded_other_target": 0,
            "rows_excluded_by_policy": 0,
            "teachable_rows_before_conflict_dedupe": 0,
            "output_rows": 0,
        }
    )
    TRAIN_ADMIT_QUARANTINE.clear()
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for pack_row in pack_rows:
        stats["rows_seen"] += 1
        try:
            row_targets = normalize_training_targets(pack_row.get("training_targets"))
        except ValueError:
            stats["rows_excluded_missing_or_malformed"] += 1
            continue
        if "slm" not in row_targets:
            stats["rows_excluded_other_target"] += 1
            continue
        stats["rows_explicitly_targeting"] += 1
        assessment = assess_prompt_training_pack_row(pack_row, corpus_root=corpus_root)
        if assessment.get("disposition") == "exclude":
            stats["rows_excluded_by_policy"] += 1
            continue
        prompt = _text(pack_row.get("base_prompt"))
        reply = _text(pack_row.get("assistant_reply"))
        if not prompt or not reply:
            stats["rows_excluded_by_policy"] += 1
            continue
        stats["teachable_rows_before_conflict_dedupe"] += 1
        grouped.setdefault((prompt, reply), []).append(
            {
                "derived_label": str(assessment.get("disposition")),
                "claimed_label": "admit" if pack_row.get("admit") is True else "reject",
                "discipline": _text(pack_row.get("discipline"), 64),
                "source": pack_row.get("_path", ""),
                "reason": str(assessment.get("reason") or ""),
            }
        )

    rows: list[dict[str, Any]] = []
    for (prompt, reply), evidence in grouped.items():
        claimed = {item["claimed_label"] for item in evidence}
        derived = {item["derived_label"] for item in evidence}
        claimed_disagrees_with_current = any(
            item["claimed_label"] != item["derived_label"] for item in evidence
        )
        if len(claimed) != 1 or len(derived) != 1 or claimed_disagrees_with_current:
            pair_sha = hashlib.sha256(
                (prompt + "\0" + reply).encode("utf-8")
            ).hexdigest()
            TRAIN_ADMIT_QUARANTINE.append(
                {
                    "schema": "engel_train_admit_conflict_quarantine_v1",
                    "pair_sha256": pair_sha,
                    "rows": len(evidence),
                    "claimed_labels": sorted(claimed),
                    "derived_labels": sorted(derived),
                    "sources": sorted({str(item["source"]) for item in evidence}),
                }
            )
            continue
        first = evidence[0]
        rows.append(
            {
                "prompt": prompt,
                "reply": reply,
                "label": next(iter(derived)),
                "discipline": first["discipline"],
                "source": first["source"],
            }
        )
    stats["output_rows"] = len(rows)
    return rows


def _balance(rows: list[dict[str, Any]], key: str = "label") -> dict[str, int]:
    counter: collections.Counter = collections.Counter()
    for row in rows:
        value = row.get(key)
        if isinstance(value, list):
            for item in value:
                counter[item] += 1
        else:
            counter[str(value)] += 1
    return dict(counter.most_common())


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Engel SLM training datasets")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--out", default="")
    parser.add_argument(
        "--packs-dir",
        default="",
        help=f"isolated prompt-training pack directory (or set {PACKS_DIR_ENV})",
    )
    parser.add_argument(
        "--quarantine-dir",
        default="",
        help="immutable prompt-row quarantine sidecars (defaults to canonical directory)",
    )
    parser.add_argument(
        "--training-target",
        default="slm",
        choices=("slm",),
        help="model family consuming prompt-pack labels; this builder is SLM-only",
    )
    parser.add_argument(
        "--corpus-root",
        default="",
        help=f"verified construction corpus bundle root (or set {CORPUS_ROOT_ENV})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="newest N chat receipts AND newest N training-pack files (0=all)",
    )
    args = parser.parse_args()

    root = Path(args.root)
    corpus_override = Path(args.corpus_root) if str(args.corpus_root).strip() else None
    corpus_root, corpus_verification, corpus_has_state = verify_training_corpus_root(
        corpus_override
    )
    if corpus_has_state and corpus_verification.get("ok") is not True:
        print(json.dumps({
            "status": "FAIL",
            "reason": "non-empty construction corpus bundle did not verify",
            "construction_corpus_root": str(corpus_root),
            "construction_corpus_blockers": corpus_verification.get("blockers") or [],
        }, indent=2, sort_keys=True))
        return 2
    out_dir = Path(args.out) if args.out else root / "run" / "slm" / "datasets"
    out_dir.mkdir(parents=True, exist_ok=True)
    packs_dir = Path(args.packs_dir) if str(args.packs_dir).strip() else None
    quarantine_dir = (
        Path(args.quarantine_dir) if str(args.quarantine_dir).strip() else None
    )

    receipts = list(_iter_receipts(root, args.limit))
    pack_rows = list(
        _iter_training_packs(root, args.limit, packs_dir, quarantine_dir)
    )
    governor_rows = list(
        _iter_jsonl(root / "reports" / "governor" / "governor_decisions.jsonl", GOVERNOR_ROW_SCHEMA)
    )
    forge_rows = list(
        _iter_jsonl(root / "reports" / "engel_forge" / "forge_outcomes.jsonl", FORGE_ROW_SCHEMA)
    )
    prompt_training_target_filter: dict[str, Any] = {}
    datasets = {
        "intent_router": build_intent_router(receipts),
        "route_governor": build_route_governor(receipts, governor_rows),
        "style_checks": build_style_checks(receipts),
        "reply_grader": build_reply_grader(receipts),
        "train_admit": build_train_admit(
            pack_rows,
            corpus_root=corpus_root,
            training_target=args.training_target,
            target_stats=prompt_training_target_filter,
        ),
        "failure_triage": build_failure_triage(forge_rows),
    }

    manifest: dict[str, Any] = {
        "schema": "engel_slm_dataset_manifest_v2",
        "roster_schema": roster.ROSTER_SCHEMA,
        "roster": roster.catalog(),
        "root": str(root),
        "packs_dir": str(_training_packs_dir(root, packs_dir)),
        "quarantine_dir": str(
            quarantine_dir or prompt_quarantine.DEFAULT_QUARANTINE_DIR
        ),
        "construction_corpus_root": str(corpus_root),
        "construction_corpus_verified": corpus_verification.get("ok") is True,
        "construction_corpus_bundle_sha256": corpus_verification.get("bundle_sha256") or "",
        "construction_corpus_blockers": corpus_verification.get("blockers") or [],
        "receipts_scanned": len(receipts),
        "pack_rows_scanned": len(pack_rows),
        "training_target": args.training_target,
        "prompt_training_target_filter": prompt_training_target_filter,
        "train_admit_conflicts_quarantined": len(TRAIN_ADMIT_QUARANTINE),
        "governor_rows_scanned": len(governor_rows),
        "forge_rows_scanned": len(forge_rows),
        "datasets": {},
    }
    for name in roster.KNOWN_TASKS:
        rows = datasets[name]
        path = out_dir / f"{name}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
        key = "failing_checks" if name == "style_checks" else "label"
        manifest["datasets"][name] = {
            "path": str(path),
            "rows": len(rows),
            "balance": _balance(rows, key),
        }
    quarantine_path = out_dir / "train_admit_conflicts_quarantine.jsonl"
    quarantine_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in TRAIN_ADMIT_QUARANTINE),
        encoding="utf-8",
    )
    manifest["train_admit_quarantine"] = {
        "path": str(quarantine_path),
        "conflict_groups": len(TRAIN_ADMIT_QUARANTINE),
        "training_rows": 0,
    }
    manifest_path = out_dir / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
