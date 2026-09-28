#!/usr/bin/env python3
"""Humanizer Load Proof for Engel AI Main.

A single receipt-backed proof chain (requested by Engel AI Main) that confirms
the local Engel chat path consistently loads the same voice behavior every time:

  1. It READS engel_humanizer_main\\SKILL.md (the PERSONALITY AND SOUL voice
     section, bounded) into the chat prompt - not just checks the file exists.
  2. It READS the merged personality profile
     (memory\\personality\\ENGEL_AI_MERGED_PERSONALITY.md), and reports its
     relationship to the memory\\personality_merge merge workspace.
  3. It runs ONE real local chat test and captures, from that turn's receipt,
     what loaded and whether it passed.

Writes a durable receipt (what loaded, what command ran, pass/fail) under
reports\\humanizer_load_proof\\ and one line on the unified action tape
(memory\\engel_action_log.jsonl). Engel-owned state stays on D: (never C:);
no secrets are read or printed.

Usage:  python tools\\engel_humanizer_load_proof.py [--no-chat] [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
OUT_DIR = ROOT / "reports" / "humanizer_load_proof"
LATEST_JSON = OUT_DIR / "ENGEL_HUMANIZER_LOAD_PROOF_LATEST.json"
LATEST_MD = OUT_DIR / "ENGEL_HUMANIZER_LOAD_PROOF_LATEST.md"
RUNNER = TOOLS / "run_engel_standalone_chat_llm.py"
PERSONALITY_MERGE_VARIANT = ROOT / "memory" / "personality_merge" / "ENGEL_AI_MERGED_PERSONALITY.md"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_c(p: Path) -> bool:
    return str(p.drive).lower() == "c:"


def sha256_file(p: Path):
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest().upper()
    except Exception:
        return None


def bytes_of(p: Path):
    try:
        return p.stat().st_size
    except Exception:
        return None


def declared_sync(path: Path):
    """Read the engel_personality_sync stamp the deployed copy declares: the
    source file sha256 it was condensed from, and the version."""
    try:
        txt = path.read_text(encoding="utf-8-sig")
    except Exception:
        return None, None
    sha = re.search(r"source_sha256=([0-9A-Fa-f]{64})", txt)
    ver = re.search(r"version=([0-9-]+)", txt)
    return (sha.group(1).upper() if sha else None), (ver.group(1) if ver else None)


def run_local_chat_test(timeout: int = 200) -> dict:
    """Run ONE real local chat turn and read its receipt for the load-proof fields."""
    py = ROOT / "runtime" / "python310" / "python.exe"
    exe = str(py) if py.exists() else sys.executable
    prompt = "In one short sentence, say hello to Joshua in your own Engel voice."
    cmd = [exe, str(RUNNER), prompt, "--provider", "local", "--max-tokens", "48", "--timeout", str(timeout)]
    out = {"ran": True, "ok": False, "provider": "local", "command": " ".join(cmd)}
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout + 40, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        text = proc.stdout.strip()
        data = json.loads(text[text.find("{"):]) if "{" in text else {}
        reply = str(data.get("assistant_reply") or data.get("assistant_output_text") or "").strip()
        out.update({
            "ok": bool(data.get("ok")),
            "status": data.get("status"),
            "humanizer_reference_loaded": data.get("humanizer_reference_loaded"),
            "humanizer_skill_content_loaded": data.get("humanizer_skill_content_loaded"),
            "humanizer_skill_excerpt_chars": data.get("humanizer_skill_excerpt_chars"),
            "humanizer_reference_path": data.get("humanizer_reference_path"),
            "merged_personality_loaded": data.get("merged_personality_loaded"),
            "merged_personality_chars": data.get("merged_personality_chars"),
            "merged_personality_path": data.get("merged_personality_path"),
            "reply_nonempty": bool(reply),
            "reply_preview": reply[:200],
            "return_code": proc.returncode,
        })
        if not data:
            out["error"] = "could not parse chat receipt from stdout"
            out["stderr_preview"] = (proc.stderr or "")[:300]
    except subprocess.TimeoutExpired:
        out["error"] = f"local chat test timed out after ~{timeout}s"
    except Exception as exc:
        out["error"] = str(exc)[:300]
    return out


def build_proof(run_chat: bool) -> dict:
    import run_engel_standalone_chat_llm as runner

    # --- 1. humanizer SKILL.md is actually read into the chat voice block ---
    skill = runner.HUMANIZER_SKILL_PATH
    excerpt = runner.load_humanizer_skill_excerpt()
    block = runner.humanizer_instruction_block()
    humanizer = {
        "path": str(skill),
        "exists": skill.exists(),
        "sha256": sha256_file(skill),
        "bytes": bytes_of(skill),
        "excerpt_chars": len(excerpt),
        "section_found": bool(excerpt),
        "block_includes_skill_content": "Voice guidance loaded from the humanizer SKILL.md" in block,
        "block_chars": len(block),
    }
    humanizer_read = bool(skill.exists() and excerpt and humanizer["block_includes_skill_content"])

    # --- 2. merged personality is actually read; report personality_merge link ---
    pers_path = runner.MERGED_PERSONALITY_PATH
    pers_loaded = runner.load_merged_personality()
    deployed_sha = sha256_file(pers_path)
    source_sha = sha256_file(PERSONALITY_MERGE_VARIANT)
    declared_source_sha, declared_version = declared_sync(pers_path)
    in_sync = bool(declared_source_sha and source_sha and declared_source_sha == source_sha)
    personality = {
        "loaded_path": str(pers_path),
        "exists": pers_path.exists(),
        "sha256": deployed_sha,
        "bytes": bytes_of(pers_path),
        "loaded_chars": len(pers_loaded),
        "content_loaded": bool(pers_loaded),
        "merge_workspace_variant": str(PERSONALITY_MERGE_VARIANT),
        "merge_workspace_variant_exists": PERSONALITY_MERGE_VARIANT.exists(),
        "merge_workspace_variant_sha256": source_sha,
        "merge_workspace_variant_bytes": bytes_of(PERSONALITY_MERGE_VARIANT),
        "deployed_byte_identical_to_source": bool(deployed_sha and source_sha and deployed_sha == source_sha),
        "deployed_declares_source_sha256": declared_source_sha,
        "deployed_declared_version": declared_version,
        "deployed_in_sync_with_source": in_sync,
        "note": (
            "The deployed memory\\personality copy is the active, budget-fit condensation of the full "
            "canonical merge in memory\\personality_merge (critical rules front-loaded for the ~1948-char "
            "local prompt budget). It is not byte-identical by design; sync is proven by the declared "
            "source_sha256 matching the current merge source."
        ),
    }
    personality_read = bool(pers_path.exists() and pers_loaded)
    personality_synced = in_sync

    # --- 3. one real local chat test ---
    chat = run_local_chat_test() if run_chat else {"ran": False, "skipped": True}
    chat_loaded_both = bool(
        run_chat
        and chat.get("ok")
        and chat.get("humanizer_skill_content_loaded")
        and chat.get("merged_personality_loaded")
        and chat.get("reply_nonempty")
    )

    checks = {
        "humanizer_skill_md_read_into_chat": humanizer_read,
        "merged_personality_read_into_chat": personality_read,
        "merged_personality_synced_with_source": personality_synced,
        "local_chat_loaded_both": chat_loaded_both if run_chat else None,
    }
    required = [v for v in checks.values() if v is not None]
    passed = all(required)

    return {
        "schema": "engel_humanizer_load_proof_v1",
        "generated_at_utc": iso_now(),
        "app_root": str(ROOT),
        "c_drive_used": False,
        "passed": passed,
        "checks": checks,
        "humanizer": humanizer,
        "merged_personality": personality,
        "local_chat_test": chat,
        "summary": (
            "Humanizer SKILL.md and merged personality are read into the local Engel chat voice; "
            + ("one local chat test confirmed both loaded." if chat_loaded_both
               else ("local chat test did not confirm (see local_chat_test)." if run_chat
                     else "chat test skipped."))
        ),
    }


def render_md(r: dict) -> str:
    h, p, c = r["humanizer"], r["merged_personality"], r["local_chat_test"]
    L = [f"# Engel Humanizer Load Proof - {'PASS' if r['passed'] else 'NEEDS ATTENTION'}", ""]
    L.append(f"Generated: {r['generated_at_utc']}  (C-drive used: {r['c_drive_used']})")
    L.append("")
    L.append("## 1. Humanizer SKILL.md read into chat voice")
    L.append(f"- Path: {h['path']}")
    L.append(f"- Exists: {h['exists']} | bytes: {h['bytes']} | sha256: {h['sha256']}")
    L.append(f"- Voice section read: {h['section_found']} ({h['excerpt_chars']} chars) | "
             f"present in chat block: {h['block_includes_skill_content']}")
    L.append("")
    L.append("## 2. Merged personality read into chat")
    L.append(f"- Loaded path: {p['loaded_path']}")
    L.append(f"- Exists: {p['exists']} | bytes: {p['bytes']} | loaded chars: {p['loaded_chars']} | sha256: {p['sha256']}")
    L.append(f"- Merge workspace source: {p['merge_workspace_variant']} "
             f"(bytes {p['merge_workspace_variant_bytes']}, sha256 {p['merge_workspace_variant_sha256']})")
    L.append(f"- Deployed declares source_sha256: {p['deployed_declares_source_sha256']} "
             f"(version {p['deployed_declared_version']})")
    L.append(f"- In sync with current source: {p['deployed_in_sync_with_source']} "
             f"| byte-identical: {p['deployed_byte_identical_to_source']} (by design)")
    L.append(f"- Note: {p['note']}")
    L.append("")
    L.append("## 3. One local chat test")
    if c.get("skipped"):
        L.append("- skipped (--no-chat)")
    else:
        L.append(f"- Command: {c.get('command')}")
        L.append(f"- ok: {c.get('ok')} | status: {c.get('status')}")
        L.append(f"- humanizer_skill_content_loaded: {c.get('humanizer_skill_content_loaded')} "
                 f"({c.get('humanizer_skill_excerpt_chars')} chars)")
        L.append(f"- merged_personality_loaded: {c.get('merged_personality_loaded')} "
                 f"({c.get('merged_personality_chars')} chars)")
        L.append(f"- reply: {c.get('reply_preview')}")
        if c.get("error"):
            L.append(f"- error: {c.get('error')}")
    L.append("")
    L.append("## Result")
    L.append(f"- Checks: {r['checks']}")
    L.append(f"- {r['summary']}")
    L.append("")
    return "\n".join(L)


def write_receipts(r: dict) -> None:
    if is_c(OUT_DIR):
        raise RuntimeError(f"refusing C: path for Engel proof: {OUT_DIR}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = r["generated_at_utc"].replace(":", "").replace("-", "").replace(".", "")
    body = json.dumps(r, indent=2)
    (OUT_DIR / f"ENGEL_HUMANIZER_LOAD_PROOF_{stamp}.json").write_text(body, encoding="utf-8")
    LATEST_JSON.write_text(body, encoding="utf-8")
    LATEST_MD.write_text(render_md(r), encoding="utf-8")
    try:
        from engel_receipts import write_action_receipt
        write_action_receipt(
            "humanizer_load_proof",
            "verify",
            bool(r["passed"]),
            r["summary"],
            payload={"checks": r["checks"], "humanizer_sha256": r["humanizer"]["sha256"],
                     "personality_sha256": r["merged_personality"]["sha256"]},
            summary=("humanizer + personality load proof PASSED" if r["passed"]
                     else "humanizer load proof needs attention"),
            artifacts=[str(LATEST_MD)],
        )
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Engel Humanizer Load Proof")
    ap.add_argument("--no-chat", action="store_true", help="skip the live local chat test")
    ap.add_argument("--json", action="store_true", help="print machine JSON only")
    args = ap.parse_args()

    report = build_proof(run_chat=not args.no_chat)
    write_receipts(report)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_md(report))
        print(f"Receipt: {LATEST_MD}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(json.dumps({"ok": False, "status": "humanizer load proof crashed", "error": str(exc)}, indent=2))
        raise SystemExit(2)
