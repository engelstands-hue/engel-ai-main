from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "connection_loop_doctor"
LANGUAGE_ROOT = ROOT / "engel_library" / "approved_library" / "coding_languages"
TUNNEL_SCRIPT = ROOT / "scripts" / "Start-EngelMainServerChatTunnelPersistent.ps1"
INSTALLER_SCRIPT = ROOT / "scripts" / "Install-EngelMainPersistentAgenticSystem.ps1"
CONNECTION_TEST_SCRIPT = ROOT / "scripts" / "Test-EngelMainOneSystemConnections.ps1"
DEFAULT_KEY = Path.home() / ".ssh" / "engel_ai_main_ct246_ed25519"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def tcp_open(host: str, port: int, timeout: float = 2.0) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "open"
    except OSError as exc:
        return False, str(exc)


def http_json(url: str, timeout: float = 8.0) -> tuple[bool, str, dict[str, Any] | None]:
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 0) or 0)
            body = response.read().decode("utf-8", errors="replace")
        if status and (status < 200 or status >= 300):
            return False, f"HTTP {status}", None
        payload = json.loads(body)
        if isinstance(payload, dict):
            return bool(payload.get("ok") is True or payload.get("status") == "running"), "json", payload
        return False, "non-object json", None
    except TimeoutError as exc:
        return False, f"health timeout: {exc}", None
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return False, str(exc), None


def run_powershell(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", *args]
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return completed.returncode, completed.stdout.strip(), completed.stderr.strip()
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", "timeout"
    except OSError as exc:
        return 127, "", str(exc)


def scheduled_task_state(task_name: str) -> tuple[bool, str]:
    code, stdout, stderr = run_powershell(
        [
            "-Command",
            (
                "$task=Get-ScheduledTask -TaskName "
                + json.dumps(task_name)
                + " -ErrorAction SilentlyContinue; "
                "if($null -eq $task){'missing'}else{$task.State}"
            ),
        ],
        timeout=12,
    )
    status = stdout.strip() or stderr.strip() or f"exit {code}"
    return code == 0 and status.lower() != "missing", status


def start_task(task_name: str) -> dict[str, Any]:
    code, stdout, stderr = run_powershell(
        ["-Command", "Start-ScheduledTask -TaskName " + json.dumps(task_name)],
        timeout=15,
    )
    return {"ok": code == 0, "exit_code": code, "stdout": stdout, "stderr": stderr}


def start_tunnel(
    host: str,
    port: int,
    user: str,
    key_path: Path,
    office_port: int,
) -> dict[str, Any]:
    if not TUNNEL_SCRIPT.is_file():
        return {"ok": False, "reason": f"missing script: {TUNNEL_SCRIPT}"}
    if not key_path.is_file():
        return {"ok": False, "reason": f"missing key: {key_path}"}
    args = [
        "-NoProfile",
        "-WindowStyle",
        "Hidden",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(TUNNEL_SCRIPT),
        "-CtHost",
        host,
        "-CtPort",
        str(port),
        "-CtUser",
        user,
        "-KeyPath",
        str(key_path),
        "-OfficeLocalPort",
        str(office_port),
    ]
    try:
        subprocess.Popen(
            ["powershell.exe", *args],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as exc:
        return {"ok": False, "reason": str(exc)}
    return {"ok": True, "reason": "tunnel process started"}


def recycle_stale_local_tunnels(chat_port: int, meeting_port: int) -> dict[str, Any]:
    """Stop hung Engel CT246 SSH forwards that accept TCP but never answer /health.

    A second start_tunnel cannot bind 127.0.0.1:24680/8790 while the stale
    listener is still up, so repair would keep probing the dead tunnel.
    Only ssh.exe rows that mention the Engel CT246 key and those local
    forwards are touched.
    """
    script = (
        "$key = 'engel_ai_main_ct246_ed25519'; "
        f"$ports = @({int(chat_port)},{int(meeting_port)}); "
        "$killed = @(); "
        "Get-CimInstance Win32_Process -Filter \"Name='ssh.exe'\" -ErrorAction SilentlyContinue | "
        "ForEach-Object { "
        "  $cmd = [string]$_.CommandLine; "
        "  if ($cmd -notmatch [regex]::Escape($key)) { return }; "
        "  $hit = $false; "
        "  foreach ($port in $ports) { "
        "    if ($cmd -match [regex]::Escape(('127.0.0.1:' + $port))) { $hit = $true } "
        "  }; "
        "  if (-not $hit) { return }; "
        "  try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop; "
        "        $killed += [string]$_.ProcessId } catch {} "
        "}; "
        "$killed -join ','"
    )
    code, stdout, stderr = run_powershell(["-Command", script], timeout=15)
    killed = [item for item in stdout.split(",") if item.strip()]
    return {
        "ok": code == 0,
        "exit_code": code,
        "killed_pids": killed,
        "reason": (
            f"recycled {len(killed)} stale Engel SSH tunnel(s)"
            if killed
            else "no matching stale Engel SSH tunnel"
        ),
        "stderr": stderr,
    }


def wait_for_required_services(
    chat_url: str,
    meeting_room_url: str,
    seconds: int,
) -> dict[str, Any]:
    """Check both required services within one shared time budget."""
    deadline = time.monotonic() + max(1, seconds)
    urls = {"chat": chat_url, "meeting_room": meeting_room_url}
    results: dict[str, dict[str, Any]] = {
        name: {"ok": False, "status": "not checked", "payload": None}
        for name in urls
    }
    while True:
        for name, url in urls.items():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            ok, status, payload = http_json(url, timeout=min(8.0, remaining))
            results[name] = {"ok": ok, "status": status, "payload": payload}
        if all(bool(result.get("ok")) for result in results.values()):
            return {
                "ok": True,
                "status": "Chat and Meeting Room are ready",
                "services": results,
            }
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(1.0, remaining))
    return {
        "ok": False,
        "status": "Chat or Meeting Room is still unavailable",
        "services": results,
    }


def language_scaffold_disclosure() -> dict[str, Any]:
    """Describe the retired scaffold side effect without touching its files."""
    return {
        "generated_root": str(REPORT_ROOT / "generated_code"),
        "source_root": str(LANGUAGE_ROOT),
        "requested": False,
        "generated": False,
        "writes_performed": False,
        "count": 0,
        "items": [],
        "reason": "Language scaffold generation is not part of Connection Doctor v2.",
    }


def build_check(name: str, ok: bool, status: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "ok": ok, "status": status, "details": details or {}}


def replace_check(
    checks: list[dict[str, Any]],
    name: str,
    ok: bool,
    status: str,
    details: dict[str, Any] | None = None,
) -> None:
    replacement = build_check(name, ok, status, details)
    for index, check in enumerate(checks):
        if check.get("name") == name:
            checks[index] = replacement
            return
    checks.append(replacement)


def run_doctor(args: argparse.Namespace) -> dict[str, Any]:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    key_path = Path(args.key_path).expanduser()
    checks: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    ct_ok, ct_status = tcp_open(args.ct_host, args.ct_port, timeout=2.5)
    checks.append(build_check("ct_ssh_tcp", ct_ok, f"{args.ct_host}:{args.ct_port} {ct_status}"))

    proxmox_ssh_ok, proxmox_ssh_status = tcp_open(args.ct_host, 22, timeout=2.5)
    checks.append(build_check("proxmox_host_ssh_tcp", proxmox_ssh_ok, f"{args.ct_host}:22 {proxmox_ssh_status}"))

    proxmox_ui_ok, proxmox_ui_status = tcp_open(args.ct_host, 8006, timeout=2.5)
    checks.append(build_check("proxmox_web_ui_tcp", proxmox_ui_ok, f"{args.ct_host}:8006 {proxmox_ui_status}"))

    key_ok = key_path.is_file()
    pub_ok = Path(str(key_path) + ".pub").is_file()
    checks.append(
        build_check(
            "rog_ssh_key",
            key_ok and pub_ok,
            str(key_path),
            {"private_key_exists": key_ok, "public_key_exists": pub_ok},
        )
    )

    task_ok, task_status = scheduled_task_state(args.task_name)
    checks.append(build_check("windows_persistent_link_task", task_ok, task_status, {"task_name": args.task_name}))

    chat_tcp_ok, chat_tcp_status = tcp_open("127.0.0.1", args.chat_local_port, timeout=1.0)
    checks.append(build_check("local_chat_tunnel_tcp", chat_tcp_ok, f"127.0.0.1:{args.chat_local_port} {chat_tcp_status}"))

    chat_health_url = f"http://127.0.0.1:{args.chat_local_port}/health"
    chat_health_ok, chat_health_status, chat_health_payload = http_json(chat_health_url, timeout=8.0)
    checks.append(
        build_check(
            "local_chat_health",
            chat_health_ok,
            chat_health_url if chat_health_ok else chat_health_status,
            {"payload": chat_health_payload} if chat_health_payload else {},
        )
    )

    meeting_tcp_ok, meeting_tcp_status = tcp_open("127.0.0.1", args.meeting_local_port, timeout=1.0)
    checks.append(
        build_check("local_meeting_room_tunnel_tcp", meeting_tcp_ok, f"127.0.0.1:{args.meeting_local_port} {meeting_tcp_status}")
    )

    meeting_health_url = f"http://127.0.0.1:{args.meeting_local_port}/health"
    meeting_health_ok, meeting_health_status, meeting_health_payload = http_json(meeting_health_url, timeout=8.0)
    checks.append(
        build_check(
            "local_meeting_room_health",
            meeting_health_ok,
            meeting_health_url if meeting_health_ok else meeting_health_status,
            {"payload": meeting_health_payload} if meeting_health_payload else {},
        )
    )

    office_tcp_ok, office_tcp_status = tcp_open("127.0.0.1", args.office_local_port, timeout=1.0)
    checks.append(build_check("local_office_tcp", office_tcp_ok, f"127.0.0.1:{args.office_local_port} {office_tcp_status}"))

    required_health_before_repair = {
        "chat": chat_health_ok,
        "meeting_room": meeting_health_ok,
    }
    required_services_ready_before_repair = all(required_health_before_repair.values())
    if args.fix and not required_services_ready_before_repair:
        if task_ok:
            actions.append(
                {
                    "name": "start_windows_task",
                    "kind": "repair",
                    "attempted": True,
                    **start_task(args.task_name),
                }
            )
        if ct_ok and key_ok:
            recycle_result = recycle_stale_local_tunnels(
                args.chat_local_port,
                args.meeting_local_port,
            )
            actions.append(
                {
                    "name": "recycle_stale_local_tunnels",
                    "kind": "repair",
                    "attempted": True,
                    **recycle_result,
                }
            )
            tunnel_result = start_tunnel(
                args.ct_host,
                args.ct_port,
                args.ct_user,
                key_path,
                args.office_local_port,
            )
            actions.append(
                {
                    "name": "start_persistent_tunnel",
                    "kind": "repair",
                    "attempted": True,
                    **tunnel_result,
                }
            )
        elif not ct_ok:
            actions.append(
                {
                    "name": "start_persistent_tunnel",
                    "kind": "repair",
                    "attempted": False,
                    "ok": False,
                    "reason": "CT SSH route is not reachable",
                }
            )
        elif not key_ok:
            actions.append(
                {
                    "name": "start_persistent_tunnel",
                    "kind": "repair",
                    "attempted": False,
                    "ok": False,
                    "reason": f"SSH key missing. Run {INSTALLER_SCRIPT} once.",
                }
            )

        attempted_repairs = [
            action
            for action in actions
            if action.get("kind") == "repair" and action.get("attempted") is True
        ]
        if attempted_repairs:
            repaired = wait_for_required_services(
                chat_health_url,
                meeting_health_url,
                seconds=args.wait_seconds,
            )
            actions.append(
                {
                    "name": "wait_required_services",
                    "kind": "validation",
                    "attempted": True,
                    **repaired,
                }
            )
            repaired_services = repaired.get("services")
            if isinstance(repaired_services, dict):
                repaired_chat = repaired_services.get("chat")
                if isinstance(repaired_chat, dict):
                    chat_health_ok = bool(repaired_chat.get("ok"))
                    chat_health_status = str(
                        repaired_chat.get("status") or "health check did not return a status"
                    )
                    repaired_payload = repaired_chat.get("payload")
                    chat_health_payload = repaired_payload if isinstance(repaired_payload, dict) else None
                repaired_meeting_room = repaired_services.get("meeting_room")
                if isinstance(repaired_meeting_room, dict):
                    meeting_health_ok = bool(repaired_meeting_room.get("ok"))
                    meeting_health_status = str(
                        repaired_meeting_room.get("status") or "health check did not return a status"
                    )
                    repaired_payload = repaired_meeting_room.get("payload")
                    meeting_health_payload = (
                        repaired_payload if isinstance(repaired_payload, dict) else None
                    )

    if args.fix and not required_services_ready_before_repair:
        chat_tcp_ok, chat_tcp_status = tcp_open("127.0.0.1", args.chat_local_port, timeout=1.0)
        meeting_tcp_ok, meeting_tcp_status = tcp_open(
            "127.0.0.1",
            args.meeting_local_port,
            timeout=1.0,
        )
        replace_check(
            checks,
            "local_chat_tunnel_tcp",
            chat_tcp_ok,
            f"127.0.0.1:{args.chat_local_port} {chat_tcp_status}",
        )
        replace_check(
            checks,
            "local_chat_health",
            chat_health_ok,
            chat_health_url if chat_health_ok else chat_health_status,
            {"payload": chat_health_payload} if chat_health_payload else {},
        )
        replace_check(
            checks,
            "local_meeting_room_tunnel_tcp",
            meeting_tcp_ok,
            f"127.0.0.1:{args.meeting_local_port} {meeting_tcp_status}",
        )
        replace_check(
            checks,
            "local_meeting_room_health",
            meeting_health_ok,
            meeting_health_url if meeting_health_ok else meeting_health_status,
            {"payload": meeting_health_payload} if meeting_health_payload else {},
        )

    services = {
        "chat": {
            "state": "ready" if chat_health_ok else "unavailable",
            "ok": chat_health_ok,
            "tcp_ok": chat_tcp_ok,
            "health_ok": chat_health_ok,
            "health_url": chat_health_url,
            "status": chat_health_url if chat_health_ok else chat_health_status,
        },
        "meeting_room": {
            "state": "ready" if meeting_health_ok else "unavailable",
            "ok": meeting_health_ok,
            "tcp_ok": meeting_tcp_ok,
            "health_ok": meeting_health_ok,
            "health_url": meeting_health_url,
            "status": meeting_health_url if meeting_health_ok else meeting_health_status,
        },
        "office": {
            "state": "ready" if office_tcp_ok else "unavailable",
            "ok": office_tcp_ok,
            "tcp_ok": office_tcp_ok,
            "health_ok": None,
            "health_url": None,
            "status": f"127.0.0.1:{args.office_local_port} {office_tcp_status}",
        },
    }

    ok = chat_health_ok and meeting_health_ok
    if ok and office_tcp_ok:
        overall_state = "ready"
    elif ok:
        overall_state = "partial"
    elif not key_ok:
        overall_state = "setup_required"
    elif not ct_ok:
        overall_state = "server_unreachable"
    elif chat_health_ok or meeting_health_ok or office_tcp_ok:
        overall_state = "partial"
    else:
        overall_state = "unavailable"

    if overall_state == "ready":
        status = "Chat, Meeting Room, and Office are ready"
        diagnosis = "All checked connection services are healthy"
    elif overall_state == "partial":
        ready_services = [name for name, service in services.items() if service["ok"]]
        unavailable_services = [name for name, service in services.items() if not service["ok"]]
        status = "connection services partially available"
        diagnosis = (
            f"Ready: {', '.join(ready_services) or 'none'}; "
            f"unavailable: {', '.join(unavailable_services) or 'none'}"
        )
    elif overall_state == "setup_required":
        status = "connection setup required"
        diagnosis = "ROG SSH private key file is missing"
    elif overall_state == "server_unreachable" and proxmox_ssh_ok:
        status = "Proxmox reachable, CT SSH forward offline"
        diagnosis = (
            "The Proxmox host is reachable on SSH, but the CT 246 forwarded SSH port "
            f"{args.ct_port} is refusing or unavailable. This is not an SSH-key setup failure."
        )
    elif overall_state == "server_unreachable":
        status = "server SSH route offline"
        diagnosis = "CT-forwarded SSH port is not reachable"
    else:
        status = "connection services unavailable"
        diagnosis = "Chat and Meeting Room did not answer"

    repair_actions = [action for action in actions if action.get("kind") == "repair"]
    validation_actions = [action for action in actions if action.get("kind") == "validation"]
    attempted_repair_actions = [action for action in repair_actions if action.get("attempted") is True]
    required_health_after_repair = {
        "chat": chat_health_ok,
        "meeting_room": meeting_health_ok,
    }
    required_services_ready_after_repair = all(required_health_after_repair.values())
    if not args.fix:
        repair_outcome = "not_requested"
    elif required_services_ready_before_repair:
        repair_outcome = "not_needed"
    elif required_services_ready_after_repair:
        repair_outcome = "succeeded"
    elif attempted_repair_actions:
        repair_outcome = "failed"
    else:
        repair_outcome = "blocked"

    repair = {
        "requested": bool(args.fix),
        "target_services": ["chat", "meeting_room"],
        "attempted": bool(attempted_repair_actions),
        "outcome": repair_outcome,
        "required_services_ready_before": required_services_ready_before_repair,
        "required_services_ready_after": required_services_ready_after_repair,
        "before": {
            name: "ready" if ready else "unavailable"
            for name, ready in required_health_before_repair.items()
        },
        "after": {
            name: "ready" if ready else "unavailable"
            for name, ready in required_health_after_repair.items()
        },
        "restored": {
            name: bool(not required_health_before_repair[name] and ready)
            for name, ready in required_health_after_repair.items()
        },
        "actions": repair_actions,
        "validation_actions": validation_actions,
        "remote_server_changes_attempted": False,
    }

    receipt_path = REPORT_ROOT / f"ENGEL_CONNECTION_LOOP_DOCTOR_{stamp()}.json"
    latest_path = REPORT_ROOT / "latest.json"
    diagnostic_report_writes = {
        "performed": True,
        "count": 2,
        "files": [
            {
                "kind": "timestamped_receipt",
                "path": str(receipt_path),
                "operation": "write",
            },
            {
                "kind": "latest_receipt",
                "path": str(latest_path),
                "operation": "write",
                "replaces_previous": True,
            },
        ],
    }
    language_report = language_scaffold_disclosure()
    receipt = {
        "schema": "engel_connection_loop_doctor_v2",
        "schema_version": 2,
        "ok": ok,
        "overall_state": overall_state,
        "services": services,
        "status": status,
        "diagnosis": diagnosis,
        "created_at_utc": now_iso(),
        "project_root": str(ROOT),
        "mode": "fix" if args.fix else "check",
        "chat_health_url": chat_health_url,
        "meeting_room_health_url": meeting_health_url,
        "ct_route": f"ssh {args.ct_user}@{args.ct_host} -p {args.ct_port}",
        "ssd_only": True,
        "vault_used": False,
        "storage_mutation_performed": True,
        "storage_mutation_scope": "diagnostic report files",
        "diagnostic_report_writes": diagnostic_report_writes,
        "secrets_read": False,
        "checks": checks,
        "actions": actions,
        "repair": repair,
        "server_side_fix_candidates": [
            "On Proxmox host: pct status 246",
            "If CT 246 is stopped: pct start 246",
            "Check the host NAT/forward rule for 192.0.2.50:24622 -> CT 246 sshd",
            "Inside CT 246: systemctl status ssh engel-main-chat.service",
        ]
        if not ct_ok and proxmox_ssh_ok
        else [],
        "language_scaffolds": language_report,
        "receipt_path": str(receipt_path),
        "user_actions": ["Check connection", "Repair connection", "Open reports"],
    }
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    latest_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Engel Connection Loop Doctor")
    parser.add_argument("--fix", action="store_true", help="Start the safe local tunnel repair path.")
    parser.add_argument("--json", action="store_true", help="Print JSON receipt.")
    parser.add_argument("--ct-host", default=os.environ.get("ENGEL_MAIN_SERVER_HOST", "192.0.2.50"))
    parser.add_argument("--ct-port", type=int, default=int(os.environ.get("ENGEL_MAIN_SERVER_SSH_PORT", "24622")))
    parser.add_argument("--ct-user", default=os.environ.get("ENGEL_MAIN_SERVER_SSH_USER", "root"))
    parser.add_argument("--key-path", default=os.environ.get("ENGEL_MAIN_SERVER_KEY_PATH", str(DEFAULT_KEY)))
    parser.add_argument(
        "--task-name",
        default="EngelChatLinkSvc",
        help="Canonical Windows lifecycle task for the CT246 chat and reverse bridge tunnels.",
    )
    parser.add_argument("--chat-local-port", type=int, default=24680)
    parser.add_argument("--meeting-local-port", type=int, default=8790)
    parser.add_argument("--office-local-port", type=int, default=3000)
    parser.add_argument("--wait-seconds", type=int, default=18)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    receipt = run_doctor(args)
    if args.json:
        print(json.dumps(receipt, indent=2))
    else:
        print(f"Engel Connection Loop Doctor: {receipt['status']}")
        for check in receipt["checks"]:
            mark = "PASS" if check["ok"] else "FAIL"
            print(f"{mark} {check['name']}: {check['status']}")
        if receipt["actions"]:
            print("Actions:")
            for action in receipt["actions"]:
                print(f"- {action.get('name')}: {action.get('reason') or action.get('stdout') or action.get('status')}")
        print(f"Receipt: {receipt['receipt_path']}")
    return 0 if receipt.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
