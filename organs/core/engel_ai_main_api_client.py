"""Portable Engel AI Main CLI client for another computer.

No HTTP. The other computer talks to Engel AI Main by:
- local stdio, if Engel App is on that same computer, or
- SSH stdio, if Josh granted a key-based login to the Engel host.

Never store passwords or private keys in this folder. Point key_path at an
existing OpenSSH key file the operator already created.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA = "engel_ai_main_api_client_v1"
EXAMPLE_NAME = "config.example.json"
CONFIG_NAME = "config.json"


def _here() -> Path:
    return Path(__file__).resolve().parent


def example_config() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "transport": "ssh_stdio",
        "ssh": {
            "host": "YOUR-ENGEL-HOST",
            "port": 22,
            "user": "YOUR-SSH-USER",
            "key_path": "",
            "remote_python": "/opt/engel/.venv/bin/python",
            "remote_api": "/opt/engel/engel_ai_main_api.py",
            "strict_host_key_checking": "yes",
            "known_hosts": "",
        },
        "notes": [
            "transport must be ssh_stdio or local_stdio. HTTP is refused.",
            "key_path is a path to YOUR key file. Leave empty to use ssh-agent.",
            "SSH host keys are verified (StrictHostKeyChecking=yes) by default.",
            "Set known_hosts to an operator-managed file when a dedicated key list is needed.",
            "Do not paste private key text into this file.",
        ],
    }


def load_config(path: Path | None = None) -> dict[str, Any]:
    target = path or (_here() / CONFIG_NAME)
    if not target.is_file():
        example = _here() / EXAMPLE_NAME
        if example.is_file():
            return json.loads(example.read_text(encoding="utf-8-sig"))
        return example_config()
    # `utf-8-sig` remains identical for ordinary UTF-8 and also accepts a
    # BOM emitted by common Windows editors, keeping copied configs usable.
    data = json.loads(target.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("config.json must be an object.")
    return data


def _refuse_http(config: dict[str, Any]) -> None:
    transport = str(config.get("transport") or "").strip().casefold()
    if transport in {"http", "https", "http_stdio", "rest", "url"}:
        raise ValueError("HTTP is refused. Use ssh_stdio or local_stdio.")
    dumped = json.dumps(config).casefold()
    if "http://" in dumped or "https://" in dumped:
        raise ValueError("HTTP URLs are refused in Engel AI Main CLI client config.")


def _refuse_embedded_key(config: dict[str, Any]) -> None:
    blob = json.dumps(config)
    if "BEGIN OPENSSH PRIVATE KEY" in blob or "BEGIN RSA PRIVATE KEY" in blob:
        raise ValueError("Do not put a private key in config.json. Use key_path only.")


def _reject_control_chars(value: str, label: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{label} must not be empty.")
    if any(ord(char) < 32 or ord(char) == 127 for char in clean):
        raise ValueError(f"{label} contains an unsupported control character.")
    return clean


def _validate_ssh_endpoint(user: str, host: str) -> tuple[str, str]:
    user = _reject_control_chars(user, "ssh.user")
    host = _reject_control_chars(host, "ssh.host")
    if user == "YOUR-SSH-USER" or host == "YOUR-ENGEL-HOST":
        raise ValueError("Fill ssh.host and ssh.user in config.json before connecting.")
    # Keep the destination a single SSH target.  Shell metacharacters, spaces,
    # and an embedded @ are never valid here; IPv6 may be bracketed.
    if not re.fullmatch(r"[A-Za-z0-9._-]+", user):
        raise ValueError("ssh.user contains unsupported characters.")
    if not re.fullmatch(r"(?:[A-Za-z0-9._:-]+|\[[0-9A-Fa-f:]+\])", host):
        raise ValueError("ssh.host contains unsupported characters.")
    return user, host


def _remote_word(value: Any, label: str) -> str:
    return _reject_control_chars(str(value or ""), label)


def _ssh_command(config: dict[str, Any], remote_command: list[str]) -> list[str]:
    ssh = config.get("ssh") if isinstance(config.get("ssh"), dict) else {}
    user, host = _validate_ssh_endpoint(
        str(ssh.get("user") or ""), str(ssh.get("host") or "")
    )
    try:
        port = int(ssh.get("port") or 22)
    except (TypeError, ValueError) as exc:
        raise ValueError("ssh.port must be an integer.") from exc
    if not 1 <= port <= 65535:
        raise ValueError("ssh.port must be between 1 and 65535.")
    raw_key_path = str(ssh.get("key_path") or "").strip()
    key_path = _reject_control_chars(raw_key_path, "ssh.key_path") if raw_key_path else ""
    policy = str(ssh.get("strict_host_key_checking") or "yes").strip().casefold()
    if policy not in {"yes", "accept-new"}:
        raise ValueError("ssh.strict_host_key_checking must be 'yes' or 'accept-new'.")
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=" + policy,
        "-p",
        str(port),
    ]
    if key_path:
        key = Path(key_path).expanduser()
        if not key.is_file():
            raise ValueError("ssh.key_path does not exist: " + str(key))
        command.extend(["-i", str(key)])
    raw_known_hosts = str(ssh.get("known_hosts") or "").strip()
    known_hosts = _reject_control_chars(raw_known_hosts, "ssh.known_hosts") if raw_known_hosts else ""
    if known_hosts:
        known_hosts_file = Path(known_hosts).expanduser()
        if not known_hosts_file.is_file():
            raise ValueError("ssh.known_hosts does not exist: " + str(known_hosts_file))
        command.extend(["-o", "UserKnownHostsFile=" + str(known_hosts_file)])
    command.append(user + "@" + host)
    if not remote_command or any("\x00" in str(item) for item in remote_command):
        raise ValueError("remote command must contain at least one safe argument.")
    # OpenSSH invokes a remote shell for the command string.  Quote each word
    # before joining so spaces, quotes, semicolons, and substitutions in a
    # configured path cannot change what executes on the host.
    safe_remote = [_remote_word(item, "remote command argument") for item in remote_command]
    command.append(shlex.join(safe_remote))
    return command


def _run(
    command: list[str],
    stdin_text: str = "",
    timeout: int = 90,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            input=stdin_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(1, min(600, int(timeout))),
            check=False,
            cwd=cwd,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "text": "Engel AI Main did not finish before the local request timeout.",
            "error": "request_timeout",
            "error_code": "request_timeout",
            "http": False,
            "exit_code": None,
        }
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "text": "Engel AI Main CLI runtime could not be started.",
            "error": "runtime_not_found",
            "error_code": "runtime_not_found",
            "error_detail": str(exc),
            "http": False,
            "exit_code": None,
        }
    except OSError as exc:
        return {
            "ok": False,
            "text": "Engel AI Main CLI runtime could not be started.",
            "error": type(exc).__name__,
            "error_code": "process_start_failed",
            "error_detail": str(exc),
            "http": False,
            "exit_code": None,
        }
    # A remote/native Windows stdio hop may prefix its UTF-8 JSON with a BOM
    # (PowerShell does this for piped native output).  Strip only that marker
    # so the client still accepts the documented JSON envelope.
    stdout = str(completed.stdout or "").lstrip("\ufeff").strip()
    stderr = str(completed.stderr or "").strip()
    payload: dict[str, Any]
    try:
        payload = json.loads(stdout.splitlines()[-1] if stdout else "")
    except Exception:
        payload = {
            "ok": False,
            "text": "Engel AI Main returned no usable JSON reply.",
            "error": "unusable_reply",
            "error_code": "unusable_reply",
            "stdout": stdout[-2000:],
            "stderr": stderr[-2000:],
            "http": False,
        }
    if not isinstance(payload, dict):
        payload = {
            "ok": False,
            "text": "Engel AI Main returned an invalid reply object.",
            "error": "unusable_reply",
            "error_code": "unusable_reply",
            "http": False,
        }
    if payload.get("http") is not False:
        # The local API contract is explicitly stdio-only.  Do not let a
        # malformed or unexpected remote reply (including an HTTP-shaped
        # payload) be relabeled as a successful local response.
        payload = {
            "ok": False,
            "text": "Engel AI Main returned an invalid transport envelope.",
            "error": "invalid_transport",
            "error_code": "invalid_transport",
            "http": False,
        }
    payload["exit_code"] = completed.returncode
    payload["http"] = False
    if completed.returncode != 0 and payload.get("ok") is True:
        # A successful-looking JSON envelope cannot override a failed SSH or
        # interpreter process.  Preserve the original payload for diagnostics.
        payload["ok"] = False
        payload["error"] = "transport_exit"
        payload["error_code"] = "transport_exit"
        payload["error_detail"] = "remote process exited with code " + str(completed.returncode)
    return payload


def _local_python_and_api() -> tuple[Path, Path] | None:
    here = _here()
    api = here / "engel_ai_main_api.py"
    if not api.is_file():
        for env_name in ("ENGEL_ROOT", "ENGEL_APP_ROOT", "ENGEL_PROJECT_ROOT"):
            env_root = str(os.environ.get(env_name) or "").strip()
            if env_root:
                candidate = Path(env_root).expanduser() / "engel_ai_main_api.py"
                if candidate.is_file():
                    api = candidate
                    break
    if not api.is_file():
        return None
    python = api.parent / "runtime" / "python310" / "python.exe"
    if python.is_file():
        return python, api
    discovered = os.environ.get("PYTHON") or sys.executable
    return Path(discovered), api


def call(command: str, *, prompt: str = "", system: str = "", config_path: Path | None = None) -> dict[str, Any]:
    if command not in {"ping", "status", "chat"}:
        raise ValueError("command must be ping, status, or chat.")
    config = load_config(config_path)
    _refuse_http(config)
    _refuse_embedded_key(config)
    transport = str(config.get("transport") or "ssh_stdio").strip().casefold()
    if transport == "local_stdio":
        pair = _local_python_and_api()
        if pair is None:
            raise ValueError(
                "local_stdio needs the full Engel App root (engel_ai_main_api.py and its source modules) "
                "next to this client or in ENGEL_ROOT/ENGEL_APP_ROOT."
            )
        python, api = pair
        argv = [str(python), str(api), command]
        stdin_text = ""
        if command == "chat":
            stdin_text = json.dumps({"prompt": prompt, "system": system}, ensure_ascii=False)
        local_env = dict(os.environ)
        root_text = str(api.parent)
        old_pythonpath = str(local_env.get("PYTHONPATH") or "").strip()
        local_env["PYTHONPATH"] = root_text + (os.pathsep + old_pythonpath if old_pythonpath else "")
        return _run(argv, stdin_text, cwd=root_text, env=local_env)
    if transport != "ssh_stdio":
        raise ValueError("transport must be ssh_stdio or local_stdio.")
    ssh = config.get("ssh") if isinstance(config.get("ssh"), dict) else {}
    remote_python = str(ssh.get("remote_python") or "/opt/engel/.venv/bin/python")
    remote_api = str(ssh.get("remote_api") or "/opt/engel/engel_ai_main_api.py")
    remote = [remote_python, remote_api, command]
    stdin_text = ""
    if command == "chat":
        stdin_text = json.dumps({"prompt": prompt, "system": system}, ensure_ascii=False)
    return _run(_ssh_command(config, remote), stdin_text)


def _write_json(payload: dict[str, Any]) -> None:
    """Emit valid UTF-8/ASCII JSON on both modern and legacy consoles."""
    stream = sys.stdout
    try:
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, OSError, ValueError):
        pass
    try:
        stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except UnicodeEncodeError:
        stream.write(json.dumps(payload, ensure_ascii=True) + "\n")
    stream.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Call Engel AI Main from another computer without HTTP."
    )
    parser.add_argument("command", choices=("ping", "status", "chat", "write-example-config"))
    parser.add_argument("--prompt", default="", help="chat prompt")
    parser.add_argument("--system", default="", help="optional chat system text")
    parser.add_argument("--config", default="", help="path to config.json")
    args = parser.parse_args(argv)
    if args.command == "write-example-config":
        path = _here() / EXAMPLE_NAME
        path.write_text(json.dumps(example_config(), indent=2) + "\n", encoding="utf-8")
        sys.stdout.write(str(path) + "\n")
        return 0
    config_path = Path(args.config).expanduser() if args.config else None
    try:
        result = call(
            args.command,
            prompt=args.prompt,
            system=args.system,
            config_path=config_path,
        )
    except Exception as exc:
        _write_json({"ok": False, "error": str(exc), "error_code": "client_config_error", "http": False})
        return 1
    _write_json(result)
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
