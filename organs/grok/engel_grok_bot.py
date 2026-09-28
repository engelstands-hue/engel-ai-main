"""Engel Grok Bot -- named teammates on the shared Engel computer.

Maps the Grok Bot product idea onto Engel's existing cluster. A Bot is one
persistent named teammate. Every Bot shares CT 246, the ROG controller,
Meeting Room, Android workers, and Sub-Engel. This module does not create a
cloud VM, call a provider, start a background worker, or mutate queues.

Routes: engel.grok_bot.*
Contract: memory/ENGEL_GROK_BOT_CONTRACT_V1.md
Verifier: tools/verify_engel_grok_bot.py
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engel_project_paths import resolve_engel_app_root
from engel_prompt_injection_guard import check_prompt_injection


ROOT = resolve_engel_app_root(__file__)
STATE_DIR = ROOT / "runtime" / "grok_bots"
BOT_DIR = STATE_DIR / "bots"
THREAD_DIR = STATE_DIR / "threads"
REGISTRY_PATH = STATE_DIR / "registry.json"
RECEIPT_DIR = ROOT / "reports" / "grok_bots"
CONTRACT_PATH = ROOT / "memory" / "ENGEL_GROK_BOT_CONTRACT_V1.md"

SCHEMA_BOT = "engel_grok_bot_v1"
SCHEMA_REGISTRY = "engel_grok_bot_registry_v1"
DEFAULT_SLUG = "grok"
DEFAULT_NAME = "Grok"

_CREATE_PREFIXES = (
    "create grok bot ",
    "new grok bot ",
    "add grok bot ",
)
_MESSAGE_PREFIXES = (
    "message grok bot ",
    "ask grok bot ",
    "tell grok bot ",
)
_HANDOFF_PREFIXES = (
    "handoff grok bot ",
    "grok bot handoff ",
    "send grok bot ",
)
_BARE_COMMANDS = {
    "grok bot",
    "grok bots",
    "create grok bot",
    "message grok bot",
    "ask grok bot",
    "tell grok bot",
    "handoff grok bot",
    "grok bot handoff",
    "grok bot status",
    "list grok bots",
    "what is grok bot",
    "grok bot computer",
    "grok bot approvals",
    "grok bot docs",
}

_SLUG_RE = re.compile(r"[^a-z0-9]+")

# Shared-computer body parts. Classification is local keyword matching only.
_BODY_PARTS: tuple[tuple[tuple[str, ...], str, str, str, str], ...] = (
    (
        ("chat", "talk", "conversation", "reply", "message user"),
        "ct246-chat",
        "CT 246 Engel chat body",
        "http://127.0.0.1:24680  (tunnel to engel-main-chat)",
        "Bucket 1 for status. Bucket 3 for provider/model/network changes.",
    ),
    (
        ("meeting room", "teammate", "coordinate", "handoff", "agent card"),
        "meeting-room",
        "Agent Meeting Room",
        "http://127.0.0.1:8790  +  python engel_agent_meeting_room.py",
        "Bucket 1 to stage an order. Send Job / Android packet stays explicit.",
    ),
    (
        ("android", "phone", "adb", "alpha", "beta", "gamma", "moto"),
        "android-workers",
        "Android worker fleet",
        "remote_workers/android_worker_*  +  engel.android_workers.*",
        "Bucket 3 to start or dispatch a phone job. This Bot will not create jobs.",
    ),
    (
        ("sub-engel", "sub engel", "windows sub", "extra computer", "other pc"),
        "sub-engel",
        "Sub-Engel / Windows-sub limbs",
        "remote_workers/sub_engel_os_worker  +  remote_nodes/",
        "Preview / staged packet only until Josh approves live remote control.",
    ),
    (
        ("architect", "plan.md", "spec.md", "founder gate", "planner"),
        "architect",
        "Architect Agent",
        "engel.architect.*  +  memory/architect_state/",
        "Bucket 2/3 to advance or approve the Founder Gate. Room may only read status.",
    ),
    (
        ("model", "gguf", "lora", "llama", "train", "adapter"),
        "models",
        "Active models on CT 246",
        "/opt/engel/models-active  (archive: /mnt/engel-hdd-vault)",
        "Bucket 3 for training, swap, or archive mutation.",
    ),
    (
        ("verify", "verifier", "smoke", "codex verify"),
        "verifiers",
        "Verifier / report spine",
        "scripts/codex_verify.ps1  +  reports/codex_bridge/",
        "Bucket 1.",
    ),
    (
        ("skill", "routine", "lesson", "remember", "reps", "workflow"),
        "reps-skills",
        "REPS + saved skills",
        "memory/reps/  +  skills/  +  /reps/* on CT chat",
        "Bucket 1 to record. Bucket 2 to promote a skill/routine.",
    ),
    (
        ("3d", "virtual office", "claw3d"),
        "3d-office",
        "3D cluster office",
        "scripts/Start-EngelAgentMeetingRoomOffice.ps1",
        "Bucket 1 to view. Bucket 3 to change the office runtime.",
    ),
    (
        ("route", "command", "phrase", "ask engel"),
        "routes",
        "Engel route spine",
        "engel_ai.py ask  +  UPDATE_ROUTES",
        "Bucket 1 for status routes. Action routes stay explicit.",
    ),
    (
        ("icm", "folder structure", "workspace structure", "system map"),
        "icm-architect",
        "ICM Architect on Engel AI Main",
        r"D:\b.WorkSpace\icm-architect-main\icm-architect-main  +  memory/icm/engel-ai-main/",
        "Bucket 1 for inventory/propose. Bucket 3 to move Engel files.",
    ),
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slugify(value: str) -> str:
    slug = _SLUG_RE.sub("-", str(value or "").casefold()).strip("-")
    return slug or "bot"


def _clip(value: Any, limit: int = 240) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _strip_prefixes(text: str, prefixes: tuple[str, ...]) -> str:
    raw = " ".join(str(text or "").split())
    low = raw.casefold()
    if low in _BARE_COMMANDS:
        return ""
    for prefix in prefixes:
        if low.startswith(prefix):
            return raw[len(prefix) :].strip()
    return raw


def _split_name_payload(rest: str) -> tuple[str, str]:
    text = str(rest or "").strip()
    if not text:
        return DEFAULT_SLUG, ""
    if "|" in text:
        name, task = text.split("|", 1)
        return _slugify(name), task.strip()
    parts = text.split(None, 1)
    if len(parts) == 1:
        maybe = _slugify(parts[0])
        if (BOT_DIR / f"{maybe}.json").is_file() or maybe == DEFAULT_SLUG:
            return maybe, ""
        return DEFAULT_SLUG, text
    maybe = _slugify(parts[0])
    if (BOT_DIR / f"{maybe}.json").is_file() or maybe == DEFAULT_SLUG:
        return maybe, parts[1].strip()
    return DEFAULT_SLUG, text


def _load_registry() -> dict[str, Any]:
    data = _read_json(REGISTRY_PATH)
    if data.get("schema") != SCHEMA_REGISTRY:
        data = {
            "schema": SCHEMA_REGISTRY,
            "computer": "shared-engel-cluster",
            "updated_at_utc": _now(),
            "bots": [],
        }
    bots = data.get("bots")
    data["bots"] = [str(item) for item in bots] if isinstance(bots, list) else []
    return data


def _save_registry(data: dict[str, Any]) -> None:
    data["schema"] = SCHEMA_REGISTRY
    data["computer"] = "shared-engel-cluster"
    data["updated_at_utc"] = _now()
    _write_json(REGISTRY_PATH, data)


def _bot_path(slug: str) -> Path:
    return BOT_DIR / f"{_slugify(slug)}.json"


def load_bot(slug: str) -> dict[str, Any] | None:
    data = _read_json(_bot_path(slug))
    if data.get("schema") != SCHEMA_BOT:
        return None
    return data


def list_bots() -> list[dict[str, Any]]:
    registry = _load_registry()
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for slug in list(registry.get("bots", [])) + [p.stem for p in BOT_DIR.glob("*.json")]:
        clean = _slugify(str(slug))
        if not clean or clean in seen:
            continue
        seen.add(clean)
        bot = load_bot(clean)
        if bot:
            found.append(bot)
    found.sort(key=lambda item: str(item.get("name", "")).casefold())
    return found


def _guard(text: str) -> dict[str, Any]:
    verdict = check_prompt_injection(text)
    status = str(getattr(verdict, "verdict", "allow") or "allow")
    return {
        "ok": status not in {"block", "review"},
        "verdict": status,
        "score": float(getattr(verdict, "score", 0.0) or 0.0),
        "reason": str(getattr(verdict, "reason", "") or ""),
    }


def classify_body_parts(task: str) -> list[dict[str, str]]:
    low = str(task or "").casefold()
    hits: list[dict[str, str]] = [
        {
            "id": "shared-computer",
            "label": "Shared Engel computer",
            "surface": "CT 246 /opt/engel + ROG controller + Meeting Room + workers",
            "approval": "All Bots share this computer. A login or file is available to every Bot.",
        }
    ]
    seen = {"shared-computer"}
    for keywords, part_id, label, surface, approval in _BODY_PARTS:
        if any(key in low for key in keywords) and part_id not in seen:
            seen.add(part_id)
            hits.append(
                {
                    "id": part_id,
                    "label": label,
                    "surface": surface,
                    "approval": approval,
                }
            )
    if len(hits) == 1:
        # Default ambitious teammate work uses the coordination spine, not chat-only.
        for part_id in ("meeting-room", "ct246-chat", "routes", "reps-skills"):
            for keywords, candidate_id, label, surface, approval in _BODY_PARTS:
                if candidate_id == part_id:
                    hits.append(
                        {
                            "id": candidate_id,
                            "label": label,
                            "surface": surface,
                            "approval": approval,
                        }
                    )
                    break
    return hits


def classify_signoff(task: str) -> dict[str, str]:
    low = str(task or "").casefold()
    bucket3 = (
        "source",
        "edit code",
        "runtime",
        "service",
        "storage",
        "proxmox",
        "provider",
        "network",
        "download",
        "install",
        "train",
        "runpod",
        "trusted memory",
        "start phone",
        "dispatch android",
        "create android job",
        "wipe",
        "format",
    )
    bucket2 = (
        "save skill",
        "save agent",
        "routine",
        "schedule",
        "promote",
        "prompt change",
        "rule edit",
    )
    if any(term in low for term in bucket3):
        return {
            "bucket": "3",
            "label": "Needs Josh call",
            "action": "Plan and stop. Do not execute.",
        }
    if any(term in low for term in bucket2):
        return {
            "bucket": "2",
            "label": "Needs sign-off",
            "action": "Draft the skill/routine. Do not promote.",
        }
    return {
        "bucket": "1",
        "label": "Auto-approve working notes",
        "action": "Record the plan and wait for an explicit handoff if work must leave this Bot.",
    }


def _presence(path: Path) -> str:
    return "present" if path.exists() else "missing"


def probe_bot_presence() -> list[dict[str, str]]:
    """Grok-Bot-style presence signals from local files only (no network).

    States: idle | ready | blocked | missing
    """
    computer = probe_shared_computer()
    by_part = {row["part"]: row["state"] for row in computer}
    bots = list_bots()

    def _state(part: str) -> str:
        return "ready" if by_part.get(part) == "present" else "missing"

    rows = [
        {
            "id": "roster",
            "label": "Bot roster",
            "lifecycle": "ready" if bots else "idle",
            "detail": f"{len(bots)} named bot(s)",
        },
        {
            "id": "meeting-room",
            "label": "Meeting Room",
            "lifecycle": _state("Meeting Room Qt"),
            "detail": "file presence only — not a live HTTP probe",
        },
        {
            "id": "android-alpha",
            "label": "Android alpha",
            "lifecycle": _state("Android alpha queue"),
            "detail": "queue folder presence",
        },
        {
            "id": "android-beta",
            "label": "Android beta",
            "lifecycle": _state("Android beta queue"),
            "detail": "queue folder presence",
        },
        {
            "id": "sub-engel",
            "label": "Sub-Engel",
            "lifecycle": _state("Sub-Engel worker"),
            "detail": "worker folder presence",
        },
        {
            "id": "reps",
            "label": "REPS",
            "lifecycle": _state("REPS runtime"),
            "detail": "runtime module presence",
        },
        {
            "id": "routines",
            "label": "Routines organ",
            "lifecycle": (
                "ready"
                if (ROOT / "engel_routines.py").is_file()
                else "missing"
            ),
            "detail": "stage-only; no background worker",
        },
    ]
    blocked = [row for row in rows if row["lifecycle"] == "missing"]
    if blocked:
        rows.append(
            {
                "id": "cluster",
                "label": "Cluster presence",
                "lifecycle": "blocked",
                "detail": "missing: " + ", ".join(row["label"] for row in blocked),
            }
        )
    else:
        rows.append(
            {
                "id": "cluster",
                "label": "Cluster presence",
                "lifecycle": "ready",
                "detail": "all probed body parts present on disk",
            }
        )
    return rows


def probe_shared_computer() -> list[dict[str, str]]:
    """File-only cluster map. No HTTP, ADB, SSH, or provider calls."""
    return [
        {
            "part": "ROG workspace",
            "path": str(ROOT),
            "state": "present",
        },
        {
            "part": "Wiki One body map",
            "path": "wiki/ONE.md",
            "state": _presence(ROOT / "wiki" / "ONE.md"),
        },
        {
            "part": "One-system launcher",
            "path": "scripts/Start-EngelMainOneSystem.ps1",
            "state": _presence(ROOT / "scripts" / "Start-EngelMainOneSystem.ps1"),
        },
        {
            "part": "One-system connection test",
            "path": "scripts/Test-EngelMainOneSystemConnections.ps1",
            "state": _presence(ROOT / "scripts" / "Test-EngelMainOneSystemConnections.ps1"),
        },
        {
            "part": "CT chat tunnel worker",
            "path": "scripts/Start-EngelMainServerChatTunnelPersistent.ps1",
            "state": _presence(ROOT / "scripts" / "Start-EngelMainServerChatTunnelPersistent.ps1"),
        },
        {
            "part": "CT chat service source",
            "path": "tools/engel_main_server_chat_http_service.py",
            "state": _presence(ROOT / "tools" / "engel_main_server_chat_http_service.py"),
        },
        {
            "part": "Meeting Room Qt",
            "path": "engel_agent_meeting_room.py",
            "state": _presence(ROOT / "engel_agent_meeting_room.py"),
        },
        {
            "part": "Meeting Room state",
            "path": "runtime/meeting_room",
            "state": _presence(ROOT / "runtime" / "meeting_room"),
        },
        {
            "part": "Android alpha queue",
            "path": "remote_workers/android_worker_alpha",
            "state": _presence(ROOT / "remote_workers" / "android_worker_alpha"),
        },
        {
            "part": "Android beta queue",
            "path": "remote_workers/android_worker_beta",
            "state": _presence(ROOT / "remote_workers" / "android_worker_beta"),
        },
        {
            "part": "Sub-Engel worker",
            "path": "remote_workers/sub_engel_os_worker",
            "state": _presence(ROOT / "remote_workers" / "sub_engel_os_worker"),
        },
        {
            "part": "Windows Sub-Engel",
            "path": "remote_workers/windows_sub_engel",
            "state": _presence(ROOT / "remote_workers" / "windows_sub_engel"),
        },
        {
            "part": "Architect agent",
            "path": "engel_architect_agent.py",
            "state": _presence(ROOT / "engel_architect_agent.py"),
        },
        {
            "part": "REPS runtime",
            "path": "tools/engel_universal_reps_runtime.py",
            "state": _presence(ROOT / "tools" / "engel_universal_reps_runtime.py"),
        },
        {
            "part": "Desktop V2",
            "path": "engel_desktop_v2.py",
            "state": _presence(ROOT / "engel_desktop_v2.py"),
        },
    ]


def _try_status_route(task: str) -> str:
    try:
        from engel_ai_update_routes import (
            ROUTE_BY_ID,
            render_update_route,
            resolve_update_route,
        )
    except Exception:
        return ""
    route_id = resolve_update_route(task)
    if not route_id or str(route_id).startswith("engel.grok_bot"):
        return ""
    route = ROUTE_BY_ID.get(route_id)
    if route is None or not bool(getattr(route, "read_only", False)):
        return ""
    try:
        return str(render_update_route(route_id, task) or "").strip()
    except Exception as exc:
        return f"(status route {route_id} unavailable: {type(exc).__name__})"


def _append_thread(slug: str, role: str, text: str) -> None:
    THREAD_DIR.mkdir(parents=True, exist_ok=True)
    path = THREAD_DIR / f"{slug}.jsonl"
    record = {
        "schema": "engel_grok_bot_thread_v1",
        "slug": slug,
        "role": role,
        "text": _clip(text, 2000),
        "at_utc": _now(),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _write_receipt(kind: str, payload: dict[str, Any]) -> Path:
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:10]
    path = RECEIPT_DIR / f"ENGEL_GROK_BOT_{kind}_{stamp}_{digest}.json"
    payload = dict(payload)
    payload["receipt_kind"] = kind
    payload["written_at_utc"] = _now()
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        if RECEIPT_DIR.resolve() == (ROOT / "reports" / "grok_bots").resolve():
            from engel_icm_output_router import file_engel_output

            icm_kind = "handoff" if str(kind) == "handoff" else "teammate"
            file_engel_output(
                kind=icm_kind,
                title=f"grok-bot {kind}",
                body=payload,
                source="engel_grok_bot",
                extra={"legacy_receipt": str(path)},
            )
    except Exception:
        pass
    return path


def _plan_lines(bot: dict[str, Any], task: str) -> tuple[list[str], dict[str, Any]]:
    parts = classify_body_parts(task)
    signoff = classify_signoff(task)
    status_hit = _try_status_route(task)
    plan = {
        "bot": bot.get("name"),
        "slug": bot.get("slug"),
        "task": task,
        "body_parts": parts,
        "signoff": signoff,
        "status_route_used": bool(status_hit),
    }
    lines = [
        f"{bot.get('name')} here. I am a named teammate on the shared Engel computer, not a fresh chat.",
        "",
        f"Task: {_clip(task, 400)}",
        f"Sign-off: Bucket {signoff['bucket']} — {signoff['label']}",
        f"Next: {signoff['action']}",
        "",
        "Body parts this job should use:",
    ]
    for part in parts:
        lines.append(f"- {part['label']}")
        lines.append(f"  surface: {part['surface']}")
        lines.append(f"  gate: {part['approval']}")
    if status_hit:
        lines.extend(["", "Existing read-only route result:", status_hit[:1800]])
    else:
        lines.extend(
            [
                "",
                "I will not pretend the work is finished in chat.",
                "Say `handoff grok bot " + str(bot.get("name") or "Grok") + " | <task>` to stage this into the Meeting Room.",
                "Android / provider / training / source work still needs an explicit Josh gate.",
            ]
        )
    return lines, plan


def render_grok_bot_docs(payload: str = "") -> str:
    del payload
    return "\n".join(
        [
            "Engel Grok Bot",
            "",
            "A Bot is one persistent named teammate. All Bots share one Engel computer:",
            "CT 246 /opt/engel, the ROG controller, Meeting Room, Android workers, and Sub-Engel.",
            "They do not get a separate cloud VM or a private login boundary.",
            "",
            "Talk to a Bot like a teammate:",
            "- Desktop shortcut: Engel Grok Bot  (opens the computer window)",
            "- python engel_grok_bot.py            (browser + files + terminal)",
            "- python engel_grok_bot.py --console  (text only)",
            "- grok bot status",
            "- grok bot computer",
            "- list grok bots",
            "- create grok bot Research Scout | deep research teammate",
            "- message grok bot Grok | check android workers and meeting room state",
            "- handoff grok bot Grok | draft a worker review for Josh to approve",
            "- grok bot approvals",
            "",
            "The computer window is current Engel AI Main (Cosmic Swarm OS):",
            "- Open Engel AI Main launches EngelAIMain.exe",
            "- Browser stays on 127.0.0.1:24680 / :8790",
            "- Filesystem and terminal are this Bot's screen on the shared computer",
            "",
            "What it will do:",
            "- keep name, notes, and thread under runtime/grok_bots/",
            "- pick the real Engel body parts for the job",
            "- run one existing read-only status route when the task is an exact alias",
            "- stage a Meeting Room order on explicit handoff",
            "- stop and ask Josh when the bucket is 2 or 3",
            "",
            "What it will not do:",
            "- provider calls, live internet research, background loops",
            "- trusted-memory writes, queue mutation, Android job create",
            "- Architect action routes from the Meeting Room",
            "",
            "Contract: memory/ENGEL_GROK_BOT_CONTRACT_V1.md",
            f"Contract file: {_presence(CONTRACT_PATH)}",
        ]
    )


def render_grok_bot_status(payload: str = "") -> str:
    del payload
    bots = list_bots()
    computer = probe_shared_computer()
    presence = probe_bot_presence()
    missing = [row["part"] for row in computer if row["state"] != "present"]
    lines = [
        "Engel Grok Bot status",
        "",
        "Computer: shared Engel cluster (not this laptop alone)",
        f"Named bots: {len(bots)}",
        f"Registry: {REGISTRY_PATH}",
        "",
        "Presence (file-only lifecycle):",
    ]
    for row in presence:
        lines.append(
            f"- [{row.get('lifecycle')}] {row.get('label')}: {row.get('detail')}"
        )
    lines.append("")
    if bots:
        for bot in bots:
            lines.append(
                f"- {bot.get('name')} ({bot.get('slug')}) — { _clip(bot.get('role'), 120) }"
            )
            last = bot.get("last_plan")
            if isinstance(last, dict) and last.get("task"):
                lines.append(f"  last task: {_clip(last.get('task'), 140)}")
    else:
        lines.append("- no named bots yet. Use: create grok bot <name> | <role>")
    lines.extend(["", "Shared computer pieces:"])
    for row in computer:
        lines.append(f"- {row['part']}: {row['state']}")
    if missing:
        lines.extend(
            [
                "",
                "Missing pieces stay listed. The Bot will not invent a live connection.",
            ]
        )
    lines.extend(
        [
            "",
            "Local faces: Desktop V2 chat, `python engel_ai.py ask \"grok bot status\"`.",
            "Server faces: http://127.0.0.1:24680  and  http://127.0.0.1:8790 after one-system start.",
            "Presence detail: `grok bot presence`",
        ]
    )
    return "\n".join(lines)


def render_grok_bot_presence(payload: str = "") -> str:
    del payload
    rows = probe_bot_presence()
    lines = [
        "Engel Grok Bot presence",
        "",
        "Lifecycle states are file-only: idle | ready | blocked | missing.",
        "No HTTP/ADB/SSH probe — use Test-EngelMainOneSystemConnections.ps1 for live links.",
        "",
    ]
    for row in rows:
        lines.append(
            f"- [{row.get('lifecycle')}] {row.get('id')}: {row.get('label')} — {row.get('detail')}"
        )
    return "\n".join(lines)


def render_grok_bot_list(payload: str = "") -> str:
    del payload
    bots = list_bots()
    lines = ["Engel Grok Bots", ""]
    if not bots:
        return "\n".join(lines + ["No named bots. Create one with: create grok bot <name> | <role>"])
    for bot in bots:
        lines.append(f"## {bot.get('name')}")
        lines.append(f"slug: {bot.get('slug')}")
        lines.append(f"role: {bot.get('role')}")
        lines.append(f"updated: {bot.get('updated_at_utc')}")
        notes = bot.get("memory_notes")
        if isinstance(notes, list) and notes:
            lines.append("notes: " + _clip(notes[-1], 180))
        lines.append("")
    lines.append("All of these Bots share the same Engel computer.")
    return "\n".join(lines).strip()


def render_grok_bot_computer(payload: str = "") -> str:
    del payload
    lines = [
        "Engel Grok Bot shared computer",
        "",
        "This is one user-scoped Engel computer. Bots share files, Meeting Room",
        "state, worker queues, and CT 246 runtime. They do not get isolated VMs.",
        "",
    ]
    for row in probe_shared_computer():
        lines.append(f"- {row['part']}: {row['state']}")
        lines.append(f"  {row['path']}")
    lines.extend(
        [
            "",
            "Wiki One: wiki/ONE.md — every Bot reads it before CODE and updates it when organs change.",
            "",
            "Intended live URLs after one-system start:",
            "- http://127.0.0.1:24680/health   CT 246 chat",
            "- http://127.0.0.1:8790/health    Meeting Room LAN",
            "",
            "This probe is file-only. It does not open SSH, HTTP, or ADB.",
            "Use: powershell -File scripts/Test-EngelMainOneSystemConnections.ps1",
        ]
    )
    return "\n".join(lines)


def render_grok_bot_approvals(payload: str = "") -> str:
    del payload
    return "\n".join(
        [
            "Engel Grok Bot approvals",
            "",
            "Josh > Guardian > Engel/runtime.",
            "A Bot only comes back when a gate is real.",
            "",
            "Bucket 1 Auto-approve",
            "- status, docs, computer map, receipts, append-only thread notes",
            "",
            "Bucket 2 Needs sign-off",
            "- save a skill, promote a routine, change future teammate behavior",
            "",
            "Bucket 3 Needs Josh call",
            "- source edits, route/runtime/service/storage changes",
            "- provider/network, downloads, training, trusted memory",
            "- Android job create, phone startup, Proxmox/storage mutation",
            "",
            "Handoff stages a Meeting Room order. It does not Send Job.",
            "Send Job / Android packet / Architect action stay explicit.",
        ]
    )


def render_grok_bot_create(payload: str = "") -> str:
    rest = _strip_prefixes(payload, _CREATE_PREFIXES)
    if not rest:
        return "Usage: create grok bot <name> | <role>\nExample: create grok bot Research Scout | cluster research teammate"
    guard = _guard(rest)
    if not guard["ok"]:
        return f"Guardian blocked Bot create ({guard['verdict']})."
    if "|" in rest:
        name, role = [part.strip() for part in rest.split("|", 1)]
    else:
        name, role = rest, "Named teammate on the shared Engel computer"
    slug = _slugify(name)
    if not slug or slug in {"create", "grok", "bot"} and name.casefold() in {"create", "grok bot"}:
        return "Usage: create grok bot <name> | <role>"
    if slug == "grok" and load_bot("grok") is not None and name.casefold() != "grok":
        slug = _slugify(name)
    existing = load_bot(slug)
    if existing is not None:
        return f"Bot already exists: {existing.get('name')} ({slug}). Message it instead."
    bot = {
        "schema": SCHEMA_BOT,
        "slug": slug,
        "name": name.strip() or slug,
        "role": role.strip() or "Named teammate on the shared Engel computer",
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
        "memory_notes": ["Created as an Engel cluster teammate. Shares the one Engel computer."],
        "preferred_surfaces": [
            "ct246-chat",
            "meeting-room",
            "android-workers",
            "sub-engel",
            "architect",
            "reps",
        ],
        "last_plan": None,
        "thread_count": 0,
    }
    _write_json(_bot_path(slug), bot)
    registry = _load_registry()
    if slug not in registry["bots"]:
        registry["bots"].append(slug)
        _save_registry(registry)
    receipt = _write_receipt("create", {"slug": slug, "name": bot["name"], "role": bot["role"]})
    return "\n".join(
        [
            f"Created Grok Bot: {bot['name']}",
            f"slug: {slug}",
            f"role: {bot['role']}",
            "computer: shared Engel cluster (CT246 + ROG + Meeting Room + workers)",
            f"state: {_bot_path(slug)}",
            f"receipt: {receipt}",
            "",
            f"Next: message grok bot {bot['name']} | <task>",
        ]
    )


def _update_bot_plan(bot: dict[str, Any], plan: dict[str, Any], persist_thread: bool) -> None:
    slug = str(bot.get("slug") or DEFAULT_SLUG)
    bot["last_plan"] = {
        "task": plan.get("task"),
        "signoff": plan.get("signoff"),
        "body_part_ids": [part.get("id") for part in plan.get("body_parts", [])],
        "at_utc": _now(),
    }
    bot["updated_at_utc"] = _now()
    if persist_thread:
        try:
            bot["thread_count"] = int(bot.get("thread_count") or 0) + 1
        except (TypeError, ValueError):
            bot["thread_count"] = 1
    _write_json(_bot_path(slug), bot)


def render_grok_bot_message(payload: str = "") -> str:
    rest = _strip_prefixes(payload, _MESSAGE_PREFIXES)
    slug, task = _split_name_payload(rest)
    if not task:
        return "Usage: message grok bot <name> | <task>\nExample: message grok bot Grok | check android workers and meeting room state"
    guard = _guard(task)
    if not guard["ok"]:
        return f"Guardian blocked Bot message ({guard['verdict']})."
    bot = load_bot(slug) or load_bot(DEFAULT_SLUG)
    if bot is None:
        return f"No Bot named {slug}. Create it with: create grok bot {slug} | <role>"
    lines, plan = _plan_lines(bot, task)
    _append_thread(str(bot.get("slug")), "user", task)
    _append_thread(str(bot.get("slug")), "bot", "\n".join(lines))
    _update_bot_plan(bot, plan, persist_thread=True)
    receipt = _write_receipt("message", plan)
    lines.extend(["", f"receipt: {receipt}"])
    return "\n".join(lines)


def render_grok_bot_handoff(payload: str = "") -> str:
    rest = _strip_prefixes(payload, _HANDOFF_PREFIXES)
    slug, task = _split_name_payload(rest)
    if not task:
        return "Usage: handoff grok bot <name> | <task>\nThis stages a Meeting Room order. It does not Send Job or create Android work."
    guard = _guard(task)
    if not guard["ok"]:
        return f"Guardian blocked Bot handoff ({guard['verdict']})."
    bot = load_bot(slug) or load_bot(DEFAULT_SLUG)
    if bot is None:
        return f"No Bot named {slug}. Create it first."
    signoff = classify_signoff(task)
    lines, plan = _plan_lines(bot, task)
    meeting: dict[str, Any] = {"accepted": False, "reason": "not attempted"}
    if signoff["bucket"] == "3":
        lines.extend(
            [
                "",
                "Handoff stopped at Josh. Bucket 3 work is not staged into the Meeting Room",
                "from this Bot. Name the approved surface if you want it executed.",
            ]
        )
    else:
        order_text = (
            "Coordinate Grok Bot handoff for "
            + str(bot.get("name"))
            + ". Check and draft the cluster plan for: "
            + task
        )
        try:
            from engel_agent_meeting_room import submit_order_from_engel_main_ui

            meeting = submit_order_from_engel_main_ui(
                order_text,
                source="Engel Grok Bot " + str(bot.get("name")),
            )
        except Exception as exc:
            meeting = {"accepted": False, "reason": f"{type(exc).__name__}: {exc}"}
        if meeting.get("accepted"):
            lines.extend(
                [
                    "",
                    "Meeting Room order staged.",
                    f"order_id: {meeting.get('order_id')}",
                    "The room can show the team. Send Job / Android packet still need the existing buttons.",
                ]
            )
        else:
            lines.extend(
                [
                    "",
                    "Meeting Room did not accept the order.",
                    f"reason: {meeting.get('reason') or meeting}",
                ]
            )
    _append_thread(str(bot.get("slug")), "user", "HANDOFF " + task)
    _append_thread(str(bot.get("slug")), "bot", "\n".join(lines))
    _update_bot_plan(bot, plan, persist_thread=True)
    receipt = _write_receipt(
        "handoff",
        {
            **plan,
            "meeting_room": {
                "accepted": bool(meeting.get("accepted")),
                "order_id": meeting.get("order_id"),
                "reason": meeting.get("reason"),
            },
        },
    )
    lines.extend(["", f"receipt: {receipt}"])
    return "\n".join(lines)


def handle_console_line(text: str) -> str:
    """Route one desktop-console line to the matching Grok Bot surface."""
    raw = " ".join(str(text or "").split())
    low = raw.casefold()
    if not raw:
        return ""
    if low in {"help", "?"}:
        return render_grok_bot_docs()
    if low in {"status", "grok bot", "grok bot status"}:
        return render_grok_bot_status()
    if low in {"list", "list grok bots", "grok bots"}:
        return render_grok_bot_list()
    if low in {"computer", "grok bot computer"}:
        return render_grok_bot_computer()
    if low in {"approvals", "grok bot approvals"}:
        return render_grok_bot_approvals()
    if low.startswith("create ") or low.startswith("create grok bot"):
        return render_grok_bot_create(raw if low.startswith("create grok bot") else "create grok bot " + raw[7:].strip())
    if low.startswith("handoff ") or low.startswith("handoff grok bot") or low.startswith("send grok bot"):
        payload = raw
        if low.startswith("handoff ") and not low.startswith("handoff grok bot"):
            payload = "handoff grok bot " + raw[8:].strip()
        return render_grok_bot_handoff(payload)
    if low.startswith("message grok bot") or low.startswith("ask grok bot") or low.startswith("tell grok bot"):
        return render_grok_bot_message(raw)
    return render_grok_bot_message("message grok bot Grok | " + raw)


def run_grok_bot_console() -> int:
    print(render_grok_bot_status())
    print()
    print("Engel Grok Bot desktop console")
    print("Shared computer: CT 246 + ROG + Meeting Room + workers")
    print("Type a task for Grok, or: status  list  computer  approvals  help  exit")
    print("Create: create <name> | <role>")
    print("Handoff: handoff <name> | <task>")
    while True:
        try:
            text = input("Grok Bot> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not text:
            continue
        if text.casefold() in {"exit", "quit"}:
            return 0
        print()
        print(handle_console_line(text))
        print()


def run_grok_bot_computer() -> int:
    from engel_grok_bot_computer import launch_computer_window

    return launch_computer_window(bot_name="Grok")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Engel Grok Bot")
    parser.add_argument("--console", action="store_true", help="text console instead of the computer window")
    parser.add_argument("--smoke", action="store_true", help="build the computer window and exit")
    args = parser.parse_args()
    if args.console:
        raise SystemExit(run_grok_bot_console())
    if args.smoke:
        from engel_grok_bot_computer import launch_computer_window

        raise SystemExit(launch_computer_window(bot_name="Grok", smoke=True))
    raise SystemExit(run_grok_bot_computer())

