from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path("F:/ENGEL_APP_MEMORY/runpod/engel_runpod_config.json")
RECEIPT_DIR = Path("F:/ENGEL_APP_MEMORY/runpod/receipts")
NEW_ENDPOINT_ID = "n9kjqfk6z6ncz8"
OLD_ENDPOINT_ID = "adhznbnyks05el"
MODEL_ID = "mistralai/Mistral-7B-Instruct-v0.3"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def latest_receipt(prefix: str) -> Path | None:
    paths = sorted(RECEIPT_DIR.glob(prefix + "*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return paths[0] if paths else None


def add(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = "") -> None:
    item: dict[str, Any] = {"name": name, "ok": bool(ok)}
    if detail != "":
        item["detail"] = detail
    checks.append(item)


def main() -> int:
    checks: list[dict[str, Any]] = []
    add(checks, "config_exists", CONFIG_PATH.exists(), str(CONFIG_PATH))
    config = read_json(CONFIG_PATH) if CONFIG_PATH.exists() else {}
    add(checks, "config_endpoint_new", config.get("endpoint_id") == NEW_ENDPOINT_ID, config.get("endpoint_id"))
    add(checks, "config_model_mistral", config.get("openai_model_id") == MODEL_ID, config.get("openai_model_id"))
    add(checks, "config_base_url_new", NEW_ENDPOINT_ID in str(config.get("openai_base_url") or ""), config.get("openai_base_url"))

    create_path = latest_receipt("RUNPOD_CREATE_ENGEL_MISTRAL_TEMPLATE_ENDPOINT_")
    add(checks, "create_receipt_exists", create_path is not None, str(create_path) if create_path else "")
    if create_path:
        create = read_json(create_path)
        add(checks, "create_receipt_ok", create.get("ok") is True, create.get("error"))
        add(checks, "create_new_endpoint", create.get("new_endpoint_id") == NEW_ENDPOINT_ID, create.get("new_endpoint_id"))
        add(checks, "create_template_model", create.get("template_model") == MODEL_ID, create.get("template_model"))

    stretch_path = latest_receipt("RUNPOD_ENGEL_STRETCH_")
    add(checks, "stretch_receipt_exists", stretch_path is not None, str(stretch_path) if stretch_path else "")
    if stretch_path:
        stretch = read_json(stretch_path)
        tasks = stretch.get("tasks") if isinstance(stretch.get("tasks"), list) else []
        model_ids = ((stretch.get("models_probe") or {}).get("model_ids") or [])
        add(checks, "stretch_ok", stretch.get("ok") is True, stretch.get("receipt_path"))
        add(checks, "stretch_new_endpoint", NEW_ENDPOINT_ID in str(stretch.get("base_url") or ""), stretch.get("base_url"))
        add(checks, "stretch_model_mistral", stretch.get("model") == MODEL_ID, stretch.get("model"))
        add(checks, "stretch_models_probe_mistral_only", model_ids == [MODEL_ID], model_ids)
        add(checks, "stretch_tasks_all_passed", len(tasks) >= 6 and all(task.get("ok") is True for task in tasks), {"task_count": len(tasks), "passed": sum(1 for task in tasks if task.get("ok") is True)})
        add(checks, "stretch_no_secret_visible", stretch.get("api_key_value_visible") is False)
        add(checks, "stretch_off_c", stretch.get("c_drive_used") is False)

    old_unwarm_path = latest_receipt("RUNPOD_OLD_ENDPOINT_UNWARM_")
    add(checks, "old_endpoint_unwarmed_receipt_exists", old_unwarm_path is not None, str(old_unwarm_path) if old_unwarm_path else "")
    if old_unwarm_path:
        old_unwarm = read_json(old_unwarm_path)
        add(checks, "old_endpoint_unwarmed", old_unwarm.get("endpoint_id") == OLD_ENDPOINT_ID and old_unwarm.get("workersMin") == 0, old_unwarm.get("workersMin"))

    active_unwarm_path = latest_receipt("RUNPOD_ACTIVE_ENDPOINT_UNWARM_")
    add(checks, "active_endpoint_unwarmed_receipt_exists", active_unwarm_path is not None, str(active_unwarm_path) if active_unwarm_path else "")
    if active_unwarm_path:
        active_unwarm = read_json(active_unwarm_path)
        add(checks, "active_endpoint_unwarmed", active_unwarm.get("endpoint_id") == NEW_ENDPOINT_ID and active_unwarm.get("workersMin") == 0, active_unwarm.get("workersMin"))

    result = {
        "ok": all(check["ok"] for check in checks),
        "schema": "engel_runpod_mistral_connection_verifier_v1",
        "checks": checks,
        "config_path": str(CONFIG_PATH),
        "receipt_dir": str(RECEIPT_DIR),
        "endpoint_id": NEW_ENDPOINT_ID,
        "model": MODEL_ID,
        "latest_stretch_receipt": str(stretch_path) if stretch_path else "",
    }
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
