#!/usr/bin/env python3
"""HTTP wrapper for the Engel Grok Headless Worker broker (runs on the ROG).

Exposes the policy-gated builder lane over the LAN so CT246 (the backbone) can
ask the ROG-side Grok worker to CREATE things and get receipts back:

  GET  /health                 -> {ok, service, busy, imagine_up}
  GET  /policy                 -> the effective policy.json (secrets already absent)
  POST /do {action, ...}       -> runs one broker action (single-flight)

Actions map 1:1 to engel_grok_headless_worker:
  status | scan{root?,max_files?} | create_project{name,brief,files?,generate?}
  draft{kind,title,content?,generate?} | imagine{prompt,type?,timeout?}
  test{project} | zip{project} | send{path}

Binds 127.0.0.1:24892 by default (loopback only; CT246 reaches it via the reverse SSH
tunnel). NOT the grok.exe CLI (24880, forbidden) and NOT the Claude bridge (24882).
Requests are serialized: the image lane and the browser profile allow one session at a time.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import engel_grok_headless_worker as W  # noqa: E402

# (2026-07-10 security) This broker drives real build/scan/imagine/test/send actions on the
# ROG, so it must NEVER be reachable by arbitrary LAN hosts (an audit found it 0.0.0.0-exposed
# with a dead approval gate -> unauthenticated RCE via create_project+test). Default bind is
# now loopback, AND every state-changing / info-disclosing route verifies the peer is loopback
# (CT246 reaches this through the reverse SSH tunnel, which appears as 127.0.0.1 here). Keep both.
HOST = os.environ.get("ENGEL_GROK_HEADLESS_HOST", "127.0.0.1")
PORT = int(os.environ.get("ENGEL_GROK_HEADLESS_PORT", "24892"))

_LOCAL_HOSTS = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}


def _peer_is_local(addr: str) -> bool:
    return addr in _LOCAL_HOSTS or addr.startswith("127.") or addr.endswith(":127.0.0.1")


_LOCK = threading.Lock()


def _dispatch(action: str, body: dict) -> dict:
    policy = W.load_policy()
    approval = set(policy.get("requires_josh_approval", []))
    if action in approval:
        return {"ok": False, "requires_approval": True, "action": action,
                "status": f"'{action}' needs Joshua's approval and is not exposed over HTTP"}
    try:
        if action == "status":
            return W.action_status(policy)
        if action == "scan":
            return W.action_scan(policy, body.get("root") or None, int(body.get("max_files", 250000)))
        if action == "create_project":
            return W.action_create_project(policy, body["name"], body["brief"],
                                           body.get("files_json"), bool(body.get("generate")))
        if action == "draft":
            return W.action_draft(policy, body["kind"], body["title"],
                                  body.get("content", ""), bool(body.get("generate")))
        if action == "imagine":
            return W.action_imagine(policy, body["prompt"], body.get("type", "image"),
                                    int(body.get("timeout", 240)))
        if action == "test":
            return W.action_test(policy, body["project"])
        if action == "zip":
            return W.action_zip(policy, body["project"])
        if action == "send":
            return W.action_send(policy, body["path"])
        return {"ok": False, "status": f"unknown action '{action}'"}
    except KeyError as exc:
        return {"ok": False, "status": f"missing required field: {exc}"}
    except Exception as exc:
        return {"ok": False, "status": f"action error: {exc}"}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, obj: dict) -> None:
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # quiet
        pass

    def do_GET(self):
        import urllib.parse
        path = urllib.parse.urlparse(self.path).path
        if path == "/health":
            imagine_up = False
            try:
                st = W.action_status(W.load_policy())
                imagine_up = st["image_lane"].get("up", False)
            except Exception:
                pass
            return self._send(200, {"ok": True, "service": "engel-grok-headless",
                                    "busy": _LOCK.locked(), "imagine_up": imagine_up, "port": PORT})
        if path == "/policy":
            # policy.json carries the CT246 SSH pivot (host/user/port/key path) + root paths
            if not _peer_is_local(self.client_address[0]):
                return self._send(403, {"ok": False, "status": "forbidden: local callers only"})
            return self._send(200, W.load_policy())
        return self._send(404, {"ok": False, "status": "not found"})

    def do_POST(self):
        import urllib.parse
        if urllib.parse.urlparse(self.path).path != "/do":
            return self._send(404, {"ok": False, "status": "POST /do only"})
        # /do executes builder actions (write files, run pytest, scan, imagine) -> loopback only
        if not _peer_is_local(self.client_address[0]):
            return self._send(403, {"ok": False, "status": "forbidden: local callers only"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8", "replace")) if n else {}
        except Exception as exc:
            return self._send(400, {"ok": False, "status": f"bad json: {exc}"})
        action = str(body.get("action", "")).strip()
        if not action:
            return self._send(400, {"ok": False, "status": "missing 'action'"})
        if not _LOCK.acquire(blocking=False):
            return self._send(409, {"ok": False, "busy": True,
                                    "status": "grok headless worker is busy with another job"})
        try:
            out = _dispatch(action, body)
        finally:
            _LOCK.release()
        return self._send(200 if out.get("ok") else 422, out)


def main() -> int:
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"engel-grok-headless broker on {HOST}:{PORT}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
