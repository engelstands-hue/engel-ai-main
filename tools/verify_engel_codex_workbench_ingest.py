#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import tempfile

from engel_codex_workbench_ingest import build_context_pack, status_snapshot
import engel_main_server_chat_http_service as chat_service


ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="engel-context-pack-") as temp:
        root = Path(temp) / "run" / "self_update" / "context_packs"
        unread_source = Path(temp) / "must_not_be_read.txt"
        unread_source.write_text("SOURCE_PATH_CONTENT_MUST_NOT_APPEAR", encoding="utf-8")
        attachments = [
            {"id": "a1", "name": "diagram.png", "kind": "image", "mime_type": "image/png", "source_path": str(unread_source), "sha256": "a" * 64},
            {"id": "a2", "name": "design.pdf", "kind": "file", "mime_type": "application/pdf", "text_preview": "PDF preview for the design."},
            {"id": "a3", "name": "workspace", "kind": "folder", "mime_type": "application/x-directory", "text_preview": "src/main.py\ntests/test_main.py"},
            {"id": "a4", "name": "screen.png", "kind": "image", "mime_type": "image/png", "source": "ROG screenshot clipboard"},
            {"id": "a5", "name": "notes.txt", "kind": "file", "mime_type": "text/plain", "text_preview": "General file context."},
        ]
        context_items = [
            {"kind": "pasted_text", "name": "clipboard.txt", "text": "Pasted input " * 80, "source": "ROG clipboard"},
            {"kind": "terminal_output", "name": "terminal.log", "text": "build passed\n" * 40, "source": "ROG terminal"},
            {"kind": "receipt", "name": "proof.json", "text": '{"ok": true, "api_key": "sk-secret123456789"}', "source": "Engel receipt"},
        ]
        result = build_context_pack(
            prompt="Review these sources",
            attachments=attachments,
            context_items=context_items,
            request={"id": "verify-1", "conversation_id": "verify-room"},
            source="verifier",
            root=root,
            chunk_chars=80,
            chunk_overlap=10,
        )
        require(result.get("created") is True, "context pack was not created", failures)
        require(result.get("item_count") == 8, "context pack item count is wrong", failures)
        require(int(result.get("chunk_count") or 0) > 8, "large context was not chunked", failures)
        require(result.get("source_lineage_retained") is True, "source lineage flag is missing", failures)
        require(result.get("training_candidate") is False, "context was auto-promoted to training", failures)
        require(result.get("trusted_memory_write") is False, "context claimed trusted-memory write", failures)
        require(result.get("external_array_used") is False, "context pack used an external array", failures)
        manifest_path = Path(str(result.get("manifest_path") or ""))
        require(manifest_path.is_file(), "context manifest is missing", failures)
        serialized = manifest_path.read_text(encoding="utf-8") if manifest_path.is_file() else ""
        require("SOURCE_PATH_CONTENT_MUST_NOT_APPEAR" not in serialized, "ingest opened an arbitrary source path", failures)
        require("sk-secret" not in serialized, "context pack leaked a secret", failures)
        manifest = json.loads(serialized) if serialized else {}
        kinds = {str(item.get("kind")) for item in manifest.get("items", []) if isinstance(item, dict)}
        for kind in ("file", "folder", "image", "pdf", "screenshot", "pasted_text", "terminal_output", "receipt"):
            require(kind in kinds, f"context pack omitted kind: {kind}", failures)
        require(all(item.get("lineage") for item in manifest.get("items", [])), "an item lost lineage", failures)
        status = status_snapshot(root)
        require(status.get("ok") is True and status.get("pack_count") == 1, "status did not find the pack", failures)

    source = (ROOT / "tools" / "engel_main_server_chat_http_service.py").read_text(encoding="utf-8")
    worker = (ROOT / "tools" / "engel_main_local_model_worker.py").read_text(encoding="utf-8")
    flutter = (ROOT / "engel_flutter_main" / "lib" / "main.dart").read_text(encoding="utf-8")
    require("build_context_pack(" in source, "chat service does not invoke context ingest", failures)
    require("/context-packs/status" in source, "context status endpoint is missing", failures)
    require("codex-workbench-context-ingest" in source, "runtime registry capability is missing", failures)
    require('"context_items"' in worker, "long-lived worker does not forward context items", failures)
    require("'context_items'" in flutter, "Flutter chat does not submit context items", failures)
    require("_pickChatFolder" in flutter, "Flutter chat has no folder context picker", failures)
    context_request = {
        "prefer_fast_local_chat": True,
        "context_pack": {"created": True, "item_count": 2},
    }
    require(
        chat_service._context_pack_requires_model(context_request),
        "context-bearing request does not require model inference",
        failures,
    )
    require(
        not chat_service._request_prefers_quick_local_chat("What should I check first?", context_request),
        "context-bearing request can still enter quick local routing",
        failures,
    )
    require(
        not chat_service._prompt_allows_default_fast_local_chat("Please help with this", context_request),
        "context-bearing request can still enter default fast routing",
        failures,
    )
    repaired = chat_service._apply_global_chat_safety(
        "Which file should I check first?",
        {"assistant_reply": "Check src/main.py first, Engel."},
        "context-ingest-verifier",
    )
    require(
        repaired.get("assistant_reply") == "Check src/main.py first.",
        "operator-address identity drift was not repaired",
        failures,
    )
    require(
        repaired.get("chat_safety_operator_address_repaired") is True,
        "operator-address repair was not recorded",
        failures,
    )

    result = {
        "schema": "ENGEL_CODEX_WORKBENCH_CONTEXT_INGEST_VERIFIER_V1",
        "ok": not failures,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "context_types_verified": ["file", "folder", "image", "pdf", "screenshot", "pasted_text", "terminal_output", "receipt"],
        "provider_calls_made": False,
        "storage_mutation": False,
        "external_array_used": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
