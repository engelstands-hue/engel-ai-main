#!/usr/bin/env python3
"""Build Engel Main's canonical training asset folder.

The active runners stay in their original locations because several Python,
Rust, and Flutter routes import or launch them directly. This script creates a
single Engel-owned training folder with copies, prompt sources, runnable
wrappers, and a manifest so the UI has one place to manage prompt training.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = ROOT / "memory" / "training" / "engel_main"
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from run_engel_one_day_local_first_chat_training import (  # noqa: E402
    ENGEL_CAPABILITIES_CARDS_V1,
    ENGEL_CAPABILITIES_MATERIAL_VERSION,
    ENGEL_CHAT_COMMUNICATION_CARDS_V1,  # noqa: F401 - chat-voice curriculum
    ENGEL_CHAT_COMMUNICATION_MATERIAL_VERSION,  # noqa: F401
    ENGEL_MATH_SCHOOL_CARDS_V1,  # noqa: F401 - math-school curriculum, one swap away
    ENGEL_MATH_SCHOOL_MATERIAL_VERSION,  # noqa: F401
    ENGEL_SELF_BUILD_CARDS_V1,  # noqa: F401 - self-build curriculum, one swap away
    ENGEL_SELF_BUILD_MATERIAL_VERSION,  # noqa: F401
    curriculum_prompts,
    fresh_material_prompts_v17,
)
from engel_construction_renewal_curriculum import (  # noqa: E402
    ENGEL_CONSTRUCTION_RENEWAL_CARDS_V1,
    ENGEL_CONSTRUCTION_RENEWAL_MATERIAL_VERSION,
    validate_renewal_cards,
)
from engel_curriculum_renewal import (  # noqa: E402
    ENGEL_CAPABILITIES_RENEWAL_CARDS_V2,
    ENGEL_CAPABILITIES_RENEWAL_MATERIAL_VERSION,
    ENGEL_CHAT_COMMUNICATION_RENEWAL_CARDS_V2,
    ENGEL_CHAT_COMMUNICATION_RENEWAL_MATERIAL_VERSION,
    ENGEL_MATH_SCHOOL_RENEWAL_CARDS_V2,
    ENGEL_MATH_SCHOOL_RENEWAL_MATERIAL_VERSION,
    ENGEL_SELF_BUILD_RENEWAL_CARDS_V2,
    ENGEL_SELF_BUILD_RENEWAL_MATERIAL_VERSION,
    validate_renewal_curricula,
)
import engel_curriculum_adoption as curriculum_adoption  # noqa: E402
import engel_construction_corpus as construction_corpus  # noqa: E402

CONSTRUCTION_CORPUS_ROOT = ROOT / "memory" / "training" / "construction_env"
GENERATED_GROUNDING_SCHEMA = "engel_generated_curriculum_grounding_v1"

# Operator direction 2026-07-30 (later): update training to cover ALL the new
# areas Engel gained this session, not math alone — one card per capability
# (math lane, ModelExpress placement, SLM roster gates, LAN device ID, authorized
# recon, worker liveness, chat routing, self-measurement). Math-school and
# self-build stay importable above; swap the two names below to restore either.
# The v17 prompt SHAPES are kept: confirmed-vs-open separation + a proof owner
# per gap, which is exactly the verify-before-asserting habit every card teaches.
CAMPAIGN_MATERIAL_VERSION = ENGEL_CAPABILITIES_RENEWAL_MATERIAL_VERSION
FRESH_MATERIAL_CARDS_V17 = ENGEL_CAPABILITIES_RENEWAL_CARDS_V2

# Every curriculum is now materialized as its OWN template + listed in an index the
# Prompt Training UI reads, so the operator can SEE and pick any of them instead of
# only whichever one the shim last generated. `capabilities` is the active default
# (feeds the back-compat MIXED template + wrapper). Import the construction v17 cards
# under their own names BEFORE the shim reassignment above would shadow them.
import run_engel_one_day_local_first_chat_training as _curric  # noqa: E402

# `discipline` selects the domain-native prompt shape + answer contract + eligibility
# gate (2026-07-31): "engineering" = Engel-systems evidence grounded in a real verifier/
# receipt; "math" = show-work-and-verify with an independent check; "aec" = the original
# construction evidence-ledger held to the CT246 incomplete-input gate. Applying the AEC
# shape to math/engineering wrongly tripped that gate and discarded every non-construction
# turn; each discipline now teaches the same verify-before-asserting habit in its own terms.
ALL_CURRICULA = [
    {
        "id": "capabilities",
        "title": "Engel Capabilities",
        "detail": "Eight new artifact-grounded capability audits: governance, agent dispatch, Code Forge, devices, Meeting Room, MIPL, self-model, and real-training handoff.",
        "cards": ENGEL_CAPABILITIES_RENEWAL_CARDS_V2,
        "version": ENGEL_CAPABILITIES_RENEWAL_MATERIAL_VERSION,
        "discipline": "engineering",
    },
    {
        "id": "math_school",
        "title": "Math School",
        "detail": "Eighty new declared problems with independent ground truth: every prompt is exactly decidable by the bounded symbolic grader.",
        "cards": ENGEL_MATH_SCHOOL_RENEWAL_CARDS_V2,
        "version": ENGEL_MATH_SCHOOL_RENEWAL_MATERIAL_VERSION,
        "discipline": "math",
    },
    {
        "id": "self_build",
        "title": "Self-Build",
        "detail": "Eight new artifact-grounded self-build reviews: inventory, failures, upgrades, evaluation, promotion, memory, routes, and weakness adoption.",
        "cards": ENGEL_SELF_BUILD_RENEWAL_CARDS_V2,
        "version": ENGEL_SELF_BUILD_RENEWAL_MATERIAL_VERSION,
        "discipline": "engineering",
    },
    {
        # (2026-08-09) Canonical eight-hour renewal material. Each card declares exact
        # manifest documents and anchors that become a verified excerpt packet before UI.
        "id": "construction",
        "title": "Construction Coordination",
        "detail": "Eight new hours of quote-bound construction review: accessibility, occupant load, authority boundaries, edition comparison, and cross-volume coordination. Every sourced claim is bound to an exact document and supplied excerpt.",
        "cards": ENGEL_CONSTRUCTION_RENEWAL_CARDS_V1,
        "version": ENGEL_CONSTRUCTION_RENEWAL_MATERIAL_VERSION,
        "discipline": "aec",
    },
    # 2026-08-01: the first curriculum whose accepted ANSWER TEXT is the training target
    # rather than a graded artifact -- it teaches Engel's own chat voice, so its
    # "communication" discipline deliberately rejects the labelled scaffolding the other
    # three require. Keeping it in this registry gives it one stable canonical picker
    # slot whose material can be renewed without changing its operator-facing identity.
    {
        "id": "chat_communication",
        "title": "Chat Communication",
        "detail": "Eight new style-card-grounded chat lessons: answer first, uncertainty, identity, continuity, length, bad news, clarification, and surface parity.",
        "cards": ENGEL_CHAT_COMMUNICATION_RENEWAL_CARDS_V2,
        "version": ENGEL_CHAT_COMMUNICATION_RENEWAL_MATERIAL_VERSION,
        "discipline": "communication",
    },
]
CANONICAL_CURRICULUM_IDS = (
    "capabilities",
    "math_school",
    "self_build",
    "construction",
    "chat_communication",
)
for _canonical_curriculum in ALL_CURRICULA:
    _canonical_curriculum["material_source"] = "canonical_handwritten"
    _canonical_curriculum["generated_source_id"] = ""
    _canonical_curriculum["generated_grounding"] = {}
    _canonical_curriculum["generated_corpus_bundle_sha256"] = ""

# (2026-08-11) Hand-written material can only be run once, which is how Construction
# reached EXHAUSTED with no way forward. engel_construction_corpus_card_generator draws
# the next unused sections from the 19,513-section code library, proves each anchor
# resolves to a real local excerpt, and writes an ADOPTED card set. Adopted generated
# material overlays the matching canonical discipline slot. That preserves the stable
# five picker identities while re-running the generator after a run yields the NEXT
# sections, so the curriculum renews instead of ending.
GENERATED_ADOPTED_PATHS = (
    (
        CANONICAL_ROOT
        / "generated"
        / "ENGEL_CONSTRUCTION_GENERATED_CARDS_ADOPTED.json",
        "construction",
    ),
    (
        CANONICAL_ROOT
        / "generated"
        / "ENGEL_COMMUNICATION_GENERATED_CARDS_ADOPTED.json",
        "communication",
    ),
)


def _generated_aec_cards_grounding(
    cards: list[Any],
    corpus_root: Path = CONSTRUCTION_CORPUS_ROOT,
) -> tuple[str | None, dict[str, Any]]:
    """Re-derive every generated AEC anchor from the verified local corpus."""
    bundle = construction_corpus.verify_corpus_bundle(corpus_root)
    if not isinstance(bundle, dict) or bundle.get("ok") is not True:
        blockers = bundle.get("blockers") if isinstance(bundle, dict) else []
        detail = str((blockers or ["verification did not pass"])[0])
        return f"construction corpus bundle is unavailable or invalid: {detail}", {}
    bundle_sha256 = str(bundle.get("bundle_sha256") or "").upper()
    if re.fullmatch(r"[0-9A-F]{64}", bundle_sha256) is None:
        return "construction corpus bundle has no valid SHA-256 binding", {}

    total_anchors = 0
    all_documents: list[str] = []
    for card_index, card in enumerate(cards, start=1):
        if not isinstance(card, dict):
            return f"generated AEC card {card_index} is not an object", {}
        anchors = card.get("evidence_anchors")
        documents = card.get("documents")
        if not isinstance(anchors, list) or not anchors:
            return f"generated AEC card {card_index} names no evidence anchors", {}
        if not isinstance(documents, list) or not documents:
            return f"generated AEC card {card_index} names no manifest document", {}
        declared_documents = [str(item or "").strip() for item in documents]
        if (
            any(not item for item in declared_documents)
            or len(set(declared_documents)) != len(declared_documents)
        ):
            return (
                f"generated AEC card {card_index} has empty or duplicate documents",
                {},
            )

        anchor_identities: list[tuple[str, str]] = []
        for anchor_index, anchor in enumerate(anchors, start=1):
            if not isinstance(anchor, dict):
                return (
                    f"generated AEC card {card_index} anchor {anchor_index} "
                    "is not an object",
                    {},
                )
            document = str(anchor.get("document") or "").strip()
            section = str(anchor.get("section") or "").strip()
            if not document or not section:
                return (
                    f"generated AEC card {card_index} anchor {anchor_index} "
                    "has no exact document/section identity",
                    {},
                )
            anchor_identities.append((document, section))
        if len(set(anchor_identities)) != len(anchor_identities):
            return f"generated AEC card {card_index} repeats an evidence anchor", {}
        anchored_documents = list(
            dict.fromkeys(document for document, _section in anchor_identities)
        )
        if declared_documents != anchored_documents:
            return (
                f"generated AEC card {card_index} document scope does not exactly "
                "match its evidence anchors",
                {},
            )

        packet = construction_corpus.build_prompt_evidence_context(
            anchors,
            corpus_root=corpus_root,
        )
        if not isinstance(packet, dict) or packet.get("ok") is not True:
            blockers = packet.get("blockers") if isinstance(packet, dict) else []
            detail = str((blockers or ["evidence verification did not pass"])[0])
            return (
                f"generated AEC card {card_index} evidence is invalid: {detail}",
                {},
            )
        packet_sha256 = str(packet.get("corpus_bundle_sha256") or "").upper()
        if packet_sha256 != bundle_sha256:
            return (
                f"generated AEC card {card_index} evidence packet is bound to "
                "a different corpus bundle",
                {},
            )
        packet_documents = packet.get("documents")
        records = packet.get("records")
        if packet_documents != declared_documents:
            return (
                f"generated AEC card {card_index} verified document coverage "
                "does not match its declared scope",
                {},
            )
        if not isinstance(records, list) or len(records) != len(anchor_identities):
            return (
                f"generated AEC card {card_index} verified anchor coverage "
                "is incomplete",
                {},
            )
        for anchor_index, ((document, section), record) in enumerate(
            zip(anchor_identities, records),
            start=1,
        ):
            if (
                not isinstance(record, dict)
                or str(record.get("document") or "") != document
                or str(record.get("section") or "") != section
            ):
                return (
                    f"generated AEC card {card_index} verified anchor "
                    f"{anchor_index} does not exactly match its declaration",
                    {},
                )
            quote = str(record.get("quote") or "").strip()
            if len(quote) < 120 or len(re.findall(r"[A-Za-z]{2,}", quote)) < 15:
                return (
                    f"generated AEC card {card_index} verified anchor "
                    f"{anchor_index} has no substantive quote",
                    {},
                )
        total_anchors += len(anchor_identities)
        for document in declared_documents:
            if document not in all_documents:
                all_documents.append(document)

    return None, {
        "schema": GENERATED_GROUNDING_SCHEMA,
        "verified": True,
        "corpus_root": str(corpus_root),
        "corpus_bundle_sha256": bundle_sha256,
        "card_count": len(cards),
        "anchor_count": total_anchors,
        "documents": all_documents,
    }


def _generated_cards_are_grounded(
    cards: list[Any], discipline: str
) -> tuple[str | None, dict[str, Any]]:
    """Each discipline proves grounding its own way; require the right one."""
    if discipline == "aec":
        return _generated_aec_cards_grounding(cards)
    for card in cards:
        if not isinstance(card, dict):
            return "a generated card is not an object", {}
        artifacts = card.get("artifacts")
        records = card.get("_grounding_artifact_records")
        if not isinstance(artifacts, list) or not artifacts:
            return "a generated card names no grounding artifacts", {}
        if not isinstance(records, list) or len(records) != len(artifacts):
            return "a generated card's artifact byte binding is incomplete", {}
        for raw_path, record in zip(artifacts, records):
            relative = Path(str(raw_path))
            if (
                not isinstance(record, dict)
                or relative.is_absolute()
                or relative.drive
                or ".." in relative.parts
            ):
                return "a generated card has an unsafe artifact byte binding", {}
            candidate = (ROOT / relative).resolve()
            if (
                ROOT.resolve() not in candidate.parents
                or not candidate.is_file()
                or candidate.is_symlink()
            ):
                return f"a generated card artifact is unavailable: {raw_path}", {}
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest().upper()
            if (
                record.get("path") != relative.as_posix()
                or record.get("bytes") != candidate.stat().st_size
                or str(record.get("sha256") or "").upper() != digest
            ):
                return f"a generated card artifact binding drifted: {raw_path}", {}
    return None, {}


def _load_adopted_generated_curricula() -> tuple[list[dict[str, Any]], list[str]]:
    """Adopted, self-generated curricula, or nothing when none has been adopted."""
    curricula: list[dict[str, Any]] = []
    problems: list[str] = []
    for path, expected_kind in GENERATED_ADOPTED_PATHS:
        if not path.is_file():
            continue
        payload, adoption_receipt, adoption_problems = (
            curriculum_adoption.verify_adoption(
                path, expected_kind=expected_kind
            )
        )
        if payload is None or adoption_problems:
            problems.extend(
                f"{path.name}: {problem}" for problem in adoption_problems
            )
            continue
        cards = payload.get("cards")
        if not isinstance(cards, list) or len(cards) != 8:
            problems.append(
                f"{path.name} must carry exactly eight one-hour cards"
            )
            continue
        discipline = str(payload.get("discipline") or "aec")
        grounding_problem, grounding_binding = _generated_cards_are_grounded(
            cards, discipline
        )
        if grounding_problem:
            problems.append(f"{path.name}: {grounding_problem}")
            # Preserve the adopted material in its stable canonical slot so the
            # operator can see what drifted. The manifest remains fail-closed via
            # this recorded problem until the generator rebinds and re-adopts it.
        curricula.append(
            {
                "id": str(payload.get("id") or path.stem.lower()),
                "title": str(payload.get("title") or "Generated curriculum"),
                "detail": str(payload.get("detail") or ""),
                "cards": cards,
                "version": str(payload.get("material_version") or "generated"),
                "discipline": discipline,
                "material_source": "adopted_generated",
                "generated_source_id": str(
                    payload.get("id") or path.stem.lower()
                ),
                "generated_source_path": str(path),
                "generated_adoption_receipt": str(
                    path.parent / str(payload["adoption_receipt"])
                ),
                "generated_adoption_receipt_sha256": hashlib.sha256(
                    (
                        path.parent / str(payload["adoption_receipt"])
                    ).read_bytes()
                ).hexdigest().upper(),
                "generated_grounding": grounding_binding,
                "generated_corpus_bundle_sha256": str(
                    grounding_binding.get("corpus_bundle_sha256") or ""
                ),
            }
        )
    return curricula, problems


_GENERATED_CURRICULA, _GENERATED_CURRICULA_PROBLEMS = _load_adopted_generated_curricula()
_GENERATED_TARGET_BY_DISCIPLINE = {
    "aec": "construction",
    "communication": "chat_communication",
}
_overlaid_targets: set[str] = set()
for _generated_curriculum in _GENERATED_CURRICULA:
    _target_id = _GENERATED_TARGET_BY_DISCIPLINE.get(
        str(_generated_curriculum.get("discipline") or "")
    )
    if not _target_id:
        _GENERATED_CURRICULA_PROBLEMS.append(
            "adopted generated curriculum has no canonical discipline slot: "
            + str(_generated_curriculum.get("id") or "<missing>")
        )
        continue
    if _target_id in _overlaid_targets:
        _GENERATED_CURRICULA_PROBLEMS.append(
            f"more than one adopted generated curriculum targets {_target_id}"
        )
        continue
    _target_index = next(
        (
            index
            for index, item in enumerate(ALL_CURRICULA)
            if item["id"] == _target_id
        ),
        -1,
    )
    if _target_index < 0:
        _GENERATED_CURRICULA_PROBLEMS.append(
            f"canonical overlay target is absent: {_target_id}"
        )
        continue
    _canonical_slot = dict(ALL_CURRICULA[_target_index])
    ALL_CURRICULA[_target_index] = {
        **_canonical_slot,
        "detail": str(_generated_curriculum.get("detail") or _canonical_slot["detail"]),
        "cards": _generated_curriculum["cards"],
        "version": _generated_curriculum["version"],
        "material_source": "adopted_generated",
        "generated_source_id": _generated_curriculum["generated_source_id"],
        "generated_source_path": _generated_curriculum["generated_source_path"],
        "generated_adoption_receipt": _generated_curriculum[
            "generated_adoption_receipt"
        ],
        "generated_adoption_receipt_sha256": _generated_curriculum[
            "generated_adoption_receipt_sha256"
        ],
        "generated_grounding": dict(
            _generated_curriculum.get("generated_grounding") or {}
        ),
        "generated_corpus_bundle_sha256": str(
            _generated_curriculum.get("generated_corpus_bundle_sha256") or ""
        ),
    }
    _overlaid_targets.add(_target_id)


def generated_grounding_metadata(entry: dict[str, Any]) -> dict[str, Any]:
    """Return the exact generated-corpus binding carried into public receipts."""
    grounding = entry.get("generated_grounding")
    copied = dict(grounding) if isinstance(grounding, dict) else {}
    digest = str(
        entry.get("generated_corpus_bundle_sha256")
        or copied.get("corpus_bundle_sha256")
        or ""
    ).upper()
    return {
        "generated_grounding": copied,
        "generated_corpus_bundle_sha256": digest,
    }


def current_generated_curriculum_problems() -> list[str]:
    """Recheck generated material at sync time to close corpus/card drift."""
    problems = list(_GENERATED_CURRICULA_PROBLEMS)
    for entry in ALL_CURRICULA:
        if entry.get("material_source") != "adopted_generated":
            continue
        problem, binding = _generated_cards_are_grounded(
            entry.get("cards") or [],
            str(entry.get("discipline") or ""),
        )
        source_id = str(entry.get("generated_source_id") or entry.get("id"))
        if problem:
            problems.append(f"{source_id}: {problem}")
            continue
        expected = generated_grounding_metadata(entry)["generated_grounding"]
        if binding != expected:
            problems.append(
                f"{source_id}: generated grounding binding drifted after adoption load"
            )
    return list(dict.fromkeys(problems))


def generated_curricula_integrity_ok(
    problems: list[str] | None = None,
) -> bool:
    """One explicit fail-closed predicate shared by index and manifest."""
    selected = (
        current_generated_curriculum_problems()
        if problems is None
        else list(problems)
    )
    return not selected


ACTIVE_CURRICULUM_ID = "capabilities"
# The MIXED/default template reproduces the active curriculum, so it must use the active
# curriculum's discipline (else the default template would carry mismatched prompt shapes).
ACTIVE_DISCIPLINE = next(
    (c["discipline"] for c in ALL_CURRICULA if c["id"] == ACTIVE_CURRICULUM_ID),
    "aec",
)
from engel_ui_prompt_training_support import (  # noqa: E402
    DEFAULT_TRAININGS_PER_HOUR,
    TRAINING_LEVEL_PROFILES,
    TRAINING_LEVELS,
    validate_training_level,
    validate_trainings_per_hour,
)
from engel_prompt_novelty import (  # noqa: E402
    DEFAULT_PACKS_DIR,
    canonical_base_prompt_sha256,
    load_prompt_history,
    material_card_sha256,
)

ACTIVE_TRAINING_SCRIPTS = [
    "tools/engel_construction_renewal_curriculum.py",
    "tools/engel_curriculum_renewal.py",
    "tools/engel_math_problems.py",
    "tools/engel_prompt_novelty.py",
    "tools/engel_ui_prompt_training_support.py",
    "tools/run_engel_flutter_main_ui_prompt_training.py",
    "tools/run_engel_ui_prompt_training.py",
    "tools/run_engel_ui_input_creation_training_hour.py",
    "tools/run_engel_ui_input_creation_training_loop.py",
    "tools/run_engel_code_creation_ui_training.py",
    "tools/run_engel_local_llm_prompt_training_template.py",
    "tools/run_engel_sub_engel_prompt_training_companion.py",
    "tools/run_engel_four_hour_prompt_training.py",
    "tools/run_engel_four_hour_cluster_prompt_training.py",
    "tools/run_engel_local_personality_training_sessions.py",
    "tools/run_engel_personality_training_sessions.py",
    "tools/run_engel_runpod_parallel_personality_training.py",
    "tools/run_engel_lora_training_on_runpod.py",
    "tools/build_engel_lora_training_package.py",
    "tools/create_engel_runpod_training_pod.py",
    "tools/prepare_local_llm_training_dataset.py",
    "tools/verify_local_llm_training_prep.py",
    "tools/verify_engel_training_trusted_memory.py",
    "tools/verify_engel_training_schedule.py",
    "tools/verify_engel_curriculum_renewal.py",
    "tools/verify_engel_prompt_novelty.py",
    "tools/verify_engel_local_personality_training.py",
    "tools/verify_engel_personality_training.py",
]

# The legacy field-coordination v17 cards remain importable for historical review, but
# they are not valid material for the current AEC admission contract. Their prompts name
# no exact corpus document/edition and request no quote-bound code claim, while AEC rows
# can now be admitted only with one manifest document, an explicit Section citation, and
# an exact local source excerpt. Offering those cards as ``Novelty Ready (AEC)`` would
# create a run whose truthful answers are structurally unable to enter training.
#
# Future AEC renewal belongs here only after each card is bound to a single manifest
# document/edition and its generated prompts ask for the Section + exact-quote proof the
# grader enforces. No nonce or cosmetic prompt mutation is an acceptable substitute.
NOVELTY_ALTERNATE_CURRICULA: list[dict[str, Any]] = []
WEAKNESS_ADOPTED_PATH = (
    CANONICAL_ROOT / "generated" / "ENGEL_WEAKNESS_CURRICULUM_ADOPTED.json"
)

PROMPT_SOURCES = [
    ("sources/system/ENGEL_SYSTEM.md", "prompts/ENGEL_SYSTEM.md"),
    ("sources/personality/personality.md", "personality.md"),
    ("sources/personality/soul.md", "soul.md"),
    (
        "sources/personality/ENGEL_AI_MERGED_PERSONALITY.md",
        "memory/personality/ENGEL_AI_MERGED_PERSONALITY.md",
    ),
    (
        "sources/personality/ENGEL_AI_SYSTEM_PROMPT_FOR_LOCAL_LLM.md",
        "memory/personality_merge/ENGEL_AI_SYSTEM_PROMPT_FOR_LOCAL_LLM.md",
    ),
    (
        "sources/four_hour_prompt/Engel AI 4-Hour Local LLM Training Prompt",
        "library_intake/Engel AI 4-Hour Local LLM Training Prompt",
    ),
    (
        "sources/overnight_training/OVERNIGHT_TRAINING_CURRICULUM.md",
        "workflows/overnight_training/OVERNIGHT_TRAINING_CURRICULUM.md",
    ),
]

HOURLY_MATERIAL_CARDS = FRESH_MATERIAL_CARDS_V17[:8]
HOUR_MATERIAL_CARD = HOURLY_MATERIAL_CARDS[0]
HOUR_PROMPTS = fresh_material_prompts_v17(HOUR_MATERIAL_CARD)[0]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def safe_write_text(path: Path, text: str) -> None:
    if path.drive.lower() == "c:":
        raise RuntimeError(f"refusing to write Engel training asset on C: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def safe_write_json(path: Path, payload: Any) -> None:
    safe_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def safe_write_stable_template(path: Path, payload: dict[str, Any]) -> None:
    """Keep byte-identical campaign templates stable across no-op asset syncs."""

    stable_payload = dict(payload)
    if path.is_file() and not path.is_symlink():
        try:
            existing = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            existing = None
        if isinstance(existing, dict):
            comparable_existing = dict(existing)
            comparable_new = dict(stable_payload)
            comparable_existing.pop("updated_at_utc", None)
            comparable_new.pop("updated_at_utc", None)
            if comparable_existing == comparable_new:
                existing_stamp = str(existing.get("updated_at_utc") or "").strip()
                if existing_stamp:
                    stable_payload["updated_at_utc"] = existing_stamp
    safe_write_json(path, stable_payload)


def copy_file(source_rel: str, dest_rel: str) -> dict[str, Any]:
    source = ROOT / source_rel
    dest = CANONICAL_ROOT / dest_rel
    record: dict[str, Any] = {
        "source": str(source),
        "canonical_copy": str(dest),
        "exists": source.is_file(),
    }
    if not source.is_file():
        return record
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    record.update(
        {
            "bytes": dest.stat().st_size,
            "sha256": sha256_file(dest),
        }
    )
    return record


def build_template(
    cards: list[dict[str, Any]] | None = None,
    version: str | None = None,
    template_id: str | None = None,
    discipline: str | None = None,
    generated_grounding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Defaults reproduce the active/MIXED template (back-compat); pass a curriculum's
    # cards+version+id+discipline to materialize any of the other curricula as its own
    # template. `discipline` selects the domain-native prompt generator (aec/math/
    # engineering) and is written into the template so the runner assembles the matching
    # level guidance + answer contract and applies the matching eligibility gate.
    discipline = discipline or ACTIVE_DISCIPLINE
    hourly_cards = (cards if cards is not None else HOURLY_MATERIAL_CARDS)[:8]
    if not hourly_cards:
        raise ValueError("training template requires at least one material card")
    if cards is ENGEL_CONSTRUCTION_RENEWAL_CARDS_V1:
        renewal_problems = validate_renewal_cards()
        if renewal_problems:
            raise ValueError(
                "construction renewal material is invalid: "
                + " | ".join(renewal_problems)
            )
    if any(
        cards is renewal_cards
        for renewal_cards in (
            ENGEL_CAPABILITIES_RENEWAL_CARDS_V2,
            ENGEL_MATH_SCHOOL_RENEWAL_CARDS_V2,
            ENGEL_SELF_BUILD_RENEWAL_CARDS_V2,
            ENGEL_CHAT_COMMUNICATION_RENEWAL_CARDS_V2,
        )
    ):
        renewal_problems = validate_renewal_curricula()
        if renewal_problems:
            raise ValueError(
                "non-AEC renewal material is invalid: "
                + " | ".join(renewal_problems)
            )
    maximum_hours = len(hourly_cards)
    hour_card = hourly_cards[0]
    hour_prompts = curriculum_prompts(hour_card, discipline)[0]
    version = version or CAMPAIGN_MATERIAL_VERSION
    template_id = template_id or "engel_main_mixed_chat_creation_scheduled"
    cycle_prompt_sets = []
    for hour, material_card in enumerate(hourly_cards, start=1):
        prompts = curriculum_prompts(material_card, discipline)[0]
        cycle_prompt_sets.append(
            {
                "cycle": hour,
                "scheduled_hour": hour,
                "minutes": 60,
                "fresh_material": True,
                "material_topic": material_card["topic"],
                "material_card": dict(material_card),
                "prompt_count": len(prompts),
                "prompts": prompts,
            }
        )
    template = {
        "schema": "engel_main_scheduled_prompt_training_template_v2",
        "template_id": template_id,
        "training_discipline": discipline,
        "updated_at_utc": utc_now(),
        "entry_point": "visible Engel AI Main chat UI",
        "material_version": version,
        "fresh_material": True,
        "material_topic": hour_card["topic"],
        "material_topics": [
            material_card["topic"] for material_card in hourly_cards
        ],
        "provider_policy": "local_only",
        "route_policy": "strict local-only ROG UI to CT246 local GGUF; provider fallback explicitly disabled for every turn",
        "scheduled_controls": {
            "minimum_hours": 1,
            "maximum_hours": maximum_hours,
            "default_hours": 1,
            "training_levels": list(TRAINING_LEVELS),
            "default_training_level": "medium",
            "minimum_trainings_per_hour": 1,
            "maximum_trainings_per_hour": 10,
            "default_trainings_per_hour": DEFAULT_TRAININGS_PER_HOUR,
            "minutes_derived_from_hours": True,
            "one_distinct_cycle_per_hour": True,
            "training_level_controls_depth_not_count": True,
            "balanced_hourly_selection": True,
        },
        "training_level_profiles": TRAINING_LEVEL_PROFILES,
        "active_prompts": hour_prompts,
        "smoke_prompts": hour_prompts[:3],
        "cycle_prompt_sets": cycle_prompt_sets,
        "maximum_scheduled_prompt_count": sum(
            len(item["prompts"]) for item in cycle_prompt_sets
        ),
        "proof_required": [
            "wrapper receipt for every prompt",
            "persistent chat memory append for every prompt",
            "Meeting Room order for creation/device/training prompts",
            "no C-drive output paths",
            "no provider API or provider bridge use",
            "CT246 semantic quality and training eligibility for every accepted turn",
        ],
    }
    if generated_grounding is not None:
        grounding = dict(generated_grounding)
        digest = str(grounding.get("corpus_bundle_sha256") or "").upper()
        if grounding and (
            grounding.get("schema") != GENERATED_GROUNDING_SCHEMA
            or grounding.get("verified") is not True
            or grounding.get("card_count") != len(hourly_cards)
            or re.fullmatch(r"[0-9A-F]{64}", digest) is None
        ):
            raise ValueError("generated AEC grounding binding is malformed")
        template["generated_grounding"] = grounding
        template["generated_corpus_bundle_sha256"] = digest
    return template


def _load_adopted_weakness_source() -> tuple[dict[str, Any] | None, list[str]]:
    """Load only explicitly adopted, still-grounded weakness cards."""

    if not WEAKNESS_ADOPTED_PATH.is_file():
        return None, []
    problems: list[str] = []
    try:
        payload = json.loads(WEAKNESS_ADOPTED_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, TypeError) as exc:
        return None, [f"adopted weakness curriculum could not be read: {exc}"]
    if not isinstance(payload, dict) or payload.get("schema") != "engel_weakness_curriculum_v1":
        return None, ["adopted weakness curriculum has the wrong schema"]
    if payload.get("adoption") != "adopted" or not payload.get("adopted_at_utc"):
        return None, ["weakness curriculum is not explicitly adopted"]
    cards = payload.get("cards")
    if not isinstance(cards, list) or not cards:
        return None, ["adopted weakness curriculum has no cards"]
    verified_cards: list[dict[str, Any]] = []
    for index, card in enumerate(cards, start=1):
        if not isinstance(card, dict):
            problems.append(f"adopted weakness card {index} is not an object")
            continue
        try:
            material_card_sha256(card)
        except ValueError as exc:
            problems.append(f"adopted weakness card {index} is incomplete: {exc}")
            continue
        artifacts = card.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            problems.append(f"adopted weakness card {index} names no grounding artifacts")
            continue
        artifact_records: list[dict[str, Any]] = []
        invalid_artifacts: list[str] = []
        root_resolved = ROOT.resolve()
        for item in artifacts:
            raw = str(item or "").replace("\\", "/").strip()
            relative = Path(raw)
            if (
                not raw
                or relative.is_absolute()
                or relative.drive
                or ".." in relative.parts
            ):
                invalid_artifacts.append(raw or "<empty>")
                continue
            candidate = ROOT / relative
            try:
                resolved = candidate.resolve(strict=True)
            except OSError:
                invalid_artifacts.append(raw)
                continue
            if (
                resolved == root_resolved
                or root_resolved not in resolved.parents
                or candidate.is_symlink()
                or not resolved.is_file()
            ):
                invalid_artifacts.append(raw)
                continue
            artifact_records.append(
                {
                    "path": relative.as_posix(),
                    "resolved_path": str(resolved),
                    "sha256": sha256_file(resolved),
                    "bytes": resolved.stat().st_size,
                }
            )
        if invalid_artifacts:
            problems.append(
                f"adopted weakness card {index} has unsafe or missing artifacts: "
                f"{invalid_artifacts}"
            )
            continue
        verified_card = dict(card)
        verified_card["_grounding_artifact_records"] = artifact_records
        verified_cards.append(verified_card)
    if problems:
        # Fail closed for the whole adopted source.  Mixing a few apparently healthy cards
        # with a now-corrupt adopted file would hide that the reviewed curriculum drifted.
        return None, problems
    return (
        {
            "id": "adopted_weaknesses",
            "title": "Adopted Measured Weaknesses",
            "detail": "Operator-adopted lessons generated from rejected packs and held-out failures.",
            "cards": verified_cards,
            "version": str(payload.get("adopted_at_utc")),
            "discipline": "engineering",
            "source_kind": "explicitly_adopted_weakness",
            "source_path": str(WEAKNESS_ADOPTED_PATH),
        },
        [],
    )


def novelty_material_sources() -> tuple[list[dict[str, Any]], list[str]]:
    """Return reviewed material sources in preparation priority order."""

    adopted, problems = _load_adopted_weakness_source()
    sources: list[dict[str, Any]] = []
    if adopted is not None:
        sources.append(adopted)
    sources.extend(dict(item) for item in NOVELTY_ALTERNATE_CURRICULA)
    sources.extend(
        {**dict(item), "source_kind": "canonical_curriculum"}
        for item in ALL_CURRICULA
    )
    return sources, problems


def prepare_novelty_templates(
    templates_dir: Path,
    *,
    packs_dir: Path = DEFAULT_PACKS_DIR,
    sources: list[dict[str, Any]] | None = None,
    maximum_cycles: int = 8,
) -> dict[str, Any]:
    """Materialize whole, genuinely unused ten-prompt cycles by discipline.

    Cards are selected, never rewritten.  A card is eligible only when all ten prompts
    generated from its scenario/constraint/proof are absent from every historical pack.
    This makes the output directly usable by the existing scheduled runner while keeping
    training discipline and answer-contract semantics coherent within a template.
    """

    templates_dir = Path(templates_dir)
    history = load_prompt_history(Path(packs_dir))
    default_sources, source_problems = novelty_material_sources()
    material_sources = list(sources) if sources is not None else default_sources
    report: dict[str, Any] = {
        "schema": "engel_novelty_aware_asset_preparation_v1",
        "ok": history.get("ok") is True and not source_problems,
        "generated_at_utc": utc_now(),
        "history_pack_count": history["history_pack_count"],
        "history_row_count": history["history_row_count"],
        "history_valid_reservation_count": history[
            "history_valid_reservation_count"
        ],
        "history_observation_count": history["history_observation_count"],
        "history_unique_prompt_count": history["history_unique_prompt_count"],
        "history_prompt_set_sha256": history["history_prompt_set_sha256"],
        "history_pack_snapshot_sha256": history["history_pack_snapshot_sha256"],
        "history_reservation_snapshot_sha256": history[
            "history_reservation_snapshot_sha256"
        ],
        "history_snapshot_sha256": history["history_snapshot_sha256"],
        "history_problems": list(history.get("problems") or []),
        "source_problems": source_problems,
        "maximum_cycles_per_template": int(maximum_cycles),
        "templates": [],
        "index_entries": [],
        "skipped": [],
    }
    if report["ok"] is not True:
        return report

    historical_hashes = set(history["history_prompt_hashes"])
    candidates_by_discipline: dict[str, list[dict[str, Any]]] = {}
    seen_material: set[str] = set()
    seen_cycles: set[str] = set()
    for source in material_sources:
        source_id = str(source.get("id") or "").strip()
        discipline = str(source.get("discipline") or "").strip().casefold()
        cards = source.get("cards")
        if not source_id or discipline not in {"aec", "math", "engineering", "communication"}:
            report["skipped"].append(
                {"source": source_id or "<missing>", "reason": "invalid source metadata"}
            )
            continue
        if not isinstance(cards, list):
            report["skipped"].append(
                {"source": source_id, "reason": "source cards are not a list"}
            )
            continue
        for card_index, card in enumerate(cards, start=1):
            if not isinstance(card, dict):
                report["skipped"].append(
                    {"source": source_id, "card": card_index, "reason": "card is not an object"}
                )
                continue
            try:
                material_sha = material_card_sha256(card)
            except ValueError as exc:
                report["skipped"].append(
                    {"source": source_id, "card": card_index, "reason": str(exc)}
                )
                continue
            if material_sha in seen_material:
                continue
            seen_material.add(material_sha)
            prompts = curriculum_prompts(card, discipline)[0]
            prompt_hashes = [canonical_base_prompt_sha256(prompt) for prompt in prompts]
            cycle_sha = hashlib.sha256(
                "\n".join(prompt_hashes).encode("ascii")
            ).hexdigest()
            if len(prompts) != 10 or len(set(prompt_hashes)) != 10:
                report["skipped"].append(
                    {
                        "source": source_id,
                        "card": card_index,
                        "material_card_sha256": material_sha,
                        "reason": "card does not generate ten distinct substantive prompts",
                    }
                )
                continue
            replayed = sorted(set(prompt_hashes).intersection(historical_hashes))
            if replayed:
                report["skipped"].append(
                    {
                        "source": source_id,
                        "card": card_index,
                        "material_card_sha256": material_sha,
                        "reason": "one or more generated base prompts already exist in history",
                        "replayed_prompt_count": len(replayed),
                        "replayed_prompt_hashes": replayed,
                    }
                )
                continue
            if cycle_sha in seen_cycles:
                continue
            seen_cycles.add(cycle_sha)
            candidates_by_discipline.setdefault(discipline, []).append(
                {
                    "source_id": source_id,
                    "source_title": str(source.get("title") or source_id),
                    "source_kind": str(source.get("source_kind") or "reviewed"),
                    "source_version": str(source.get("version") or ""),
                    "source_card_index": card_index,
                    "card": dict(card),
                    "material_card_sha256": material_sha,
                    "grounding_artifact_records": list(
                        card.get("_grounding_artifact_records") or []
                    ),
                    "prompt_hashes": prompt_hashes,
                    "prompt_set_sha256": cycle_sha,
                }
            )

    templates_dir.mkdir(parents=True, exist_ok=True)
    for discipline in ("aec", "engineering", "math", "communication"):
        candidates = candidates_by_discipline.get(discipline, [])[: int(maximum_cycles)]
        if not candidates:
            continue
        for item in candidates:
            item["material_binding_sha256"] = hashlib.sha256(
                json.dumps(
                    {
                        "material_card_sha256": item["material_card_sha256"],
                        "grounding_artifact_records": item[
                            "grounding_artifact_records"
                        ],
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
        source_digest = hashlib.sha256(
            "\n".join(item["material_binding_sha256"] for item in candidates).encode(
                "ascii"
            )
        ).hexdigest()
        template_id = f"engel_novelty_ready_{discipline}_{source_digest[:12]}"
        template = build_template(
            cards=[item["card"] for item in candidates],
            version=f"novelty_ready_{discipline}_{source_digest[:12]}",
            template_id=template_id,
            discipline=discipline,
        )
        template.update(
            {
                "novelty_prepared": True,
                "novelty_preflight_required": True,
                "novelty_policy": "whole reviewed material cards only; no nonce, suffix, or cosmetic prompt mutation",
                "history_pack_count_at_preparation": history["history_pack_count"],
                "history_unique_prompt_count_at_preparation": history[
                    "history_unique_prompt_count"
                ],
                "history_prompt_set_sha256_at_preparation": history[
                    "history_prompt_set_sha256"
                ],
                "history_pack_snapshot_sha256_at_preparation": history[
                    "history_pack_snapshot_sha256"
                ],
                "history_reservation_snapshot_sha256_at_preparation": history[
                    "history_reservation_snapshot_sha256"
                ],
                "history_snapshot_sha256_at_preparation": history[
                    "history_snapshot_sha256"
                ],
                "material_source_digest_sha256": source_digest,
            }
        )
        for cycle, candidate in zip(template["cycle_prompt_sets"], candidates):
            generated_hashes = [
                canonical_base_prompt_sha256(prompt) for prompt in cycle["prompts"]
            ]
            if generated_hashes != candidate["prompt_hashes"]:
                raise RuntimeError("novelty template prompt generation changed during preparation")
            cycle.update(
                {
                    "novelty_prepared": True,
                    "source_curriculum_id": candidate["source_id"],
                    "source_curriculum_title": candidate["source_title"],
                    "source_kind": candidate["source_kind"],
                    "source_version": candidate["source_version"],
                    "source_card_index": candidate["source_card_index"],
                    "material_card_sha256": candidate["material_card_sha256"],
                    "material_binding_sha256": candidate[
                        "material_binding_sha256"
                    ],
                    "grounding_artifact_records": candidate[
                        "grounding_artifact_records"
                    ],
                    "base_prompt_hashes": candidate["prompt_hashes"],
                    "base_prompt_set_sha256": candidate["prompt_set_sha256"],
                }
            )
        path = templates_dir / f"ENGEL_TEMPLATE_NOVELTY_READY_{discipline.upper()}.json"
        safe_write_json(path, template)
        source_ids = list(dict.fromkeys(item["source_id"] for item in candidates))
        discipline_label = "AEC" if discipline == "aec" else discipline.title()
        entry = {
            "id": f"novelty_ready_{discipline}",
            "title": f"Novelty Ready ({discipline_label})",
            "detail": (
                f"{len(candidates)} whole reviewed, historically unused prompt cycles; "
                "rechecked immediately before every scheduled run."
            ),
            "version": template["material_version"],
            "discipline": discipline,
            "template_path": str(path),
            "topic_count": len(template["material_topics"]),
            "prompt_count": template["maximum_scheduled_prompt_count"],
            "maximum_hours": len(candidates),
            "topics": template["material_topics"],
            "active": False,
            "novelty_ready": True,
            "source_curricula": source_ids,
            "history_pack_snapshot_sha256": history[
                "history_pack_snapshot_sha256"
            ],
            "history_snapshot_sha256": history["history_snapshot_sha256"],
        }
        report["templates"].append(
            {
                "discipline": discipline,
                "template_path": str(path),
                "cycle_count": len(candidates),
                "prompt_count": template["maximum_scheduled_prompt_count"],
                "material_source_digest_sha256": source_digest,
                "source_curricula": source_ids,
            }
        )
        report["index_entries"].append(entry)
    report["prepared_template_count"] = len(report["templates"])
    report["prepared_cycle_count"] = sum(
        item["cycle_count"] for item in report["templates"]
    )
    report["prepared_prompt_count"] = sum(
        item["prompt_count"] for item in report["templates"]
    )
    return report


def wrapper_script(
    hours_default: int,
    mode: str,
    # (2026-08-08) Ladder raised: expert is the new floor, so it is also the wrapper
    # default. validate_training_level clamps legacy names up before membership.
    training_level_default: str = "expert",
    trainings_per_hour_default: int = DEFAULT_TRAININGS_PER_HOUR,
) -> str:
    if not 1 <= int(hours_default) <= 8:
        raise ValueError("wrapper default hours must be from 1 through 8")
    training_level_default = validate_training_level(training_level_default)
    if training_level_default not in TRAINING_LEVELS:
        raise ValueError(
            "wrapper default training level must be one of: "
            + ", ".join(TRAINING_LEVELS)
        )
    trainings_per_hour_default = validate_trainings_per_hour(
        trainings_per_hour_default
    )
    template = CANONICAL_ROOT / "templates" / "ENGEL_HOUR_PROMPT_TRAINING_MIXED.json"
    profiles_json = json.dumps(
        TRAINING_LEVEL_PROFILES,
        separators=(",", ":"),
        sort_keys=True,
    ).replace("'", "''")
    return rf"""param(
  [ValidateRange(1, 8)]
  [int]$Hours = {hours_default},
  [ValidateSet('low', 'medium', 'high', 'expert', 'principal', 'distinguished', 'fellow')]
  [string]$TrainingLevel = '{training_level_default}',
  [ValidateSet('slm', 'llm', 'slm,llm')]
  [string]$TrainingTargets = 'slm,llm',
  [ValidateRange(1, 10)]
  [int]$TrainingsPerHour = {trainings_per_hour_default},
  [ValidateRange(1, 8)]
  [int]$TemplateCycle = 1,
  [ValidateRange(1, 80)]
  [int]$StartIndex = 1,
  [int]$PerPromptTimeout = 760,
  [string]$Template = '{template}'
)
$ErrorActionPreference = 'Stop'
$AppRoot = '{ROOT}'
$CanonicalRoot = '{CANONICAL_ROOT}'
$RunDir = Join-Path $CanonicalRoot 'runs\ui_prompt'
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
$Stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ') + "_p$PID"
$Log = Join-Path $RunDir "engel_scheduled_prompt_training_$Stamp.log"
$Receipt = Join-Path $RunDir "engel_scheduled_prompt_training_lifecycle_$Stamp.json"
$Python = Join-Path $AppRoot 'runtime\python310\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {{ $Python = 'python.exe' }}
$LevelProfiles = '{profiles_json}' | ConvertFrom-Json
$LevelProfile = $LevelProfiles.PSObject.Properties[$TrainingLevel].Value
$CadenceSeconds = [double](3600 / $TrainingsPerHour)
$PlanPrompts = if ('{mode}' -eq 'smoke') {{ 3 }} else {{ [int]$Hours * [int]$TrainingsPerHour }}
if ($StartIndex -gt $PlanPrompts) {{
  throw "StartIndex $StartIndex is past the $PlanPrompts prompts in this plan."
}}
$RequestedPrompts = [int]($PlanPrompts - $StartIndex + 1)
$Minutes = if ('{mode}' -eq 'smoke') {{
  3.0
}} else {{
  [double](($RequestedPrompts * $CadenceSeconds) / 60)
}}
if ([string]::IsNullOrWhiteSpace($Template)) {{
  throw 'Curriculum template is required; refusing to substitute another curriculum.'
}}
if (-not (Test-Path -LiteralPath $Template -PathType Leaf)) {{
  throw "Selected curriculum template no longer exists: $Template"
}}
try {{
  $TemplatePayload = Get-Content -LiteralPath $Template -Raw -Encoding UTF8 | ConvertFrom-Json
}} catch {{
  throw ('Selected curriculum template is not valid JSON: ' + $Template)
}}
$MaterialVersion = [string]$TemplatePayload.material_version
if ([string]::IsNullOrWhiteSpace($MaterialVersion)) {{
  throw ('Selected curriculum template has no material_version: ' + $Template)
}}
$Args = @(
  (Join-Path $AppRoot 'tools\run_engel_flutter_main_ui_prompt_training.py'),
  '--mode', '{mode}',
  '--minutes', [string]$Minutes,
  '--hours', [string]$Hours,
  '--training-level', $TrainingLevel,
  '--training-targets', $TrainingTargets,
  '--trainings-per-hour', [string]$TrainingsPerHour,
  '--template-cycle', [string]$TemplateCycle,
  '--exact-template-cycle',
  '--start-index', [string]$StartIndex,
  '--per-prompt-timeout', [string]$PerPromptTimeout,
  '--template', $Template,
  '--launcher-pid', [string]$PID,
  '--launcher-log', $Log,
  '--lifecycle-receipt', $Receipt,
  '--local-only',
  '--fresh-chat'
)
$Controls = [pscustomobject]@{{
  scheduled_hours = $Hours
  requested_minutes = $Minutes
  training_level = $TrainingLevel
  training_targets = $TrainingTargets
  training_level_profile = $LevelProfile.profile_id
  training_level_guidance = $LevelProfile.guidance
  trainings_per_hour = $TrainingsPerHour
  template_cycle = $TemplateCycle
  template_cycle_contract = 'EXACT'
  start_index = $StartIndex
  plan_prompts = $PlanPrompts
  requested_prompts = $RequestedPrompts
  cadence_seconds = $CadenceSeconds
  distinct_hourly_cycles = $Hours
  template = $Template
  material_version = $MaterialVersion
}}
$lifecycle = [pscustomobject]@{{
  schema = 'engel_main_prompt_training_launch_lifecycle_v2'
  status = 'RUNNING'
  started_at_utc = (Get-Date).ToUniversalTime().ToString('o')
  finished_at_utc = $null
  exit_code = $null
  app_root = $AppRoot
  canonical_root = $CanonicalRoot
  python = $Python
  script = $Args[0]
  mode = '{mode}'
  template = $Template
  controls = $Controls
  training_level = $TrainingLevel
  training_targets = $TrainingTargets
  trainings_per_hour = $TrainingsPerHour
  template_cycle = $TemplateCycle
  template_cycle_contract = 'EXACT'
  distinct_hourly_cycles = $Hours
  provider_policy = 'local_only'
  prompt_run_claim_owner = 'python_runner_os_lock'
  active_guard_owner = 'python_runner'
  material_version = $MaterialVersion
  log = $Log
  events = @(
    [pscustomobject]@{{
      event = 'launch_started'
      time_utc = (Get-Date).ToUniversalTime().ToString('o')
      status = 'RUNNING'
      training_level = $TrainingLevel
      training_targets = $TrainingTargets
      trainings_per_hour = $TrainingsPerHour
      template_cycle = $TemplateCycle
      template_cycle_contract = 'EXACT'
    }}
  )
}}
$lifecycle | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Receipt -Encoding UTF8
# Python owns the OS-released prompt-run claim and active.json guard.  The launcher
# records process lifecycle only and must never overwrite either concurrency surface.
$Exit = 1
try {{
  # (2026-08-10) EAP must be Continue across the native call: with Stop, the FIRST
  # stderr line becomes a throwing NativeCommandError and the log captures one line
  # instead of the traceback (the novelty-refusal launch failed with an unreadable
  # log exactly this way). Continue lets *> stream the full stderr into $Log.
  $ErrorActionPreference = 'Continue'
  & $Python @Args *> $Log
  $Exit = $LASTEXITCODE
  if ($null -eq $Exit) {{ $Exit = 1 }}
}} catch {{
  "launcher error: $($_ | Out-String)" | Add-Content -LiteralPath $Log
  $Exit = 1
}} finally {{
  $ErrorActionPreference = 'Stop'
}}
$lifecycle.status = $(if ($Exit -eq 0) {{ 'COMPLETE' }} else {{ 'FAILED' }})
$lifecycle.finished_at_utc = (Get-Date).ToUniversalTime().ToString('o')
$lifecycle.exit_code = $Exit
$lifecycle.events += [pscustomobject]@{{
  event = 'launch_finished'
  time_utc = $lifecycle.finished_at_utc
  status = $lifecycle.status
  exit_code = $Exit
  training_level = $TrainingLevel
  training_targets = $TrainingTargets
  trainings_per_hour = $TrainingsPerHour
  template_cycle = $TemplateCycle
  template_cycle_contract = 'EXACT'
}}
$lifecycle | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Receipt -Encoding UTF8
exit $Exit
"""


def sync_assets() -> dict[str, Any]:
    CANONICAL_ROOT.mkdir(parents=True, exist_ok=True)
    generated_curriculum_problems = current_generated_curriculum_problems()
    copied_scripts = [
        copy_file(source, f"scripts/source_copies/{Path(source).name}")
        for source in ACTIVE_TRAINING_SCRIPTS
    ]
    copied_prompts = [copy_file(source, dest) for dest, source in PROMPT_SOURCES]

    templates_dir = CANONICAL_ROOT / "templates"
    template_path = templates_dir / "ENGEL_HOUR_PROMPT_TRAINING_MIXED.json"
    # Build the MIXED/default template from the ACTIVE curriculum's own entry (cards +
    # version + discipline) so there is one source of truth. Relying on build_template()'s
    # shim defaults could emit MIXED with cards from one curriculum but a discipline from
    # another if the shim were swapped without updating ACTIVE_CURRICULUM_ID.
    active_entry = next(
        (c for c in ALL_CURRICULA if c["id"] == ACTIVE_CURRICULUM_ID), ALL_CURRICULA[0]
    )
    template_payload = build_template(
        cards=active_entry["cards"],
        version=active_entry["version"],
        discipline=active_entry["discipline"],
        generated_grounding=(
            active_entry.get("generated_grounding")
            if active_entry.get("material_source") == "adopted_generated"
            else None
        ),
    )
    safe_write_json(template_path, template_payload)

    # Materialize EVERY curriculum as its own template + an index the UI reads, so
    # all training combinations are visible and selectable, not just the active one.
    canonical_history = load_prompt_history(DEFAULT_PACKS_DIR)
    historical_prompt_hashes = set(canonical_history["history_prompt_hashes"])
    curricula_index: list[dict[str, Any]] = []
    for entry in ALL_CURRICULA:
        curric_template_id = f"engel_template_{entry['id']}"
        payload = build_template(
            cards=entry["cards"],
            version=entry["version"],
            template_id=curric_template_id,
            discipline=entry["discipline"],
            generated_grounding=(
                entry.get("generated_grounding")
                if entry.get("material_source") == "adopted_generated"
                else None
            ),
        )
        curric_path = templates_dir / f"ENGEL_TEMPLATE_{entry['id'].upper()}.json"
        safe_write_stable_template(curric_path, payload)
        cycle_novelty: list[bool] = []
        replayed_prompt_hashes: set[str] = set()
        for cycle in payload["cycle_prompt_sets"]:
            cycle_hashes = [
                canonical_base_prompt_sha256(prompt)
                for prompt in cycle["prompts"]
            ]
            replayed = set(cycle_hashes).intersection(historical_prompt_hashes)
            replayed_prompt_hashes.update(replayed)
            cycle_novelty.append(
                len(cycle_hashes) == 10
                and len(set(cycle_hashes)) == 10
                and not replayed
            )
        # (2026-08-10) Availability is the LONGEST RUN of consecutive novel
        # cycles, starting anywhere and wrapping — the exact shape a plan takes
        # (_load_training_schedule walks (cycle_start + offset) % cycles, and
        # the runner auto-advances its start cycle past consumed material).
        # The old prefix-from-cycle-1 count called a curriculum with 7 fresh
        # hours "USED" the moment hour 1 was spent, which disabled its tile and
        # refused a launch the planner could compose without a single replay.
        cycle_count = len(cycle_novelty)
        complete_novel_cycles = sum(1 for value in cycle_novelty if value)
        if cycle_count and complete_novel_cycles == cycle_count:
            novel_run_hours = cycle_count
            novel_run_start_cycle = 1
        else:
            novel_run_hours = 0
            novel_run_start_cycle = 0
            for start in range(cycle_count):
                run = 0
                while run < cycle_count and cycle_novelty[(start + run) % cycle_count]:
                    run += 1
                if run > novel_run_hours:
                    novel_run_hours = run
                    novel_run_start_cycle = start + 1
        fully_ready = (
            canonical_history.get("ok") is True
            and len(cycle_novelty) == 8
            and complete_novel_cycles == 8
            and novel_run_hours == 8
        )
        # A curriculum is runnable while ANY fresh hour remains; the picker caps
        # the duration slider at novel_run_hours so a plan can never replay.
        can_run_fresh = (
            canonical_history.get("ok") is True and novel_run_hours >= 1
        )
        novelty_status = (
            "BLOCKED_HISTORY"
            if canonical_history.get("ok") is not True
            else "READY"
            if fully_ready
            else "EXHAUSTED"
            if complete_novel_cycles == 0
            else "PARTIAL"
        )
        curricula_index.append(
            {
                "id": entry["id"],
                "title": entry["title"],
                "detail": entry["detail"],
                "version": entry["version"],
                "discipline": entry["discipline"],
                "material_source": entry["material_source"],
                "generated_source_id": entry["generated_source_id"],
                "generated_source_path": entry.get("generated_source_path", ""),
                "generated_adoption_receipt": entry.get(
                    "generated_adoption_receipt", ""
                ),
                "generated_adoption_receipt_sha256": entry.get(
                    "generated_adoption_receipt_sha256", ""
                ),
                **generated_grounding_metadata(entry),
                "template_path": str(curric_path),
                "template_sha256": sha256_file(curric_path).lower(),
                "topic_count": len(payload["material_topics"]),
                "prompt_count": payload["maximum_scheduled_prompt_count"],
                "maximum_hours": int(
                    payload["scheduled_controls"]["maximum_hours"]
                ),
                "novelty_ready": can_run_fresh,
                "novelty_fully_ready": fully_ready,
                "novelty_status": novelty_status,
                "novel_hours_available": novel_run_hours,
                "novel_hours_start_cycle": novel_run_start_cycle,
                "novel_complete_cycle_count": complete_novel_cycles,
                "replayed_prompt_count": len(replayed_prompt_hashes),
                "history_snapshot_sha256": canonical_history[
                    "history_snapshot_sha256"
                ],
                "topics": payload["material_topics"],
                "active": entry["id"] == ACTIVE_CURRICULUM_ID,
            }
        )
    all_curricula_ready = (
        [item["id"] for item in curricula_index]
        == list(CANONICAL_CURRICULUM_IDS)
        and len(curricula_index) == 5
        and generated_curricula_integrity_ok(generated_curriculum_problems)
        and all(
            item["topic_count"] == 8
            and item["prompt_count"] == 80
            and item["maximum_hours"] == 8
            and item["novelty_fully_ready"] is True
            and item["novel_hours_available"] == 8
            and item["replayed_prompt_count"] == 0
            for item in curricula_index
        )
    )
    novelty_preparation = prepare_novelty_templates(templates_dir)
    # The five canonical curriculum IDs now point directly at complete renewal sets.
    # Keep novelty preparation as a proof report, but do not add duplicate
    # "Novelty Ready" choices beside the same material in the Training picker.
    safe_write_json(
        templates_dir / "novelty_preparation.json",
        novelty_preparation,
    )
    safe_write_json(
        templates_dir / "curricula_index.json",
        {
            "schema": "engel_training_curricula_index_v1",
            "updated_at_utc": utc_now(),
            "active_id": ACTIVE_CURRICULUM_ID,
            "default_template_path": str(template_path),
            "curriculum_count": len(curricula_index),
            "total_topics": sum(c["topic_count"] for c in curricula_index),
            "total_prompts": sum(c["prompt_count"] for c in curricula_index),
            "all_curricula_ready": all_curricula_ready,
            "curriculum_problems": list(generated_curriculum_problems),
            "curricula": curricula_index,
        },
    )
    safe_write_text(
        CANONICAL_ROOT / "run_hour_prompt_training.ps1",
        wrapper_script(1, "scheduled"),
    )
    safe_write_text(
        CANONICAL_ROOT / "run_smoke_prompt_training.ps1",
        wrapper_script(1, "smoke"),
    )
    safe_write_text(
        CANONICAL_ROOT / "README.md",
        "\n".join(
            [
                "# Engel Main Training Assets",
                "",
                "This is the canonical Engel Main training folder.",
                "",
                "- `scripts/source_copies` contains copied active training runners for inventory and review.",
                "- `templates/ENGEL_HOUR_PROMPT_TRAINING_MIXED.json` contains eight distinct fresh hourly cycles.",
                "- `templates/ENGEL_TEMPLATE_NOVELTY_READY_*.json` contains only whole reviewed material cards whose ten base prompts do not occur in any stamped historical training pack.",
                "- Every scheduled run rechecks canonical base-prompt hashes before opening Chat; repeated, duplicate, or unprovable history blocks the run before GPU refresh or UI delivery.",
                "- Before each scheduled prompt reaches Chat, Python publishes one immutable prompt-use reservation under an OS-released exclusive claim; a crash or failed pack cannot make delivered work replayable.",
                "- `run_hour_prompt_training.ps1` accepts `-Hours 1..8`, `-TrainingLevel low|medium|high|expert`, independent `-TrainingsPerHour 1..10`, and `-TrainingTargets slm|llm|slm,llm` controls.",
                "- Prompt Training records the selected model targets in its lifecycle and pack receipts; Train Selected Models applies admitted rows to those trainers.",
                "- Training level changes the depth and guidance embedded in every submitted prompt; it does not change the hourly count.",
                "- Trainings per hour defaults to 6 and selects a deterministic balanced set from each ten-prompt hourly cycle.",
                "- `run_smoke_prompt_training.ps1` launches the visible Engel Main chat runner against the smoke prompt set.",
                "- `runs/ui_prompt` receives launch logs and one valid JSON lifecycle receipt per run.",
                "",
                "The original active scripts remain in `tools` because existing Python, Rust, and Flutter routes call them directly.",
                "",
            ]
        ),
    )

    missing = [
        item["source"]
        for item in copied_scripts + copied_prompts
        if not item.get("exists")
    ]
    asset_integrity_ok = (
        not missing
        and novelty_preparation.get("ok") is True
        and generated_curricula_integrity_ok(generated_curriculum_problems)
        and [item["id"] for item in curricula_index]
        == list(CANONICAL_CURRICULUM_IDS)
        and len(curricula_index) == 5
        and all(
            item["topic_count"] == 8
            and item["prompt_count"] == 80
            and item["maximum_hours"] == 8
            for item in curricula_index
        )
    )
    manifest = {
        "schema": "engel_main_training_assets_manifest_v1",
        # Asset integrity is stable across a campaign. Prompt novelty availability is
        # intentionally separate: completed curricula become unavailable for another
        # prompt run, but their exact immutable bindings remain valid model evidence.
        "ok": asset_integrity_ok,
        "asset_integrity_ok": asset_integrity_ok,
        "updated_at_utc": utc_now(),
        "app_root": str(ROOT),
        "canonical_root": str(CANONICAL_ROOT),
        "scripts": copied_scripts,
        "prompt_sources": copied_prompts,
        "template_path": str(template_path),
        "material_version": CAMPAIGN_MATERIAL_VERSION,
        "provider_policy": "local_only",
        "template_prompt_count": len(template_payload["active_prompts"]),
        "template_hourly_cycle_count": len(template_payload["cycle_prompt_sets"]),
        "template_maximum_prompt_count": template_payload[
            "maximum_scheduled_prompt_count"
        ],
        "scheduled_controls": template_payload["scheduled_controls"],
        "all_five_curricula_ready": all_curricula_ready,
        "curriculum_bindings": [
            {
                **{
                    key: item[key]
                    for key in (
                        "id",
                        "title",
                        "discipline",
                        "version",
                        "template_path",
                        "template_sha256",
                        "prompt_count",
                        "maximum_hours",
                    )
                },
                "generated_grounding": dict(
                    item.get("generated_grounding") or {}
                ),
                "generated_corpus_bundle_sha256": str(
                    item.get("generated_corpus_bundle_sha256") or ""
                ),
            }
            for item in curricula_index
        ],
        "curriculum_problems": list(generated_curriculum_problems),
        "training_level_profiles": template_payload["training_level_profiles"],
        "novelty_preparation": novelty_preparation,
        "wrappers": {
            "scheduled": str(CANONICAL_ROOT / "run_hour_prompt_training.ps1"),
            "hour": str(CANONICAL_ROOT / "run_hour_prompt_training.ps1"),
            "smoke": str(CANONICAL_ROOT / "run_smoke_prompt_training.ps1"),
        },
        "script_count": sum(1 for item in copied_scripts if item.get("exists")),
        "prompt_source_count": sum(1 for item in copied_prompts if item.get("exists")),
        "missing": missing,
        "c_drive_used": False,
    }
    safe_write_json(CANONICAL_ROOT / "training_assets_manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    manifest = sync_assets()
    if args.summary:
        print(
            json.dumps(
                {
                    "ok": manifest["ok"],
                    "canonical_root": manifest["canonical_root"],
                    "script_count": manifest["script_count"],
                    "prompt_source_count": manifest["prompt_source_count"],
                    "template_path": manifest["template_path"],
                    "template_prompt_count": manifest["template_prompt_count"],
                    "template_hourly_cycle_count": manifest[
                        "template_hourly_cycle_count"
                    ],
                    "template_maximum_prompt_count": manifest[
                        "template_maximum_prompt_count"
                    ],
                    "missing_count": len(manifest["missing"]),
                    "novelty_prepared_template_count": int(
                        (manifest.get("novelty_preparation") or {}).get(
                            "prepared_template_count", 0
                        )
                    ),
                    "novelty_prepared_prompt_count": int(
                        (manifest.get("novelty_preparation") or {}).get(
                            "prepared_prompt_count", 0
                        )
                    ),
                },
                indent=2,
            )
        )
    else:
        print(json.dumps(manifest, indent=2))
    return 0 if manifest["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
