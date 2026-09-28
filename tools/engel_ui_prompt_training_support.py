#!/usr/bin/env python3
"""Support code for Engel UI prompt-training evidence.

The helpers here are intentionally read-only for registries. They discover
current device state, build reviewable selection/proposal records, and write
bounded reports under the Engel workspace.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any
import uuid
from urllib import error, request

from tools.engel_phone_presence import parse_utc as parse_presence_utc


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "codex_bridge"
MEMORY_DIR = ROOT / "memory" / "training"
# (2026-08-08, operator directive: "expert is the new low".) The ladder was raised a full
# band: expert -- yesterday's ceiling -- is now the FLOOR, and three senior tiers sit
# above it. Legacy level names remain accepted everywhere (old receipts, saved UI
# preferences, CLI callers) but CLAMP UP to expert: nothing can ever train shallower
# than expert again.
TRAINING_LEVELS = ("expert", "principal", "distinguished", "fellow")
LEGACY_TRAINING_LEVEL_ALIASES = {"low": "expert", "medium": "expert", "high": "expert"}
TRAINING_MODEL_TARGETS = ("slm", "llm")
DEFAULT_TRAININGS_PER_HOUR = 6
# depth_rank continues the historical scale (legacy low/medium/high were 1-3, expert 4),
# so ranks in old receipts stay comparable: the new tiers extend upward, never renumber.
# The expert profile text is byte-identical to before the ladder was raised -- it is the
# delivery contract the capability eval measures against, and the floor must not drift.
TRAINING_LEVEL_PROFILES: dict[str, dict[str, Any]] = {
    "expert": {
        "profile_id": "expert_depth",
        "depth_rank": 4,
        "guidance": (
            "Expert depth: perform systems-level analysis with counterfactuals, "
            "decision ownership, failure containment, and auditable proof closure."
        ),
        "prompt_instruction": (
            "Teach this at an expert systems level. Include competing hypotheses, "
            "counterfactual checks, dependency and failure-containment analysis, an "
            "owned decision ledger, and an auditable proof-based closeout. Explicitly "
            "mark residual uncertainty and do not invent evidence."
        ),
    },
    "principal": {
        "profile_id": "principal_depth",
        "depth_rank": 5,
        "guidance": (
            "Principal depth: expert rigor plus cross-system design -- second-order "
            "effects, interface contracts, blast radius, rollback, and quantified "
            "tradeoffs against the alternative that was rejected."
        ),
        "prompt_instruction": (
            "Teach this at a principal-engineer level. Beyond expert rigor, analyze the "
            "second-order effects on neighboring systems, state the interface contracts "
            "involved, bound the blast radius and give the rollback path, and quantify "
            "the tradeoff against the strongest rejected alternative. Mark residual "
            "uncertainty plainly and do not invent evidence."
        ),
    },
    "distinguished": {
        "profile_id": "distinguished_depth",
        "depth_rank": 6,
        "guidance": (
            "Distinguished depth: adversarial self-refutation -- build the strongest "
            "case against the answer, attempt falsification at the boundaries, and "
            "keep only the claims that survive."
        ),
        "prompt_instruction": (
            "Teach this at a distinguished-engineer level. Present the answer, then "
            "build the strongest honest case AGAINST it, attempt falsification at "
            "boundary and degenerate conditions, show which claims survived and which "
            "were cut, and close with the evidence that settled it. Never soften a "
            "counter-argument to protect the answer."
        ),
    },
    "fellow": {
        "profile_id": "fellow_depth",
        "depth_rank": 7,
        "guidance": (
            "Fellow depth: first-principles derivation that ends in a reusable "
            "invariant -- derive rather than recall, and leave a lesson the system "
            "can keep."
        ),
        "prompt_instruction": (
            "Teach this at a fellow level. Derive the answer from first principles "
            "rather than recall, state the invariant the result protects, show the "
            "auditable proof chain end to end, and close with the one reusable lesson "
            "this case should leave behind. Mark anything underived as open; derive "
            "nothing from authority."
        ),
    },
}

# Discipline-specific level instructions (2026-07-31). The default prompt_instruction
# above is the CONSTRUCTION ("aec") discipline and deliberately injects evidence-ledger
# vocabulary. For math and Engel-systems ("engineering") curricula that same vocabulary
# wrongly trips the CT246 incomplete-input gate on every turn, so those disciplines get
# their own level instructions that teach the SAME verify-before-asserting depth in their
# own words and avoid the AEC incomplete-input trigger. Any discipline/level not listed
# here falls back to the strict AEC prompt_instruction above (fail toward more rigor).
DISCIPLINE_PROMPT_INSTRUCTIONS: dict[str, dict[str, str]] = {
    "math": {
        "expert": (
            "Work at an expert level: prove each step, cross-check by a second "
            "independent method, hunt one counterexample, and mark plainly any step "
            "the deterministic lane could not settle. Never state a number you did "
            "not verify."
        ),
        "principal": (
            "Work at a principal level: prove each step, verify by two independent "
            "methods, analyze how the result behaves at boundary values and under "
            "perturbation, and state which class of problems the same method settles. "
            "Never state a number you did not verify."
        ),
        "distinguished": (
            "Work at a distinguished level: prove the result, then attack it -- hunt "
            "counterexamples across boundary and degenerate cases, prove the solution "
            "set is complete (nothing missing, nothing extra), and mark plainly "
            "anything that resisted proof. Never state a number you did not verify."
        ),
        "fellow": (
            "Work at a fellow level: derive the result from first principles, prove "
            "correctness and completeness, state the general theorem or invariant this "
            "case instantiates, and give the independent check that pins it. Never "
            "state a number you did not verify."
        ),
    },
    # Communication discipline (2026-08-01). This lane trains Engel AI Main's own CHAT
    # VOICE, so the accepted answer text becomes SFT target text -- which inverts the rule
    # every other discipline follows here. Asking for evidence ledgers, labelled sections,
    # or staged analysis would bake that scaffolding straight into the voice Joshua talks
    # to, and a chat that answers in headings is the exact regression this curriculum
    # exists to prevent. So these instructions raise the DEPTH OF JUDGEMENT while holding
    # the FORM at ordinary first-person prose; the runner's conversational gate then
    # refuses any answer that drifts back into scaffolding.
    "communication": {
        "expert": (
            "Answer at an expert level of judgement but in ordinary chat prose: say the "
            "honest thing including what you do not know, keep it in your own first-person "
            "voice, and do not use headers, labels, or bullet lists."
        ),
        "principal": (
            "Answer with the judgement of a principal engineer but in ordinary chat prose: "
            "say what you would actually do, name the tradeoff you weighed and why the "
            "other path lost, keep it in your own first-person voice, and do not use "
            "headers, labels, or bullet lists."
        ),
        "distinguished": (
            "Answer with distinguished-level judgement but in ordinary chat prose: give "
            "your honest view, then say the strongest argument against it and why you "
            "still hold the view or where it changed you, in your own first-person voice "
            "with no headers, labels, or bullet lists."
        ),
        "fellow": (
            "Answer at a fellow level but in ordinary chat prose: answer so plainly and "
            "completely that Joshua leaves knowing the principle behind it, be honest "
            "about what nobody knows yet, and keep it in your own first-person voice with "
            "no headers, labels, or bullet lists."
        ),
    },
    "engineering": {
        "expert": (
            "Answer at an expert level: ground every claim in a named Engel verifier "
            "or receipt, name how each check could regress, keep an honest answer "
            "honest, and never assert a capability you cannot point a verifier at."
        ),
        "principal": (
            "Answer at a principal level: ground every claim in a named Engel verifier "
            "or receipt, name what depends on each component you touch and the blast "
            "radius if it breaks, give the rollback path, and never assert a capability "
            "you cannot point a verifier at."
        ),
        "distinguished": (
            "Answer at a distinguished level: ground every claim in a named verifier or "
            "receipt, then attack your own answer -- name how each cited check could be "
            "fooled, what a false green would look like, and which claim would fall "
            "first. Never assert a capability you cannot point a verifier at."
        ),
        "fellow": (
            "Answer at a fellow level: state the system invariant each claim protects "
            "and the verifier that pins it, derive the design from the constraint that "
            "forces it, and close with the reusable lesson. Never assert a capability "
            "you cannot point a verifier at."
        ),
    },
}


def validate_training_hours(value: Any) -> int:
    """Return a scheduled training duration constrained to one through eight hours."""
    if isinstance(value, bool):
        raise ValueError("training hours must be a whole number from 1 through 8")
    try:
        hours = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError("training hours must be a whole number from 1 through 8") from exc
    if not 1 <= hours <= 8:
        raise ValueError("training hours must be from 1 through 8")
    return hours


def validate_training_level(value: Any) -> str:
    """Return a normalized supported training level.

    Legacy levels (low/medium/high) are accepted from every historical caller -- saved
    UI preferences, resume receipts, CLI -- and CLAMP UP to expert, the new floor.
    Raising the floor must never turn an old preference file into a crash."""
    level = str(value or "").strip().casefold()
    level = LEGACY_TRAINING_LEVEL_ALIASES.get(level, level)
    if level not in TRAINING_LEVELS:
        choices = ", ".join(TRAINING_LEVELS)
        raise ValueError(f"training level must be one of: {choices}")
    return level


def validate_trainings_per_hour(value: Any) -> int:
    """Return an independent hourly training count from one through ten."""
    if isinstance(value, bool):
        raise ValueError("trainings per hour must be a whole number from 1 through 10")
    try:
        count = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "trainings per hour must be a whole number from 1 through 10"
        ) from exc
    if not 1 <= count <= 10:
        raise ValueError("trainings per hour must be from 1 through 10")
    return count


def validate_training_targets(value: Any) -> str:
    """Return a stable comma-separated set of trainable Engel model families.

    The local SLM roster and the CT246 Qwen adapter are the two training lanes
    implemented by Engel. Runtime GGUF choices and cloud providers are deliberately
    absent: selecting a model that cannot consume the resulting pack would make the
    Training window promise work that no trainer performs.
    """
    if isinstance(value, (list, tuple, set)):
        raw = [str(item).strip().casefold() for item in value]
    else:
        raw = [item.strip().casefold() for item in str(value or "").split(",")]
    selected = {item for item in raw if item}
    unsupported = sorted(selected - set(TRAINING_MODEL_TARGETS))
    if unsupported:
        raise ValueError(
            "training targets contain unsupported model families: "
            + ", ".join(unsupported)
        )
    if not selected:
        raise ValueError("training targets must include slm, llm, or both")
    return ",".join(item for item in TRAINING_MODEL_TARGETS if item in selected)


def training_level_profile(value: Any) -> dict[str, Any]:
    """Return a detached, auditable prompt-depth profile."""
    level = validate_training_level(value)
    profile = TRAINING_LEVEL_PROFILES[level]
    return {
        "training_level": level,
        "profile_id": str(profile["profile_id"]),
        "depth_rank": int(profile["depth_rank"]),
        "guidance": str(profile["guidance"]),
        "prompt_instruction": str(profile["prompt_instruction"]),
    }


def balanced_training_positions(trainings_per_hour: Any) -> list[int]:
    """Return deterministic positions spread across one ten-prompt hourly cycle."""
    count = validate_trainings_per_hour(trainings_per_hour)
    if count == 1:
        return [1]
    denominator = count - 1
    return [
        1 + ((2 * index * 9 + denominator) // (2 * denominator))
        for index in range(count)
    ]


def select_balanced_training_prompts(
    prompts: list[str],
    trainings_per_hour: Any,
) -> list[tuple[int, str]]:
    """Select an independent, balanced count from one ten-prompt hourly cycle."""
    if len(prompts) != 10:
        raise ValueError(
            f"scheduled hourly cycles must contain exactly 10 prompts; received {len(prompts)}"
        )
    return [
        (position, prompts[position - 1])
        for position in balanced_training_positions(trainings_per_hour)
    ]


def discipline_prompt_instruction(training_level: Any, discipline: Any = "aec") -> str:
    """Return the level instruction for a discipline, falling back to the strict AEC one."""
    profile = training_level_profile(training_level)
    level = profile["training_level"]
    discipline_key = str(discipline or "aec").strip().casefold()
    return DISCIPLINE_PROMPT_INSTRUCTIONS.get(discipline_key, {}).get(
        level, profile["prompt_instruction"]
    )


def apply_training_level_to_prompt(
    prompt: Any, training_level: Any, discipline: Any = "aec"
) -> str:
    """Materially apply the selected training depth to one submitted prompt.

    `discipline` selects a domain-appropriate level instruction (aec/math/engineering);
    it defaults to 'aec' so every existing caller keeps the original construction depth.
    """
    base_prompt = str(prompt or "").strip()
    if not base_prompt:
        raise ValueError("training prompt cannot be empty")
    profile = training_level_profile(training_level)
    level_label = profile["training_level"].title()
    instruction = discipline_prompt_instruction(training_level, discipline)
    return (
        f"Training depth: {level_label} ({profile['profile_id']}).\n"
        f"{instruction}\n\n"
        f"Training task:\n{base_prompt}"
    )


def fuzzy_prompt_match(
    expected: str,
    actual: str,
    *,
    max_prefix_loss: int = 16,
    minimum_similarity: float = 0.97,
) -> dict[str, Any]:
    """Match a recent stored prompt while tolerating only a small input-prefix loss."""
    import difflib
    import re

    def normalize(value: str) -> str:
        # (2026-08-14) Encoding-drift tolerance: the app->CT handoff mojibakes
        # non-ASCII typography (a CALDAG excerpt's 6-inch marks arrived on CT as
        # "6a??" — UTF-8 bytes decoded as CP1252), so the SAME prompt hashes and
        # compares differently on the two sides and every prompt on that corpus
        # card was declared a delivery failure (killed the 70-prompt run twice at
        # 39/70 and 44/70). Matching must not depend on bytes outside printable
        # ASCII: drop them AND literal '?' (mojibake replacement debris) from BOTH
        # sides before comparing.
        value = re.sub(r"[^\x20-\x7e]+", "", str(value or ""))
        value = value.replace("?", "")
        return re.sub(r"\s+", " ", value.casefold()).strip()

    expected_normalized = normalize(expected)
    actual_normalized = normalize(actual)
    if not expected_normalized or not actual_normalized:
        return {"matched": False, "kind": "empty", "similarity": 0.0, "prefix_loss": 0}
    if expected_normalized == actual_normalized:
        return {"matched": True, "kind": "exact", "similarity": 1.0, "prefix_loss": 0}
    if expected_normalized in actual_normalized:
        return {
            "matched": True,
            "kind": "expected_contained",
            "similarity": 1.0,
            "prefix_loss": 0,
        }
    maximum = min(max(0, int(max_prefix_loss)), max(0, len(expected_normalized) - 32))
    for prefix_loss in range(1, maximum + 1):
        suffix = expected_normalized[prefix_loss:]
        if actual_normalized == suffix or suffix in actual_normalized:
            return {
                "matched": True,
                "kind": "small_prefix_loss",
                "similarity": round(len(suffix) / len(expected_normalized), 6),
                "prefix_loss": prefix_loss,
            }
    similarity = difflib.SequenceMatcher(
        None,
        expected_normalized,
        actual_normalized,
        autojunk=False,
    ).ratio()
    length_delta = abs(len(expected_normalized) - len(actual_normalized))
    matched = bool(
        min(len(expected_normalized), len(actual_normalized)) >= 32
        and length_delta <= max_prefix_loss
        and similarity >= minimum_similarity
    )
    return {
        "matched": matched,
        "kind": "bounded_similarity" if matched else "different",
        "similarity": round(similarity, 6),
        "prefix_loss": max(0, len(expected_normalized) - len(actual_normalized)),
    }
REMOTE_WORKERS_ROOT = ROOT / "remote_workers"
LAN_STATE_PATH = ROOT / "remote_workers" / "lan_link_manager" / "session_state.json"
WINDOWS_SUB_ENGEL_ROOT = ROOT / "remote_nodes" / "windows_sub_engel"
WINDOWS_FLEET_PATH = WINDOWS_SUB_ENGEL_ROOT / "fleet_manifest.json"
LATEST_NODE_READY_PATH = ROOT / "runtime" / "windows_sub_engel_bootstrap" / "latest_node_ready.json"


SENSITIVE_KEY_PARTS = (
    "token",
    "secret",
    "password",
    "private_key",
    "api_key",
    "salt",
    "pairing_code",
)


@dataclass
class DeviceRecord:
    device_id: str
    kind: str
    label: str
    stable_identity: str
    capability_summary: str
    availability: str
    safety_status: str
    approval_required: bool
    current_address: str
    address_source: str
    source_path: str
    score: int
    notes: list[str]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return f"{utc_now().strftime('%Y%m%dT%H%M%S%fZ')}_p{os.getpid()}_{uuid.uuid4().hex[:8]}"


def ensure_dirs() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def write_json(path: Path, payload: Any) -> None:
    if Path(path).drive.lower() == "c:":
        raise RuntimeError(f"refusing to write Engel training evidence on C: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(redact(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def redact(value: Any, key_hint: str = "") -> Any:
    lowered = key_hint.lower()
    if any(part in lowered for part in SENSITIVE_KEY_PARTS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(key): redact(item, str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, key_hint) for item in value]
    return value


def parse_time(value: Any) -> datetime | None:
    return parse_presence_utc(value)


def live_windows_sub_health(url: str, timeout: float = 1.5) -> dict[str, Any]:
    clean = str(url or "").strip().rstrip("/")
    if not clean:
        return {"ok": False, "error": "missing_url"}
    if "://" not in clean:
        clean = "http://" + clean
    try:
        req = request.Request(clean + "/health", headers={"Accept": "application/json"})
        with request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else {"ok": False, "error": "invalid_health_payload"}
    except error.HTTPError as exc:
        return {"ok": False, "error": f"http_{exc.code}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def runtime_windows_sub_url(session: dict[str, Any]) -> str:
    if os.name != "nt" and session.get("ct_relay_url"):
        return str(session.get("ct_relay_url") or "")
    return str(session.get("url") or "")


def windows_sub_local_llm_assets_ok(node_root: Any) -> bool:
    root_text = str(node_root or "").strip()
    if not root_text:
        return False
    root = Path(root_text)
    manifest = root / "models" / "sub_engel_local_helper_model.json"
    cli = root / "runtimes" / "llama.cpp" / "cuda" / "llama-cli.exe"
    models = list((root / "models").glob("**/*.gguf")) if (root / "models").exists() else []
    return manifest.exists() and cli.exists() and bool(models)


def windows_sub_storage_penalty(node_root: Any) -> int:
    text = str(node_root or "").lower()
    if not text:
        return 0
    if "\\my drive\\" in text or "/my drive/" in text or text.startswith("g:\\"):
        return -90
    return 0


def hours_since(value: Any) -> float | None:
    parsed = parse_time(value)
    if parsed is None:
        return None
    return max(0.0, (utc_now() - parsed).total_seconds() / 3600.0)


def _lan_worker_state() -> dict[str, dict[str, Any]]:
    payload = read_json(LAN_STATE_PATH)
    if not isinstance(payload, dict):
        return {}
    workers = payload.get("workers")
    if not isinstance(workers, dict):
        return {}
    return {str(worker_id): record for worker_id, record in workers.items() if isinstance(record, dict)}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def discover_android_workers() -> list[DeviceRecord]:
    if str(ROOT) not in os.sys.path:
        os.sys.path.insert(0, str(ROOT))
    try:
        from engel_device_capability_registry import load_device_capabilities

        capabilities = load_device_capabilities()
    except Exception:
        capabilities = {}
    lan = _lan_worker_state()
    records: list[DeviceRecord] = []
    for worker_dir in sorted(REMOTE_WORKERS_ROOT.glob("android_worker_*")):
        if not worker_dir.is_dir():
            continue
        worker_id = worker_dir.name
        caps = capabilities.get(worker_id, {}) if isinstance(capabilities, dict) else {}
        identity = read_json(worker_dir / "config" / "worker_identity.json")
        identity = identity if isinstance(identity, dict) else {}
        lan_record = lan.get(worker_id, {})
        lan_identity = lan_record.get("identity") if isinstance(lan_record.get("identity"), dict) else {}
        last_seen = lan_record.get("last_seen_utc")
        age = hours_since(last_seen)
        has_lan = age is not None and age <= (5.0 / 60.0)
        assigned = bool(caps.get("assigned", True))
        manual_transfer = bool(identity.get("manual_transfer_mode") or caps.get("manual_transfer_mode"))
        if has_lan:
            availability = "available_recent_lan"
        elif assigned or manual_transfer:
            availability = "review_required_no_recent_lan"
        else:
            availability = "unavailable_no_assigned_device"
        allowed = _string_list(caps.get("allowed_jobs") or identity.get("allowed_task_types"))
        label = str(
            caps.get("device_label")
            or identity.get("device_label")
            or caps.get("worker_name")
            or identity.get("worker_name")
            or worker_id
        )
        address = str(lan_identity.get("remote_address") or "")
        address_source = str(LAN_STATE_PATH) if address else ""
        safety_status = "candidate_output_only_no_auto_apply"
        score = 10
        if has_lan:
            score += 20
        if assigned:
            score += 10
        if "draft_code_artifact" in allowed or "summarize_text" in allowed:
            score += 5
        records.append(
            DeviceRecord(
                device_id=worker_id,
                kind="android_remote_worker",
                label=label,
                stable_identity=worker_id,
                capability_summary=", ".join(allowed) if allowed else "capabilities registry missing",
                availability=availability,
                safety_status=safety_status,
                approval_required=True,
                current_address=address,
                address_source=address_source,
                source_path=str(worker_dir / "config" / "worker_capabilities.json"),
                score=score,
                notes=[
                    "stable worker_id used for routing",
                    "temporary address read from LAN state only" if address else "no current address in LAN state",
                    "phone outputs remain review-only",
                ],
            )
        )
    return records


def discover_windows_sub_engels() -> list[DeviceRecord]:
    fleet = read_json(WINDOWS_FLEET_PATH)
    fleet_nodes = {}
    if isinstance(fleet, dict):
        for node in fleet.get("nodes", []):
            if isinstance(node, dict) and node.get("node_id"):
                fleet_nodes[str(node["node_id"])] = node
    node_ids = set(fleet_nodes)
    node_root = WINDOWS_SUB_ENGEL_ROOT / "nodes"
    if node_root.exists():
        node_ids.update(path.name for path in node_root.iterdir() if path.is_dir())
    records: list[DeviceRecord] = []
    for node_id in sorted(node_ids):
        if node_id.casefold() == str(os.environ.get("COMPUTERNAME") or "").casefold():
            continue
        fleet_node = fleet_nodes.get(node_id, {})
        session_path = node_root / node_id / "session.json"
        session = read_json(session_path)
        session = session if isinstance(session, dict) else {}
        if session.get("disabled_for_engel_main") is True or fleet_node.get("disabled_for_engel_main") is True:
            continue
        if str(session.get("agent_meeting_status") or fleet_node.get("agent_meeting_status") or "").lower() in {
            "not_selectable",
            "not_selectable_external_jobs",
            "reserved_external_jobs",
            "disabled",
            "retired",
        }:
            continue
        expires_at = parse_time(session.get("expires_at_utc"))
        session_valid = bool(expires_at and expires_at > utc_now())
        display = str(fleet_node.get("display_name") or session.get("hostname") or node_id)
        address = ""
        session_url = runtime_windows_sub_url(session)
        if session_url:
            address = session_url
        elif isinstance(session.get("last_known_ips"), list) and session["last_known_ips"]:
            address = str(session["last_known_ips"][0])
        elif isinstance(fleet_node.get("last_known_ips"), list) and fleet_node["last_known_ips"]:
            address = str(fleet_node["last_known_ips"][0])
        status = str(fleet_node.get("agent_meeting_status") or "")
        availability = "available_session_valid" if session_valid else "review_required_stale_or_expired_session"
        score = 15
        if session_valid:
            score += 25
        if "registered" in status:
            score += 10
        health = live_windows_sub_health(address) if address else {"ok": False, "error": "missing_address"}
        health_ok = bool(health.get("ok"))
        allowed_actions = _string_list(health.get("allowed_actions")) if health_ok else _string_list(session.get("allowed_actions"))
        node_root_hint = health.get("node_root") or session.get("node_root") or fleet_node.get("node_root")
        local_llm_assets_ok = windows_sub_local_llm_assets_ok(node_root_hint)
        if health_ok and session_valid:
            availability = "available_live_session"
            score += 80
            if "shared_room.process_latest_work_order" in allowed_actions:
                score += 20
            if "local_llm.status" in allowed_actions:
                score += 20
            if local_llm_assets_ok:
                score += 130
        elif session_valid:
            availability = "review_required_session_valid_health_unreachable"
            score -= 30
        elif health_ok:
            availability = "review_required_live_service_expired_session"
            score -= 40
        score += windows_sub_storage_penalty(node_root_hint)
        records.append(
            DeviceRecord(
                device_id=node_id,
                kind="windows_sub_engel_node",
                label=display,
                stable_identity=node_id,
                capability_summary=", ".join(allowed_actions) or "status and diagnostics actions",
                availability=availability,
                safety_status="preview_checkin_only_no_remote_control",
                approval_required=True,
                current_address=address,
                address_source=str(session_path if session_path.exists() else WINDOWS_FLEET_PATH),
                source_path=str(session_path if session_path.exists() else WINDOWS_FLEET_PATH),
                score=score,
                notes=[
                    "stable node_id used for routing",
                    "temporary address is current metadata only" if address else "no current address in session",
                    "live health ok" if health_ok else f"live health not ok: {health.get('error', 'unknown')}",
                    "local LLM assets verified under node_root" if local_llm_assets_ok else "local LLM assets not verified under node_root",
                    f"node_root={node_root_hint}" if node_root_hint else "node_root missing",
                    "Sub-Engel path is preview/check-in only",
                ],
            )
        )
    latest = read_json(LATEST_NODE_READY_PATH)
    if isinstance(latest, dict) and latest.get("computer_name"):
        node_id = str(latest["computer_name"])
        if node_id not in {record.device_id for record in records}:
            address = str(latest.get("remote_addr") or latest.get("node_ip") or "")
            records.append(
                DeviceRecord(
                    device_id=node_id,
                    kind="windows_sub_engel_node",
                    label=node_id,
                    stable_identity=node_id,
                    capability_summary="latest bootstrap ready state",
                    availability="review_required_latest_ready_record",
                    safety_status="preview_checkin_only_no_remote_control",
                    approval_required=True,
                    current_address=address,
                    address_source=str(LATEST_NODE_READY_PATH) if address else "",
                    source_path=str(LATEST_NODE_READY_PATH),
                    score=20,
                    notes=["latest ready record discovered dynamically", "sensitive bootstrap fields redacted in reports"],
                )
            )
    return records


def discover_local_controller() -> list[DeviceRecord]:
    computer = os.environ.get("COMPUTERNAME") or "local_windows_pc"
    return [
        DeviceRecord(
            device_id="local_windows_pc",
            kind="local_controller",
            label=f"Engel AI Main controller ({computer})",
            stable_identity=computer,
            capability_summary="local LLM, GPU, files under Engel workspace, Agent Meeting Room coordination",
            availability="available_local_process",
            safety_status="local_controller_human_supervised",
            approval_required=False,
            current_address="localhost",
            address_source="process environment",
            source_path=str(ROOT),
            score=50,
            notes=["main controller stays local and supervised", "no provider API required"],
        )
    ]


def discover_devices() -> list[dict[str, Any]]:
    devices = discover_local_controller() + discover_android_workers() + discover_windows_sub_engels()
    return [asdict(device) for device in sorted(devices, key=lambda item: (item.kind, -item.score, item.device_id))]


def _select_best(devices: list[dict[str, Any]], kind: str) -> dict[str, Any] | None:
    candidates = [device for device in devices if device.get("kind") == kind]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (-int(item.get("score") or 0), str(item.get("device_id") or "")))[0]


def build_device_selection(run_id: str, meeting_order_ids: list[str] | None = None) -> dict[str, Any]:
    devices = discover_devices()
    decisions = []
    tasks = [
        ("android_remote_worker_task", "android_remote_worker", "best current Android worker for bounded remote-worker prompt training"),
        ("local_controller_task", "local_controller", "main Engel controller task and local LLM proof"),
        ("sub_engel_node_task", "windows_sub_engel_node", "best current Sub-Engel node for preview/check-in task"),
    ]
    for task_type, kind, reason in tasks:
        selected = _select_best(devices, kind)
        decision = {
            "task_type": task_type,
            "source_route": "Engel main chat -> Agent Meeting Room",
            "selection_method": "dynamic registry/state scoring; stable identity first, address metadata second",
            "evaluated_device_count": len(devices),
            "candidate_device_ids": [device.get("device_id") for device in devices if device.get("kind") == kind],
            "selected_device_id": selected.get("device_id") if selected else "",
            "selected_stable_identity": selected.get("stable_identity") if selected else "",
            "selected_label": selected.get("label") if selected else "",
            "current_discovered_address": selected.get("current_address") if selected else "",
            "address_source": selected.get("address_source") if selected else "",
            "reason": reason if selected else f"no {kind} device currently discovered",
            "safety_status": selected.get("safety_status") if selected else "blocked_no_device",
            "approval_required": bool(selected.get("approval_required")) if selected else True,
            "availability": selected.get("availability") if selected else "blocked",
            "meeting_room_order_ids": meeting_order_ids or [],
        }
        decisions.append(decision)
    payload = {
        "schema": "engel_ui_prompt_training_device_selection_v1",
        "ok": bool(devices),
        "run_id": run_id,
        "updated_at_utc": iso_now(),
        "no_hard_coded_ips": True,
        "devices": devices,
        "decisions": decisions,
        "discovery_sources": [
            str(REMOTE_WORKERS_ROOT),
            str(LAN_STATE_PATH),
            str(WINDOWS_FLEET_PATH),
            str(WINDOWS_SUB_ENGEL_ROOT / "nodes"),
            str(LATEST_NODE_READY_PATH),
        ],
    }
    return payload


def _agent_id(task_type: str, stable_identity: str) -> str:
    digest = hashlib.sha256(f"{task_type}:{stable_identity}".encode("utf-8")).hexdigest()[:12]
    return f"engel_agent_{digest}"


def build_agent_proposals(selection: dict[str, Any]) -> dict[str, Any]:
    proposals = []
    for decision in selection.get("decisions", []):
        stable = str(decision.get("selected_stable_identity") or "")
        task_type = str(decision.get("task_type") or "")
        if not stable:
            continue
        label = str(decision.get("selected_label") or stable)
        if task_type == "android_remote_worker_task":
            name = f"Engel Android Device Agent for {label}"
        elif task_type == "sub_engel_node_task":
            name = f"Engel Sub-Engel Node Agent for {label}"
        else:
            name = "Engel Main Local Controller Agent"
        proposals.append(
            {
                "agent_id": _agent_id(task_type, stable),
                "agent_name": name,
                "target_stable_id": stable,
                "target_device_label": label,
                "current_discovered_address": decision.get("current_discovered_address") or "",
                "address_source": decision.get("address_source") or "",
                "task_type": task_type,
                "reason_for_device_selection": decision.get("reason") or "",
                "safety_status": decision.get("safety_status") or "",
                "approval_required": bool(decision.get("approval_required")),
                "created_or_proposed": "proposed",
                "created_proposed_at_utc": iso_now(),
                "source_route": "Engel main chat -> Agent Meeting Room",
            }
        )
    return {
        "schema": "engel_ui_prompt_training_agent_proposals_v1",
        "ok": bool(proposals),
        "updated_at_utc": iso_now(),
        "run_id": selection.get("run_id"),
        "proposals": proposals,
    }


def prompt_bank(mode: str) -> list[str]:
    base = [
        "Run Engel UI prompt training step 1: Confirm this session is using Engel AI local LLM mode only. Do not use external providers. Send this to the Agent Meeting Room for routing.",
        "Run Engel UI prompt training step 2: Agent Meeting Room, discover all currently known devices, workers, and Sub-Engel nodes from Engel registry and state.",
        "Run Engel UI prompt training step 3: Choose the best device for an Android remote-worker task. Use stable worker_id or device_id, not a fixed IP.",
        "Run Engel UI prompt training step 4: Choose the best device for a local controller task and explain why Engel AI Main should keep it local.",
        "Run Engel UI prompt training step 5: Choose the best device for a Sub-Engel node task. If the node is stale, mark review-required instead of pretending it works.",
        "Run Engel UI prompt training step 6: Create or propose the correct agent for the selected device and include the source route from Engel main chat to Agent Meeting Room.",
        "Run Engel UI prompt training step 7: Explain why this device was selected and what safety status applies.",
        "Run Engel UI prompt training step 8: If the needed device is unavailable, create a blocked or review-required result instead of pretending success.",
        "Run Engel UI prompt training step 9: Summarize the routing decision, selected device, proposed agent, and verification result.",
        "Run Engel UI prompt training step 10: Verify no fixed IP address is required; use current address metadata only as temporary connection data.",
        "Run Engel UI prompt training step 11: Route a bounded code-draft style task to the best review-only device worker and keep all outputs candidate-only.",
        "Run Engel UI prompt training step 12: Route a bounded report-format style task and explain whether Android Beta, Android Gamma, local controller, or a Sub-Engel node is the correct match.",
    ]
    if mode == "smoke":
        return [base[0], base[2], base[4]]
    return base


def render_plan() -> str:
    return "\n".join(
        [
            "# Engel UI Prompt Training Plan",
            "",
            "- Entry: visible Engel AI chat widget send handler.",
            "- Local LLM: tools/run_engel_standalone_chat_llm.py through local Rust CUDA Qwen Coder GGUF.",
            "- Meeting Room: submit_order_from_engel_main_ui and complete_order_from_engel_main_ui.",
            "- Device selection: dynamic registry/state discovery, stable IDs first, current address metadata second.",
            "- Modes: smoke mode first; scheduled mode is manual and bounded to 1-8 hours.",
            "- Levels: low, medium, high, and expert independently change the depth and guidance applied to every submitted prompt.",
            "- Trainings per hour: an independent 1-10 control selects a balanced set from each distinct hourly cycle; default 6.",
            "- Evidence: reports/codex_bridge and memory/training only for required training files.",
            "- Safety: no provider API, no C drive writes, no hidden persistent workers, no trusted memory mutation.",
            "",
            "Required files:",
            "- reports/codex_bridge/ENGEL_UI_PROMPT_TRAINING_SMOKE_REPORT.md",
            "- reports/codex_bridge/ENGEL_UI_PROMPT_TRAINING_ONE_HOUR_REPORT.md",
            "- reports/codex_bridge/ENGEL_UI_PROMPT_TRAINING_SCHEDULED_REPORT.md",
            "- memory/training/ENGEL_UI_PROMPT_TRAINING_SESSION.json",
            "- memory/training/ENGEL_AGENT_MEETING_ROOM_DEVICE_SELECTION.json",
            "- memory/training/ENGEL_AGENT_MEETING_ROOM_AGENT_PROPOSALS.json",
        ]
    ) + "\n"


def write_plan() -> Path:
    ensure_dirs()
    path = REPORT_DIR / "ENGEL_UI_PROMPT_TRAINING_PLAN.md"
    path.write_text(render_plan(), encoding="utf-8")
    return path


def render_training_report(receipt: dict[str, Any]) -> str:
    summary = receipt.get("summary") if isinstance(receipt.get("summary"), dict) else {}
    selection = receipt.get("device_selection") if isinstance(receipt.get("device_selection"), dict) else {}
    proposals = receipt.get("agent_proposals") if isinstance(receipt.get("agent_proposals"), dict) else {}
    decisions = selection.get("decisions") if isinstance(selection.get("decisions"), list) else []
    lines = [
        f"# Engel UI Prompt Training {str(receipt.get('mode', '')).title()} Report",
        "",
        f"- Status: {receipt.get('status')}",
        f"- Run ID: {receipt.get('run_id')}",
        f"- Started: {receipt.get('started_at_utc')}",
        f"- Finished: {receipt.get('finished_at_utc')}",
        f"- Scheduled hours: {receipt.get('scheduled_hours')}",
        f"- Requested minutes: {receipt.get('requested_minutes')}",
        f"- Training level: {receipt.get('training_level')}",
        f"- Training profile: {receipt.get('training_level_profile')}",
        f"- Level guidance: {receipt.get('training_level_guidance')}",
        f"- Hourly cycles: {summary.get('hourly_cycle_count')}",
        f"- Trainings per hour: {summary.get('trainings_per_hour')}",
        f"- Cadence seconds: {summary.get('cadence_seconds')}",
        f"- Actual duration seconds: {receipt.get('actual_duration_seconds')}",
        f"- UI path used: {receipt.get('ui_path_used')}",
        f"- Local LLM only: {summary.get('local_llm_only')}",
        f"- Meeting Room orders: {summary.get('meeting_room_order_count')}",
        f"- Android worker claims: {summary.get('android_worker_claim_count')}",
        f"- Android worker returns: {summary.get('android_worker_return_count')}",
        f"- Android required return failures: {summary.get('android_worker_required_return_failures')}",
        f"- Prompts completed: {summary.get('prompts_completed')} / {summary.get('prompts_requested')}",
        f"- Device records discovered: {summary.get('device_count')}",
        f"- Agent proposals recorded: {len(proposals.get('proposals') or [])}",
        "",
        "## Device Decisions",
    ]
    for decision in decisions:
        lines.append(
            "- {task}: {device} ({stable}) | {availability} | {safety} | approval_required={approval}".format(
                task=decision.get("task_type"),
                device=decision.get("selected_label"),
                stable=decision.get("selected_stable_identity"),
                availability=decision.get("availability"),
                safety=decision.get("safety_status"),
                approval=decision.get("approval_required"),
            )
        )
    lines += ["", "## Prompt Results"]
    for item in receipt.get("prompt_results", []):
        android = item.get("android_worker_return") if isinstance(item.get("android_worker_return"), dict) else {}
        lines.append(
            f"- {item.get('status')}: {item.get('prompt_index')} | hour={item.get('scheduled_hour')} | "
            f"level={item.get('training_level')} | source_prompt={item.get('source_prompt_index')} | "
            f"order={item.get('order_id')} | "
            f"receipt={item.get('local_llm_receipt_path')} | android_return={android.get('status')}"
        )
    lines += [
        "",
        "## Verification",
        f"- No C drive output paths: {summary.get('no_c_drive_output_paths')}",
        f"- No provider API reported by local LLM receipts: {summary.get('no_provider_api')}",
        f"- No hard-coded IPs in new training scripts: {summary.get('no_hard_coded_ips')}",
        f"- Hidden persistent worker started: {summary.get('hidden_persistent_worker_started')}",
        "",
        "## Files",
    ]
    for path in receipt.get("output_files", []):
        lines.append(f"- {path}")
    blockers = receipt.get("blockers") or []
    if blockers:
        lines += ["", "## Blockers"]
        lines.extend(f"- {item}" for item in blockers)
    return "\n".join(lines).rstrip() + "\n"


def training_report_path(mode: Any) -> Path:
    """Route each training mode to its stable human-readable report."""
    mode = str(mode or "smoke").strip().casefold()
    if mode == "scheduled":
        return REPORT_DIR / "ENGEL_UI_PROMPT_TRAINING_SCHEDULED_REPORT.md"
    if mode == "one-hour":
        return REPORT_DIR / "ENGEL_UI_PROMPT_TRAINING_ONE_HOUR_REPORT.md"
    return REPORT_DIR / "ENGEL_UI_PROMPT_TRAINING_SMOKE_REPORT.md"


def write_reports(receipt: dict[str, Any]) -> dict[str, str]:
    ensure_dirs()
    report_path = training_report_path(receipt.get("mode"))
    report_path.write_text(render_training_report(receipt), encoding="utf-8")
    write_json(MEMORY_DIR / "ENGEL_UI_PROMPT_TRAINING_SESSION.json", receipt)
    if isinstance(receipt.get("device_selection"), dict):
        write_json(MEMORY_DIR / "ENGEL_AGENT_MEETING_ROOM_DEVICE_SELECTION.json", receipt["device_selection"])
    if isinstance(receipt.get("agent_proposals"), dict):
        write_json(MEMORY_DIR / "ENGEL_AGENT_MEETING_ROOM_AGENT_PROPOSALS.json", receipt["agent_proposals"])
    if receipt.get("status") != "PASS":
        blocked = REPORT_DIR / "ENGEL_UI_PROMPT_TRAINING_BLOCKED.md"
        blocked.write_text(render_training_report(receipt), encoding="utf-8")
    return {"report": str(report_path)}
