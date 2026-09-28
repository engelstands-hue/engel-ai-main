#!/usr/bin/env python3
"""Verify the shareable Engel AI Main CLI API package has no HTTP and no secrets."""
from __future__ import annotations

import json
import hashlib
import re
import shlex
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "workflows" / "engel_ai_main_cli_api_share"
DIST = ROOT / "dist"


def main() -> int:
    checks: list[tuple[str, bool]] = []

    def check(name: str, ok: bool) -> None:
        checks.append((name, bool(ok)))
        print(("PASS " if ok else "FAIL ") + name)

    client = (ROOT / "engel_ai_main_api_client.py").read_text(encoding="utf-8")
    check("client_exists", (ROOT / "engel_ai_main_api_client.py").is_file())
    check("client_refuses_http", "HTTP is refused" in client)
    check("client_refuses_embedded_key", "BEGIN OPENSSH PRIVATE KEY" in client)
    check("client_uses_ssh_stdio", "ssh_stdio" in client and "BatchMode=yes" in client)
    check("client_has_no_http_server", "HTTPServer" not in client and "urlopen" not in client)
    check("client_shell_quotes_remote_command", "shlex.join" in client and "Quote each word" in client)
    check("client_verifies_host_keys_by_default", 'StrictHostKeyChecking=" + policy' in client and 'or "yes"' in client)
    check("client_has_structured_process_errors", "request_timeout" in client and "process_start_failed" in client)
    check("client_accepts_utf8_bom", 'lstrip("\\ufeff")' in client)

    example = json.loads((SRC / "config.example.json").read_text(encoding="utf-8"))
    dumped = json.dumps(example)
    check("example_has_placeholders", "YOUR-ENGEL-HOST" in dumped and "YOUR-SSH-USER" in dumped)
    check("example_has_no_private_key", "BEGIN " not in dumped and example["ssh"]["key_path"] == "")
    check("example_transport_is_ssh_stdio", example.get("transport") == "ssh_stdio")
    cmd_wrapper = (SRC / "Engel-AI-Main-API.cmd").read_text(encoding="utf-8", errors="replace")
    check("windows_wrapper_uses_python3_launcher", "py -3" in cmd_wrapper and "Python 3 on PATH" in cmd_wrapper)

    zips = sorted(DIST.glob("EngelAI-Main-CLI-API-*.zip"), key=lambda path: path.stat().st_mtime)
    check("zip_exists", bool(zips))
    if zips:
        latest_zip = zips[-1]
        sidecar = latest_zip.with_suffix(latest_zip.suffix + ".sha256")
        digest = hashlib.sha256(latest_zip.read_bytes()).hexdigest()
        sidecar_text = sidecar.read_text(encoding="ascii").strip() if sidecar.is_file() else ""
        check("zip_checksum_sidecar_exists", sidecar.is_file())
        check("zip_checksum_matches", bool(re.fullmatch(r"[0-9a-f]{64}  " + re.escape(latest_zip.name), sidecar_text, re.IGNORECASE)) and sidecar_text.split()[0].casefold() == digest)
        with zipfile.ZipFile(latest_zip) as zf:
            names = zf.namelist()
            blob = " ".join(zf.read(name).decode("utf-8", "replace") for name in names if not name.endswith("/"))
            readme = zf.read("EngelAI-Main-CLI-API/README.md").decode("utf-8", "replace")
            example = zf.read("EngelAI-Main-CLI-API/config.example.json").decode("utf-8", "replace")
            manifest_text = zf.read("EngelAI-Main-CLI-API/PACKAGE_MANIFEST.json").decode("utf-8", "replace")
            checksums_text = zf.read("EngelAI-Main-CLI-API/SHA256SUMS.txt").decode("utf-8", "replace")
            modes = {
                info.filename.rsplit("/", 1)[-1]: (info.external_attr >> 16) & 0o777
                for info in zf.infolist()
            }
            member_bytes = {name: zf.read(name) for name in names}
        check("zip_has_client", any(name.endswith("engel_ai_main_api_client.py") for name in names))
        check("zip_has_readme", any(name.endswith("README.md") for name in names))
        check("zip_has_example_config", any(name.endswith("config.example.json") for name in names))
        check("zip_has_package_manifest", any(name.endswith("PACKAGE_MANIFEST.json") for name in names))
        check("zip_has_payload_checksums", any(name.endswith("SHA256SUMS.txt") for name in names))
        check("readme_has_no_http_url", "http://" not in readme.casefold() and "https://" not in readme.casefold())
        check("example_has_no_http_url", "http://" not in example.casefold() and "https://" not in example.casefold())
        check("zip_has_no_private_key_block", "-----BEGIN" not in example and "-----BEGIN" not in readme)
        check("zip_has_no_token_word_assignment", "DISCORD_BOT_TOKEN" not in blob and "API_KEY=" not in blob)
        try:
            manifest = json.loads(manifest_text)
        except json.JSONDecodeError:
            manifest = {}
        check("manifest_is_client_only", manifest.get("package_kind") == "client_only" and manifest.get("http") is False)
        check("manifest_documents_full_local_runtime", "complete Engel App source tree" in json.dumps(manifest))
        checksum_rows = {}
        for line in checksums_text.splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2:
                checksum_rows[parts[1].strip()] = parts[0].casefold()
        checksum_ok = True
        for name, expected in checksum_rows.items():
            member = "EngelAI-Main-CLI-API/" + name
            if member not in names:
                checksum_ok = False
                continue
            checksum_ok = checksum_ok and hashlib.sha256(member_bytes[member]).hexdigest() == expected
        check("payload_checksums_match", bool(checksum_rows) and checksum_ok)
        check("shell_wrapper_is_executable", modes.get("Engel-AI-Main-API.sh", 0) & 0o111 == 0o111)

    import sys
    sys.path.insert(0, str(ROOT))
    from engel_ai_main_api_client import call, example_config, load_config

    cfg = example_config()
    check("example_config_schema", cfg.get("schema") == "engel_ai_main_api_client_v1")
    with tempfile.TemporaryDirectory(prefix="engel-cli-bom-") as temp_dir:
        bom_config_path = Path(temp_dir) / "config.json"
        bom_config_path.write_text("\ufeff" + json.dumps(cfg), encoding="utf-8")
        try:
            bom_config = load_config(bom_config_path)
        except Exception:
            bom_config = {}
    check("config_accepts_utf8_bom", bom_config.get("schema") == "engel_ai_main_api_client_v1")
    try:
        call("ping", config_path=SRC / "config.example.json")
        placeholder_blocked = False
    except Exception as exc:
        placeholder_blocked = "Fill ssh.host" in str(exc)
    check("placeholder_config_does_not_connect", placeholder_blocked)
    http_cfg = SRC / "config.example.json"
    # HTTP transport must fail closed without running a server.
    try:
        from engel_ai_main_api_client import _refuse_http

        _refuse_http({"transport": "http", "ssh": {}})
        http_blocked = False
    except Exception as exc:
        http_blocked = "HTTP is refused" in str(exc)
    check("http_transport_is_refused", http_blocked)
    # Prove remote paths are quoted as one shell-safe command string without
    # opening an SSH connection.
    from engel_ai_main_api_client import _ssh_command

    safe_cfg = example_config()
    safe_cfg["ssh"].update({"host": "engel.example", "user": "operator"})
    remote = ["/opt/engel runtime/python", "/opt/engel/api;printf BAD", "chat"]
    command = _ssh_command(safe_cfg, remote)
    try:
        round_trip = shlex.split(command[-1])
    except ValueError:
        round_trip = []
    check("remote_command_is_shell_quoted", command[-1] == shlex.join(remote) and round_trip == remote)
    try:
        _ssh_command({**safe_cfg, "ssh": {**safe_cfg["ssh"], "host": "evil;echo BAD"}}, ["python", "api", "ping"])
        endpoint_blocked = False
    except ValueError:
        endpoint_blocked = True
    check("unsafe_ssh_endpoint_is_refused", endpoint_blocked)

    # A failed child process must not be promoted to success merely because it
    # printed an optimistic JSON envelope.
    import subprocess
    import types
    import engel_ai_main_api_client as client_module

    original_run = client_module.subprocess.run
    client_module.subprocess.run = lambda *args, **kwargs: types.SimpleNamespace(
        returncode=7, stdout=json.dumps({"ok": True, "http": False, "text": "connected"}), stderr=""
    )
    try:
        transport_result = client_module._run(["fake"], timeout=1)
    finally:
        client_module.subprocess.run = original_run
    check("nonzero_child_cannot_report_success", transport_result.get("ok") is False and transport_result.get("error_code") == "transport_exit")
    client_module.subprocess.run = lambda *args, **kwargs: types.SimpleNamespace(
        returncode=0, stdout=json.dumps({"ok": True, "http": True, "text": "unexpected HTTP-shaped reply"}), stderr=""
    )
    try:
        invalid_transport_result = client_module._run(["fake"], timeout=1)
    finally:
        client_module.subprocess.run = original_run
    check(
        "invalid_transport_envelope_cannot_report_success",
        invalid_transport_result.get("ok") is False
        and invalid_transport_result.get("error_code") == "invalid_transport"
        and invalid_transport_result.get("http") is False,
    )
    client_module.subprocess.run = lambda *args, **kwargs: types.SimpleNamespace(
        returncode=0,
        stdout="\ufeff" + json.dumps({"ok": True, "http": False, "text": "connected"}),
        stderr="",
    )
    try:
        bom_result = client_module._run(["fake"], timeout=1)
    finally:
        client_module.subprocess.run = original_run
    check(
        "bom_stdio_envelope_is_accepted",
        bom_result.get("ok") is True
        and bom_result.get("text") == "connected"
        and bom_result.get("http") is False,
    )
    del http_cfg

    failed = [name for name, ok in checks if not ok]
    if failed:
        print("ENGEL_AI_MAIN_CLI_API_SHARE_VERIFY_FAIL")
        return 1
    print(f"ENGEL_AI_MAIN_CLI_API_SHARE_VERIFY_PASS {len(checks)}/{len(checks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
