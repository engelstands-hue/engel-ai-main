#!/usr/bin/env python3
"""HTTP wrapper for the Engel Grok Imagine browser worker (runs on the ROG).

Lets Engel's server side (CT 246, Discord bridge) ask Grok to CREATE images
and videos over the LAN, then fetch the produced files:

  GET  /health                     -> {ok, logged_in_last, busy}
  POST /imagine {prompt, type,     -> runs the Playwright worker (single-flight)
                 timeout}             and returns its JSON result
  GET  /file?path=<abs path>       -> streams a produced file (outputs dir only)

Binds 127.0.0.1:24890 by default (loopback only; local callers + the CT246 reverse
tunnel). The browser profile only supports one session at a time, so requests are serialized.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "tools" / "engel_grok_imagine_worker.py"
BROWSER_PY = ROOT / "runtime" / "browser_ai_venv" / "Scripts" / "python.exe"
OUTPUT_DIR = (ROOT / "runtime" / "grok_imagine" / "outputs").resolve()

# (2026-07-10 security) Loopback-only by default: this endpoint drives the owner's signed-in
# Grok browser session, so an unauthenticated LAN caller must not reach it (audit found it
# 0.0.0.0-exposed with no auth). /imagine and /file additionally verify the peer is loopback
# (local callers + the CT246 reverse tunnel appear as 127.0.0.1).
HOST = os.environ.get("ENGEL_GROK_IMAGINE_HOST", "127.0.0.1")
PORT = int(os.environ.get("ENGEL_GROK_IMAGINE_PORT", "24890"))

_LOCAL_HOSTS = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}


def _peer_is_local(addr: str) -> bool:
    return addr in _LOCAL_HOSTS or addr.startswith("127.") or addr.endswith(":127.0.0.1")


_LOCK = threading.Lock()
_LAST = {"logged_in_last": None, "last_status": ""}


def _extract_last_json(text: str) -> dict | None:
    end = text.rfind("}")
    while end >= 0:
        depth = 0
        for start in range(end, -1, -1):
            if text[start] == "}":
                depth += 1
            elif text[start] == "{":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start : end + 1])
                        if isinstance(obj, dict):
                            return obj
                    except Exception:
                        break
        end = text.rfind("}", 0, end)
    return None


def run_imagine(prompt: str, media_type: str, timeout_s: int) -> dict:
    if not _LOCK.acquire(blocking=False):
        return {"ok": False, "busy": True, "status": "imagine worker is busy with another generation"}
    try:
        cmd = [
            str(BROWSER_PY), str(WORKER), "imagine", prompt,
            "--type", "video" if str(media_type).lower().startswith("v") else "image",
            "--timeout", str(max(30, min(300, timeout_s))),
            "--signin-if-needed",
        ]
        proc = subprocess.run(
            cmd, cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=max(120, timeout_s + 240),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        result = _extract_last_json(proc.stdout or "") or {
            "ok": False,
            "status": f"worker produced no JSON (exit {proc.returncode})",
            "stderr_tail": (proc.stderr or "")[-500:],
        }
        _LAST["logged_in_last"] = not result.get("needs_login", False)
        _LAST["last_status"] = str(result.get("status") or "")
        return result
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": "imagine worker timed out"}
    except Exception as exc:
        return {"ok": False, "status": f"imagine service error: {exc}"}
    finally:
        _LOCK.release()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # keep stdout quiet; service log is enough
        pass

    def _send_json(self, payload: dict, code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/health":
            self._send_json({"ok": True, "service": "engel-grok-imagine", "busy": _LOCK.locked(), **_LAST})
            return
        if parsed.path == "/file":
            if not _peer_is_local(self.client_address[0]):
                self._send_json({"ok": False, "status": "forbidden: local callers only"}, 403)
                return
            qs = urllib.parse.parse_qs(parsed.query)
            raw = (qs.get("path") or [""])[0]
            path = Path(raw).resolve()
            # real containment (a str.startswith prefix also matches sibling dirs like
            # outputs_evil\): require the resolved path to be OUTPUT_DIR or strictly under it.
            try:
                contained = path == OUTPUT_DIR or OUTPUT_DIR in path.parents
            except Exception:
                contained = False
            if not contained or not path.is_file():
                self._send_json({"ok": False, "status": "file not found or outside outputs dir"}, 404)
                return
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self._send_json({"ok": False, "status": "unknown route"}, 404)

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path != "/imagine":
            self._send_json({"ok": False, "status": "unknown route"}, 404)
            return
        if not _peer_is_local(self.client_address[0]):
            self._send_json({"ok": False, "status": "forbidden: local callers only"}, 403)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8", errors="replace") or "{}")
        except Exception:
            self._send_json({"ok": False, "status": "bad JSON body"}, 400)
            return
        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            self._send_json({"ok": False, "status": "empty prompt"}, 400)
            return
        result = run_imagine(
            prompt,
            str(payload.get("type") or "image"),
            int(payload.get("timeout") or 150),
        )
        self._send_json(result)


def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"engel-grok-imagine service on {HOST}:{PORT}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
