"""Engel Speech Packet Compiler (SPC).

SPC is the speech-side twin of MIPL. It compiles hear (STT) and speak (TTS)
turns into bounded, non-authorizing packets. It does not record a microphone,
play audio, download models, or call cloud STT/TTS.

Chain:

    hear packet (STT lane)
        -> Lifted iNTent + MIPL (existing)
        -> chat LLM
        -> Humanization SLM (existing spoken rewrite)
        -> speak packet (TTS lane)

Lanes are complementary, not clones:

- Engel AI Main / CT246 owns Nemotron ASR and the compile/bind.
- Sub-Engel (DESKTOP-UE5A6GG) owns Windows audio plus Whisper+Piper helper
  weights. Sub-Engel is not Chase.
- ROG is the face/controller and may use Windows SAPI as a helper.
- Discord stays text-only (speak_skip). Humanization already owns the words.

Authority: Josh > Guardian > Engel/runtime.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
RECEIPT_DIR = ROOT / "reports" / "engel_speech_spc"
LATEST_RECEIPT = RECEIPT_DIR / "LATEST.json"

SCHEMA = "engel_speech_spc_v1"
LANGUAGE = "Engel SPC"
VERSION = 1
PROFILE = "spc1-speech-packet"
MAX_TEXT_CHARS = 800
MAX_PATH_CHARS = 240

CT_ASR_CANDIDATES = (
    Path("/opt/engel/models-active/asr/nemotron-3.5-asr-streaming-0.6b"),
    ROOT / "models-active" / "asr" / "nemotron-3.5-asr-streaming-0.6b",
)
WHISPER_CANDIDATES = (
    Path("/opt/engel/models-active/speech"),
    ROOT / "runtime" / "next_stage" / "speech",
    ROOT / "models" / "speech" / "whisper",
)
PIPER_CANDIDATES = (
    Path("/opt/engel/models-active/speech/en_US-amy-medium.onnx"),
    ROOT / "runtime" / "next_stage" / "speech" / "en_US-amy-medium.onnx",
    ROOT / "models" / "speech" / "piper" / "en_US-amy-medium.onnx",
)
SUB_ENGEL_ROOTS = (
    Path(r"D:\EngelWindowsSubNode"),
    Path(r"D:\EngelSubEngelDrop"),
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _one_line(value: Any, limit: int = MAX_TEXT_CHARS) -> str:
    text = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())
    return text[:limit]


def _hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def _first_present(paths: tuple[Path, ...]) -> str:
    for path in paths:
        if _exists(path):
            return str(path)[:MAX_PATH_CHARS]
    return ""


def inspect_sub_engel_mmap() -> dict[str, Any]:
    """Read-only mmap facts for Sub-Engel. Does not load a model."""
    root = next((path for path in SUB_ENGEL_ROOTS if _exists(path)), None)
    cli = (root / "runtimes" / "llama.cpp" / "cuda" / "llama-cli.exe") if root else Path("")
    gguf = (
        root / "models" / "mistral-7b-instruct-v0.3" / "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"
        if root
        else Path("")
    )
    fallback_on = str(os.environ.get("ENGEL_SUB_ENGEL_ENABLE_LLAMA_CPP_FALLBACK") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return {
        "owner": "sub_engel",
        "sub_engel_is_not_chase": True,
        "node_root_present": bool(root),
        "preferred_runtime": "peft_lora_transformers",
        "preferred_uses_gguf_mmap": False,
        "peft_is_weight_load_not_mmap": True,
        "legacy_llama_cpp": {
            "cli_present": _exists(cli),
            "gguf_present": _exists(gguf),
            "mmap": "llama.cpp default enabled (--mmap)",
            "argv_sets_no_mmap": False,
            "fallback_enabled_now": fallback_on,
            "runtime_mode": "one_shot_cli" if fallback_on else "disabled_by_default",
        },
        "not_ct246_resident_mmap": True,
        "ct246_mmap_mode": "task_routed_single_resident_mmap",
        "note": "Sub-Engel prefers PEFT. GGUF mmap is only the disabled llama-cli fallback unless explicitly enabled.",
    }


def inspect_lanes() -> dict[str, Any]:
    """Read-only lane inventory. Presence is not permission to play or capture."""
    whisper = _first_present(WHISPER_CANDIDATES)
    piper = _first_present(PIPER_CANDIDATES)
    asr = _first_present(CT_ASR_CANDIDATES)
    return {
        "hear_ct_asr": {
            "kind": "hear",
            "owner": "engel_ai_main_ct246",
            "present": bool(asr),
            "path": asr,
            "role": "server streaming ASR",
        },
        "hear_whisper": {
            "kind": "hear",
            "owner": "sub_engel_helper",
            "present": bool(whisper),
            "path": whisper,
            "role": "offline Whisper helper (Sub-Engel / next_stage)",
        },
        "speak_piper": {
            "kind": "speak",
            "owner": "sub_engel_helper",
            "present": bool(piper),
            "path": piper,
            "role": "offline Piper Amy helper",
        },
        "speak_sapi": {
            "kind": "speak",
            "owner": "rog_controller",
            "present": sys.platform == "win32",
            "path": "windows-sapi" if sys.platform == "win32" else "",
            "role": "ROG face helper only, not CT246 default",
        },
        "speak_skip": {
            "kind": "speak",
            "owner": "engel_ai_main",
            "present": True,
            "path": "text-only",
            "role": "Discord/chat text; humanization already spoke in words",
        },
        "sub_engel_mmap": inspect_sub_engel_mmap(),
    }


def _pick_hear_lane(lanes: Mapping[str, Any]) -> str:
    if lanes.get("hear_ct_asr", {}).get("present"):
        return "hear_ct_asr"
    if lanes.get("hear_whisper", {}).get("present"):
        return "hear_whisper"
    return "hear_missing"


def _pick_speak_lane(source: str, lanes: Mapping[str, Any]) -> str:
    src = str(source or "").strip().casefold()
    if src.startswith("discord") or src in {"discord_public", "discord_bridge"}:
        return "speak_skip"
    if lanes.get("speak_piper", {}).get("present"):
        return "speak_piper"
    if lanes.get("speak_sapi", {}).get("present"):
        return "speak_sapi"
    return "speak_skip"


def compile_speech_packet(
    *,
    kind: str,
    text: str,
    source: str = "",
    caller: str = "engel_ai_main",
    request_id: str = "",
    lnt: Mapping[str, Any] | None = None,
    humanization: Mapping[str, Any] | None = None,
    slm_advisory: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile one hear or speak packet. Never plays, records, or downloads."""
    kind_text = str(kind or "").strip().casefold()
    if kind_text not in {"hear", "speak"}:
        kind_text = "speak"
    lanes = inspect_lanes()
    lane = _pick_hear_lane(lanes) if kind_text == "hear" else _pick_speak_lane(source, lanes)
    lane_meta = dict(lanes.get(lane) or {"present": False, "owner": "none"})
    lifted = dict(lnt) if isinstance(lnt, Mapping) else {}
    body = {
        "schema": SCHEMA,
        "language": LANGUAGE,
        "version": VERSION,
        "profile": PROFILE,
        "kind": kind_text,
        "text": _one_line(text),
        "source": _one_line(source, 80),
        "caller": _one_line(caller, 120),
        "request_id": _one_line(request_id, 160),
        "lane": lane,
        "lane_present": bool(lane_meta.get("present")),
        "lane_owner": str(lane_meta.get("owner") or ""),
        "execution_authorized": False,
        "playback_authorized": False,
        "capture_authorized": False,
        "does_not_call_cloud": True,
        "does_not_mutate_lnt": True,
        "sub_engel_is_not_chase": True,
        "lnt_effect": lifted.get("effect"),
        "lnt_contract_id": lifted.get("contract_id"),
        "humanization_used": bool((humanization or {}).get("used") or (humanization or {}).get("humanization_slm_used")),
        "slm_intent": (slm_advisory or {}).get("intent") if isinstance(slm_advisory, Mapping) else None,
    }
    body["packet_hash"] = _hash(
        {
            "kind": body["kind"],
            "text": body["text"],
            "lane": body["lane"],
            "lnt_contract_id": body["lnt_contract_id"],
        }
    )
    body["created_at_utc"] = _now()
    return body


def _write_receipt(packet: Mapping[str, Any]) -> dict[str, Any]:
    receipt = dict(packet)
    receipt["receipt_schema"] = "engel_speech_spc_receipt_v1"
    try:
        RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
        path = RECEIPT_DIR / f"{str(packet.get('kind') or 'speak').upper()}_{packet.get('created_at_utc')}_{str(packet.get('packet_hash') or '')[:12]}.json"
        payload = json.dumps(receipt, indent=2, ensure_ascii=False)
        temp = path.with_suffix(".tmp")
        temp.write_text(payload, encoding="utf-8")
        temp.replace(path)
        latest_temp = LATEST_RECEIPT.with_suffix(".tmp")
        latest_temp.write_text(payload, encoding="utf-8")
        latest_temp.replace(LATEST_RECEIPT)
        receipt["receipt_path"] = str(path)
    except OSError as exc:
        receipt["receipt_path"] = ""
        receipt["write_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    return receipt


def attach_speech_spc(
    prompt: str,
    reply: str,
    receipt: Mapping[str, Any] | None = None,
    *,
    source: str = "",
    caller: str = "engel_ai_main",
) -> dict[str, Any]:
    """Stamp a speak packet onto a chat receipt. Fail-open at the caller."""
    rec = dict(receipt or {})
    packet = compile_speech_packet(
        kind="speak",
        text=reply or prompt,
        source=source or str(rec.get("source") or rec.get("runtime_provider") or ""),
        caller=caller,
        request_id=str(rec.get("run_id") or rec.get("id") or ""),
        lnt=rec.get("lnt") if isinstance(rec.get("lnt"), Mapping) else rec.get("lifted_intent"),
        humanization={
            "used": rec.get("humanization_slm_used"),
            "reason": rec.get("humanization_slm_reason"),
        },
        slm_advisory=rec.get("slm_router_advisory")
        if isinstance(rec.get("slm_router_advisory"), Mapping)
        else rec.get("slm_advisory"),
    )
    saved = _write_receipt(packet)
    rec["speech_spc"] = {
        "name": "speech_packet_compiler",
        "kind": saved.get("kind"),
        "lane": saved.get("lane"),
        "lane_present": saved.get("lane_present"),
        "execution_authorized": False,
        "playback_authorized": False,
        "capture_authorized": False,
        "packet_hash": saved.get("packet_hash"),
        "receipt_path": saved.get("receipt_path") or "",
    }
    rec["speech_spc_receipt_path"] = saved.get("receipt_path") or ""
    return rec


def load_latest_receipt() -> dict[str, Any] | None:
    try:
        value = json.loads(LATEST_RECEIPT.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, TypeError):
        return None
    return value if isinstance(value, dict) and value.get("schema") == SCHEMA else None


def render_docs(_text: str = "") -> str:
    return "\n".join(
        (
            "Engel Speech Packet Compiler (SPC)",
            "",
            "SPC compiles hear/speak turns the way MIPL compiles intent. It is not a",
            "microphone, speaker, cloud voice API, or background listener.",
            "",
            "Chain: hear -> LNT/MIPL -> chat LLM -> humanization SLM -> speak.",
            "Hear lanes: CT246 Nemotron ASR, Sub-Engel Whisper helper.",
            "Speak lanes: Sub-Engel Piper helper, ROG SAPI, or text-only skip.",
            "",
            "Safety:",
            "- execution_authorized, playback_authorized, and capture_authorized stay false.",
            "- No cloud STT/TTS. No model download. No C: writes.",
            "- Sub-Engel is not Chase. Live 7B stays on CT246.",
            "- Humanization already owns spoken wording; SPC only packets the turn.",
            "",
            "Commands: speech spc status; speech spc docs; speech spc latest; compile speech <text>.",
        )
    )


def render_status(_text: str = "") -> str:
    lanes = inspect_lanes()
    latest = load_latest_receipt()
    count = len(list(RECEIPT_DIR.glob("*.json"))) if RECEIPT_DIR.is_dir() else 0
    lines = [
        "Engel Speech Packet Compiler status",
        f"profile: {PROFILE}",
        f"receipts: {count}",
        f"latest: {(latest or {}).get('packet_hash', '')[:16] or 'none'}",
        f"latest lane: {(latest or {}).get('lane') or 'none'}",
        "",
        "Lanes:",
    ]
    for name, meta in lanes.items():
        mark = "present" if meta.get("present") else "absent"
        lines.append(f"  {name}: {mark} owner={meta.get('owner')}")
    lines.append("")
    mmap = lanes.get("sub_engel_mmap") if isinstance(lanes.get("sub_engel_mmap"), dict) else inspect_sub_engel_mmap()
    lines.append("Sub-Engel mmap:")
    lines.append(f"  preferred_runtime: {mmap.get('preferred_runtime')}")
    lines.append(f"  preferred_uses_gguf_mmap: {mmap.get('preferred_uses_gguf_mmap')}")
    legacy = mmap.get("legacy_llama_cpp") if isinstance(mmap.get("legacy_llama_cpp"), dict) else {}
    lines.append(f"  llama.cpp mmap: {legacy.get('mmap')} fallback_enabled={legacy.get('fallback_enabled_now')}")
    lines.append(f"  not CT246 resident mmap: {mmap.get('not_ct246_resident_mmap')}")
    lines.append("")
    lines.append("Compile only. Playback and capture stay unsigned.")
    return "\n".join(lines)


def render_latest(_text: str = "") -> str:
    latest = load_latest_receipt()
    if not latest:
        return "No SPC receipt yet. Say compile speech <text> or send a chat turn."
    return json.dumps(
        {
            "kind": latest.get("kind"),
            "lane": latest.get("lane"),
            "text": latest.get("text"),
            "packet_hash": latest.get("packet_hash"),
            "execution_authorized": latest.get("execution_authorized"),
            "playback_authorized": latest.get("playback_authorized"),
            "receipt_path": latest.get("receipt_path"),
        },
        indent=2,
        ensure_ascii=False,
    )


def render_compile(text: str = "") -> str:
    payload = str(text or "").strip()
    for prefix in ("compile speech", "speech spc compile", "spc compile"):
        if payload.casefold().startswith(prefix):
            payload = payload[len(prefix) :].strip()
            break
    packet = compile_speech_packet(kind="speak", text=payload or "hello Engel", caller="speech_spc_preview")
    saved = _write_receipt(packet)
    return json.dumps(
        {
            "ok": True,
            "kind": saved.get("kind"),
            "lane": saved.get("lane"),
            "lane_present": saved.get("lane_present"),
            "execution_authorized": False,
            "playback_authorized": False,
            "packet_hash": saved.get("packet_hash"),
            "receipt_path": saved.get("receipt_path"),
            "text": saved.get("text"),
        },
        indent=2,
        ensure_ascii=False,
    )


def render_chat(text: str) -> str:
    low = str(text or "").strip().casefold()
    if "latest" in low:
        return render_latest(text)
    if low.startswith(("compile speech", "speech spc compile", "spc compile")):
        return render_compile(text)
    if "doc" in low or "help" in low:
        return render_docs(text)
    return render_status(text)
