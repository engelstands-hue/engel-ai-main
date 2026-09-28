from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
except Exception:
    pass


APP_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ZIP = APP_ROOT / "runtime" / "engel_lora_training_package" / "engel_standalone_lora_training_package.zip"
LOCAL_ARTIFACT_ROOT = APP_ROOT / "runtime" / "engel_lora_training_artifacts"
RUNPOD_MEMORY_ROOT = Path(os.environ.get("ENGEL_RUNPOD_MEMORY_ROOT", str(APP_ROOT / "runtime" / "runpod")))
RECEIPT_ROOT = RUNPOD_MEMORY_ROOT / "receipts"
EXTERNAL_ARTIFACT_ROOT = RUNPOD_MEMORY_ROOT / "standalone_llm_training" / "artifacts"
RUNPOD_KEY_PATH = Path(os.environ.get("ENGEL_RUNPOD_KEY_PATH", str(RUNPOD_MEMORY_ROOT / "secrets" / "runpod_api_key.txt")))
SSH_KEY_PATH = Path("D:/pod/id_ed25519")
KNOWN_HOSTS_PATH = RUNPOD_MEMORY_ROOT / "known_hosts"
RUNPOD_API_BASE = "https://rest.runpod.io/v1"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_receipt(prefix: str, payload: dict[str, Any]) -> Path:
    path = RECEIPT_ROOT / f"{prefix}_{utc_stamp()}.json"
    write_json(path, payload)
    return path


def load_api_key() -> str:
    key = os.environ.get("RUNPOD_API_KEY", "").strip()
    if key:
        return key
    if not RUNPOD_KEY_PATH.exists():
        raise FileNotFoundError(f"RunPod API key not found: {RUNPOD_KEY_PATH}")
    return RUNPOD_KEY_PATH.read_text(encoding="utf-8").strip()


def runpod_request(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{RUNPOD_API_BASE}{path}",
        method=method,
        data=data,
        headers={
            "Authorization": f"Bearer {load_api_key()}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"RunPod HTTP {exc.code}: {raw}") from exc


def redact_pod(pod: Any) -> Any:
    if isinstance(pod, dict):
        redacted: dict[str, Any] = {}
        for key, value in pod.items():
            lowered = key.lower()
            if "key" in lowered or "token" in lowered or "secret" in lowered:
                redacted[key] = "[REDACTED]"
            elif key == "env" and isinstance(value, dict):
                redacted[key] = {env_key: "[REDACTED]" for env_key in value}
            else:
                redacted[key] = redact_pod(value)
        return redacted
    if isinstance(pod, list):
        return [redact_pod(item) for item in pod]
    return pod


def status_pod(pod_id: str) -> dict[str, Any]:
    return runpod_request("GET", f"/pods/{pod_id}?includeMachine=true")


def is_ipv4(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", value) is not None


def scan_for_ssh(obj: Any, inherited_ip: str | None = None) -> list[tuple[str | None, int]]:
    found: list[tuple[str | None, int]] = []
    if isinstance(obj, dict):
        ip = inherited_ip
        for key in ("publicIp", "publicIP", "ip"):
            if is_ipv4(obj.get(key)):
                ip = obj[key]
                break

        private_port = obj.get("privatePort") or obj.get("containerPort") or obj.get("port")
        public_port = obj.get("publicPort") or obj.get("hostPort") or obj.get("externalPort")
        if str(private_port) == "22" and public_port:
            try:
                found.append((ip, int(public_port)))
            except (TypeError, ValueError):
                pass

        mappings = obj.get("portMappings")
        if isinstance(mappings, dict):
            for key, value in mappings.items():
                if str(key) == "22" or str(key).endswith(":22"):
                    if isinstance(value, dict):
                        port_value = value.get("publicPort") or value.get("hostPort") or value.get("externalPort") or value.get("port")
                    else:
                        port_value = value
                    try:
                        found.append((ip, int(port_value)))
                    except (TypeError, ValueError):
                        pass

        for value in obj.values():
            found.extend(scan_for_ssh(value, ip))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(scan_for_ssh(item, inherited_ip))
    return found


def infer_ssh_target(pod: dict[str, Any]) -> tuple[str | None, int | None]:
    top_ip = pod.get("publicIp") if is_ipv4(pod.get("publicIp")) else None
    for ip, port in scan_for_ssh(pod, top_ip):
        if ip and port:
            return ip, port
    return top_ip, None


def wait_for_ssh_target(pod_id: str, attempts: int, delay_seconds: int) -> tuple[str, int, dict[str, Any], Path]:
    last: dict[str, Any] = {}
    for attempt in range(1, attempts + 1):
        pod = status_pod(pod_id)
        ip, port = infer_ssh_target(pod)
        last = {
            "ok": bool(ip and port),
            "schema": "engel_runpod_lora_pod_ready_v1",
            "checked_at_utc": iso_now(),
            "attempt": attempt,
            "pod_id": pod_id,
            "public_ip_present": bool(ip),
            "ssh_port_present": bool(port),
            "public_ip": ip or "",
            "ssh_port": port or "",
            "desired_status": pod.get("desiredStatus", ""),
            "runtime_status": pod.get("runtimeStatus", ""),
            "pod": redact_pod(pod),
        }
        print(json.dumps({k: last[k] for k in ("attempt", "ok", "public_ip_present", "ssh_port_present", "desired_status", "runtime_status")}, sort_keys=True), flush=True)
        if ip and port:
            receipt = write_receipt("RUNPOD_ENGEL_LORA_TRAINING_POD_READY", last)
            return ip, port, last, receipt
        time.sleep(delay_seconds)
    receipt = write_receipt("RUNPOD_ENGEL_LORA_TRAINING_POD_READY", last)
    raise RuntimeError(f"Pod did not expose SSH target after {attempts} attempts. receipt={receipt}")


def ssh_base(ip: str, port: int) -> list[str]:
    KNOWN_HOSTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    connect_timeout = os.environ.get("ENGEL_RUNPOD_SSH_CONNECT_TIMEOUT", "8").strip() or "8"
    return [
        "ssh",
        "-i",
        str(SSH_KEY_PATH),
        "-p",
        str(port),
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        f"UserKnownHostsFile={KNOWN_HOSTS_PATH}",
        "-o",
        f"ConnectTimeout={connect_timeout}",
        f"root@{ip}",
    ]


def scp_base(port: int) -> list[str]:
    KNOWN_HOSTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    connect_timeout = os.environ.get("ENGEL_RUNPOD_SSH_CONNECT_TIMEOUT", "8").strip() or "8"
    return [
        "scp",
        "-i",
        str(SSH_KEY_PATH),
        "-P",
        str(port),
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        f"UserKnownHostsFile={KNOWN_HOSTS_PATH}",
        "-o",
        f"ConnectTimeout={connect_timeout}",
    ]


def run_command(args: list[str], *, receipt_prefix: str, cwd: Path | None = None, timeout: int | None = None) -> tuple[subprocess.CompletedProcess[str], Path]:
    started = time.perf_counter()
    display = [arg if "Bearer " not in arg else "[REDACTED]" for arg in args]
    print(f"RUN {' '.join(display)}", flush=True)
    result = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    output = result.stdout or ""
    receipt = {
        "ok": result.returncode == 0,
        "schema": "engel_runpod_lora_command_receipt_v1",
        "finished_at_utc": iso_now(),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "returncode": result.returncode,
        "command": display,
        "output_tail": output[-12000:],
    }
    path = write_receipt(receipt_prefix, receipt)
    print(output[-12000:], flush=True)
    print(f"receipt={path}", flush=True)
    return result, path


def require_inputs() -> None:
    missing = []
    if not PACKAGE_ZIP.exists():
        missing.append(str(PACKAGE_ZIP))
    if not SSH_KEY_PATH.exists():
        missing.append(str(SSH_KEY_PATH))
    if missing:
        raise FileNotFoundError("Missing required file(s): " + ", ".join(missing))


def ssh_test(ip: str, port: int) -> Path:
    command = "echo ENGEL_SSH_OK && hostname && nvidia-smi --query-gpu=name,memory.total --format=csv,noheader"
    result, receipt = run_command(ssh_base(ip, port) + [command], receipt_prefix="RUNPOD_ENGEL_LORA_TRAINING_SSH_TEST", timeout=90)
    if result.returncode != 0:
        raise RuntimeError(f"SSH test failed. receipt={receipt}")
    return receipt


def upload_package(ip: str, port: int) -> Path:
    package_hash = sha256_file(PACKAGE_ZIP)
    result, receipt = run_command(
        scp_base(port) + [str(PACKAGE_ZIP), f"root@{ip}:/workspace/engel_standalone_lora_training_package.zip"],
        receipt_prefix="RUNPOD_ENGEL_LORA_TRAINING_UPLOAD",
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Package upload failed. receipt={receipt}")
    verify_cmd = (
        "python3 - <<'PY'\n"
        "import hashlib, pathlib\n"
        "p=pathlib.Path('/workspace/engel_standalone_lora_training_package.zip')\n"
        "h=hashlib.sha256(p.read_bytes()).hexdigest().upper()\n"
        f"print('REMOTE_ZIP_SHA256='+h)\nprint('EXPECTED_ZIP_SHA256={package_hash}')\n"
        "raise SystemExit(0 if h == '" + package_hash + "' else 7)\n"
        "PY"
    )
    result, verify_receipt = run_command(ssh_base(ip, port) + [verify_cmd], receipt_prefix="RUNPOD_ENGEL_LORA_TRAINING_UPLOAD_VERIFY", timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Remote package hash verification failed. receipt={verify_receipt}")
    return verify_receipt


def remote_training_command(max_steps: int, max_length: int, base_model: str, learning_rate: float, target_seconds: int, logging_steps: int) -> str:
    return f"""set -e
cd /workspace
rm -rf engel_lora_train engel_standalone_lora_adapter
mkdir -p engel_lora_train engel_standalone_lora_adapter
python3 - <<'PY'
import pathlib, zipfile
zip_path = pathlib.Path('/workspace/engel_standalone_lora_training_package.zip')
target = pathlib.Path('/workspace/engel_lora_train')
with zipfile.ZipFile(zip_path) as archive:
    archive.extractall(target)
print('ENGEL_PACKAGE_EXTRACTED', target)
PY
cd /workspace/engel_lora_train
# Keep the pod's preinstalled torch (RunPod images ship a CUDA-matched torch;
# the package's cu118 pin breaks Blackwell + violates PEP-668). Install only
# the pure-python training deps into the system env.
python3 -m pip install --break-system-packages --upgrade pip
python3 -m pip install --break-system-packages huggingface_hub==0.24.7 accelerate==0.34.2 datasets==2.20.0 peft==0.12.0 safetensors==0.4.5 transformers==4.44.2 sentencepiece==0.2.0 protobuf==4.25.3
BASE_MODEL='{base_model}' python3 train_engel_lora.py --base-model '{base_model}' --output-dir /workspace/engel_standalone_lora_adapter --max-steps {max_steps} --max-length {max_length} --lr {learning_rate} --target-seconds {target_seconds} --logging-steps {logging_steps} --progress-path /workspace/engel_standalone_lora_adapter/ENGEL_LORA_PROGRESS.json
python3 - <<'PY'
import hashlib, json, pathlib
out = pathlib.Path('/workspace/engel_standalone_lora_adapter')
files = []
for path in sorted(out.rglob('*')):
    if path.is_file():
        digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        files.append({{'path': str(path.relative_to(out)), 'bytes': path.stat().st_size, 'sha256': digest}})
required = ['adapter_config.json', 'adapter_model.safetensors', 'ENGEL_LORA_TRAINING_RECEIPT.json']
summary = {{
    'ok': all((out / item).exists() for item in required),
    'schema': 'engel_lora_remote_artifact_verify_v1',
    'verified_at_utc': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
    'required': required,
    'files': files,
}}
(out / 'ENGEL_LORA_ARTIFACT_VERIFY.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\\n', encoding='utf-8')
print(json.dumps(summary, indent=2, sort_keys=True))
raise SystemExit(0 if summary['ok'] else 9)
PY
"""


def train_remote(ip: str, port: int, max_steps: int, max_length: int, base_model: str, learning_rate: float, target_seconds: int, logging_steps: int) -> Path:
    result, receipt = run_command(
        ssh_base(ip, port) + [remote_training_command(max_steps=max_steps, max_length=max_length, base_model=base_model, learning_rate=learning_rate, target_seconds=target_seconds, logging_steps=logging_steps)],
        receipt_prefix="RUNPOD_ENGEL_LORA_TRAINING_REMOTE_RUN",
        timeout=max(7200, int(target_seconds or 0) + 3600),
    )
    if result.returncode != 0:
        raise RuntimeError(f"Remote training failed. receipt={receipt}")
    return receipt


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def download_artifacts(ip: str, port: int, pod_id: str) -> tuple[Path, Path, Path]:
    artifact_name = f"engel_standalone_lora_adapter_{pod_id}_{utc_stamp()}"
    local_target = LOCAL_ARTIFACT_ROOT / artifact_name
    external_target = EXTERNAL_ARTIFACT_ROOT / artifact_name
    local_target.parent.mkdir(parents=True, exist_ok=True)
    result, receipt = run_command(
        scp_base(port) + ["-r", f"root@{ip}:/workspace/engel_standalone_lora_adapter", str(local_target)],
        receipt_prefix="RUNPOD_ENGEL_LORA_TRAINING_DOWNLOAD",
        timeout=1200,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Artifact download failed. receipt={receipt}")
    EXTERNAL_ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    copy_tree(local_target, external_target)
    return local_target, external_target, receipt


def verify_artifacts(local_target: Path, external_target: Path, pod_id: str, receipts: dict[str, str]) -> Path:
    required = ["adapter_config.json", "adapter_model.safetensors", "ENGEL_LORA_TRAINING_RECEIPT.json", "ENGEL_LORA_ARTIFACT_VERIFY.json"]
    files = []
    for path in sorted(local_target.rglob("*")):
        if path.is_file():
            files.append(
                {
                    "path": str(path.relative_to(local_target)),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    training_receipt_path = local_target / "ENGEL_LORA_TRAINING_RECEIPT.json"
    training_receipt = json.loads(training_receipt_path.read_text(encoding="utf-8")) if training_receipt_path.exists() else {}
    payload = {
        "ok": all((local_target / item).exists() for item in required) and training_receipt.get("ok") is True,
        "schema": "engel_lora_training_artifact_verifier_v1",
        "verified_at_utc": iso_now(),
        "pod_id": pod_id,
        "local_artifact_dir": str(local_target),
        "external_artifact_dir": str(external_target),
        "required": required,
        "files": files,
        "training_receipt_ok": training_receipt.get("ok"),
        "training_base_model": training_receipt.get("base_model", ""),
        "training_gpu_name": training_receipt.get("gpu_name", ""),
        "training_max_steps": training_receipt.get("max_steps", ""),
        "training_elapsed_seconds": training_receipt.get("elapsed_seconds", ""),
        "stage_receipts": receipts,
    }
    latest = APP_ROOT / "runtime" / "engel_lora_training_artifact_verifier_latest.json"
    write_json(latest, payload)
    receipt = write_receipt("RUNPOD_ENGEL_LORA_TRAINING_ARTIFACT_VERIFY", payload)
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    print(f"receipt={receipt}", flush=True)
    if not payload["ok"]:
        raise RuntimeError(f"Artifact verification failed. receipt={receipt}")
    return latest


def stop_pod(pod_id: str) -> Path:
    payload: dict[str, Any]
    try:
        response = runpod_request("POST", f"/pods/{pod_id}/stop", {})
        payload = {
            "ok": True,
            "schema": "engel_runpod_lora_pod_stop_v1",
            "stopped_at_utc": iso_now(),
            "pod_id": pod_id,
            "response": redact_pod(response),
        }
    except Exception as exc:
        payload = {
            "ok": False,
            "schema": "engel_runpod_lora_pod_stop_v1",
            "stopped_at_utc": iso_now(),
            "pod_id": pod_id,
            "error": str(exc),
        }
    receipt = write_receipt("RUNPOD_ENGEL_LORA_TRAINING_POD_STOP", payload)
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    print(f"receipt={receipt}", flush=True)
    return receipt


def run_all(args: argparse.Namespace) -> int:
    require_inputs()
    receipts: dict[str, str] = {}
    ip = ""
    port = 0
    stopped = False
    run_started = time.perf_counter()
    cost_per_hr = 0.0
    budget_plan: dict[str, Any] = {}
    try:
        ip, port, ready_state, ready_receipt = wait_for_ssh_target(args.pod_id, args.ready_attempts, args.ready_delay)
        pod_for_budget = ready_state.get("pod") if isinstance(ready_state.get("pod"), dict) else {}
        try:
            cost_per_hr = float(pod_for_budget.get("costPerHr") or 0.0)
        except (TypeError, ValueError):
            cost_per_hr = 0.0
        receipts["ready"] = str(ready_receipt)
        receipts["ssh_test"] = str(ssh_test(ip, port))
        receipts["upload"] = str(upload_package(ip, port))
        target_seconds = max(0, int(args.target_seconds or 0))
        if target_seconds <= 0 and float(args.budget_usd or 0) > 0 and cost_per_hr > 0:
            total_budget_seconds = float(args.budget_usd) / cost_per_hr * 3600.0
            target_seconds = max(60, int(total_budget_seconds - (time.perf_counter() - run_started) - int(args.stop_margin_seconds)))
        budget_plan = {
            "ok": target_seconds > 0,
            "schema": "engel_runpod_lora_budget_plan_v1",
            "planned_at_utc": iso_now(),
            "pod_id": args.pod_id,
            "budget_usd": float(args.budget_usd or 0),
            "cost_per_hr": cost_per_hr,
            "target_seconds": target_seconds,
            "max_steps": args.max_steps,
            "base_model": args.base_model,
            "learning_rate": args.lr,
            "logging_steps": args.logging_steps,
            "stop_margin_seconds": args.stop_margin_seconds,
        }
        budget_receipt = write_receipt("RUNPOD_ENGEL_LORA_TRAINING_BUDGET_PLAN", budget_plan)
        receipts["budget_plan"] = str(budget_receipt)
        print(json.dumps(budget_plan, indent=2, sort_keys=True), flush=True)
        print(f"receipt={budget_receipt}", flush=True)
        receipts["training"] = str(train_remote(ip, port, args.max_steps, args.max_length, args.base_model, args.lr, target_seconds, args.logging_steps))
        local_target, external_target, download_receipt = download_artifacts(ip, port, args.pod_id)
        receipts["download"] = str(download_receipt)
        receipts["verify"] = str(verify_artifacts(local_target, external_target, args.pod_id, receipts))
        return 0
    except Exception as exc:
        failure = {
            "ok": False,
            "schema": "engel_runpod_lora_training_failure_v1",
            "failed_at_utc": iso_now(),
            "pod_id": args.pod_id,
            "ssh_ip": ip,
            "ssh_port": port,
            "error": str(exc),
            "stage_receipts": receipts,
            "budget_plan": budget_plan,
        }
        receipt = write_receipt("RUNPOD_ENGEL_LORA_TRAINING_FAILURE", failure)
        print(json.dumps(failure, indent=2, sort_keys=True), flush=True)
        print(f"receipt={receipt}", flush=True)
        return 1
    finally:
        if args.stop:
            stop_pod(args.pod_id)
            stopped = True
        elapsed = time.perf_counter() - run_started
        if cost_per_hr > 0:
            summary = {
                "ok": True,
                "schema": "engel_runpod_lora_budget_summary_v1",
                "finished_at_utc": iso_now(),
                "pod_id": args.pod_id,
                "budget_usd": float(args.budget_usd or 0),
                "cost_per_hr": cost_per_hr,
                "elapsed_seconds": round(elapsed, 3),
                "estimated_spend_usd": round(cost_per_hr * elapsed / 3600.0, 4),
                "stage_receipts": receipts,
                "budget_plan": budget_plan,
            }
            summary_receipt = write_receipt("RUNPOD_ENGEL_LORA_TRAINING_BUDGET_SUMMARY", summary)
            print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
            print(f"receipt={summary_receipt}", flush=True)
        if stopped:
            print("ENGEL_RUNPOD_POD_STOP_REQUESTED", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real Engel standalone LLM LoRA training on a RunPod pod.")
    parser.add_argument("--pod-id", default="6uvpuagk0c0rbl")
    parser.add_argument("--base-model", default=os.environ.get("BASE_MODEL", "mistralai/Mistral-7B-Instruct-v0.3"))
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--max-length", type=int, default=768)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--target-seconds", type=int, default=0)
    parser.add_argument("--logging-steps", type=int, default=25)
    parser.add_argument("--budget-usd", type=float, default=0.0)
    parser.add_argument("--stop-margin-seconds", type=int, default=120)
    parser.add_argument("--ready-attempts", type=int, default=60)
    parser.add_argument("--ready-delay", type=int, default=10)
    parser.add_argument("--stop", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("command", choices=["run-all", "status", "stop"], nargs="?", default="run-all")
    args = parser.parse_args()

    if args.command == "status":
        pod = status_pod(args.pod_id)
        ip, port = infer_ssh_target(pod)
        payload = {
            "ok": bool(ip and port),
            "schema": "engel_runpod_lora_pod_status_v1",
            "checked_at_utc": iso_now(),
            "pod_id": args.pod_id,
            "public_ip": ip or "",
            "ssh_port": port or "",
            "pod": redact_pod(pod),
        }
        receipt = write_receipt("RUNPOD_ENGEL_LORA_TRAINING_POD_STATUS", payload)
        print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
        print(f"receipt={receipt}", flush=True)
        return 0 if payload["ok"] else 1
    if args.command == "stop":
        stop_pod(args.pod_id)
        return 0
    return run_all(args)


if __name__ == "__main__":
    raise SystemExit(main())
