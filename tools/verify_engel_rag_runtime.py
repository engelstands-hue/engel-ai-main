#!/usr/bin/env python3
"""Deterministic production verifier for Engel's ten CT246 RAG routes."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import engel_rag_runtime as rag


MEMORY_CALLS: list[dict[str, Any]] = []
MODEL_CALLS: list[dict[str, Any]] = []


def _memory_fixture(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 0,
) -> dict[str, Any]:
    del timeout
    MEMORY_CALLS.append({"method": method, "path": path, "payload": payload})
    if method == "GET" and path == "/health":
        return {"ok": True, "service": "engel-memory-search", "indexed": 2475}
    if method != "POST" or path != "/search" or payload is None:
        raise AssertionError(f"unexpected memory request: {method} {path}")

    query = str(payload.get("query") or "")
    low = query.casefold()
    if "prove critical topology" in low and "verified evidence" not in low:
        return {
            "ok": True,
            "results": [
                {
                    "text": "A partial record exists but does not establish the requested topology.",
                    "source": "memory/partial_record.md",
                    "score": 0.36,
                }
            ],
        }

    results = [
        {
            "text": (
                "CT246 is the Engel AI Main server authority. Engel uses the CT246 memory "
                "index and the ROG workstation is its native control surface."
            ),
            "source": "memory/ENGEL_PRIMARY_GOAL_V1.md",
            "score": 0.82,
        },
        {
            "text": (
                "Joshua's saved owner preference keeps active Engel runtime work on CT246 "
                "SSD storage and uses local models before provider escalation."
            ),
            "source": "saved_facts",
            "score": 0.76,
        },
        {
            "text": (
                "Engel AI Main, CT246, Sub-Engel, and paired workers are connected through "
                "the agent meeting room workload fabric."
            ),
            "source": "memory/ENGEL_DEVICE_FABRIC.md",
            "score": 0.71,
        },
    ]
    if "relationships connections dependencies" in low:
        results[0]["text"] += " CT246 depends on the local model lane and semantic index."
    return {"ok": True, "results": results}


def _model_fixture(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 0,
) -> dict[str, Any]:
    del timeout
    MODEL_CALLS.append({"method": method, "path": path, "payload": payload})
    if method == "GET" and path == "/v1/models":
        return {"data": [{"id": "engel-local-mistral-test"}]}
    if method != "POST" or path != "/v1/chat/completions" or payload is None:
        raise AssertionError(f"unexpected model request: {method} {path}")

    messages = payload.get("messages") if isinstance(payload.get("messages"), list) else []
    prompt = "\n".join(
        str(item.get("content") or "")
        for item in messages
        if isinstance(item, dict)
    )
    low = prompt.casefold()
    if "hypothetical answer" in low:
        text = "CT246 hosts Engel AI Main's local runtime, semantic memory, and orchestration services."
    elif "judge whether the evidence is sufficient" in low:
        text = "SUFFICIENT: the evidence directly identifies CT246 and the local-first policy."
    elif "choose one production retrieval route" in low:
        text = "graph: the question asks about connected components and dependencies."
    else:
        text = "CT246 is Engel AI Main's server authority and local runtime [1]. The owner policy is local-first [2]."
    return {"choices": [{"message": {"content": text}}]}


def _run(strategy: str, query: str, *, modal_context: str = "") -> dict[str, Any]:
    return rag.execute(
        query,
        strategy=strategy,
        k=4,
        modal_context=modal_context,
        memory_requester=_memory_fixture,
        model_requester=_model_fixture,
        write_receipt=False,
    )


def main() -> int:
    checks: list[dict[str, Any]] = []

    status = rag.status_snapshot(_memory_fixture, _model_fixture)
    checks.append(
        {
            "check": "status proves ten ready production routes and five live stages",
            "ok": status.get("ok") is True
            and status.get("production_route_count") == 10
            and len(status.get("strategies") or []) == 10
            and [item.get("status") for item in status.get("pipeline") or []]
            == ["live", "live", "live", "live", "live"],
        }
    )

    queries = {
        "simple": "What is the CT246 role?",
        "memory": "What do you remember about my local model preference?",
        "multi_query": "Compare the different ways Engel, CT246, memory, and workers collaborate.",
        "hyde": "How does Engel preserve continuity across its architecture?",
        "adaptive": "What is connected to CT246 in the Engel topology?",
        "corrective": "Prove critical topology data.",
        "self_rag": "Verify the factual role of CT246.",
        "agentic": "Trace the relationships between Engel, CT246, and workers.",
        "multimodal": "What does this system diagram show?",
        "graph": "Follow the relationship between Engel AI Main and CT246.",
    }
    results: dict[str, dict[str, Any]] = {}
    for strategy, query in queries.items():
        results[strategy] = _run(
            strategy,
            query,
            modal_context=(
                "OCR: diagram shows CT246 connected to Engel AI Main, semantic memory, "
                "Sub-Engel, and three worker devices."
                if strategy == "multimodal"
                else ""
            ),
        )

    checks.append(
        {
            "check": "all ten requested production routes execute locally",
            "ok": len(results) == 10
            and all(item.get("ok") is True for item in results.values())
            and all(item.get("requested_strategy") == strategy for strategy, item in results.items())
            and all(item.get("provider_called") is False for item in results.values()),
        }
    )
    checks.append(
        {
            "check": "multi-query performs a three-query fan-out",
            "ok": len(results["multi_query"]["route_meta"].get("route_queries") or []) >= 3,
        }
    )
    checks.append(
        {
            "check": "HyDE drafts locally and retrieves with the hypothetical document",
            "ok": "hypothetical_document" in results["hyde"]["route_meta"].get("local_model_steps", [])
            and bool(results["hyde"]["route_meta"].get("hypothetical_document"))
            and len(results["hyde"]["route_meta"].get("route_queries") or []) == 2,
        }
    )
    checks.append(
        {
            "check": "adaptive routing selects and records a real child route",
            "ok": results["adaptive"]["executed_strategy"] == "graph"
            and bool(results["adaptive"]["route_meta"].get("child_route")),
        }
    )
    checks.append(
        {
            "check": "corrective routing detects weak evidence and retries",
            "ok": results["corrective"]["route_meta"].get("correction_applied") is True
            and len(results["corrective"]["route_meta"].get("route_queries") or []) >= 2,
        }
    )
    checks.append(
        {
            "check": "Self-RAG runs a local evidence critique before generation",
            "ok": "evidence_critique" in results["self_rag"]["route_meta"].get("local_model_steps", [])
            and str(results["self_rag"]["route_meta"].get("evidence_critique") or "").startswith("SUFFICIENT"),
        }
    )
    checks.append(
        {
            "check": "agentic RAG plans and executes a bounded graph subroute",
            "ok": "route_plan" in results["agentic"]["route_meta"].get("local_model_steps", [])
            and results["agentic"]["route_meta"].get("agent_selected_strategy") == "graph"
            and results["agentic"].get("executed_strategy") == "graph",
        }
    )
    checks.append(
        {
            "check": "multimodal RAG consumes normalized media context without storing raw media",
            "ok": results["multimodal"]["route_meta"].get("modal_context_present") is True
            and len(str(results["multimodal"]["route_meta"].get("modal_context_sha256") or "")) == 64,
        }
    )
    checks.append(
        {
            "check": "Graph RAG creates entity/source nodes and relationship edges",
            "ok": results["graph"]["route_meta"].get("graph_entity_count", 0) > 0
            and len(results["graph"]["route_meta"].get("graph", {}).get("nodes") or []) > 0
            and len(results["graph"]["route_meta"].get("graph", {}).get("edges") or []) > 0,
        }
    )
    checks.append(
        {
            "check": "all routes rerank, generate citations, and preserve read-only memory boundaries",
            "ok": all(item.get("result_count", 0) > 0 for item in results.values())
            and all("[1]" in str(item.get("answer") or "") for item in results.values())
            and all(item.get("trusted_memory_write") is False for item in results.values())
            and all(item.get("index_mutation") is False for item in results.values()),
        }
    )

    bounded = rag.execute(
        "Bound this retrieval request.",
        strategy="simple",
        k=999,
        memory_requester=_memory_fixture,
        model_requester=_model_fixture,
        write_receipt=False,
    )
    checks.append({"check": "top-k is bounded", "ok": bounded.get("top_k") == rag.MAX_K})

    undersized_rejected = False
    unknown_rejected = False
    try:
        _run("simple", "x")
    except ValueError:
        undersized_rejected = True
    try:
        _run("not_a_route", "This query should be rejected.")
    except ValueError:
        unknown_rejected = True
    checks.append(
        {
            "check": "undersized queries and unknown routes fail closed",
            "ok": undersized_rejected and unknown_rejected,
        }
    )

    failed = [item for item in checks if item.get("ok") is not True]
    payload = {
        "schema": "ENGEL_RAG_RUNTIME_VERIFIER_V2",
        "ok": not failed,
        "checks_total": len(checks),
        "checks_passed": len(checks) - len(failed),
        "checks_failed": len(failed),
        "checks": checks,
        "routes_exercised": list(results),
        "memory_calls": len(MEMORY_CALLS),
        "local_model_calls": len(MODEL_CALLS),
        "provider_called": False,
        "trusted_memory_write": False,
        "index_mutation": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
