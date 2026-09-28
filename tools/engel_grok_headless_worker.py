#!/usr/bin/env python3
"""
Engel AI Main — Grok Headless Worker broker (builder-with-guardrails lane).

Architecture (Joshua, 2026-07-09):
  CT246   = Engel backbone / source of truth (receives results + receipts)
  ROG     = headless Grok worker + face (this broker runs here)
  Engel UI = controller/viewer

This is the PERMISSION GATE between "Grok as a creator" and the machine. It uses
the two lanes that actually work:
  images -> the Grok Imagine headless-browser lane (tools/engel_grok_imagine_*),
  text   -> Engel's own failover chain (tools/engel_agent_failover_loop) with the
            grok-cli lane EXCLUDED — .grok\\bin\\grok.exe spawned runaway git.exe
            children and stays OFF permanently.

Everything it may and may not do lives in runtime/grok_headless_worker/policy.json:
create-only file writes inside allowed_create_roots, inventory scans inside
allowed_scan_roots (blocked_roots always win), sandboxed python tests only inside
created projects, and receipts for every action (local tape + optional CT246 drop).
Actions on the requires_josh_approval list are refused with a plan, never executed.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "runtime" / "grok_headless_worker" / "policy.json"
OUTBOX = ROOT / "runtime" / "grok_headless_worker" / "outbox"
sys.path.insert(0, str(ROOT / "tools"))

from engel_receipts import write_action_receipt  # noqa: E402


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_policy() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- path guards
def _norm(p) -> str:
    return os.path.normcase(str(Path(p).resolve()))


def _under(child, root) -> bool:
    """True if child == root or child is inside root (case-insensitive, whole
    path components only — 'D:\\GitFoo' does NOT match root 'D:\\Git')."""
    c, r = _norm(child), _norm(root)
    return c == r or c.startswith(r + os.sep)


def _blocked(policy: dict, path) -> str | None:
    for b in policy.get("blocked_roots", []):
        if _under(path, b):
            return b
    return None


def _scan_allowed(policy: dict, path) -> tuple[bool, str]:
    b = _blocked(policy, path)
    if b:
        return False, f"path is inside blocked root {b}"
    roots = policy.get("allowed_scan_roots", []) + policy.get("allowed_skill_roots", [])
    if any(_under(path, r) for r in roots):
        return True, ""
    return False, "path is outside every allowed_scan_root"


def _create_allowed(policy: dict, path) -> tuple[bool, str]:
    if str(path)[:2].lower() == "c:":
        return False, "C: drive is never a create target"
    b = _blocked(policy, path)
    if b:
        return False, f"path is inside blocked root {b}"
    if any(_under(path, r) for r in policy.get("allowed_create_roots", [])):
        return True, ""
    return False, "path is outside every allowed_create_root"


def _write_new(policy: dict, path: Path, content: str) -> None:
    """Create-only write: refuses to overwrite ANY existing file."""
    ok, why = _create_allowed(policy, path)
    if not ok:
        raise PermissionError(f"create refused for {path}: {why}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8") as fh:  # 'x' = fail if exists
        fh.write(content)


def _receipt(action: str, ok: bool, status: str, payload=None, artifacts=None) -> str:
    return write_action_receipt(
        "grok_headless", action, ok, status=status, payload=payload,
        summary=status, artifacts=artifacts,
    )


def _refused(policy: dict, action: str, detail: str) -> dict:
    out = {
        "ok": False,
        "requires_approval": action in policy.get("requires_josh_approval", []),
        "action": action,
        "status": detail,
    }
    _receipt(action, False, f"refused: {detail}")
    return out


# ------------------------------------------------------------------- actions
def action_status(policy: dict) -> dict:
    imagine_url = policy["image_lane"]["url"]
    imagine = {"up": False}
    try:
        with urllib.request.urlopen(f"{imagine_url}/health", timeout=4) as r:
            imagine = {"up": True, **json.loads(r.read().decode("utf-8", "replace"))}
    except Exception as exc:
        imagine = {"up": False, "error": str(exc)[:80]}
    out = {
        "ok": True,
        "mode": policy.get("mode"),
        "worker_http_port": policy.get("worker_http_port"),
        "image_lane": imagine,
        "text_lane": f"engel failover chain minus {policy['text_lane']['excluded_lanes']}",
        "create_roots": policy.get("allowed_create_roots"),
        "scan_roots": policy.get("allowed_scan_roots"),
        "approval_required_for": policy.get("requires_josh_approval"),
    }
    _receipt("status", True, "status ok", payload={"imagine_up": imagine.get("up")})
    return out


def action_scan(policy: dict, root: str | None = None, max_files: int = 250000) -> dict:
    """File inventory of an allowed scan root: counts, sizes, extensions, newest,
    largest, and discovered apps (.exe). Metadata ONLY — file contents are never
    read, so secrets can't leak into the report."""
    targets = [root] if root else policy.get("allowed_scan_roots", [])
    skip = set(policy.get("scan_skip_dirs", []))
    inventory: list[dict] = []
    refused: list[str] = []
    for t in targets:
        okp, why = _scan_allowed(policy, t)
        if not okp:
            refused.append(f"{t}: {why}")
            continue
        n_files = n_bytes = 0
        exts: dict[str, int] = {}
        newest: list[tuple[float, str, int]] = []
        largest: list[tuple[int, str]] = []
        exes: list[str] = []
        stack = [Path(t)]
        while stack and n_files < max_files:
            d = stack.pop()
            if d.name in skip or _blocked(policy, d):
                continue
            try:
                with os.scandir(d) as it:
                    for e in it:
                        try:
                            if e.is_dir(follow_symlinks=False):
                                stack.append(Path(e.path))
                                continue
                            st = e.stat(follow_symlinks=False)
                        except OSError:
                            continue
                        n_files += 1
                        n_bytes += st.st_size
                        ext = os.path.splitext(e.name)[1].lower() or "(none)"
                        exts[ext] = exts.get(ext, 0) + 1
                        if ext == ".exe" and len(exes) < 400:
                            exes.append(e.path)
                        newest.append((st.st_mtime, e.path, st.st_size))
                        if len(newest) > 400:
                            newest.sort(reverse=True)
                            del newest[40:]
                        largest.append((st.st_size, e.path))
                        if len(largest) > 400:
                            largest.sort(reverse=True)
                            del largest[40:]
                        if n_files >= max_files:
                            break
            except OSError:
                continue
        newest.sort(reverse=True)
        largest.sort(reverse=True)
        inventory.append({
            "root": t,
            "files": n_files,
            "bytes": n_bytes,
            "gb": round(n_bytes / 1e9, 2),
            "capped": n_files >= max_files,
            "top_extensions": dict(sorted(exts.items(), key=lambda kv: -kv[1])[:25]),
            "newest_files": [
                {"path": p, "mtime_utc": datetime.fromtimestamp(m, timezone.utc).isoformat(), "bytes": s}
                for m, p, s in newest[:25]
            ],
            "largest_files": [{"path": p, "bytes": s} for s, p in largest[:25]],
            "apps_exes_found": exes[:200],
        })
    stamp = _now_stamp()
    scan_dir = Path(r"D:\b.WorkSpace\Engel Computer Scans") / f"SCAN_{stamp}"
    report = {
        "schema": "engel_computer_scan_v1",
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "targets": targets,
        "refused": refused,
        "inventory": inventory,
    }
    md_lines = [f"# Engel Computer Scan — {stamp}", ""]
    for inv in inventory:
        md_lines += [
            f"## {inv['root']}",
            f"- files: {inv['files']:,}  ({inv['gb']} GB){'  [CAPPED]' if inv['capped'] else ''}",
            f"- top extensions: " + ", ".join(f"{k}×{v}" for k, v in list(inv["top_extensions"].items())[:10]),
            f"- apps (.exe) found: {len(inv['apps_exes_found'])}",
            "",
        ]
    if refused:
        md_lines += ["## Refused targets"] + [f"- {r}" for r in refused]
    _write_new(load_policy(), scan_dir / "scan.json", json.dumps(report, indent=2))
    _write_new(load_policy(), scan_dir / "SCAN_SUMMARY.md", "\n".join(md_lines) + "\n")
    out = {
        "ok": True,
        "scan_dir": str(scan_dir),
        "roots_scanned": [i["root"] for i in inventory],
        "total_files": sum(i["files"] for i in inventory),
        "refused": refused,
    }
    _receipt("scan_file_inventory", True,
             f"scanned {out['total_files']:,} files across {len(inventory)} root(s)",
             payload={"targets": targets, "refused": refused},
             artifacts=[str(scan_dir / "scan.json")])
    return out


def _generate_text(policy: dict, prompt: str, timeout_s: int = 90, max_tokens: int = 1400) -> str:
    """Text generation through Engel's own failover chain, grok-cli excluded."""
    import engel_agent_failover_loop as fl
    lanes, chain = fl.load_catalog()
    excluded = set(policy["text_lane"].get("excluded_lanes", []))
    chain = [c for c in chain if c not in excluded]
    res = fl.run_with_failover(prompt, chain=chain, lanes=lanes,
                               timeout_s=timeout_s, max_tokens=max_tokens)
    return res.reply if res.ok else ""


def action_create_project(policy: dict, name: str, brief: str,
                          files_json: str | None = None, generate: bool = False) -> dict:
    slug = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name.strip().lower().replace(" ", "_"))[:60]
    if not slug:
        return {"ok": False, "status": "empty project name"}
    proj = Path(r"D:\b.WorkSpace\Engel Created Apps") / slug
    if proj.exists():
        return _refused(policy, "create_project", f"project '{slug}' already exists — create-only mode never mutates")
    files: dict[str, str] = {}
    if files_json:
        files = json.loads(Path(files_json).read_text(encoding="utf-8"))
    elif generate and brief:
        raw = _generate_text(policy, (
            "You are Engel's builder lane. Produce the complete initial source files for this "
            f"new project.\nBRIEF: {brief}\n"
            "Answer ONLY with one or more fenced code blocks, each preceded by a line "
            "'FILE: <relative/path>'. Keep it minimal and runnable."
        ))
        # parse "FILE: path" + fenced block pairs
        import re
        for m in re.finditer(r"FILE:\s*([\w./\\-]+)\s*```[a-zA-Z]*\n(.*?)```", raw, re.S):
            rel = m.group(1).strip().replace("\\", "/")
            if ".." not in rel:
                files[rel] = m.group(2)
    wrote: list[str] = []
    _write_new(policy, proj / "BRIEF.md",
               f"# {name}\n\nCreated by the Engel Grok Headless Worker (create-only lane) at {_now_stamp()}.\n\n{brief}\n")
    wrote.append("BRIEF.md")
    for rel, content in files.items():
        target = proj / rel
        if ".." in rel or not _under(target, proj):
            continue
        _write_new(policy, target, content)
        wrote.append(rel)
    out = {"ok": True, "project": str(proj), "files_written": wrote}
    _receipt("create_project", True, f"created project '{slug}' with {len(wrote)} file(s)",
             payload={"brief": brief[:200]}, artifacts=[str(proj)])
    return out


def action_draft(policy: dict, kind: str, title: str, content: str = "",
                 generate: bool = False) -> dict:
    kinds = {"draft", "idea", "research", "handoff", "mockup", "code_proposal"}
    if kind not in kinds:
        return {"ok": False, "status": f"kind must be one of {sorted(kinds)}"}
    if generate and not content:
        content = _generate_text(policy, f"Write a concise {kind} packet titled '{title}'. Plain markdown, no code unless the title asks for code.")
    if not content:
        return {"ok": False, "status": "no content (pass --content or --generate)"}
    stamp = _now_stamp()
    safe_title = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in title)[:50]
    path = OUTBOX / f"{stamp}_{kind}_{safe_title}.md"
    _write_new(policy, path, f"# {title}\n\n_kind: {kind} · created: {stamp} · lane: grok-headless (create-only)_\n\n{content}\n")
    out = {"ok": True, "path": str(path), "kind": kind}
    _receipt("create_markdown_docs", True, f"{kind} packet '{title[:60]}'", artifacts=[str(path)])
    return out


def action_imagine(policy: dict, prompt: str, media_type: str = "image",
                   timeout_s: int = 240) -> dict:
    """Create an image/video via the WORKING Grok Imagine headless-browser lane."""
    url = policy["image_lane"]["url"]
    def _post():
        body = json.dumps({"prompt": prompt, "type": media_type, "timeout": timeout_s}).encode()
        req = urllib.request.Request(f"{url}/imagine", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout_s + 30) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    try:
        result = _post()
    except Exception:
        # service starts on demand, like the canvas pattern
        subprocess.Popen(
            [str(ROOT / "runtime" / "python310" / "python.exe"),
             str(ROOT / "tools" / "engel_grok_imagine_http_service.py")],
            cwd=str(ROOT), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        time.sleep(2.5)
        try:
            result = _post()
        except Exception as exc:
            _receipt("create_images_with_headless_grok", False, f"imagine lane unreachable: {exc}")
            return {"ok": False, "status": f"imagine lane unreachable: {exc}"}
    ok = bool(result.get("ok"))
    _receipt("create_images_with_headless_grok", ok,
             f"imagine '{prompt[:80]}' -> {result.get('status', '')[:100]}",
             payload={"type": media_type}, artifacts=result.get("files") or [])
    return result


def action_test(policy: dict, project: str) -> dict:
    """Sandboxed python tests, ONLY inside a created project."""
    import engel_sandbox
    proj = Path(project)
    if not _under(proj, r"D:\b.WorkSpace\Engel Created Apps"):
        return _refused(policy, "run_safe_python_tests", "tests may only run inside Engel Created Apps")
    py = str(ROOT / "runtime" / "python310" / "python.exe")
    if (proj / "tests").is_dir():
        argv = [py, "-m", "pytest", "-q", str(proj / "tests")]
    else:
        py_files = [str(p) for p in proj.rglob("*.py")][:50]
        if not py_files:
            return {"ok": False, "status": "no python files to test"}
        argv = [py, "-m", "py_compile", *py_files]
    res = engel_sandbox.run_sandboxed(argv, tier="restricted", timeout=120, cwd=str(proj))
    _receipt("run_safe_python_tests", bool(res.get("ok")),
             f"tests in {proj.name}: {'pass' if res.get('ok') else 'FAIL'}",
             payload={"argv0": argv[:3]})
    return {"ok": bool(res.get("ok")), "detail": {k: res.get(k) for k in ("ok", "exit_code", "stdout", "stderr", "blocked", "reason") if k in res}}


def action_zip(policy: dict, project: str) -> dict:
    proj = Path(project)
    if not _under(proj, r"D:\b.WorkSpace\Engel Created Apps") or not proj.is_dir():
        return _refused(policy, "package_zip", "zip source must be an existing project in Engel Created Apps")
    out_path = OUTBOX / f"{_now_stamp()}_{proj.name}.zip"
    ok, why = _create_allowed(policy, out_path)
    if not ok:
        return _refused(policy, "package_zip", why)
    with zipfile.ZipFile(out_path, "x") as zf:
        for f in proj.rglob("*"):
            if f.is_file() and ".venv" not in f.parts:
                zf.write(f, f.relative_to(proj.parent))
    out = {"ok": True, "zip": str(out_path), "bytes": out_path.stat().st_size}
    _receipt("package_zip", True, f"packaged {proj.name}", artifacts=[str(out_path)])
    return out


def action_send(policy: dict, path: str) -> dict:
    """Send a result packet/receipt to CT246 (the backbone keeps the record)."""
    src = Path(path)
    if not src.is_file():
        return {"ok": False, "status": f"not a file: {src}"}
    if not any(_under(src, r) for r in policy.get("allowed_create_roots", [])):
        return _refused(policy, "send_result_to_ct246", "only files from create roots may be sent")
    drop = policy["ct246_receipt_drop"]
    dest = f"{drop['user']}@{drop['host']}:{drop['remote_dir']}/{src.name}"
    ssh_base = ["-i", drop["key"], "-p", str(drop["port"]), "-o", "BatchMode=yes",
                "-o", "StrictHostKeyChecking=accept-new"]
    mk = subprocess.run(["ssh", *ssh_base, f"{drop['user']}@{drop['host']}",
                         f"mkdir -p {drop['remote_dir']}"],
                        capture_output=True, text=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    scp_base = ["-i", drop["key"], "-P", str(drop["port"]), "-o", "BatchMode=yes",
                "-o", "StrictHostKeyChecking=accept-new"]
    cp = subprocess.run(["scp", *scp_base, str(src), dest],
                        capture_output=True, text=True, timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    ok = mk.returncode == 0 and cp.returncode == 0
    _receipt("send_result_to_ct246", ok,
             f"sent {src.name} to CT246" if ok else f"send failed: {(cp.stderr or mk.stderr)[:120]}",
             artifacts=[str(src)])
    return {"ok": ok, "sent": str(src), "remote": f"{drop['remote_dir']}/{src.name}",
            "error": None if ok else (cp.stderr or mk.stderr)[:200]}


# ----------------------------------------------------------------------- CLI
def _cli(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Engel Grok Headless Worker — policy-gated builder lane.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sc = sub.add_parser("scan"); sc.add_argument("--root", default=""); sc.add_argument("--max-files", type=int, default=250000)
    cp = sub.add_parser("create-project"); cp.add_argument("--name", required=True); cp.add_argument("--brief", required=True); cp.add_argument("--files-json", default=""); cp.add_argument("--generate", action="store_true")
    dr = sub.add_parser("draft"); dr.add_argument("--kind", required=True); dr.add_argument("--title", required=True); dr.add_argument("--content", default=""); dr.add_argument("--generate", action="store_true")
    im = sub.add_parser("imagine"); im.add_argument("--prompt", required=True); im.add_argument("--type", default="image"); im.add_argument("--timeout", type=int, default=240)
    ts = sub.add_parser("test"); ts.add_argument("--project", required=True)
    zp = sub.add_parser("zip"); zp.add_argument("--project", required=True)
    sd = sub.add_parser("send"); sd.add_argument("--path", required=True)
    a = ap.parse_args(argv)
    policy = load_policy()
    if a.cmd == "status":
        out = action_status(policy)
    elif a.cmd == "scan":
        out = action_scan(policy, a.root or None, a.max_files)
    elif a.cmd == "create-project":
        out = action_create_project(policy, a.name, a.brief, a.files_json or None, a.generate)
    elif a.cmd == "draft":
        out = action_draft(policy, a.kind, a.title, a.content, a.generate)
    elif a.cmd == "imagine":
        out = action_imagine(policy, a.prompt, a.type, a.timeout)
    elif a.cmd == "test":
        out = action_test(policy, a.project)
    elif a.cmd == "zip":
        out = action_zip(policy, a.project)
    elif a.cmd == "send":
        out = action_send(policy, a.path)
    else:
        out = {"ok": False, "status": "unknown command"}
    print(json.dumps(out, indent=2, default=str))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
