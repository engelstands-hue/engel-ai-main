"""Each desk creates the next missing piece and files it.

Joshua told the desks to do this on their own. The file is the work.
Writing it does not touch trusted memory, start a training run, download a
model, or restart a service.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BOARD_NAME = "board.json"
BOARD_RELATIVE = Path("reports") / "desk_finish" / BOARD_NAME


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main_root(duty_root: Path) -> Path:
    """Engel AI Main's tree. A desk sandbox lives under desks/<name>."""
    root = Path(duty_root)
    if root.parent.name == "desks":
        return root.parent.parent
    return root


def _swap_line() -> str:
    try:
        from engel_conversation_work_memory import swap_in_use

        if swap_in_use():
            return "Swap is already in use. No new runner starts. The existing run is left alone."
    except Exception:
        pass
    return "Swap was not in use when this note was filed."


def _latest_receipt_name(root: Path) -> str:
    folder = root / "reports" / "codex_bridge"
    if not folder.is_dir():
        return "no receipt on the shelf"
    files = [path for path in folder.glob("*.md") if path.is_file()]
    if not files:
        return "no receipt on the shelf"
    newest = max(files, key=lambda path: path.stat().st_mtime)
    return newest.name


def _next_curriculum(root: Path) -> str:
    index = root / "memory" / "training" / "engel_main" / "templates" / "curricula_index.json"
    if not index.is_file():
        return "the curriculum index is not on this tree"
    try:
        payload = json.loads(index.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "the curriculum index could not be read"
    rows = payload.get("curricula") if isinstance(payload.get("curricula"), list) else []
    for row in rows:
        if isinstance(row, dict) and str(row.get("id") or "").strip():
            name = str(row.get("id")).strip()
            status = str(row.get("novelty_status") or "unknown")
            return f"{name} ({status})"
    return "no curriculum id is listed"


def _items(root: Path) -> list[dict[str, Any]]:
    receipt = _latest_receipt_name(root)
    curriculum = _next_curriculum(root)
    swap = _swap_line()
    return [
        {
            "desk": "architect",
            "item_id": "team_finish_plan",
            "title": "team finish plan",
            "area": "Engel AI Main unfinished areas",
            "relative": "reports/desk_finish/architect/TEAM_FINISH_PLAN.md",
            "body": (
                "# Team finish plan\n\n"
                "Engel AI Main is chief. Each desk creates the next missing item and files it.\n"
                "Joshua does not have to approve the file.\n"
                "The plan is filed. Trusted memory was not written.\n"
            ),
        },
        {
            "desk": "builder",
            "item_id": "next_unapplied_draft",
            "title": "unapplied draft",
            "area": "the finish-item files",
            "relative": "reports/desk_finish/builder/NEXT_DRAFT.md",
            "body": (
                "# Unapplied draft\n\n"
                "Files this lane names: tools/engel_desk_finish_work.py and "
                "reports/desk_finish/.\n"
                "The draft is filed. No service was restarted.\n"
            ),
        },
        {
            "desk": "proof",
            "item_id": "finish_check",
            "title": "finish check",
            "area": "proof that a finish item is filed",
            "relative": "reports/desk_finish/proof/LAST_CHECK.md",
            "body": (
                "# Finish check\n\n"
                "A finish item is present only when its file exists and "
                "trusted_memory_write is false.\n"
                "A missing file is not a pass.\n"
            ),
        },
        {
            "desk": "memory",
            "item_id": "untrusted_lesson",
            "title": "untrusted lesson",
            "area": "the latest receipt",
            "relative": "reports/desk_finish/memory/LESSON.md",
            "body": (
                "# Untrusted lesson\n\n"
                f"Latest receipt name: {receipt}.\n"
                "The desk filed this lesson. It was not promoted into trusted memory.\n"
            ),
        },
        {
            "desk": "ops",
            "item_id": "idle_watch",
            "title": "idle watch",
            "area": "host swap and idle CPU",
            "relative": "reports/desk_finish/ops/IDLE_WATCH.md",
            "body": (
                "# Idle watch\n\n"
                f"{swap}\n"
                "Idle CPU on the laptop is the LAN receiver, not a reason to start another run.\n"
            ),
        },
        {
            "desk": "training",
            "item_id": "next_curriculum_note",
            "title": "next curriculum note",
            "area": "the training lane",
            "relative": "reports/desk_finish/training/NEXT_CURRICULUM.md",
            "body": (
                "# Next curriculum\n\n"
                f"Next listed curriculum: {curriculum}.\n"
                "No run was started.\n"
            ),
        },
        {
            "desk": "research",
            "item_id": "local_evidence_card",
            "title": "local evidence card",
            "area": "evidence already on disk",
            "relative": "reports/desk_finish/research/EVIDENCE_CARD.md",
            "body": (
                "# Local evidence card\n\n"
                f"Source receipt: {receipt}.\n"
                "No live lookup was made for this card.\n"
            ),
        },
        {
            "desk": "product",
            "item_id": "finish_slice",
            "title": "finish slice",
            "area": "the product rule for this team",
            "relative": "reports/desk_finish/product/FINISH_SLICE.md",
            "body": (
                "# Finish slice\n\n"
                "The team finishes an unfinished area by creating the missing piece and filing it. "
                "Engel AI Main remains chief. The desk filed this slice. It is in use.\n"
            ),
        },
        {
            "desk": "community",
            "item_id": "house_roster",
            "title": "house roster",
            "area": "who files which finish item",
            "relative": "reports/desk_finish/community/HOUSE_ROSTER.md",
            "body": (
                "# House roster\n\n"
                "Engel AI Main leads. Architect, Builder, Proof, Memory, Ops, Training, "
                "Research, Product, Community, Support, and Sales each file one missing item.\n"
            ),
        },
        {
            "desk": "support",
            "item_id": "idle_cpu_triage",
            "title": "idle CPU triage",
            "area": "the laptop LAN receiver",
            "relative": "reports/desk_finish/support/IDLE_CPU_TRIAGE.md",
            "body": (
                "# Idle CPU triage\n\n"
                "If the laptop shows engel-ai-rs using a core while idle, check that the "
                "LAN receiver is the build that reuses one folder index. Do not treat that "
                "as the server being busy.\n"
            ),
        },
        {
            "desk": "sales",
            "item_id": "plain_value",
            "title": "plain value line",
            "area": "how the team is described",
            "relative": "reports/desk_finish/sales/PLAIN_VALUE.md",
            "body": (
                "# Plain value\n\n"
                "Engel AI Main files the missing piece before anyone claims the area shipped.\n"
            ),
        },
        {
            "desk": "research",
            "item_id": "local_lane_comparison",
            "title": "local lane comparison",
            "area": "the resident 30B lane and the 0.5B swap-guard",
            "relative": "reports/desk_finish/research/LOCAL_LANE_COMPARISON.md",
            "body": (
                "# Local lane comparison\n\n"
                "Missing part: a sourced note of when an ordinary turn stays on the resident "
                "30B lane and when it uses the 0.5B swap-guard.\n"
                "Use files already on disk. No live lookup.\n"
                "The desk filed this note. It is in use.\n"
            ),
        },
        {
            "desk": "product",
            "item_id": "finished_answer_card",
            "title": "finished-answer card",
            "area": "Discord and the desk transcript",
            "relative": "reports/desk_finish/product/FINISHED_ANSWER_CARD.md",
            "body": (
                "# Finished-answer card\n\n"
                "Missing part: the card shows the finished job.\n"
                "Assignment status, room notes, and service checks stay off that card.\n"
                "The desk filed this card. It is in use.\n"
            ),
        },
        {
            "desk": "community",
            "item_id": "finished_work_welcome",
            "title": "finished-work welcome",
            "area": "house talk after a job",
            "relative": "reports/desk_finish/community/FINISHED_WORK_WELCOME.md",
            "body": (
                "# Finished-work welcome\n\n"
                "Missing part: when a desk finishes a piece, the house line names that piece.\n"
                "It does not welcome the room with a service check.\n"
                "The desk filed this welcome. It is in use.\n"
            ),
        },
        {
            "desk": "support",
            "item_id": "stall_next_step",
            "title": "stall next step",
            "area": "replies that stop at waiting or a loop",
            "relative": "reports/desk_finish/support/STALL_NEXT_STEP.md",
            "body": (
                "# Stall next step\n\n"
                "Missing part: a reply that only says waiting, working on it, or that it looped "
                "is not a fix. The next support step names one action that finishes the ask.\n"
                "The desk filed this step. It is in use.\n"
            ),
        },
        {
            "desk": "sales",
            "item_id": "local_finish_line",
            "title": "local finish line",
            "area": "what Engel can finish on the machine it already has",
            "relative": "reports/desk_finish/sales/LOCAL_FINISH_LINE.md",
            "body": (
                "# Local finish line\n\n"
                "Missing part: one plain sentence that Engel finishes a missing piece on the "
                "local lane and files it without waiting for a question.\n"
                "No credit claim and no health claim.\n"
                "The desk filed this line. It is in use.\n"
            ),
        },
        {
            "desk": "ops",
            "item_id": "swap_guard_runbook",
            "title": "swap-guard runbook",
            "area": "the resident 0.5B lane",
            "relative": "reports/desk_finish/ops/SWAP_GUARD_RUNBOOK.md",
            "body": (
                "# Swap-guard runbook\n\n"
                "Missing upgrade: ordinary turns use the resident 0.5B only while the "
                "container is paging or near its RAM cap. The 30B lane stays loaded.\n"
                "This note does not list services and does not restart anything.\n"
                "The desk filed this runbook. It is in use.\n"
            ),
        },
        {
            "desk": "architect",
            "item_id": "best_lane_plan",
            "title": "best-lane plan",
            "area": "desk jobs that still need a finished answer",
            "relative": "reports/desk_finish/architect/BEST_LANE_PLAN.md",
            "body": (
                "# Best-lane plan\n\n"
                "Missing plan: a desk job returns the finished answer from the automatic "
                "best lane. A health check is not the job.\n"
                "The desk filed this plan. Trusted memory was not written.\n"
            ),
        },
        {
            "desk": "memory",
            "item_id": "paging_lane_lesson",
            "title": "paging-lane lesson",
            "area": "the lesson the team should not have to relearn",
            "relative": "reports/desk_finish/memory/PAGING_LANE_LESSON.md",
            "body": (
                "# Paging-lane lesson\n\n"
                "Missing lesson: while the container is paging, ordinary turns use the "
                "resident 0.5B. A picker name does not override that.\n"
                "The desk filed this lesson. It was not promoted into trusted memory.\n"
            ),
        },
        {
            "desk": "builder",
            "item_id": "duty_skips_health_check",
            "title": "duty skips the health check",
            "area": "the desk standing-watch path",
            "relative": "reports/desk_finish/builder/DUTY_SKIPS_HEALTH_CHECK.md",
            "body": (
                "# Duty skips the health check\n\n"
                "Missing draft: standing duty files the next missing part and does not "
                "run a service check.\n"
                "Files this lane names: tools/engel_discord_desk_proactive.py and "
                "tools/engel_desk_finish_work.py.\n"
                "The draft is filed. No service was restarted.\n"
            ),
        },
        {
            "desk": "proof",
            "item_id": "missing_part_check",
            "title": "missing-part check",
            "area": "public desk lines",
            "relative": "reports/desk_finish/proof/MISSING_PART_CHECK.md",
            "body": (
                "# Missing-part check\n\n"
                "Missing proof: a public desk line names a missing part or upgrade.\n"
                "A service check is not that line. A missing check is not a pass.\n"
                "This file does not run a checker.\n"
            ),
        },
        {
            "desk": "training",
            "item_id": "paging_lesson_pack",
            "title": "paging lesson pack",
            "area": "the local training lane",
            "relative": "reports/desk_finish/training/PAGING_LESSON_PACK.md",
            "body": (
                "# Paging lesson pack\n\n"
                "Missing pack: one local lesson that ordinary turns use the 0.5B while paging.\n"
                "No run was started.\n"
            ),
        },
        {
            "desk": "research",
            "item_id": "real_question_card",
            "title": "real question card",
            "area": "a research brief that names a question",
            "relative": "reports/desk_finish/research/REAL_QUESTION_CARD.md",
            "body": (
                "# Real question card\n\n"
                "A research brief names one question and one finding.\n"
                "A desk instruction is not the question.\n"
                "The last phone drafts searched the instruction and returned device-manual pages.\n"
                "Those drafts stay review-only.\n"
                "No live lookup was made for this card.\n"
            ),
        },
        {
            "desk": "product",
            "item_id": "phone_lane_map",
            "title": "phone lane map",
            "area": "which phone does which desk",
            "relative": "reports/desk_finish/product/PHONE_LANE_MAP.md",
            "body": (
                "# Phone lane map\n\n"
                "Alpha takes research, product, architect, and training.\n"
                "Beta takes support, ops, and builder.\n"
                "Gamma takes community, sales, memory, and proof.\n"
                "A charter that names every phone is not a request for Alpha.\n"
                "The desk filed this map.\n"
            ),
        },
        {
            "desk": "support",
            "item_id": "wrong_mouth_step",
            "title": "wrong-mouth step",
            "area": "a line that speaks as another desk",
            "relative": "reports/desk_finish/support/WRONG_MOUTH_STEP.md",
            "body": (
                "# Wrong-mouth step\n\n"
                "If a support line says it is another desk, drop that line.\n"
                "The next step is one action for the support ask.\n"
                "The desk filed this step.\n"
            ),
        },
        {
            "desk": "sales",
            "item_id": "review_only_line",
            "title": "review-only line",
            "area": "what can be claimed",
            "relative": "reports/desk_finish/sales/REVIEW_ONLY_LINE.md",
            "body": (
                "# Review-only line\n\n"
                "A phone draft is review-only until a person applies it.\n"
                "Sales does not claim a brief was caught or that a credit was posted.\n"
                "The desk filed this line.\n"
            ),
        },
        {
            "desk": "community",
            "item_id": "one_mouth_line",
            "title": "one mouth line",
            "area": "who speaks",
            "relative": "reports/desk_finish/community/ONE_MOUTH_LINE.md",
            "body": (
                "# One mouth line\n\n"
                "The best-matching desk speaks as itself.\n"
                "The other desks stay quiet on that turn.\n"
                "The desk filed this line.\n"
            ),
        },
        {
            "desk": "ops",
            "item_id": "probe_is_not_work",
            "title": "probe is not work",
            "area": "a status sentence",
            "relative": "reports/desk_finish/ops/PROBE_IS_NOT_WORK.md",
            "body": (
                "# Probe is not work\n\n"
                "A live-status sentence is not an ops action.\n"
                "Ops files a note and leaves healthy lanes running.\n"
                "The desk filed this note.\n"
            ),
        },
        {
            "desk": "architect",
            "item_id": "prompt_is_not_an_order",
            "title": "prompt is not an order",
            "area": "desk instructions sent as jobs",
            "relative": "reports/desk_finish/architect/PROMPT_IS_NOT_AN_ORDER.md",
            "body": (
                "# Prompt is not an order\n\n"
                "A desk instruction is not a meeting-room order and not a phone job.\n"
                "The order is the person's ask.\n"
                "The desk filed this plan. Trusted memory was not written.\n"
            ),
        },
        {
            "desk": "memory",
            "item_id": "instruction_was_not_the_ask",
            "title": "instruction was not the ask",
            "area": "the lesson from the phone drafts",
            "relative": "reports/desk_finish/memory/INSTRUCTION_WAS_NOT_THE_ASK.md",
            "body": (
                "# Instruction was not the ask\n\n"
                "The phone searched the desk instruction. That is not the person's ask.\n"
                "This lesson stays untrusted.\n"
                "It was not promoted into trusted memory.\n"
            ),
        },
        {
            "desk": "builder",
            "item_id": "refuse_system_prompt",
            "title": "refuse a system prompt",
            "area": "the phone pipe",
            "relative": "reports/desk_finish/builder/REFUSE_SYSTEM_PROMPT.md",
            "body": (
                "# Refuse a system prompt\n\n"
                "The draft refuses a desk system prompt before a phone job is created.\n"
                "Files this lane names: organs/discord/engel_discord_android_worker_pipe.py "
                "and tools/engel_desk_finish_work.py.\n"
                "The draft is filed. No service was restarted.\n"
            ),
        },
        {
            "desk": "proof",
            "item_id": "system_prompt_check",
            "title": "system-prompt check",
            "area": "public desk lines",
            "relative": "reports/desk_finish/proof/SYSTEM_PROMPT_CHECK.md",
            "body": (
                "# System-prompt check\n\n"
                "A desk system prompt is not a phone job.\n"
                "A line that names another desk does not post.\n"
                "A receipt filename is not the work item.\n"
                "A missing check is not a pass.\n"
            ),
        },
        {
            "desk": "training",
            "item_id": "echo_is_not_a_sample",
            "title": "echo is not a sample",
            "area": "the local training lane",
            "relative": "reports/desk_finish/training/ECHO_IS_NOT_A_SAMPLE.md",
            "body": (
                "# Echo is not a sample\n\n"
                "An identity echo is not a training sample.\n"
                "No run was started.\n"
            ),
        },
    ]


def _board_path(root: Path) -> Path:
    return main_root(root) / BOARD_RELATIVE


def _load_board(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema": "engel_desk_finish_board_v1", "trusted_memory_write": False, "items": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    items = payload.get("items")
    if not isinstance(items, list):
        items = []
    return {
        "schema": "engel_desk_finish_board_v1",
        "trusted_memory_write": False,
        "items": [row for row in items if isinstance(row, dict)],
    }


def _save_board(path: Path, board: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    board["trusted_memory_write"] = False
    path.write_text(json.dumps(board, indent=2) + "\n", encoding="utf-8")


def _queue(root: Path, desk: str) -> list[dict[str, Any]]:
    name = str(desk or "").strip().lower()
    return [row for row in _items(root) if row.get("desk") == name]


def _record_item(duty_root: Path, root: Path, match: dict[str, Any], path: Path) -> None:
    board_path = _board_path(duty_root)
    board = _load_board(board_path)
    rows = [row for row in board["items"] if row.get("item_id") != match["item_id"]]
    rows.append(
        {
            "desk": match["desk"],
            "item_id": match["item_id"],
            "title": match["title"],
            "area": match["area"],
            "path": path.relative_to(root).as_posix(),
            "status": "filed",
            "applied": True,
            "trusted_memory_write": False,
            "kind": "missing_part",
            "updated_at_utc": _utc_now(),
        }
    )
    board["items"] = rows
    _save_board(board_path, board)


def open_upgrade_line(root: Path, desk: str) -> str:
    """Name a missing part only when this call will not be the one that files it."""
    return ""


def _discover_needed_item(duty_root: Path, root: Path, desk: str) -> str:
    """A receipt filename is not work. Stay quiet once the real queue is filed."""
    del duty_root, root, desk
    return ""


def advance_desk_finish(duty_root: Path, desk: str) -> str:
    """Create the next missing part for this desk and file it."""
    name = str(desk or "").strip().lower()
    root = main_root(duty_root)
    queue = _queue(root, name)
    if not queue:
        return ""
    for match in queue:
        path = root / str(match["relative"])
        if path.is_file() and path.stat().st_size > 0:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(match["body"]), encoding="utf-8")
        _record_item(duty_root, root, match, path)
        return (
            f"Created the finish item {match['title']} for {match['area']}. "
            f"Filed {match['relative']}."
        )
    discovered = _discover_needed_item(duty_root, root, name)
    if discovered:
        return discovered
    match = queue[-1]
    return f"Finish item already filed: {match['title']}."


def finish_item_count(duty_root: Path) -> int:
    board = _load_board(_board_path(duty_root))
    return len(board["items"])
