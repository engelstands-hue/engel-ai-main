#!/usr/bin/env python3
"""Deterministic verifier for the twelve operational AI-system contracts."""

from __future__ import annotations

from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import engel_ai_systems_runtime as systems
import engel_build_preference_dataset as preference
import engel_main_server_chat_http_service as service


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _rag_fixture() -> dict:
    return {
        "ok": True,
        "production_route_count": 10,
        "indexed_items": 2475,
        "local_model_ready": True,
        "local_model_id": "engel-local-test.gguf",
    }


def main() -> int:
    checks: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="engel_ai_systems_") as temporary:
        root = Path(temporary)
        prompt = "Explain how Engel verifies a completed local model training run."
        chosen = (
            "Engel verifies the dataset receipt, held-out evaluation, adapter hash, and "
            "promotion receipt before reporting that a model changed. The candidate stays "
            "separate from production until the operator approves promotion."
        )
        rejected = (
            "The model is trained automatically and is already live. No receipt or held-out "
            "evaluation is needed because the training command finished successfully."
        )
        _append_jsonl(
            root / "memory" / "persistent_chat" / "ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl",
            [
                {
                    "ok": True,
                    "prompt": prompt,
                    "assistant_reply": chosen,
                    "updated_at_utc": "2026-08-02T00:01:00Z",
                    "receipt_path": "/opt/engel/reports/chosen.json",
                    "selected_provider": "local",
                }
            ],
        )
        _append_jsonl(
            root / "memory" / "persistent_chat" / "ENGEL_CHAT_REJECTED_SAMPLES.jsonl",
            [
                {
                    "schema": "engel_chat_rejected_sample_v1",
                    "active": True,
                    "sample_key": "sample-1",
                    "prompt": prompt,
                    "assistant_reply": rejected,
                    "reason": "owner rejected unsupported completion claim",
                    "receipt_path": "/opt/engel/reports/rejected.json",
                }
            ],
        )
        preference_result = preference.build_dataset(root)
        checks.append(
            {
                "check": "owner feedback becomes an exact-prompt DPO-compatible pair dataset",
                "ok": preference_result.get("ok") is True
                and preference_result.get("matched_pair_count") == 1
                and preference_result.get("weight_training_started") is False
                and len(str(preference_result.get("train_sha256") or "")) == 64,
            }
        )

        dataset_path = root / "reports" / "llm_training" / "ENGEL_TRAINING_DATASET_LATEST.json"
        _write_json(
            dataset_path,
            {
                "raw_counts": {"teacher": 16, "prompt_training": 22},
                "train": 1508,
                "val": 35,
            },
        )
        _write_json(
            root / "llm_training" / "datasets" / "latest" / "dataset_manifest.json",
            {
                "system_prompt": (
                    "Do not reveal scratch work. Never output a Thinking Process section."
                )
            },
        )
        _write_json(
            root / "reports" / "llm_training" / "ENGEL_WEEKLY_RETRAIN_LATEST.json",
            {
                "phases": [
                    {
                        "phase": "train",
                        "val_loss_before": 2.7,
                        "val_loss": 2.3,
                        "val_loss_delta": -0.4,
                    },
                    {
                        "phase": "COMPLETE",
                        "at_s": 4000,
                        "adapter": "/opt/engel/candidate/adapter",
                    },
                ]
            },
        )
        _write_json(
            root / "reports" / "llm_training" / "ENGEL_CT246_LORA_PROOF_LATEST.json",
            {
                "ok": True,
                "new_adapter_trained": True,
                "adapter_files": [
                    {"relative_path": "tokenizer.json", "sha256": "A" * 64}
                ],
            },
        )
        _write_json(
            root / "runtime" / "engel_standalone_chat_llm" / "trained_lora_adapter_manifest.json",
            {
                "runtime_loaded_by_current_chat_endpoint": True,
                "serving_base_gguf_model_sha256": "B" * 64,
                "adapter_model_gguf": {"sha256": "C" * 64},
            },
        )
        _write_json(
            root / "reports" / "rag_runtime" / "latest.json",
            {"ok": True, "result_count": 4},
        )
        for name in ("engel_build_lane.py", "engel_workspace_scaffold.py"):
            path = root / "tools" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# fixture\n", encoding="utf-8")

        status = systems.status_snapshot(root, _rag_fixture)
        checks.append(
            {
                "check": "all twelve cards resolve to evidence-backed operational systems",
                "ok": status.get("ok") is True
                and status.get("ready_count") == 12
                and len(status.get("systems") or []) == 12,
            }
        )
        by_id = {item["id"]: item for item in status.get("systems") or []}
        checks.append(
            {
                "check": "only real optimizer lanes claim weight changes",
                "ok": status.get("weight_training_system_count") == 3
                and {key for key, item in by_id.items() if item.get("changes_weights")}
                == {"05", "06", "07"}
                and by_id["08"].get("system_type") == "retrieval_runtime"
                and by_id["09"].get("system_type") == "reasoning_safety_runtime",
            }
        )
        checks.append(
            {
                "check": "status proof cannot train, promote, call providers, or store hidden reasoning",
                "ok": status.get("boundaries")
                == {
                    "status_probe_is_read_only": True,
                    "weight_training_started": False,
                    "model_promoted": False,
                    "provider_called": False,
                    "trusted_memory_write": False,
                    "hidden_reasoning_stored": False,
                },
            }
        )

        service.ai_systems_status_snapshot = lambda: status
        service._AI_SYSTEMS_IMPORT_ERROR = ""
        service._SNAPSHOT_CACHE.clear()
        server = ThreadingHTTPServer(("127.0.0.1", 0), service.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_address[1]}/ai-systems/status",
                timeout=5,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
            checks.append(
                {
                    "check": "HTTP status endpoint returns the twelve-system proof contract",
                    "ok": response.status == 200
                    and payload.get("schema") == "ENGEL_AI_SYSTEMS_STATUS_V1"
                    and payload.get("ready_count") == 12,
                }
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    deploy_source = (ROOT / "scripts" / "Start-EngelMainServerChatService.ps1").read_text(
        encoding="utf-8"
    )
    checks.append(
        {
            "check": "deployment includes the systems proof and preference dataset modules",
            "ok": '"tools\\engel_ai_systems_runtime.py"' in deploy_source
            and '"tools\\engel_build_preference_dataset.py"' in deploy_source,
        }
    )

    failed = [item for item in checks if item.get("ok") is not True]
    payload = {
        "schema": "ENGEL_AI_SYSTEMS_RUNTIME_VERIFIER_V1",
        "ok": not failed,
        "checks_total": len(checks),
        "checks_passed": len(checks) - len(failed),
        "checks_failed": len(failed),
        "checks": checks,
        "provider_called": False,
        "trusted_memory_write": False,
        "weight_training_started": False,
        "model_promoted": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
