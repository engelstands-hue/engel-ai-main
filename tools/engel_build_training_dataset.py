#!/usr/bin/env python3
"""Standing Engel training-dataset builder (runs on engel-ai-main, CT 246).

Sweeps ALL of Engel's accumulated conversation material into a clean SFT
dataset, ready for the next fine-tune:

  - persistent chat memory   (app + Discord provider turns, attachment turns)
  - chat receipts            (provider bridge receipts)
  - Discord training log     (real chat routes; weak replies excluded)
  - teacher distillation     (any teacher_gen.jsonl found in past run dirs)
  - prompt-training packs    (local curriculum turns the training run itself
                              graded; stamp + current-policy reverified)

Cleaning: real-provider replies only, canned/template/zombie lines excluded,
Discord context wrappers stripped to the current user line, secret-looking
examples dropped whole, dedupe by user text (verified/admitted quality wins;
stable first row wins ties).

Output: /opt/engel/llm_training/datasets/latest/ (sft_train.jsonl, sft_val.jsonl,
dataset_manifest.json) plus a dated copy, and a receipt in reports/llm_training.
Scheduled daily via the engel-training-dataset systemd timer.
"""
import argparse
import hashlib
import json
import os
import random
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import engel_prompt_training_quarantine as prompt_quarantine
from engel_training_capture_filter import classify_training_pair, decision_dict

ROOT = Path("/opt/engel")
MEMORY = ROOT / "memory" / "persistent_chat" / "ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl"
RECEIPTS = ROOT / "reports" / "engel_standalone_chat_llm" / "chat_receipts"
DISCORD = ROOT / "memory" / "discord_bridge" / "ENGEL_DISCORD_CHAT_TRAINING.jsonl"
IDENTITY_SEED = ROOT / "memory" / "training" / "engel_identity_seed.jsonl"
MATH_REPAIR_SEED = ROOT / "memory" / "training" / "engel_math_repair_seed.jsonl"
SELF_UPGRADE_SEED = ROOT / "memory" / "training" / "engel_self_upgrade_seed.jsonl"
NEURO_SYSTEM_SEED = ROOT / "memory" / "training" / "engel_neuro_system_seed.jsonl"
PACKS = ROOT / "memory" / "training" / "packs"
PACKS_DIR_ENV = "ENGEL_PROMPT_TRAINING_PACKS_DIR"
PACKS_DIR_OVERRIDE: Path | None = None
CORPUS = ROOT / "memory" / "training" / "construction_env"
CORPUS_ROOT_ENV = "ENGEL_CONSTRUCTION_CORPUS_ROOT"
TEACHER_GLOB = ROOT / "llm_training"
DATASETS = ROOT / "llm_training" / "datasets"
RECEIPT_DIR = ROOT / "reports" / "llm_training"

# (2026-07-10) The base training prompt == the served ENGEL_LOCAL_CHAT_SYSTEM_PROMPT (verified
# byte-identical), so training and serving already share this base. What the model was NOT
# trained on is what serve appends: the identity guards + the persona STYLE CARD. Those are now
# folded into the training system prompt so TRAIN == SERVE on the static prefix and the model
# stops being served context it never saw. Dynamic per-turn facts/semantic/retrieved-examples
# stay serve-only context (they vary per turn; the model learns to treat them as context).
_BASE_SYSTEM_PROMPT = (
    "You are Engel, Joshua's local AI on engel-ai-main. Speak in first person, plain and "
    "direct. Be honest about limits and failures - never invent results, links, or status. "
    "For hard problems, reason in numbered steps first, then give a crisp conclusion. "
    "Keep warmth without corporate filler, and answer the current message directly."
)


def _serve_aligned_system_prompt() -> str:
    """Build the training system prompt to MATCH the STATIC prefix the model is actually served
    under. Reuses the real serve function (engel_local_model_service._direct_chat_system_prompt)
    so the identity guards can't drift, then appends the persona style card the same way serve
    does. Fail-open to the base prompt if the serve modules/card aren't importable at build time."""
    import os as _os
    import sys as _sys

    prefix = _BASE_SYSTEM_PROMPT
    try:
        _sys.path.insert(0, str(ROOT / "tools"))
        _os.environ.setdefault("ENGEL_LOCAL_CHAT_SYSTEM_PROMPT", _BASE_SYSTEM_PROMPT)
        from engel_local_model_service import _direct_chat_system_prompt as _dsp
        prefix = _dsp()  # base (== _BASE_SYSTEM_PROMPT) + identity guards + no-scratch line
    except Exception:
        pass
    card = ""
    try:
        card_path = ROOT / "memory" / "personality" / "ENGEL_STYLE_CARD.md"
        if card_path.is_file():
            card = card_path.read_text(encoding="utf-8").strip()
    except Exception:
        card = ""
    parts = [prefix]
    if card:
        parts.append("ENGEL STYLE CARD (follow strictly):\n" + card)
    return "\n\n".join(parts)


SYSTEM_PROMPT = _serve_aligned_system_prompt()

REAL_PROVIDERS = ("anthropic", "xai", "openai", "chatgpt_browser", "gemini", "codex")
# Pinned by exact string: a pack row that does not declare this schema is a stranger, and a
# stranger is not admitted (a future v2 row shape must opt in here deliberately, not by drift).
PACK_ROW_SCHEMA = "engel_prompt_training_pack_row_v1"
PACK_REQUIRED_FIELDS = frozenset(
    {
        "schema",
        "run_id",
        "created_at_utc",
        "session_receipt",
        "prompt_index",
        "discipline",
        "base_prompt",
        "delivered_prompt",
        "assistant_reply",
        "prompt_sha256",
        "status",
        "admit",
        "admit_reason",
        "training_sample_eligible",
        "discipline_eligibility_ok",
        "local_only_training",
        "selected_provider",
        "contract_echo",
    }
)
PACK_CHAT_PROVIDERS = frozenset({"local", "ct_sparse_moe_specialist"})
PACK_MIN_REPLY_CHARS = 80
PACK_DISCIPLINES = frozenset({"aec", "math", "engineering", "communication"})
TRAINING_TARGETS = ("slm", "llm")
CANNED_MARKERS = (
    "Agent Meeting Room has a live server room",
    "Good morning, Joshua. I am ready",
    "Use the Discord bridge media tool",
    "server chat brain is connected",
    "I am here. I will answer the current message directly",
    "You are right to flag it. The fast fallback",
    "I am here with you; what should we work on next",
)


def normalize_training_targets(value: Any) -> tuple[str, ...]:
    """Return a strict, stable model-family set carried by one training row.

    Prompt packs persist either the runner's canonical comma-separated string or a
    JSON string list. Nothing else is accepted: missing, empty, nested, or unknown
    values are provenance failures and target-aware consumers exclude the row.
    """
    if isinstance(value, str):
        raw = value.split(",")
    elif isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
        raw = list(value)
    else:
        raise ValueError("training_targets must be a string or list of strings")
    selected = {item.strip().casefold() for item in raw if item.strip()}
    unsupported = sorted(selected - set(TRAINING_TARGETS))
    if unsupported:
        raise ValueError("unsupported training target(s): " + ", ".join(unsupported))
    if not selected:
        raise ValueError("training_targets must explicitly include slm, llm, or both")
    return tuple(item for item in TRAINING_TARGETS if item in selected)


def _single_training_target(value: Any, expected: str) -> str:
    """Argparse adapter for a builder that owns exactly one model family."""
    selected = normalize_training_targets(value)
    if selected != (expected,):
        raise argparse.ArgumentTypeError(
            f"this builder only accepts --training-target {expected}"
        )
    return expected


SECRET_PATTERNS = [
    re.compile(p)
    for p in (
        r"sk-[A-Za-z0-9_\-]{18,}",
        r"ghp_[A-Za-z0-9]{20,}",
        r"AIza[0-9A-Za-z_\-]{30,}",
        r"xox[bap]-",
        r"BEGIN [A-Z ]*PRIVATE KEY",
        r"[A-Fa-f0-9]{48,}",
    )
]
CURRENT_LINE = "current user message:"
REJECTED_TRAINING_CAPTURES: list[dict] = []


def current_user_line(text: str) -> str:
    low = text.casefold()
    idx = low.rfind(CURRENT_LINE)
    if idx < 0:
        return text
    return text[idx + len(CURRENT_LINE):].strip() or text


def clean_pair(user: str, assistant: str) -> tuple[str, str] | None:
    user = " ".join(current_user_line(str(user)).split())[:2000]
    assistant = str(assistant).replace("\x00", "").strip()[:4000]
    if len(user) < 8 or len(assistant) < 80:
        return None
    blob = user + "\n" + assistant
    if any(marker in assistant for marker in CANNED_MARKERS):
        return None
    if any(p.search(blob) for p in SECRET_PATTERNS):
        return None
    return user, assistant


def capture_row(source: str, obj: dict, user: str, assistant: str) -> dict | None:
    pair = clean_pair(user, assistant)
    if not pair:
        return None
    decision = classify_training_pair(source=source, user=pair[0], assistant=pair[1], record=obj, root=ROOT)
    if not decision.accept:
        REJECTED_TRAINING_CAPTURES.append(
            {
                "schema": "ENGEL_REJECTED_TRAINING_CAPTURE_V1",
                "source": source,
                "user": pair[0],
                "assistant": pair[1],
                "decision": decision_dict(decision),
            }
        )
        return None
    return {
        "source": source,
        "user": pair[0],
        "assistant": pair[1],
        "training_capture": decision_dict(decision),
        # (NT-1) carry cascade depth from the source record into the SFT rows so the
        # weekly-LoRA pipeline can learn WHEN each depth was needed (null if absent).
        "activation_depth": obj.get("activation_depth"),
        "escalated_from": obj.get("escalated_from"),
    }


def record_is_real_provider(obj: dict) -> bool:
    sel = str(obj.get("selected_provider") or "").casefold()
    if sel in REAL_PROVIDERS:
        return True
    prov = str(obj.get("provider") or "").casefold()
    return any(k in prov for k in ("claude", "anthropic", "grok", "xai", "chatgpt", "openai", "gemini", "codex"))


def iter_jsonl(path: Path):
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except Exception:
            continue


def from_memory() -> list[dict]:
    rows = []
    for obj in iter_jsonl(MEMORY):
        if obj.get("ok") is not True or not record_is_real_provider(obj):
            continue
        row = capture_row("memory", obj, obj.get("prompt", ""), obj.get("assistant_reply") or obj.get("assistant_output_text") or "")
        if row:
            rows.append(row)
    return rows


def from_receipts() -> list[dict]:
    rows = []
    if not RECEIPTS.is_dir():
        return rows
    for path in sorted(RECEIPTS.glob("*.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if obj.get("ok") is not True or not record_is_real_provider(obj):
            continue
        row = capture_row("receipts", obj, obj.get("prompt", ""), obj.get("assistant_reply") or obj.get("assistant_output_text") or "")
        if row:
            rows.append(row)
    return rows


def from_discord() -> list[dict]:
    rows = []
    for obj in iter_jsonl(DISCORD):
        row = capture_row("discord", obj, obj.get("prompt") or "", obj.get("assistant_reply") or "")
        if row:
            rows.append(row)
    return rows


def _packs_dir() -> Path:
    """Resolve packs at call time: CLI override, environment, then production default."""
    if PACKS_DIR_OVERRIDE is not None:
        return PACKS_DIR_OVERRIDE
    env = str(os.environ.get(PACKS_DIR_ENV) or "").strip()
    if env:
        return Path(env)
    return PACKS


def resolve_corpus_root(override: Path | str | None = None) -> Path:
    """Resolve an explicit builder root before the environment and CT default."""
    if override is not None and str(override).strip():
        return Path(override)
    env = str(os.environ.get(CORPUS_ROOT_ENV) or "").strip()
    return Path(env) if env else CORPUS


def verify_training_corpus_root(
    override: Path | str | None = None,
) -> tuple[Path, dict[str, Any], bool]:
    """Return (root, verification, has_any_state) for fail-closed builder startup.

    A deliberately empty/nonexistent root is allowed so non-AEC datasets can still be
    built; every AEC row then grades undecidable. Any non-empty partial/tampered bundle
    is a hard builder error rather than a silent fallback to another corpus.
    """
    root = resolve_corpus_root(override)
    try:
        import engel_construction_corpus as construction_corpus

        verification = construction_corpus.verify_corpus_bundle(root)
    except Exception as exc:  # noqa: BLE001 - preflight must report, never trust fallback
        verification = {
            "ok": False,
            "files": [],
            "bundle_sha256": "",
            "blockers": [f"corpus verifier unavailable: {type(exc).__name__}: {exc}"],
        }
    try:
        has_any_state = root.is_symlink() or (root.exists() and any(root.iterdir()))
    except OSError:
        has_any_state = True
    return root, verification, has_any_state


def assess_prompt_training_pack_row(
    obj: dict[str, Any], *, corpus_root: Path | str | None = None
) -> dict[str, Any]:
    """Re-derive the current downstream disposition of one prompt-training row.

    A pack is evidence, not authority.  `admit=true` is retained for audit comparison,
    but every consumer calls this policy again before using the text.  Provenance/action
    failures are *excluded* because they are not reply-quality labels.  Completed local
    chat replies that fail a content gate are *rejects*, which train_admit may learn from.
    """

    def verdict(disposition: str, reason: str, verification_rank: int = 0, **extra: Any) -> dict[str, Any]:
        return {
            "disposition": disposition,
            "reason": reason,
            "verification_rank": int(verification_rank),
            **extra,
        }

    if not isinstance(obj, dict) or obj.get("schema") != PACK_ROW_SCHEMA:
        return verdict("exclude", "pack schema is not the pinned v1 contract")
    missing = sorted(PACK_REQUIRED_FIELDS.difference(obj))
    if missing:
        return verdict("exclude", f"pack row is missing required v1 fields: {missing}")
    if not isinstance(obj.get("admit"), bool):
        return verdict("exclude", "pack row has no boolean audit verdict")
    if obj.get("duplicate_of_prompt_index") not in (None, ""):
        return verdict("exclude", "row is session-level duplicate evidence, not a quality label")
    if str(obj.get("status") or "") != "DONE":
        return verdict("exclude", "turn did not complete as a clean chat reply")
    if obj.get("local_only_training") is not True:
        return verdict("exclude", "local-only provenance is not proven")

    provider = str(obj.get("selected_provider") or "").strip().casefold()
    if provider not in PACK_CHAT_PROVIDERS:
        return verdict("exclude", f"provider {provider or '<missing>'} is not an allowed chat lane")
    if obj.get("response_kind") not in (None, "", "chat"):
        return verdict("exclude", "row declares a non-chat response kind")
    if "action_lane_used" in obj and not isinstance(obj.get("action_lane_used"), bool):
        return verdict("exclude", "row has a malformed action-lane flag")
    if obj.get("action_lane_used") is True:
        return verdict("exclude", "row declares that an action lane was used")
    action_flags = (
        "creation_job",
        "build_lane_used",
        "expected_build_lane",
        "workspace_created",
        "build_artifact_verified",
    )
    if any(name in obj and not isinstance(obj.get(name), bool) for name in action_flags):
        return verdict("exclude", "row has a malformed action/build flag")
    if any(obj.get(name) is True for name in action_flags):
        return verdict("exclude", "row records an action/build result rather than a chat answer")
    if str(obj.get("workspace_path") or "").strip():
        return verdict("exclude", "row carries a workspace action path")

    discipline = str(obj.get("discipline") or "").strip().casefold()
    if discipline not in PACK_DISCIPLINES:
        return verdict("exclude", f"unknown training discipline {discipline or '<missing>'}")
    base_prompt = str(obj.get("base_prompt") or "").strip()
    assistant_reply = str(obj.get("assistant_reply") or "").strip()
    if not base_prompt or not assistant_reply:
        return verdict("exclude", "prompt or reply is empty")
    if len(assistant_reply) < PACK_MIN_REPLY_CHARS:
        return verdict("reject", f"reply is shorter than {PACK_MIN_REPLY_CHARS} characters")
    if obj.get("contract_echo") is not False:
        return verdict("reject", "reply echoes the delivery contract")
    if obj.get("training_sample_eligible") is not True:
        return verdict("reject", "upstream deterministic quality gate did not admit the reply")
    if obj.get("discipline_eligibility_ok") is False:
        return verdict("reject", "discipline-specific quality gate rejected the reply")
    if discipline != "aec" and obj.get("discipline_eligibility_ok") is not True:
        return verdict("reject", "non-AEC discipline verdict is missing")

    if discipline == "aec":
        try:
            import engel_construction_corpus as construction_corpus

            grade = construction_corpus.grade_reply(
                assistant_reply,
                corpus_root=resolve_corpus_root(corpus_root),
                context=base_prompt,
            )
        except Exception as exc:  # noqa: BLE001 - unavailable proof fails closed
            return verdict("reject", f"AEC claim-support grader unavailable: {type(exc).__name__}")
        if not isinstance(grade, dict):
            return verdict("reject", "AEC claim-support grader returned no structured result")
        exact = grade.get("exactly_verified") is True
        claim_supported = grade.get("claim_support_verified") is True
        if not (exact and claim_supported):
            return verdict(
                "reject",
                "AEC claims are not exactly supported by the construction corpus",
                aec_grade=grade,
            )
        return verdict(
            "admit",
            "current policy reverified the local AEC chat answer",
            verification_rank=4,
            aec_grade=grade,
        )

    exact = bool(obj.get("math_exactly_verified") or obj.get("code_exactly_verified"))
    truth_verdict = str(
        obj.get("math_truth_verdict") or obj.get("code_truth_verdict") or ""
    ).casefold()
    rank = 4 if exact else 3 if truth_verdict == "verified" else 2
    return verdict(
        "admit",
        "current policy reverified the completed local chat answer",
        verification_rank=rank,
    )


# (2026-08-01) Local prompt-training turns are excluded from the provider sweep above on
# purpose: a reply is not training material just because Engel produced it, and admitting the
# whole local lane would feed the model its own ungraded output until it drifts. This path is
# the one exception, and the exception is earned per row, not per lane - the prompt-training
# run grades every turn as it goes and STAMPS the verdict into the pack. A stamp is only an
# audit claim: downstream policy independently re-derives it before admitting the row.
# The full policy is re-derived here instead of trusting the runner's single `admit` flag,
# because a pack is only a file on disk - a truncated, malformed or hand-edited pack must not
# be able to inject rows into the daily SFT build just by writing admit=true. Fail CLOSED:
# anything this function cannot verify for itself is dropped, not admitted.
def from_prompt_training(
    *,
    corpus_root: Path | str | None = None,
    quarantine_dir: Path | str | None = None,
    training_target: str = "llm",
    target_stats: dict[str, Any] | None = None,
) -> list[dict]:
    """Admit graded turns from ENGEL_PROMPT_TRAINING_PACK_*.jsonl written by prompt-training runs.

    Admitted rows still pass through capture_row, so the ordinary length / canned-marker /
    secret / identity gates apply to them exactly as they do to every other source, and
    rejections land in negative_eval.jsonl with the rest.
    """
    selected_target = normalize_training_targets(training_target)
    if selected_target != ("llm",):
        raise ValueError("the SFT builder only consumes prompt rows targeting llm")
    stats = target_stats if target_stats is not None else {}
    stats.clear()
    stats.update(
        {
            "training_target": "llm",
            "rows_seen": 0,
            "rows_explicitly_targeting": 0,
            "rows_excluded_missing_or_malformed": 0,
            "rows_excluded_other_target": 0,
            "rows_excluded_by_admission": 0,
            "rows_captured_before_reply_dedupe": 0,
            "output_rows": 0,
        }
    )
    rows: list[dict] = []
    packs = _packs_dir()
    if not packs.is_dir():
        return rows
    # (2026-08-08) Reply-level near-dedup. The prompt-level dedupe downstream keeps the best
    # answer PER PROMPT, but a stuck lane answers DIFFERENT prompts with the same text (live
    # construction run 5188cd2f: turns 29/30 byte-identical, turns 38-40 at 0.90-0.96
    # similarity) and every copy would land as its own SFT row. Same-topic answers
    # legitimately share the contract's mandated opener (measured 0.66-0.69 similarity
    # within a cycle), so the threshold is >= 0.90 against an earlier reply in the same
    # opener bucket -- the best answer survives once, the echoes are dropped.
    accepted: list[tuple[str, dict]] = []
    seen_reply_buckets: dict[str, list[int]] = {}

    def _keep_best_distinct_reply(row: dict, reply_text: str) -> None:
        """Keep one near-identical reply, preferring verified quality; ties keep first."""
        norm = " ".join(re.sub(r"[^a-z0-9 ]+", " ", reply_text.casefold()).split())
        bucket = seen_reply_buckets.setdefault(norm[:240], [])
        for index in bucket:
            prior_norm, prior_row = accepted[index]
            if SequenceMatcher(None, norm, prior_norm).ratio() < 0.90:
                continue
            if _sft_selection_quality(row) > _sft_selection_quality(prior_row):
                accepted[index] = (norm, row)
            return
        bucket.append(len(accepted))
        accepted.append((norm, row))

    # *.jsonl only - this deliberately leaves ENGEL_PROMPT_TRAINING_PACK_LATEST.json (a pointer
    # receipt, not training rows) out of the sweep.
    quarantine_root = (
        Path(quarantine_dir)
        if quarantine_dir is not None and str(quarantine_dir).strip()
        else prompt_quarantine.DEFAULT_QUARANTINE_DIR
    )
    for path in sorted(packs.glob("ENGEL_PROMPT_TRAINING_PACK_*.jsonl")):
        loaded = prompt_quarantine.load_pack(path, quarantine_root)
        if loaded.get("blockers"):
            raise RuntimeError(
                f"prompt-training quarantine verification failed for {path.name}: "
                + " | ".join(str(item) for item in loaded["blockers"][:3])
            )
        for parsed in loaded.get("rows") or []:
            if parsed.get("quarantined") is True:
                continue
            obj = parsed.get("row")
            if not isinstance(obj, dict):
                continue
            stats["rows_seen"] += 1
            try:
                row_targets = normalize_training_targets(obj.get("training_targets"))
            except ValueError:
                stats["rows_excluded_missing_or_malformed"] += 1
                continue
            if "llm" not in row_targets:
                stats["rows_excluded_other_target"] += 1
                continue
            stats["rows_explicitly_targeting"] += 1
            assessment = assess_prompt_training_pack_row(obj, corpus_root=corpus_root)
            # The historical verdict remains a necessary audit signal, but it is never
            # sufficient: current policy and current AEC evidence must independently pass.
            if obj.get("admit") is not True or assessment["disposition"] != "admit":
                stats["rows_excluded_by_admission"] += 1
                continue
            base_prompt = str(obj.get("base_prompt") or "").strip()
            assistant_reply = str(obj.get("assistant_reply") or "").strip()
            # Train on base_prompt, NEVER delivered_prompt: the delivered text carries the
            # training-depth wrapper and the answer contract, so training on it would teach
            # Engel to expect that scaffolding on every real user turn.
            # The source string matters beyond bookkeeping: "prompt_training" is an owner
            # lane in engel_training_capture_filter, so ordinary chat prose that addresses
            # Joshua by name is read as owner speech rather than a guest-answered-as-Joshua
            # confusion. Renaming it would silently start discarding this material.
            row = capture_row("prompt_training", obj, base_prompt, assistant_reply)
            if row:
                stats["rows_captured_before_reply_dedupe"] += 1
                row["_selection_quality"] = (1, int(assessment["verification_rank"]))
                _keep_best_distinct_reply(row, assistant_reply)
    rows.extend(row for _, row in accepted)
    stats["output_rows"] = len(rows)
    return rows


def from_teacher_runs() -> list[dict]:
    rows = []
    for path in sorted(TEACHER_GLOB.glob("*/data/teacher_gen.jsonl")):
        for obj in iter_jsonl(path):
            source = str(obj.get("source") or "teacher")
            row = capture_row(source, obj, obj.get("user", ""), obj.get("assistant", ""))
            if row:
                rows.append(row)
    return rows


def from_identity_seed() -> list[dict]:
    """Curated Engel identity/voice anchors ('who are you' -> Engel-first).
    Duplicated 3x so ~14 hand-written pairs hold their ground against
    hundreds of organic examples during fine-tuning."""
    rows = []
    for obj in iter_jsonl(IDENTITY_SEED):
        user = " ".join(str(obj.get("user") or "").split())
        assistant = str(obj.get("assistant") or "").strip()
        if len(user) >= 3 and len(assistant) >= 30:
            decision = classify_training_pair(source="identity_seed", user=user, assistant=assistant, record=obj, root=ROOT)
            if decision.accept:
                rows.append({"source": "identity_seed", "user": user, "assistant": assistant, "training_capture": decision_dict(decision)})
            else:
                REJECTED_TRAINING_CAPTURES.append(
                    {
                        "schema": "ENGEL_REJECTED_TRAINING_CAPTURE_V1",
                        "source": "identity_seed",
                        "user": user,
                        "assistant": assistant,
                        "decision": decision_dict(decision),
                    }
                )
    return rows


def from_self_upgrade_seed() -> list[dict]:
    """(2026-07-26) Curated pairs teaching the governed self-upgrade system
    (cycle, quorum, rollback, broker, pipes, catalog, honesty rules) so the
    local model natively knows its own change-control loop. Anchored 3x like
    the identity seed."""
    rows = []
    for obj in iter_jsonl(SELF_UPGRADE_SEED):
        user = " ".join(str(obj.get("user") or "").split())
        assistant = str(obj.get("assistant") or "").strip()
        if len(user) >= 3 and len(assistant) >= 30:
            decision = classify_training_pair(source="self_upgrade_seed", user=user, assistant=assistant, record=obj, root=ROOT)
            if decision.accept:
                rows.append({"source": "self_upgrade_seed", "user": user, "assistant": assistant, "training_capture": decision_dict(decision)})
            else:
                REJECTED_TRAINING_CAPTURES.append(
                    {
                        "schema": "ENGEL_REJECTED_TRAINING_CAPTURE_V1",
                        "source": "self_upgrade_seed",
                        "user": user,
                        "assistant": assistant,
                        "decision": decision_dict(decision),
                    }
                )
    return rows


def from_neuro_system_seed() -> list[dict]:
    """(2026-07-26) Curated pairs teaching the neuron-transfer system (NT-1
    activation depth, NT-2 fire-past-threshold escalation, NT-3 retrieve-once)
    so the local model natively knows how its own thinking routes. Anchored
    x12 like the self-upgrade seed (3x proved too weak for fact recall)."""
    rows = []
    for obj in iter_jsonl(NEURO_SYSTEM_SEED):
        user = " ".join(str(obj.get("user") or "").split())
        assistant = str(obj.get("assistant") or "").strip()
        if len(user) >= 3 and len(assistant) >= 30:
            decision = classify_training_pair(source="neuro_system_seed", user=user, assistant=assistant, record=obj, root=ROOT)
            if decision.accept:
                rows.append({"source": "neuro_system_seed", "user": user, "assistant": assistant, "training_capture": decision_dict(decision)})
            else:
                REJECTED_TRAINING_CAPTURES.append(
                    {
                        "schema": "ENGEL_REJECTED_TRAINING_CAPTURE_V1",
                        "source": "neuro_system_seed",
                        "user": user,
                        "assistant": assistant,
                        "decision": decision_dict(decision),
                    }
                )
    return rows


def from_math_repair_seed() -> list[dict]:
    """Curated repair rows for canary failures.

    These rows are intentionally weighted into the training split only. They
    target known bad generations caught by the canary gate without weakening
    the canary itself or touching production chat.
    """
    rows = []
    for obj in iter_jsonl(MATH_REPAIR_SEED):
        user = " ".join(str(obj.get("user") or "").split())
        assistant = str(obj.get("assistant") or "").strip()
        if len(user) >= 3 and len(assistant) >= 30:
            decision = classify_training_pair(source="math_repair_seed", user=user, assistant=assistant, record=obj, root=ROOT)
            if decision.accept:
                rows.append({"source": "math_repair_seed", "user": user, "assistant": assistant, "training_capture": decision_dict(decision)})
            else:
                REJECTED_TRAINING_CAPTURES.append(
                    {
                        "schema": "ENGEL_REJECTED_TRAINING_CAPTURE_V1",
                        "source": "math_repair_seed",
                        "user": user,
                        "assistant": assistant,
                        "decision": decision_dict(decision),
                    }
                )
    return rows


def _run_governed_backlog_driver() -> None:
    """(2026-07-28) Daily baked-in movement: groom + ONE governed dry-run
    draft before the dataset rebuild, so the backlog never silently piles up
    again (20260727 lesson: the gates were fine, movement was missing) and
    the rebuild can capture the fresh driver receipts. Bounded and dry-run
    only - the driver never applies patches; a failure here must never block
    the dataset build. Kill switch: ENGEL_DAILY_BACKLOG_DRIVER_ENABLED=0."""
    import os
    import subprocess
    import sys

    enabled = str(
        os.environ.get("ENGEL_DAILY_BACKLOG_DRIVER_ENABLED", "1") or "1"
    ).strip().casefold() not in {"0", "false", "no", "off"}
    if not enabled:
        print("[daily-backlog-driver] disabled by env")
        return
    driver = Path(__file__).resolve().parent / "engel_self_upgrade_backlog_driver.py"
    if not driver.exists():
        print("[daily-backlog-driver] driver missing, skipped")
        return
    venv_python = ROOT / ".venv" / "bin" / "python"
    interpreter = str(venv_python) if venv_python.exists() else sys.executable
    try:
        completed = subprocess.run(
            [interpreter, str(driver), "drive", "--limit", "1"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=1500,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        tail = (completed.stdout or completed.stderr or "").strip()[-400:]
        print(f"[daily-backlog-driver] exit={completed.returncode} {tail}")
    except Exception as exc:
        print(f"[daily-backlog-driver] skipped: {exc}")


def _sft_selection_quality(row: dict[str, Any]) -> tuple[int, int]:
    """Comparable deterministic quality; no length/verbosity signal is allowed."""
    raw = row.get("_selection_quality")
    if isinstance(raw, (tuple, list)) and len(raw) == 2:
        try:
            return int(raw[0]), int(raw[1])
        except (TypeError, ValueError):
            pass
    # Organic/provider rows have passed the ordinary capture filter, but they lack a
    # prompt-training admission proof.  A currently reverified pack row therefore wins.
    return (0, 0)


def dedupe_sft_examples(buckets: dict[str, list[dict]]) -> list[dict]:
    """Select one row per user prompt by proof quality; stable first wins ties."""
    weighted_seed_names = {
        "identity_seed",
        "math_repair_seed",
        "self_upgrade_seed",
        "neuro_system_seed",
    }
    seen: dict[str, dict] = {}
    for name, rows in buckets.items():
        if name in weighted_seed_names:
            continue
        for row in rows:
            key = hashlib.sha256(row["user"].casefold().encode()).hexdigest()[:20]
            old = seen.get(key)
            if old is None or _sft_selection_quality(row) > _sft_selection_quality(old):
                seen[key] = row
    examples: list[dict] = []
    for selected in seen.values():
        clean = dict(selected)
        clean.pop("_selection_quality", None)
        examples.append(clean)
    return examples


def main() -> int:
    global PACKS_DIR_OVERRIDE
    parser = argparse.ArgumentParser(description="Build Engel's standing SFT dataset")
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
        default="llm",
        choices=("llm",),
        help="model family consuming this SFT dataset; this builder is LLM-only",
    )
    parser.add_argument(
        "--corpus-root",
        default="",
        help=f"verified construction corpus bundle root (or set {CORPUS_ROOT_ENV})",
    )
    args = parser.parse_args()
    PACKS_DIR_OVERRIDE = Path(args.packs_dir) if str(args.packs_dir).strip() else None
    quarantine_dir = Path(args.quarantine_dir) if str(args.quarantine_dir).strip() else None
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
        }))
        return 2

    _run_governed_backlog_driver()
    prompt_training_target_filter: dict[str, Any] = {}
    buckets = {
        "identity_seed": from_identity_seed(),
        "math_repair_seed": from_math_repair_seed(),
        "self_upgrade_seed": from_self_upgrade_seed(),
        "neuro_system_seed": from_neuro_system_seed(),
        "teacher": from_teacher_runs(),
        "memory": from_memory(),
        "receipts": from_receipts(),
        "discord": from_discord(),
        # Organic like memory/receipts/discord, so it dedupes with them and is NOT replicated.
        # Current verification/admission quality selects the winner; reply length never does.
        "prompt_training": from_prompt_training(
            corpus_root=corpus_root,
            quarantine_dir=quarantine_dir,
            training_target=args.training_target,
            target_stats=prompt_training_target_filter,
        ),
    }
    identity_rows = buckets["identity_seed"]
    math_repair_rows = buckets["math_repair_seed"]
    self_upgrade_rows = buckets["self_upgrade_seed"]
    neuro_rows = buckets["neuro_system_seed"]
    examples = dedupe_sft_examples(buckets)
    random.Random(7).shuffle(examples)
    n_val = max(8, len(examples) // 20)
    val, train = examples[:n_val], examples[n_val:]
    # (2026-07-27) identity anchor raised 3x -> 12x. With TWO 12x knowledge seeds
    # (self-upgrade + neuro) a 3x identity anchor was outvoted and the 20260727
    # canary caught a real identity regression ("I'm Joshua" + invented IPs).
    # Identity must weigh at least as much as any knowledge seed.
    train = train + identity_rows * 12  # anchor Engel identity against the organic mass
    train = train + math_repair_rows * 12  # repair known canary miss without diluting validation
    train = train + self_upgrade_rows * 12  # anchor the governed self-upgrade knowledge (3x proved too weak for fact recall at 1.5B)
    train = train + neuro_rows * 12  # anchor the neuron-transfer knowledge the same way
    random.Random(11).shuffle(train)
    for row in train + val:
        row["system"] = SYSTEM_PROMPT

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for out_dir in (DATASETS / "latest", DATASETS / stamp):
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "sft_train.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in train) + "\n", encoding="utf-8"
        )
        (out_dir / "sft_val.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in val) + "\n", encoding="utf-8"
        )
        (out_dir / "dataset_manifest.json").write_text(
            json.dumps(
                {
                    "schema": "engel_training_dataset_manifest_v1",
                    "built_at_utc": stamp,
                    "prompt_training_packs_dir": str(_packs_dir()),
                    "prompt_training_quarantine_dir": str(
                        quarantine_dir or prompt_quarantine.DEFAULT_QUARANTINE_DIR
                    ),
                    "training_target": args.training_target,
                    "prompt_training_target_filter": prompt_training_target_filter,
                    "construction_corpus_root": str(corpus_root),
                    "construction_corpus_verified": corpus_verification.get("ok") is True,
                    "construction_corpus_bundle_sha256": corpus_verification.get("bundle_sha256") or "",
                    "construction_corpus_blockers": corpus_verification.get("blockers") or [],
                    "raw_counts": {name: len(rows) for name, rows in buckets.items()},
                    "training_capture_filter": "ENGEL_TRAINING_CAPTURE_DECISION_V1",
                    "rejected_training_captures": len(REJECTED_TRAINING_CAPTURES),
                    "negative_eval_captures": sum(1 for item in REJECTED_TRAINING_CAPTURES if item.get("decision", {}).get("bucket") == "negative_eval"),
                    "deduped": len(examples),
                    "train": len(train),
                    "val": len(val),
                    "system_prompt": SYSTEM_PROMPT,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (out_dir / "negative_eval.jsonl").write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in REJECTED_TRAINING_CAPTURES) + ("\n" if REJECTED_TRAINING_CAPTURES else ""),
            encoding="utf-8",
        )
    # keep only the 10 newest dated snapshots
    dated = sorted(d for d in DATASETS.iterdir() if d.is_dir() and d.name != "latest")
    for stale in dated[:-10]:
        for f in stale.glob("*"):
            f.unlink()
        stale.rmdir()

    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    (RECEIPT_DIR / "ENGEL_TRAINING_DATASET_LATEST.json").write_text(
        json.dumps(
            {
                "schema": "engel_training_dataset_receipt_v1",
                "built_at_utc": stamp,
                "dataset_dir": str(DATASETS / "latest"),
                "prompt_training_packs_dir": str(_packs_dir()),
                "training_target": args.training_target,
                "prompt_training_target_filter": prompt_training_target_filter,
                "construction_corpus_root": str(corpus_root),
                "construction_corpus_verified": corpus_verification.get("ok") is True,
                "construction_corpus_bundle_sha256": corpus_verification.get("bundle_sha256") or "",
                "construction_corpus_blockers": corpus_verification.get("blockers") or [],
                "raw_counts": {name: len(rows) for name, rows in buckets.items()},
                "training_capture_filter": "ENGEL_TRAINING_CAPTURE_DECISION_V1",
                "rejected_training_captures": len(REJECTED_TRAINING_CAPTURES),
                "negative_eval_captures": sum(1 for item in REJECTED_TRAINING_CAPTURES if item.get("decision", {}).get("bucket") == "negative_eval"),
                "deduped": len(examples),
                "train": len(train),
                "val": len(val),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"raw_counts": {n: len(r) for n, r in buckets.items()}, "prompt_training_packs_dir": str(_packs_dir()), "training_target": args.training_target, "prompt_training_target_filter": prompt_training_target_filter, "construction_corpus_root": str(corpus_root), "construction_corpus_verified": corpus_verification.get("ok") is True, "construction_corpus_bundle_sha256": corpus_verification.get("bundle_sha256") or "", "rejected_training_captures": len(REJECTED_TRAINING_CAPTURES), "deduped": len(examples), "train": len(train), "val": len(val), "dataset": str(DATASETS / "latest")}))
    return 0 if len(train) >= 60 else 1


if __name__ == "__main__":
    raise SystemExit(main())
