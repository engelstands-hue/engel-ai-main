#!/usr/bin/env python3
"""Dispatch one CT246 transport order to paired Sub-Engel over direct HTTP."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TRANSPORT_ROOT = Path(
    os.environ.get(
        "ENGEL_SUB_ENGEL_TRANSPORT_ROOT",
        str(ROOT / "run" / "sub_engel_transport"),
    )
)
WORK_ORDERS = TRANSPORT_ROOT / "SUB_ENGEL_WORK_ORDERS"
SENT_WORK = TRANSPORT_ROOT / "SUB_ENGEL_SENT_WORK"
RECEIPTS = TRANSPORT_ROOT / "receipts"
BUS = TRANSPORT_ROOT / "engel_shared_room_bus.jsonl"
DEFAULT_NODE_ID = os.environ.get("ENGEL_WINDOWS_SUB_NODE_ID", "DESKTOP-UE5A6GG")
DEFAULT_NODE_URL = os.environ.get("ENGEL_WINDOWS_SUB_NODE_URL", "http://198.51.100.227:8776")
DIRECT_ACTION = "direct_work.execute"
SENSITIVE_PARTS = ("token", "secret", "password", "credential", "api_key")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON file is not an object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, sort_keys=True) + "\n")


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("[redacted]" if any(part in key.lower() for part in SENSITIVE_PARTS) else redact(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def safe_name(value: Any) -> str:
    raw = str(value or "").strip()
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._-")
    if not safe:
        raise ValueError("work order id has no safe filename characters")
    return safe[:160]


def under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def assert_server_transport() -> None:
    text = str(TRANSPORT_ROOT).replace("\\", "/").lower()
    forbidden = ("google drive", "my drive", "/mnt/engel-vault", "engel-vault-main")
    if any(item in text for item in forbidden):
        raise ValueError(f"forbidden transport root: {TRANSPORT_ROOT}")
    if os.name != "nt" and str(TRANSPORT_ROOT) != "/opt/engel/run/sub_engel_transport":
        raise ValueError(f"CT246 transport must be /opt/engel/run/sub_engel_transport, got {TRANSPORT_ROOT}")


def decode_action_stdout(remote: dict[str, Any]) -> dict[str, Any]:
    result = remote.get("result") if isinstance(remote.get("result"), dict) else {}
    stdout = str(result.get("stdout") or "").strip()
    if not stdout:
        return {}
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def remote_proof(remote: dict[str, Any]) -> dict[str, Any]:
    result = remote.get("result") if isinstance(remote.get("result"), dict) else {}
    return {
        "ok": remote.get("ok") is True,
        "http_status": remote.get("http_status"),
        "error": str(remote.get("error") or "")[:1000],
        "result": {
            "action": result.get("action"),
            "return_code": result.get("return_code"),
            "timeout_seconds": result.get("timeout_seconds"),
        },
    }


def order_hash(order: dict[str, Any]) -> str:
    canonical = json.dumps(order, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def dispatch(
    order_path: Path,
    run_action_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    assert_server_transport()
    resolved_order = order_path.resolve()
    if not under(resolved_order, WORK_ORDERS):
        raise ValueError(f"order must be inside {WORK_ORDERS}: {order_path}")
    order = read_json(resolved_order)
    order_id = str(order.get("id") or order.get("order_id") or "").strip()
    if not order_id:
        raise ValueError("work order is missing id/order_id")
    if not str(order.get("order_text") or "").strip():
        raise ValueError("work order is missing order_text")

    selected = order.get("selected_node") if isinstance(order.get("selected_node"), dict) else {}
    node_id = str(
        selected.get("node_id")
        or selected.get("hostname")
        or selected.get("computer_name")
        or DEFAULT_NODE_ID
    ).strip()
    node_url = str(selected.get("url") or selected.get("node_url") or DEFAULT_NODE_URL).strip()
    if node_id.upper() != "DESKTOP-UE5A6GG":
        raise ValueError(f"refusing unapproved Sub-Engel node: {node_id}")
    if node_url.rstrip("/") != "http://198.51.100.227:8776":
        raise ValueError(f"refusing unapproved Sub-Engel URL: {node_url}")

    if run_action_fn is None:
        from engel_sub_node_remote_control import run_action as run_action_fn

    prepared_order = dict(order)
    prepared_order["schema"] = "engel_sub_engel_direct_work_order_v1"
    prepared_order["source"] = "CT246 Engel AI Main authenticated direct HTTP"
    prepared_order["transport"] = "ct246_authenticated_direct_http"
    prepared_order["proof_required"] = True
    prepared_order["selected_node"] = {
        "node_id": node_id,
        "hostname": node_id,
        "url": node_url,
    }
    dispatched_at = utc_stamp()
    remote = run_action_fn(
        DIRECT_ACTION,
        url=node_url,
        node_kind="windows",
        node_id=node_id,
        payload={
            "work_order": prepared_order,
            "client_timeout_seconds": 600,
        },
    )
    direct = decode_action_stdout(remote)
    result_wrapper = remote.get("result") if isinstance(remote.get("result"), dict) else {}
    remote_ok = (
        remote.get("ok") is True
        and int(result_wrapper.get("return_code") or 0) == 0
        and direct.get("ok") is True
    )
    safe_id = safe_name(order_id)
    server_receipt = {
        "schema": "engel_ct246_sub_engel_direct_dispatch_receipt_v1",
        "ok": remote_ok,
        "event": "ct246_sub_engel_direct_work_returned" if remote_ok else "ct246_sub_engel_direct_work_failed",
        "container": "CT246",
        "server_hostname": "engel-ai-main",
        "proxmox_node": "engel-spine-01",
        "transport": "ct246_authenticated_direct_http",
        "transport_root": str(TRANSPORT_ROOT),
        "google_drive_used": False,
        "power_vault_used": False,
        "action": DIRECT_ACTION,
        "order_id": order_id,
        "order_sha256": order_hash(prepared_order),
        "order_file": str(resolved_order),
        "node_id": node_id,
        "node_url": node_url,
        "dispatched_at_utc": dispatched_at,
        "completed_at_utc": utc_stamp(),
        "worker_engine": direct.get("worker_engine", ""),
        "worker_output": str(direct.get("worker_output") or "")[:6000],
        "local_llm_attempted": direct.get("local_llm_attempted") is True,
        "persistent_memory": redact(direct.get("persistent_memory", {})),
        "training_processes_unchanged": direct.get("training_processes_unchanged"),
        "model_output_trusted": False,
        "auto_apply": False,
        "requires_review_before_apply": True,
        "sub_receipt": redact(direct),
        "remote_result": remote_proof(remote),
    }
    output_path = SENT_WORK / f"{node_id}__{safe_id}.done.json"
    failure_path = RECEIPTS / f"{safe_id}.dispatch.json"
    write_json(failure_path, {**server_receipt, "server_receipt_file": str(failure_path)})
    if remote_ok:
        write_json(output_path, {**server_receipt, "server_receipt_file": str(failure_path)})
    append_jsonl(BUS, {
        "timestamp_utc": utc_stamp(),
        "sender": "Engel AI Main CT246",
        "channel": "SUB_ENGEL_RESULT" if remote_ok else "SUB_ENGEL_ERROR",
        "message": (
            f"Sub-Engel returned direct work order {order_id}"
            if remote_ok
            else f"Sub-Engel direct work order failed {order_id}"
        ),
        "order_id": order_id,
        "node_id": node_id,
        "path": str(output_path if remote_ok else failure_path),
        "transport": "ct246_authenticated_direct_http",
    })
    server_receipt["server_receipt_file"] = str(failure_path)
    server_receipt["returned_file"] = str(output_path) if remote_ok else ""
    return server_receipt


def resolve_order(args: argparse.Namespace) -> Path:
    if args.order_file:
        return Path(args.order_file)
    if args.order_id:
        return WORK_ORDERS / f"{safe_name(args.order_id)}.json"
    candidates = sorted(WORK_ORDERS.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not candidates:
        raise ValueError(f"no work orders found in {WORK_ORDERS}")
    return candidates[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--order-file", default="")
    group.add_argument("--order-id", default="")
    group.add_argument("--latest", action="store_true")
    return parser.parse_args()


def main() -> int:
    try:
        receipt = dispatch(resolve_order(parse_args()))
    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "error": str(exc),
            "container": "CT246",
            "transport": "ct246_authenticated_direct_http",
            "google_drive_used": False,
        }, indent=2, sort_keys=True))
        return 1
    print(json.dumps(redact(receipt), indent=2, sort_keys=True))
    return 0 if receipt.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
