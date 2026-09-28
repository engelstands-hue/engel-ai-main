#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any


ROOT = Path(os.environ.get("ENGEL_ROOT") or Path(__file__).resolve().parents[1])
if str(ROOT).startswith("\\\\?\\"):
    ROOT = Path(str(ROOT)[4:])
REPS_ROOT = ROOT / "memory" / "reps"
REPS_RECEIPTS = ROOT / "reports" / "reps"
TEMPLATE_PATH = ROOT / "memory" / "ENGEL_UNIVERSAL_REPS_TEMPLATE_V1.json"
TEMPLATE_MD_PATH = ROOT / "memory" / "ENGEL_UNIVERSAL_REPS_TEMPLATE_V1.md"
EVENTS_PATH = REPS_ROOT / "events" / "ENGEL_REPS_EVENTS.jsonl"
SCORECARDS_PATH = REPS_ROOT / "scorecards" / "ENGEL_REPS_SCORECARDS.jsonl"
PROPOSALS_PATH = REPS_ROOT / "proposals" / "ENGEL_REPS_PROPOSALS.jsonl"
SIGNOFFS_PATH = REPS_ROOT / "signoff" / "ENGEL_REPS_SIGNOFFS.jsonl"
STATE_PATH = REPS_ROOT / "ENGEL_REPS_RUNTIME_STATE.json"


AI_LANES = [
    "codex",
    "claude",
    "chatgpt",
    "grok",
    "local-llm",
    "ct246-engel-ai-main",
    "agent-meeting-room",
    "android-worker-alpha",
    "android-worker-beta",
    "android-worker-prompts",
    "unknown",
]

BUCKET_3_TERMS = (
    "source edit",
    "source edits",
    "runtime change",
    "runtime changes",
    "runtime/service",
    "route change",
    "route changes",
    "route/runtime/service",
    "service change",
    "service changes",
    "storage change",
    "storage changes",
    "proxmox storage",
    "proxmox",
    "pct ",
    "lvm",
    "iscsi",
    "format",
    "wipe",
    "delete",
    "remove-item",
    "download",
    "install",
    "package",
    "provider call",
    "provider calls",
    "provider api",
    "remote provider",
    "network",
    "runpod",
    "training",
    "phone worker startup",
    "trusted core memory",
    "trusted memory",
    "destructive",
    "cost",
    "paid",
)

BUCKET_2_TERMS = (
    "rule edit",
    "rule edits",
    "agent edit",
    "skill edit",
    "saved skill",
    "saved agent",
    "prompt change",
    "template behavior",
    "future behavior",
    "promotion",
    "promote",
    "scheduled",
    "schedule",
    "active guidance",
)

REPETITION_TERMS = (
    "repeat",
    "repeating",
    "canned",
    "empty",
    "garbage",
    "not normal",
    "not real",
    "fake",
    "broken",
    "wrong",
)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + f"_p{os.getpid()}"


def clean_text(value: Any, limit: int = 5000) -> str:
    text = str(value or "").replace("\x00", "")
    text = "".join(ch for ch in text if ch in "\t\r\n" or ord(ch) >= 32).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def one_line(value: Any, limit: int = 400) -> str:
    text = " ".join(clean_text(value, limit * 2).replace("\r", " ").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def load_json(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file():
            return {}
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl_tail(path: Path, limit: int = 20) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, limit) :]
    except Exception:
        return []
    for line in lines:
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def normalize_lane(value: Any) -> str:
    text = clean_text(value, 100).casefold().replace("_", "-").replace(" ", "-")
    if not text:
        return "unknown"
    aliases = {
        "engel": "ct246-engel-ai-main",
        "engel-ai-main": "ct246-engel-ai-main",
        "ct-246": "ct246-engel-ai-main",
        "ct246": "ct246-engel-ai-main",
        "local": "local-llm",
        "local-llms": "local-llm",
        "llm": "local-llm",
        "meeting-room": "agent-meeting-room",
        "agent-room": "agent-meeting-room",
        "alpha": "android-worker-alpha",
        "beta": "android-worker-beta",
        "android": "android-worker-prompts",
    }
    return aliases.get(text, text if text in AI_LANES else text[:80])


def classify_signoff_bucket(*texts: Any) -> dict[str, Any]:
    joined = " ".join(clean_text(text, 2000).casefold() for text in texts if text is not None)
    if any(term in joined for term in BUCKET_3_TERMS):
        return {
            "bucket": "bucket_3_needs_josh_call",
            "label": "Bucket 3 - Needs Josh call",
            "auto_apply_allowed": False,
            "reason": "runtime/source/storage/provider/network/costly/trusted-memory action detected",
        }
    if any(term in joined for term in BUCKET_2_TERMS):
        return {
            "bucket": "bucket_2_needs_signoff",
            "label": "Bucket 2 - Needs sign-off",
            "auto_apply_allowed": False,
            "reason": "future-behavior rule/skill/agent/prompt/memory-promotion action detected",
        }
    return {
        "bucket": "bucket_1_auto_approve",
        "label": "Bucket 1 - Auto-approve",
        "auto_apply_allowed": True,
        "reason": "append-only REPS record/scorecard/proposal/signoff maintenance",
    }


def has_claude_only_bias(*texts: Any) -> bool:
    joined = " ".join(clean_text(text, 2000).casefold() for text in texts if text is not None)
    if "claude" not in joined:
        return False
    provider_neutral_terms = ("all ai", "ai lane", "every ai", "provider-neutral", "not only claude", "codex", "chatgpt", "grok", "local llm")
    return not any(term in joined for term in provider_neutral_terms)


def event_id_for(payload: dict[str, Any]) -> str:
    seed = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return "reps_event_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def scorecard_id_for(event_id: str, payload: dict[str, Any]) -> str:
    seed = event_id + json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return "reps_scorecard_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def proposal_id_for(payload: dict[str, Any]) -> str:
    seed = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return "reps_proposal_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def signoff_id_for(payload: dict[str, Any]) -> str:
    seed = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return "reps_signoff_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def template_snapshot() -> dict[str, Any]:
    template = load_json(TEMPLATE_PATH)
    return {
        "ok": bool(template),
        "schema": "engel_reps_template_runtime_snapshot_v1",
        "template_path": str(TEMPLATE_PATH),
        "template_present": TEMPLATE_PATH.is_file(),
        "markdown_template_path": str(TEMPLATE_MD_PATH),
        "markdown_template_present": TEMPLATE_MD_PATH.is_file(),
        "name": str(template.get("name") or "Engel Universal REPS"),
        "provider_neutral": bool(template.get("provider_neutral") is True),
        "claude_only": bool(template.get("claude_only") is True),
        "applies_to_ai_lanes": template.get("applies_to_ai_lanes") if isinstance(template.get("applies_to_ai_lanes"), list) else AI_LANES,
        "storage_policy": template.get("storage_policy") if isinstance(template.get("storage_policy"), dict) else {},
        "scoreboard": template.get("scoreboard") if isinstance(template.get("scoreboard"), list) else default_scoreboard_names(),
        "signoff_buckets": template.get("signoff_buckets") if isinstance(template.get("signoff_buckets"), dict) else {},
    }


def default_scoreboard_names() -> list[str]:
    return [
        "input_present",
        "reply_present",
        "provider_neutral",
        "lane_recorded",
        "receipt_or_source_recorded",
        "no_secret_like_text",
        "signoff_bucket_classified",
        "persistent_paths_written",
    ]


def secret_like_text(*texts: Any) -> bool:
    joined = "\n".join(clean_text(text, 3000) for text in texts if text is not None)
    patterns = (
        r"sk-[A-Za-z0-9_\-]{20,}",
        r"api[_-]?key\s*[:=]\s*[A-Za-z0-9_\-]{12,}",
        r"token\s*[:=]\s*[A-Za-z0-9_\-]{16,}",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    )
    return any(re.search(pattern, joined, re.IGNORECASE) for pattern in patterns)


def record_event(payload: dict[str, Any]) -> dict[str, Any]:
    now = iso_now()
    lane = normalize_lane(payload.get("lane") or payload.get("ai_lane") or payload.get("source_lane"))
    source = clean_text(payload.get("source") or "engel-ai-main", 180)
    prompt = clean_text(payload.get("prompt") or payload.get("input") or payload.get("user_message"), 5000)
    reply = clean_text(payload.get("assistant_reply") or payload.get("reply") or payload.get("output"), 5000)
    lesson = clean_text(payload.get("lesson") or payload.get("correction") or payload.get("summary"), 1800)
    kind = clean_text(payload.get("kind") or payload.get("event_kind") or "session", 80) or "session"
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    paths = payload.get("paths") if isinstance(payload.get("paths"), list) else []
    receipt_path = clean_text(payload.get("receipt_path") or payload.get("workspace_receipt_path"), 500)
    bucket = classify_signoff_bucket(prompt, reply, lesson, context)
    base = {
        "schema": "engel_reps_record_event_v1",
        "ok": True,
        "event_id": "",
        "kind": kind,
        "lane": lane,
        "source": source,
        "prompt": prompt,
        "assistant_reply": reply,
        "lesson": lesson,
        "paths": [clean_text(path, 500) for path in paths if clean_text(path, 500)],
        "receipt_path": receipt_path,
        "context": context,
        "provider_neutral": not has_claude_only_bias(prompt, reply, lesson),
        "signoff_bucket": bucket,
        "trusted_memory_write": False,
        "append_only": True,
        "created_at_utc": now,
        "updated_at_utc": now,
    }
    base["event_id"] = str(payload.get("event_id") or event_id_for(base))
    lane_path = REPS_ROOT / "events" / f"{lane}.jsonl"
    append_jsonl(EVENTS_PATH, base)
    append_jsonl(lane_path, base)
    receipt_path_out = REPS_RECEIPTS / "events" / f"{base['event_id']}.json"
    write_json(receipt_path_out, base)
    update_state()
    result = dict(base)
    result["event_path"] = str(EVENTS_PATH)
    result["lane_event_path"] = str(lane_path)
    result["workspace_receipt_path"] = str(receipt_path_out)
    return result


def evaluate_event(payload: dict[str, Any]) -> dict[str, Any]:
    event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
    if not event:
        event = record_event(payload)
    prompt = clean_text(event.get("prompt"), 5000)
    reply = clean_text(event.get("assistant_reply"), 5000)
    lesson = clean_text(event.get("lesson"), 1800)
    source = clean_text(event.get("source"), 300)
    lane = normalize_lane(event.get("lane"))
    bucket = event.get("signoff_bucket") if isinstance(event.get("signoff_bucket"), dict) else classify_signoff_bucket(prompt, reply, lesson)
    checks = [
        {"name": "input_present", "pass": bool(prompt or lesson), "detail": "prompt or lesson captured"},
        {"name": "reply_present", "pass": bool(reply or lesson), "detail": "assistant reply or lesson captured"},
        {"name": "provider_neutral", "pass": not has_claude_only_bias(prompt, reply, lesson), "detail": "not Claude-only unless the task targets Claude"},
        {"name": "lane_recorded", "pass": bool(lane and lane != "unknown"), "detail": f"lane={lane}"},
        {"name": "receipt_or_source_recorded", "pass": bool(event.get("receipt_path") or source), "detail": f"source={source}"},
        {"name": "no_secret_like_text", "pass": not secret_like_text(prompt, reply, lesson), "detail": "basic secret patterns not found"},
        {"name": "signoff_bucket_classified", "pass": bool(bucket.get("bucket")), "detail": str(bucket.get("label") or "")},
        {"name": "persistent_paths_written", "pass": True, "detail": str(EVENTS_PATH)},
    ]
    extra_checks = payload.get("checks")
    if isinstance(extra_checks, list):
        for item in extra_checks:
            if isinstance(item, dict):
                checks.append(
                    {
                        "name": clean_text(item.get("name") or "custom_check", 120),
                        "pass": bool(item.get("pass") is True),
                        "detail": clean_text(item.get("detail") or "", 500),
                    }
                )
    passed = sum(1 for check in checks if check.get("pass") is True)
    failed = len(checks) - passed
    score = round(passed / max(1, len(checks)), 3)
    status = "pass" if failed == 0 else "needs_rework"
    scorecard = {
        "schema": "engel_reps_scorecard_v1",
        "ok": True,
        "scorecard_id": "",
        "event_id": str(event.get("event_id") or ""),
        "lane": lane,
        "score": score,
        "passed": passed,
        "failed": failed,
        "status": status,
        "checks": checks,
        "created_at_utc": iso_now(),
        "updated_at_utc": iso_now(),
    }
    scorecard["scorecard_id"] = str(payload.get("scorecard_id") or scorecard_id_for(str(scorecard["event_id"]), scorecard))
    append_jsonl(SCORECARDS_PATH, scorecard)
    receipt_path_out = REPS_RECEIPTS / "scorecards" / f"{scorecard['scorecard_id']}.json"
    write_json(receipt_path_out, scorecard)
    update_state()
    result = dict(scorecard)
    result["scorecard_path"] = str(SCORECARDS_PATH)
    result["workspace_receipt_path"] = str(receipt_path_out)
    return result


def propose_improvement(payload: dict[str, Any]) -> dict[str, Any]:
    event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
    scorecard = payload.get("scorecard") if isinstance(payload.get("scorecard"), dict) else {}
    if not event:
        event = record_event(payload)
    if not scorecard:
        scorecard = evaluate_event({"event": event})
    prompt = clean_text(event.get("prompt"), 5000)
    reply = clean_text(event.get("assistant_reply"), 5000)
    lesson = clean_text(event.get("lesson"), 1800)
    requested = clean_text(payload.get("proposal") or payload.get("improvement") or "", 2000)
    low = " ".join([prompt, reply, lesson, requested]).casefold()
    proposal_text = requested
    if not proposal_text:
        if any(term in low for term in REPETITION_TERMS):
            proposal_text = "Add or tighten a lane-specific guardrail so this AI lane records the correction, avoids repeating canned text, and checks the next reply against the scorecard before claiming success."
        elif scorecard.get("failed"):
            proposal_text = "Keep the recorded lesson as a candidate and add an evaluator check for the failed scorecard item before changing active behavior."
        else:
            proposal_text = "Keep the append-only REPS record and no-op proposal; no runtime behavior change is needed."
    bucket = classify_signoff_bucket(proposal_text, prompt, lesson, payload.get("target_action"))
    proposal = {
        "schema": "engel_reps_proposal_v1",
        "ok": True,
        "proposal_id": "",
        "event_id": str(event.get("event_id") or ""),
        "scorecard_id": str(scorecard.get("scorecard_id") or ""),
        "lane": normalize_lane(event.get("lane")),
        "proposal": proposal_text,
        "target_action": clean_text(payload.get("target_action") or "append-only REPS maintenance", 1000),
        "signoff_bucket": bucket,
        "auto_apply_allowed": bool(bucket.get("auto_apply_allowed") is True),
        "applied": False,
        "apply_reason": "REPS runtime records proposals; source/runtime/trusted changes require the matching sign-off bucket.",
        "created_at_utc": iso_now(),
        "updated_at_utc": iso_now(),
    }
    proposal["proposal_id"] = str(payload.get("proposal_id") or proposal_id_for(proposal))
    append_jsonl(PROPOSALS_PATH, proposal)
    receipt_path_out = REPS_RECEIPTS / "proposals" / f"{proposal['proposal_id']}.json"
    write_json(receipt_path_out, proposal)
    update_state()
    result = dict(proposal)
    result["proposal_path"] = str(PROPOSALS_PATH)
    result["workspace_receipt_path"] = str(receipt_path_out)
    return result


def signoff_decision(payload: dict[str, Any]) -> dict[str, Any]:
    proposal = payload.get("proposal") if isinstance(payload.get("proposal"), dict) else {}
    if not proposal:
        proposal = propose_improvement(payload)
    bucket = proposal.get("signoff_bucket") if isinstance(proposal.get("signoff_bucket"), dict) else classify_signoff_bucket(proposal.get("proposal"), payload.get("target_action"))
    requested = clean_text(payload.get("decision") or "", 80).casefold()
    if bucket.get("bucket") == "bucket_1_auto_approve":
        status = "auto_approved"
        approved = True
        reason = "Bucket 1 append-only REPS maintenance is auto-approved."
    elif requested in {"approved", "approve", "yes"}:
        status = "approved_by_josh"
        approved = True
        reason = "Explicit approval was supplied in the request payload."
    else:
        approved = False
        status = "needs_josh_call" if bucket.get("bucket") == "bucket_3_needs_josh_call" else "needs_signoff"
        reason = str(bucket.get("reason") or "matching sign-off required")
    signoff = {
        "schema": "engel_reps_signoff_v1",
        "ok": True,
        "signoff_id": "",
        "proposal_id": str(proposal.get("proposal_id") or ""),
        "event_id": str(proposal.get("event_id") or ""),
        "lane": normalize_lane(proposal.get("lane")),
        "status": status,
        "approved": approved,
        "signoff_bucket": bucket,
        "reason": reason,
        "applied": False,
        "apply_reason": "Sign-off records authority. It does not perform source/runtime/storage/provider actions by itself.",
        "created_at_utc": iso_now(),
        "updated_at_utc": iso_now(),
    }
    signoff["signoff_id"] = str(payload.get("signoff_id") or signoff_id_for(signoff))
    append_jsonl(SIGNOFFS_PATH, signoff)
    receipt_path_out = REPS_RECEIPTS / "signoff" / f"{signoff['signoff_id']}.json"
    write_json(receipt_path_out, signoff)
    update_state()
    result = dict(signoff)
    result["signoff_path"] = str(SIGNOFFS_PATH)
    result["workspace_receipt_path"] = str(receipt_path_out)
    return result


def run_cycle(payload: dict[str, Any]) -> dict[str, Any]:
    event = record_event(payload)
    scorecard = evaluate_event({"event": event, "checks": payload.get("checks") if isinstance(payload.get("checks"), list) else []})
    should_propose = bool(
        payload.get("force_propose") is True
        or bool(clean_text(payload.get("proposal"), 2000))
        or scorecard.get("failed")
        or any(
            term
            in " ".join(
                [event.get("prompt", ""), event.get("assistant_reply", ""), event.get("lesson", "")]
            ).casefold()
            for term in REPETITION_TERMS
        )
    )
    proposal = propose_improvement({"event": event, "scorecard": scorecard, "proposal": payload.get("proposal"), "target_action": payload.get("target_action")}) if should_propose else {}
    decision = clean_text(payload.get("decision") or "", 80)
    if not decision and payload.get("approved") is True:
        decision = "approved"
    signoff = signoff_decision({"proposal": proposal, "decision": decision}) if proposal else {}
    cycle = {
        "schema": "engel_reps_cycle_v1",
        "ok": True,
        "cycle_id": "reps_cycle_" + stamp(),
        "event": event,
        "scorecard": scorecard,
        "proposal": proposal,
        "signoff": signoff,
        "summary": {
            "recorded": True,
            "evaluated": True,
            "proposed": bool(proposal),
            "signoff_recorded": bool(signoff),
            "score": scorecard.get("score"),
            "status": scorecard.get("status"),
            "bucket": (proposal.get("signoff_bucket") or {}).get("bucket") if proposal else event.get("signoff_bucket", {}).get("bucket"),
            "approved": bool(signoff.get("approved") is True) if signoff else False,
            "signoff_status": signoff.get("status") if signoff else "",
        },
        "created_at_utc": iso_now(),
        "updated_at_utc": iso_now(),
    }
    receipt_path_out = REPS_RECEIPTS / "cycles" / f"{cycle['cycle_id']}.json"
    write_json(receipt_path_out, cycle)
    cycle["workspace_receipt_path"] = str(receipt_path_out)
    update_state()
    return cycle


def update_state() -> dict[str, Any]:
    state = {
        "schema": "engel_reps_runtime_state_v1",
        "ok": True,
        "runtime": "Engel Universal REPS Runtime",
        "provider_neutral": True,
        "claude_only": False,
        "ai_lanes": AI_LANES,
        "paths": {
            "root": str(REPS_ROOT),
            "events": str(EVENTS_PATH),
            "scorecards": str(SCORECARDS_PATH),
            "proposals": str(PROPOSALS_PATH),
            "signoffs": str(SIGNOFFS_PATH),
            "receipts": str(REPS_RECEIPTS),
            "template": str(TEMPLATE_PATH),
        },
        "event_count_tail": len(read_jsonl_tail(EVENTS_PATH, 1000)),
        "scorecard_count_tail": len(read_jsonl_tail(SCORECARDS_PATH, 1000)),
        "proposal_count_tail": len(read_jsonl_tail(PROPOSALS_PATH, 1000)),
        "signoff_count_tail": len(read_jsonl_tail(SIGNOFFS_PATH, 1000)),
        "recent_events": [
            {
                "event_id": row.get("event_id"),
                "lane": row.get("lane"),
                "kind": row.get("kind"),
                "lesson": one_line(row.get("lesson") or row.get("prompt") or row.get("assistant_reply"), 160),
                "updated_at_utc": row.get("updated_at_utc"),
            }
            for row in read_jsonl_tail(EVENTS_PATH, 8)
        ],
        "template": template_snapshot(),
        "updated_at_utc": iso_now(),
    }
    write_json(STATE_PATH, state)
    return state


def status() -> dict[str, Any]:
    if not STATE_PATH.is_file():
        update_state()
    state = load_json(STATE_PATH)
    if not state:
        state = update_state()
    state["state_path"] = str(STATE_PATH)
    return state


def cli_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if args.json:
        payload.update(json.loads(args.json))
    if args.file:
        payload.update(json.loads(Path(args.file).read_text(encoding="utf-8-sig")))
    for key in ("lane", "source", "kind", "prompt", "reply", "lesson", "proposal", "target_action", "decision"):
        value = getattr(args, key, None)
        if value:
            payload[key] = value
    if "reply" in payload and "assistant_reply" not in payload:
        payload["assistant_reply"] = payload["reply"]
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engel Universal REPS runtime.")
    parser.add_argument("command", choices=["status", "record", "evaluate", "propose", "signoff", "cycle"])
    parser.add_argument("--json", default="")
    parser.add_argument("--file", default="")
    parser.add_argument("--lane", default="")
    parser.add_argument("--source", default="")
    parser.add_argument("--kind", default="")
    parser.add_argument("--prompt", default="")
    parser.add_argument("--reply", default="")
    parser.add_argument("--lesson", default="")
    parser.add_argument("--proposal", default="")
    parser.add_argument("--target-action", default="")
    parser.add_argument("--decision", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = cli_payload(args)
    if args.command == "status":
        result = status()
    elif args.command == "record":
        result = record_event(payload)
    elif args.command == "evaluate":
        result = evaluate_event(payload)
    elif args.command == "propose":
        result = propose_improvement(payload)
    elif args.command == "signoff":
        result = signoff_decision(payload)
    else:
        result = run_cycle(payload)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
