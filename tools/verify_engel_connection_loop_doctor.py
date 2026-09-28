from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import engel_connection_loop_doctor as doctor


ROOT = Path(__file__).resolve().parents[1]
MAIN_DART = ROOT / "engel_flutter_main" / "lib" / "main.dart"
DOCTOR = ROOT / "tools" / "engel_connection_loop_doctor.py"
DOCTOR_GUI = ROOT / "tools" / "engel_connection_loop_doctor_gui.py"
DOCTOR_APP = ROOT / "tools" / "engel_connection_loop_doctor_app.py"
LAUNCHER = ROOT / "scripts" / "Start-EngelConnectionLoopDoctor.ps1"
APP_LAUNCHER = ROOT / "scripts" / "Start-EngelConnectionDoctorApp.ps1"
INSTALLER = ROOT / "scripts" / "Install-EngelMainPersistentAgenticSystem.ps1"
CHAT_RUNNER = ROOT / "tools" / "run_engel_ui_chat_meeting_room_llm.py"
GENERATED_CODE_ROOT = ROOT / "reports" / "connection_loop_doctor" / "generated_code"
FINAL_BRAND_BG = ROOT / "assets" / "branding" / "final" / "engel_desktop_bg_final.png"
FINAL_BRAND_ICON = ROOT / "assets" / "branding" / "final" / "engel_icon_final.ico"
ICON_PNG = ROOT / "assets" / "branding" / "final" / "engel_connection_doctor_icon.png"
ICON_ICO = ROOT / "assets" / "branding" / "final" / "engel_connection_doctor_icon.ico"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def snapshot_tree(path: Path) -> dict[str, tuple[object, ...]]:
    if not path.exists():
        return {}
    snapshot: dict[str, tuple[object, ...]] = {}
    for item in sorted(path.rglob("*")):
        relative = item.relative_to(path).as_posix()
        stat = item.stat()
        if item.is_dir():
            snapshot[relative] = ("directory", stat.st_mtime_ns)
        elif item.is_file():
            snapshot[relative] = (
                "file",
                stat.st_size,
                stat.st_mtime_ns,
                hashlib.sha256(item.read_bytes()).hexdigest(),
            )
    return snapshot


def simulated_receipt(
    *,
    chat_ok: bool,
    meeting_room_ok: bool,
    office_ok: bool,
    ct_ok: bool = True,
    key_ok: bool = True,
    fix: bool = False,
    repair_succeeds: bool = False,
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="engel-connection-doctor-v2-") as temp:
        temp_root = Path(temp)
        report_root = temp_root / "reports"
        language_root = temp_root / "languages"
        language_root.mkdir()
        key_path = temp_root / "engel_test_key"
        if key_ok:
            key_path.write_text("test key placeholder", encoding="utf-8")
            Path(str(key_path) + ".pub").write_text("test public key placeholder", encoding="utf-8")

        args_list = [
            "--json",
            "--key-path",
            str(key_path),
            "--chat-local-port",
            "24680",
            "--meeting-local-port",
            "8790",
            "--office-local-port",
            "3000",
        ]
        if fix:
            args_list.append("--fix")
        args = doctor.parse_args(args_list)

        def fake_tcp_open(host: str, port: int, timeout: float = 2.0) -> tuple[bool, str]:
            del timeout
            if host == args.ct_host and port == args.ct_port:
                return ct_ok, "open" if ct_ok else "unreachable"
            if host == args.ct_host and port in {22, 8006}:
                return True, "open"
            if host == "127.0.0.1" and port == args.chat_local_port:
                ready = chat_ok or repair_succeeds
                return ready, "open" if ready else "offline"
            if host == "127.0.0.1" and port == args.meeting_local_port:
                ready = meeting_room_ok or repair_succeeds
                return ready, "open" if ready else "offline"
            if host == "127.0.0.1" and port == args.office_local_port:
                return office_ok, "open" if office_ok else "offline"
            return False, "unexpected simulated endpoint"

        def fake_http_json(url: str, timeout: float = 3.0) -> tuple[bool, str, dict[str, object] | None]:
            del timeout
            if url.endswith(f":{args.chat_local_port}/health"):
                return chat_ok, "json" if chat_ok else "offline", {"ok": True} if chat_ok else None
            if url.endswith(f":{args.meeting_local_port}/health"):
                return (
                    meeting_room_ok,
                    "json" if meeting_room_ok else "offline",
                    {"ok": True} if meeting_room_ok else None,
                )
            return False, "unexpected simulated URL", None

        start_task_mock = mock.Mock(
            return_value={"ok": True, "exit_code": 0, "stdout": "", "stderr": ""}
        )
        start_tunnel_mock = mock.Mock(
            return_value={"ok": True, "reason": "simulated tunnel process started"}
        )
        recycle_tunnels_mock = mock.Mock(
            return_value={
                "ok": True,
                "killed_pids": [],
                "reason": "simulated no stale tunnel",
            }
        )
        required_services_after = {
            "chat": {
                "ok": chat_ok or repair_succeeds,
                "status": "json" if chat_ok or repair_succeeds else "offline",
                "payload": {"ok": True} if chat_ok or repair_succeeds else None,
            },
            "meeting_room": {
                "ok": meeting_room_ok or repair_succeeds,
                "status": "json" if meeting_room_ok or repair_succeeds else "offline",
                "payload": {"ok": True} if meeting_room_ok or repair_succeeds else None,
            },
        }
        wait_required_services_mock = mock.Mock(
            return_value={
                "ok": all(service["ok"] for service in required_services_after.values()),
                "status": (
                    "Chat and Meeting Room are ready"
                    if repair_succeeds
                    else "Chat or Meeting Room is still unavailable"
                ),
                "services": required_services_after,
            }
        )
        with (
            mock.patch.object(doctor, "REPORT_ROOT", report_root),
            mock.patch.object(doctor, "LANGUAGE_ROOT", language_root),
            mock.patch.object(doctor, "tcp_open", side_effect=fake_tcp_open),
            mock.patch.object(doctor, "http_json", side_effect=fake_http_json),
            mock.patch.object(doctor, "scheduled_task_state", return_value=(True, "Ready")),
            mock.patch.object(doctor, "start_task", start_task_mock),
            mock.patch.object(doctor, "start_tunnel", start_tunnel_mock),
            mock.patch.object(
                doctor,
                "recycle_stale_local_tunnels",
                recycle_tunnels_mock,
            ),
            mock.patch.object(
                doctor,
                "wait_for_required_services",
                wait_required_services_mock,
            ),
        ):
            receipt = doctor.run_doctor(args)

        if not fix:
            require(start_task_mock.call_count == 0, "check mode called the Windows task repair")
            require(start_tunnel_mock.call_count == 0, "check mode called the tunnel repair")
            require(
                wait_required_services_mock.call_count == 0,
                "check mode waited on repair health",
            )
        return receipt


def verify_simulated_contract() -> None:
    scenarios = [
        (True, True, True, True, True, "ready"),
        (True, True, False, True, True, "partial"),
        (True, False, True, True, True, "partial"),
        (False, False, False, True, False, "setup_required"),
        (False, False, False, False, True, "server_unreachable"),
        (False, False, False, True, True, "unavailable"),
    ]
    for chat_ok, meeting_ok, office_ok, ct_ok, key_ok, expected_state in scenarios:
        receipt = simulated_receipt(
            chat_ok=chat_ok,
            meeting_room_ok=meeting_ok,
            office_ok=office_ok,
            ct_ok=ct_ok,
            key_ok=key_ok,
        )
        services = receipt["services"]
        require(services["chat"]["ok"] is chat_ok, "simulated Chat state mismatch")
        require(services["meeting_room"]["ok"] is meeting_ok, "simulated Meeting Room state mismatch")
        require(services["office"]["ok"] is office_ok, "simulated Office state mismatch")
        require(receipt["ok"] is (chat_ok and meeting_ok), "simulated top-level ok mismatch")
        require(receipt["overall_state"] == expected_state, "simulated overall state mismatch")
        require(receipt["repair"]["outcome"] == "not_requested", "check mode repair outcome mismatch")
        require(receipt["language_scaffolds"]["writes_performed"] is False, "simulated check wrote scaffolds")

    repaired = simulated_receipt(
        chat_ok=False,
        meeting_room_ok=True,
        office_ok=True,
        fix=True,
        repair_succeeds=True,
    )
    repair = repaired["repair"]
    require(repaired["ok"] is True, "simulated repair did not restore required services")
    require(repair["requested"] is True, "simulated repair request was not disclosed")
    require(repair["attempted"] is True, "simulated repair attempt was not disclosed")
    require(repair["outcome"] == "succeeded", "simulated repair outcome mismatch")
    require(repair["target_services"] == ["chat", "meeting_room"], "repair targets mismatch")
    require(
        repair["before"] == {"chat": "unavailable", "meeting_room": "ready"},
        "simulated repair before-state mismatch",
    )
    require(
        repair["after"] == {"chat": "ready", "meeting_room": "ready"},
        "simulated repair after-state mismatch",
    )
    require(
        repair["restored"] == {"chat": True, "meeting_room": False},
        "simulated Chat restoration was not disclosed",
    )
    require(
        [action["name"] for action in repair["actions"]]
        == [
            "start_windows_task",
            "recycle_stale_local_tunnels",
            "start_persistent_tunnel",
        ],
        "simulated repair actions mismatch",
    )
    require(
        [action["name"] for action in repair["validation_actions"]]
        == ["wait_required_services"],
        "simulated repair validation mismatch",
    )
    require(repair["remote_server_changes_attempted"] is False, "simulated repair disclosed remote changes")

    meeting_repaired = simulated_receipt(
        chat_ok=True,
        meeting_room_ok=False,
        office_ok=True,
        fix=True,
        repair_succeeds=True,
    )
    meeting_repair = meeting_repaired["repair"]
    require(meeting_repaired["ok"] is True, "Meeting-only outage was not repaired")
    require(meeting_repair["attempted"] is True, "Meeting-only repair was not attempted")
    require(meeting_repair["outcome"] == "succeeded", "Meeting-only repair outcome mismatch")
    require(
        meeting_repair["before"] == {"chat": "ready", "meeting_room": "unavailable"},
        "Meeting-only before-state mismatch",
    )
    require(
        meeting_repair["after"] == {"chat": "ready", "meeting_room": "ready"},
        "Meeting-only after-state mismatch",
    )
    require(
        meeting_repair["restored"] == {"chat": False, "meeting_room": True},
        "Meeting-only restoration was not disclosed",
    )

    office_only = simulated_receipt(
        chat_ok=True,
        meeting_room_ok=True,
        office_ok=False,
        fix=True,
    )
    office_repair = office_only["repair"]
    require(office_only["ok"] is True, "Office must not affect required-service ok")
    require(office_only["overall_state"] == "partial", "Office outage must remain visible")
    require(office_repair["attempted"] is False, "Office-only outage triggered repair")
    require(office_repair["outcome"] == "not_needed", "Office-only repair outcome mismatch")


def verify_shared_wait_contract() -> None:
    probes: list[tuple[str, float]] = []

    def unavailable(url: str, timeout: float) -> tuple[bool, str, None]:
        probes.append((url, timeout))
        return False, "offline", None

    monotonic_values = iter([0.0, 0.1, 0.2, 0.3, 1.1, 1.2])
    with (
        mock.patch.object(doctor, "http_json", side_effect=unavailable),
        mock.patch.object(doctor.time, "monotonic", side_effect=lambda: next(monotonic_values)),
        mock.patch.object(doctor.time, "sleep"),
    ):
        result = doctor.wait_for_required_services(
            "http://127.0.0.1:24680/health",
            "http://127.0.0.1:8790/health",
            seconds=1,
        )

    require(result["ok"] is False, "shared wait unexpectedly succeeded")
    require(
        [url for url, _ in probes]
        == [
            "http://127.0.0.1:24680/health",
            "http://127.0.0.1:8790/health",
        ],
        "shared wait did not probe both required services",
    )
    require(
        all(0 < timeout <= 1 for _, timeout in probes),
        "shared wait exceeded its common time budget",
    )


def main() -> int:
    for path in [
        MAIN_DART,
        DOCTOR,
        DOCTOR_GUI,
        DOCTOR_APP,
        LAUNCHER,
        APP_LAUNCHER,
        INSTALLER,
        CHAT_RUNNER,
        FINAL_BRAND_BG,
        FINAL_BRAND_ICON,
        ICON_PNG,
        ICON_ICO,
    ]:
        require(path.is_file(), f"missing file: {path}")

    dart = read(MAIN_DART)
    require("connectionLoopDoctorScriptPath" in dart, "Flutter constant missing")
    require("'connection_doctor'" in dart, "Flutter section/page missing")
    require(
        "Check connection" in dart
        and ("Repair connection" in dart or "Start connection" in dart),
        "Connection Doctor actions missing",
    )
    require("_runConnectionLoopDoctor" in dart, "Flutter doctor runner missing")
    require("Connection Doctor" in dart, "Doctor page missing")
    require("engel_connection_loop_doctor_app.py" in dart, "Flutter app launch target missing")

    doctor_source = read(DOCTOR)
    require("def generate_language_stubs" not in doctor_source, "retired language scaffold writer remains")
    require('"known_language_stubs"' not in doctor_source, "language scaffolds remain in connection checks")

    installer = read(INSTALLER)
    require("& ssh-keygen @sshKeygenArgs" in installer, "ssh-keygen argument fix missing")
    require("cmd.exe /d /c $sshKeygenCommand" not in installer, "fragile ssh-keygen command remains")

    chat_runner = read(CHAT_RUNNER)
    require("Repair connection" in chat_runner, "chat unavailable repair guidance not updated")
    require("connection_doctor_reports" in chat_runner, "chat receipt doctor path missing")

    launcher = read(LAUNCHER)
    require("-or $App" in launcher, "launcher must support app mode")
    require("Start-Process -FilePath $PythonAppExe" in launcher, "launcher must use app Python for app mode")
    require("$quotedTarget" in launcher, "launcher must quote app path with spaces")

    app_launcher = read(APP_LAUNCHER)
    require("engel_connection_loop_doctor_app.py" in app_launcher, "app launcher target missing")
    require("pythonw.exe" in app_launcher, "app launcher must use pythonw.exe app mode")
    require("$QuotedApp" in app_launcher, "app launcher must quote app path with spaces")

    app = read(DOCTOR_APP)
    require("APP_ICON_PNG" in app and "APP_ICON_ICO" in app, "doctor app icon wiring missing")
    require("BRAND_BG" in app and "engel_desktop_bg_final.png" in app, "final background branding missing")
    require("BRAND_ICON" in app and "engel_icon_final.ico" in app, "final icon branding missing")
    require("COSMIC SWARM OS" in app, "doctor app must keep Engel macOS-style header")

    for path in [DOCTOR, DOCTOR_GUI, DOCTOR_APP, LAUNCHER, APP_LAUNCHER, CHAT_RUNNER]:
        text = read(path)
        require("/mnt/engel-vault" not in text, f"Vault path should not be used in {path.name}")

    compile_result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(DOCTOR), str(DOCTOR_GUI), str(DOCTOR_APP)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    require(compile_result.returncode == 0, compile_result.stderr)
    verify_simulated_contract()
    verify_shared_wait_contract()

    generated_code_before = snapshot_tree(GENERATED_CODE_ROOT)
    doctor_result = subprocess.run(
        [sys.executable, str(DOCTOR), "--json"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=90,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    require(doctor_result.stdout.strip(), "doctor produced no JSON")
    payload = json.loads(doctor_result.stdout)
    generated_code_after = snapshot_tree(GENERATED_CODE_ROOT)

    require(payload.get("schema") == "engel_connection_loop_doctor_v2", "bad doctor schema")
    require(payload.get("schema_version") == 2, "bad doctor schema version")
    require(payload.get("secrets_read") is False, "doctor must not read secrets")
    require(payload.get("vault_used") is False, "doctor must not use Vault")
    require(payload.get("storage_mutation_performed") is True, "diagnostic report writes must be disclosed")
    require(
        payload.get("storage_mutation_scope") == "diagnostic report files",
        "diagnostic storage mutation scope missing",
    )

    services = payload.get("services")
    require(isinstance(services, dict), "service states missing")
    require(set(services) == {"chat", "meeting_room", "office"}, "service state set mismatch")
    for name in ("chat", "meeting_room", "office"):
        service = services[name]
        require(isinstance(service, dict), f"{name} service state must be an object")
        require(service.get("state") in {"ready", "unavailable"}, f"{name} service state invalid")
        require(service.get("ok") is (service.get("state") == "ready"), f"{name} state/ok mismatch")

    checks = {
        check.get("name"): check
        for check in payload.get("checks", [])
        if isinstance(check, dict) and isinstance(check.get("name"), str)
    }
    require("known_language_stubs" not in checks, "normal check still contains language generation")
    require(
        services["chat"]["ok"] is bool(checks["local_chat_health"]["ok"]),
        "Chat service state does not match Chat health",
    )
    require(
        services["meeting_room"]["ok"] is bool(checks["local_meeting_room_health"]["ok"]),
        "Meeting Room service state does not match Meeting Room health",
    )
    require(
        services["office"]["ok"] is bool(checks["local_office_tcp"]["ok"]),
        "Office service state does not match Office TCP health",
    )
    require(
        payload.get("ok") is bool(services["chat"]["ok"] and services["meeting_room"]["ok"]),
        "top-level ok must mean both Chat and Meeting Room are ready",
    )
    require(
        payload.get("overall_state")
        in {"ready", "partial", "unavailable", "setup_required", "server_unreachable"},
        "overall state invalid",
    )

    repair = payload.get("repair")
    require(isinstance(repair, dict), "repair disclosure missing")
    require(repair.get("requested") is False, "normal verification must not request repair")
    require(repair.get("attempted") is False, "normal verification must not attempt repair")
    require(repair.get("outcome") == "not_requested", "normal verification repair outcome is wrong")
    require(
        repair.get("target_services") == ["chat", "meeting_room"],
        "required repair targets are wrong",
    )
    required_states = {
        name: services[name]["state"]
        for name in ("chat", "meeting_room")
    }
    require(repair.get("before") == required_states, "normal check repair before-state mismatch")
    require(repair.get("after") == required_states, "normal check repair after-state mismatch")
    require(
        repair.get("restored") == {"chat": False, "meeting_room": False},
        "normal check reported a restored service",
    )
    require(repair.get("actions") == [], "normal verification disclosed repair actions")
    require(repair.get("validation_actions") == [], "normal verification disclosed repair validation")
    require(repair.get("remote_server_changes_attempted") is False, "remote changes must not be attempted")
    require(payload.get("actions") == [], "normal check must not run actions")
    require(
        payload.get("user_actions") == ["Check connection", "Repair connection", "Open reports"],
        "Connection Doctor user actions are stale",
    )

    report_writes = payload.get("diagnostic_report_writes")
    require(isinstance(report_writes, dict), "diagnostic report-write disclosure missing")
    require(report_writes.get("performed") is True, "diagnostic report writes not disclosed")
    report_files = report_writes.get("files")
    require(isinstance(report_files, list) and len(report_files) == 2, "expected two diagnostic report writes")
    report_paths = {
        str(item.get("path"))
        for item in report_files
        if isinstance(item, dict) and item.get("path")
    }
    require(payload.get("receipt_path") in report_paths, "timestamped receipt write missing")
    require(str(ROOT / "reports" / "connection_loop_doctor" / "latest.json") in report_paths, "latest receipt write missing")
    require(all(Path(path).is_file() for path in report_paths), "a disclosed diagnostic report was not written")

    language_scaffolds = payload.get("language_scaffolds")
    require(isinstance(language_scaffolds, dict), "language scaffold disclosure missing")
    require(language_scaffolds.get("requested") is False, "normal check requested language scaffolds")
    require(language_scaffolds.get("generated") is False, "normal check generated language scaffolds")
    require(language_scaffolds.get("writes_performed") is False, "normal check wrote language scaffolds")
    require(language_scaffolds.get("count") == 0, "normal check reported generated language scaffolds")
    require(language_scaffolds.get("items") == [], "normal check reported language scaffold items")
    require(
        generated_code_after == generated_code_before,
        "normal check changed the generated language scaffold tree",
    )

    print(
        json.dumps(
            {
                "ok": True,
                "schema": "engel_connection_loop_doctor_verify_v2",
                "doctor_schema": payload.get("schema"),
                "overall_state": payload.get("overall_state"),
                "services": services,
                "language_scaffolds_unchanged": True,
                "diagnostic_report_writes": report_files,
                "doctor_status": payload.get("status"),
                "doctor_receipt": payload.get("receipt_path"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
