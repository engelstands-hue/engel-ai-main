#!/usr/bin/env python3
"""MX Server — the ModelExpress metadata broker for Engel AI Main.

The centre box of the architecture: Engel's inference engines (the ROG GPU chat
server, the CT246 chat runtime, the image lane) tell this service which weights they
hold, and a starting engine asks it how to get them. Weights never travel through
here — only metadata. The data plane is `engel_model_express.stream_weights` (POSIX
ModelStreamer) or, on hardware that has it, peer GPUDirect RDMA.

Loopback-only by policy: the 2026-07-10 attack-surface audit found unauthenticated
LAN-reachable bridges on this box, so every Engel broker binds 127.0.0.1 and is
reached from CT246 through the existing reverse SSH tunnel, never over the LAN.
"""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for candidate in (str(ROOT), str(TOOLS)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from engel_model_express import (  # noqa: E402
    MX_SERVER_PORT,
    discover_and_register,
    forget,
    locate,
    mx_capabilities,
    mx_status,
    plan_load,
    register_resident_weights,
    stream_weights,
)


def _json(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or "0")
    if length <= 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8-sig", errors="replace")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


class Handler(BaseHTTPRequestHandler):
    server_version = "EngelModelExpress/1.0"

    def log_message(self, *_args: Any) -> None:  # quiet: this runs hidden
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        route = parsed.path.rstrip("/") or "/"
        try:
            if route in ("/", "/health", "/status"):
                _json(self, 200, {"ok": True, **mx_status()})
            elif route == "/capabilities":
                _json(self, 200, {"ok": True, **mx_capabilities()})
            elif route == "/locate":
                model_id = (query.get("model_id") or [""])[0]
                holders = locate(model_id)
                _json(self, 200, {"ok": bool(model_id), "model_id": model_id,
                                  "holders": holders, "holder_count": len(holders)})
            elif route == "/plan":
                model_id = (query.get("model_id") or [""])[0]
                requester = (query.get("requesting_holder") or [""])[0]
                _json(self, 200, plan_load(model_id, requester))
            else:
                _json(self, 404, {"ok": False, "status": "not found", "path": self.path})
        except Exception as exc:  # noqa: BLE001 - a broker answers, it does not crash
            _json(self, 500, {"ok": False, "status": f"{type(exc).__name__}: {exc}"})

    def do_POST(self) -> None:  # noqa: N802
        route = urlparse(self.path).path.rstrip("/") or "/"
        request = _read_json(self)
        try:
            if route == "/register":
                if not str(request.get("model_id") or "").strip():
                    _json(self, 400, {"ok": False, "status": "model_id is required"})
                    return
                entry = register_resident_weights(
                    model_id=request.get("model_id", ""),
                    weights_path=request.get("weights_path", ""),
                    holder=request.get("holder", ""),
                    device=request.get("device", "cpu"),
                    bytes_total=request.get("bytes_total"),
                    sha256=request.get("sha256", ""),
                    lane=request.get("lane", ""),
                    resident=request.get("resident", True) is True,
                )
                _json(self, 200, {"ok": True, "registered": entry})
            elif route == "/discover":
                _json(self, 200, discover_and_register())
            elif route == "/plan":
                _json(self, 200, plan_load(
                    request.get("model_id", ""), request.get("requesting_holder", "")
                ))
            elif route == "/forget":
                dropped = forget(request.get("model_id", ""), request.get("holder", ""))
                _json(self, 200, {"ok": True, "forgotten": dropped})
            elif route == "/stream":
                path = str(request.get("weights_path") or "")
                limit = request.get("limit_mib")
                _json(self, 200, stream_weights(
                    path,
                    limit_bytes=(int(limit) * 1024 * 1024) if limit else None,
                    verify_sha256=request.get("verify_sha256") is True,
                ))
            else:
                _json(self, 404, {"ok": False, "status": "not found", "path": self.path})
        except Exception as exc:  # noqa: BLE001
            _json(self, 500, {"ok": False, "status": f"{type(exc).__name__}: {exc}"})


def main() -> int:
    parser = argparse.ArgumentParser(description="Engel ModelExpress metadata broker")
    parser.add_argument("--host", default="127.0.0.1", help="loopback only by policy")
    parser.add_argument("--port", type=int, default=MX_SERVER_PORT)
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print(
            json.dumps(
                {
                    "ok": False,
                    "status": (
                        "refusing to bind a non-loopback address; Engel brokers are "
                        "loopback-only and reached through the CT246 reverse tunnel"
                    ),
                    "requested_host": args.host,
                }
            )
        )
        return 2
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(
        json.dumps(
            {
                "ok": True,
                "status": "engel model express broker listening",
                "url": f"http://{args.host}:{args.port}",
            }
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
