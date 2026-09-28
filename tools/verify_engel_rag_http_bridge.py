#!/usr/bin/env python3
"""Loopback HTTP contract verifier for Engel's CT246 production RAG routes."""

from __future__ import annotations

from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
from typing import Any
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import engel_main_server_chat_http_service as service


EXECUTION_CALLS: list[dict[str, Any]] = []


def _fixture_status() -> dict[str, Any]:
    return {
        "schema": "ENGEL_RAG_RUNTIME_STATUS_V2",
        "ok": True,
        "status": "all ten CT246 RAG routes ready",
        "production_route_count": 10,
        "provider_called": False,
        "trusted_memory_write": False,
        "index_mutation": False,
    }


def _fixture_execute(
    query: str,
    *,
    strategy: str,
    k: int,
    modal_context: str,
) -> dict[str, Any]:
    EXECUTION_CALLS.append(
        {
            "query": query,
            "strategy": strategy,
            "k": k,
            "modal_context": modal_context,
        }
    )
    return {
        "schema": "ENGEL_RAG_ROUTE_RESULT_V2",
        "ok": True,
        "route_id": "rag_route_fixture",
        "requested_strategy": strategy,
        "executed_strategy": strategy,
        "top_k": k,
        "answer": "Fixture production route answer [1].",
        "results": [
            {
                "source": "memory/fixture.md",
                "text": "Fixture evidence",
                "score": 0.9,
            }
        ],
        "route_meta": {"modal_context_present": bool(modal_context)},
        "provider_called": False,
        "trusted_memory_write": False,
        "index_mutation": False,
    }


def _request(
    base_url: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        base_url + path,
        data=body,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def main() -> int:
    service.rag_runtime_status_snapshot = _fixture_status
    service.execute_rag_route = _fixture_execute
    service._RAG_RUNTIME_IMPORT_ERROR = ""
    service._SNAPSHOT_CACHE.clear()

    server = ThreadingHTTPServer(("127.0.0.1", 0), service.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    checks: list[dict[str, Any]] = []
    try:
        status_code, status = _request(base_url, "GET", "/rag/status")
        checks.append(
            {
                "check": "GET /rag/status exposes ten production routes",
                "ok": status_code == 200
                and status.get("ok") is True
                and status.get("production_route_count") == 10,
            }
        )

        query_code, result = _request(
            base_url,
            "POST",
            "/rag/query",
            {
                "query": "What does this screenshot show?",
                "strategy": "multimodal",
                "top_k": 5,
                "normalized_media_context": "OCR: CT246 is connected.",
            },
        )
        checks.append(
            {
                "check": "POST /rag/query maps bounded route inputs to execution",
                "ok": query_code == 200
                and result.get("ok") is True
                and result.get("requested_strategy") == "multimodal"
                and bool(EXECUTION_CALLS)
                and EXECUTION_CALLS[-1]
                == {
                    "query": "What does this screenshot show?",
                    "strategy": "multimodal",
                    "k": 5,
                    "modal_context": "OCR: CT246 is connected.",
                },
            }
        )
        checks.append(
            {
                "check": "HTTP response preserves local-only and read-only boundaries",
                "ok": result.get("provider_called") is False
                and result.get("trusted_memory_write") is False
                and result.get("index_mutation") is False,
            }
        )

        bad_code, bad = _request(
            base_url,
            "POST",
            "/rag/query",
            {"query": "Valid text", "strategy": "simple", "top_k": "not-an-int"},
        )
        checks.append(
            {
                "check": "malformed route inputs fail closed",
                "ok": bad_code == 400 and bad.get("ok") is False,
            }
        )

        missing_code, missing = _request(base_url, "GET", "/rag/reindex")
        checks.append(
            {
                "check": "no reindex endpoint is exposed",
                "ok": missing_code == 404 and missing.get("ok") is False,
            }
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    source = Path(service.__file__).read_text(encoding="utf-8")
    checks.append(
        {
            "check": "RAG execution is explicitly restricted to loopback",
            "ok": 'if path in {"/rag/query", "/v1/rag/query"}' in source
            and "_loopback_client_address(client_host)" in source,
        }
    )
    deploy_source = (ROOT / "scripts" / "Start-EngelMainServerChatService.ps1").read_text(
        encoding="utf-8"
    )
    checks.append(
        {
            "check": "deployment ships the RAG runtime and warms semantic retrieval",
            "ok": '"tools\\engel_rag_runtime.py"' in deploy_source
            and "http://127.0.0.1:8940/search" in deploy_source
            and "semantic warm probe" in deploy_source,
        }
    )

    failed = [item for item in checks if item.get("ok") is not True]
    payload = {
        "schema": "ENGEL_RAG_HTTP_BRIDGE_VERIFIER_V1",
        "ok": not failed,
        "checks_total": len(checks),
        "checks_passed": len(checks) - len(failed),
        "checks_failed": len(failed),
        "checks": checks,
        "provider_called": False,
        "trusted_memory_write": False,
        "index_mutation": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
