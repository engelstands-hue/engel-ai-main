#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import traceback
from typing import Any
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
GROK_EXE = Path(
    os.environ.get(
        "ENGEL_GROK_CLI_EXE",
        str(ROOT / "runtime" / "xai_grok_cli" / "bin" / "grok.exe"),
    )
)
REPORT_DIR = ROOT / "reports" / "grok_cli_bridge"
CHAT_WORKSPACE = Path(
    os.environ.get("ENGEL_GROK_CLI_CHAT_WORKSPACE", str(ROOT.parent / "EngelGrokCliChatWorkspace"))
)
PROVIDER_BRIDGE_ENV_FILE = Path(
    os.environ.get("ENGEL_PROVIDER_BRIDGE_ENV_FILE", str(ROOT / "run" / "secrets" / "provider_bridges.env"))
)
CONNECTOR_PROFILE_PATH = ROOT / "runtime" / "connector_profiles" / "providers" / "xai.json"
DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("ENGEL_GROK_CLI_REQUEST_TIMEOUT_SECONDS", "180") or "180")
DEFAULT_MODEL = os.environ.get("ENGEL_GROK_CLI_MODEL", "grok-4.6").strip() or "grok-4.6"
CHAT_ATTACHMENTS_DIR = ROOT / "runtime" / "chat_attachments"
INLINE_IMAGE_MAX_BYTES = int(os.environ.get("ENGEL_GROK_INLINE_IMAGE_MAX_BYTES", str(2 * 1024 * 1024)) or str(2 * 1024 * 1024))
INLINE_JSON_MAX_BYTES = int(os.environ.get("ENGEL_GROK_INLINE_JSON_MAX_BYTES", str(12 * 1024 * 1024)) or str(12 * 1024 * 1024))
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
XAI_API_URL = os.environ.get("ENGEL_XAI_CHAT_COMPLETIONS_URL", "https://api.x.ai/v1/chat/completions").strip()
SECRET_NAMES = ["ENGEL_XAI_API_KEY", "XAI_API_KEY", "ENGEL_GROK_API_KEY", "GROK_API_KEY"]
MODEL_ENV_NAMES = ["ENGEL_XAI_CHAT_MODEL", "ENGEL_GROK_MODEL", "XAI_MODEL", "GROK_MODEL"]
API_MODEL_FALLBACKS = ["grok-4.6", "grok-4.5"]
SESSION_AUTH_PATH = ROOT / ".grok" / "auth.json"
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
PATH_SPLIT_RE = re.compile(r";+")


def _existing_dir(path: Path) -> str:
    try:
        if path.is_dir():
            return str(path)
    except OSError:
        return ""
    return ""


def _known_git_dirs() -> list[str]:
    candidates = [
        ROOT / "runtime" / "git" / "cmd",
        ROOT / "runtime" / "git" / "bin",
        ROOT / "runtime" / "tools" / "git" / "cmd",
        ROOT.parent / "flutter_local_sdk" / "bin" / "mingit" / "cmd",
        ROOT.parent / "flutter_local_sdk" / "bin" / "mingit" / "mingw64" / "bin",
        ROOT.parent / "flutter_windows_3.41.9-stable" / "flutter" / "bin" / "mingit" / "cmd",
        ROOT.parent / "flutter_windows_3.41.9-stable" / "flutter" / "bin" / "mingit" / "mingw64" / "bin",
        Path(r"C:\Program Files\Git\cmd"),
        Path(r"C:\Program Files\Git\bin"),
        Path(r"C:\Program Files (x86)\Git\cmd"),
        Path(r"C:\Program Files (x86)\Git\bin"),
    ]
    dirs: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        text = _existing_dir(candidate)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        dirs.append(text)
    return dirs


def _clean_path(path_text: str) -> tuple[str, list[str]]:
    entries = [entry.strip() for entry in PATH_SPLIT_RE.split(path_text or "") if entry.strip()]
    clean: list[str] = []
    dropped: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        expanded = os.path.expandvars(entry)
        if not Path(expanded).exists():
            dropped.append(entry)
            continue
        key = expanded.casefold()
        if key in seen:
            continue
        seen.add(key)
        clean.append(entry)
    for entry in reversed(_known_git_dirs() + [str(GROK_EXE.parent)]):
        key = entry.casefold()
        if key not in {item.casefold() for item in clean}:
            clean.insert(0, entry)
    return os.pathsep.join(clean), dropped


def _read_env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    if not PROVIDER_BRIDGE_ENV_FILE.is_file():
        return values
    try:
        for raw in PROVIDER_BRIDGE_ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            name = name.strip()
            value = value.strip().strip('"').strip("'")
            if name:
                values[name] = value
    except Exception:
        return values
    return values


def _read_windows_registry_env(names: list[str]) -> dict[str, tuple[str, str]]:
    if os.name != "nt":
        return {}
    try:
        import winreg  # type: ignore
    except Exception:
        return {}
    locations = [
        ("user_env_registry", winreg.HKEY_CURRENT_USER, r"Environment"),
        (
            "machine_env_registry",
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    ]
    values: dict[str, tuple[str, str]] = {}
    for source_type, hive, subkey in locations:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                for name in names:
                    if name in values:
                        continue
                    try:
                        value, _kind = winreg.QueryValueEx(key, name)
                    except OSError:
                        continue
                    text = str(value or "").strip()
                    if text:
                        values[name] = (text, source_type)
        except OSError:
            continue
    return values


def _secret_source() -> dict[str, Any]:
    for name in SECRET_NAMES:
        value = os.environ.get(name, "")
        if value:
            return {
                "present": True,
                "secret": value,
                "source_type": "process_env",
                "name": name,
                "path": "",
                "value_length": len(value),
            }
    registry_values = _read_windows_registry_env(SECRET_NAMES)
    for name in SECRET_NAMES:
        found = registry_values.get(name)
        if not found:
            continue
        value, source_type = found
        return {
            "present": True,
            "secret": value,
            "source_type": source_type,
            "name": name,
            "path": "",
            "value_length": len(value),
        }
    env_values = _read_env_file()
    for name in SECRET_NAMES:
        value = env_values.get(name, "")
        if value:
            return {
                "present": True,
                "secret": value,
                "source_type": "env_file",
                "name": name,
                "path": str(PROVIDER_BRIDGE_ENV_FILE),
                "value_length": len(value),
            }
    return {"present": False, "secret": "", "source_type": "", "name": "", "path": "", "value_length": 0}


def _public_secret_source(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "present": bool(source.get("present") is True),
        "source_type": source.get("source_type", ""),
        "name": source.get("name", ""),
        "path": source.get("path", ""),
        "value_length": int(source.get("value_length") or 0),
    }


def _session_auth_present() -> bool:
    """Super/grok.com login lives in Engel App\\.grok (C: Users\\.grok is a junction)."""
    try:
        return SESSION_AUTH_PATH.is_file() and SESSION_AUTH_PATH.stat().st_size > 20
    except OSError:
        return False


def _allowed_account_home(path_text: str) -> Path | None:
    raw = str(path_text or "").strip()
    if not raw:
        return None
    try:
        home = Path(raw).resolve()
        allowed = (
            ROOT.resolve(),
            (ROOT / "runtime" / "xai_grok_cli" / "accounts").resolve(),
            (ROOT / "runtime" / "cli_accounts").resolve(),
        )
        home_s = str(home)
        if any(home_s == str(root) or home_s.startswith(str(root) + os.sep) for root in allowed):
            if home.is_dir() or home == ROOT.resolve():
                return home
    except OSError:
        return None
    return None


def _grok_env(account_home: str = "") -> tuple[dict[str, str], list[str]]:
    env = dict(os.environ)
    home = _allowed_account_home(account_home) or ROOT
    # Primary Super session is ROOT\\.grok. Extra accounts use their own USERPROFILE.
    env["USERPROFILE"] = str(home)
    env["GROK_BIN_DIR"] = str(_grok_exe_path().parent)
    env.setdefault("NO_COLOR", "1")
    env["Path"], dropped = _clean_path(env.get("Path") or env.get("PATH") or "")
    env["PATH"] = env["Path"]
    return env, dropped


def _git_status(env: dict[str, str] | None = None) -> dict[str, Any]:
    found = shutil.which("git", path=(env or os.environ).get("Path") or (env or os.environ).get("PATH"))
    version = ""
    ok = False
    if found:
        try:
            raw = subprocess.run(
                [found, "--version"],
                cwd=str(ROOT),
                env=env,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=10,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            version = _clip(_strip_ansi(raw.stdout), 300)
            ok = raw.returncode == 0
        except Exception as exc:
            version = _clip(str(exc), 300)
    return {"ok": ok, "path": found or "", "version": version}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _clip(value: Any, limit: int = 4000) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "...[clipped]"


def _strip_ansi(value: str) -> str:
    return ANSI_RE.sub("", value).replace("\r\n", "\n").replace("\r", "\n").strip()


def _canonical_grok_model(value: str) -> str:
    text = str(value or "").strip()
    aliases = {
        "grok-4.6": "grok-4.6",
        "grok-4-6": "grok-4.6",
        "grok46": "grok-4.6",
        "grok-4-3-max": "grok-4.6",
        "grok-4.3-max": "grok-4.6",
        "grok-build": "grok-4.6",
        "grok-build-0-1": "grok-4.6",
        "grok-build-0.1": "grok-4.6",
        "grok-4.5": "grok-4.5",
        "grok-4-5": "grok-4.5",
    }
    return aliases.get(text.casefold(), text or DEFAULT_MODEL)


def _env_truth(name: str, *, default: bool = False) -> bool:
    raw = str(os.environ.get(name, "")).strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "no", "off"}


def _model_candidates(request: dict[str, Any] | None = None) -> list[str]:
    candidates: list[str] = []
    if isinstance(request, dict):
        requested = str(request.get("model") or request.get("provider_model") or "").strip()
        if requested and requested not in {"auto", "auto-best"}:
            if requested.startswith("grok-composer-"):
                requested = DEFAULT_MODEL
            candidates.append(_canonical_grok_model(requested))
    registry_values = _read_windows_registry_env(MODEL_ENV_NAMES)
    for name in MODEL_ENV_NAMES:
        value = str(os.environ.get(name) or "").strip()
        if not value and name in registry_values:
            value = str(registry_values[name][0] or "").strip()
        if value:
            candidates.append(value)
    candidates.extend(API_MODEL_FALLBACKS)
    deduped: list[str] = []
    for item in candidates:
        if item and item not in deduped:
            deduped.append(item)
    return deduped


def _provider_http_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            parsed = json.loads(resp.read().decode("utf-8", errors="replace"))
        return {"ok": True, "status_code": 200, "json": parsed if isinstance(parsed, dict) else {}}
    except urllib.error.HTTPError as exc:
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            error_body = ""
        return {"ok": False, "status_code": exc.code, "error": _clip(error_body or str(exc), 1400)}
    except Exception as exc:
        return {"ok": False, "status_code": 0, "error": _clip(str(exc), 1400)}


def _summarize_cli_error(value: str) -> str:
    text = _strip_ansi(value)
    low = text.casefold()
    if (
        "spending-limit" in low
        or "run out of credits" in low
        or "need a grok subscription" in low
        or "limits outage" in low
        or "limits being reached" in low
        or "elevated errors related to limits" in low
    ):
        return (
            "Grok CLI reached xAI but xAI returned a limits outage or spending/subscription gate. "
            "Wait for the xAI limit outage to clear, add Grok credits/subscription, or save ENGEL_XAI_API_KEY for the API-backed bridge."
        )
    return _clip(text, 1000)


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or "0")
    if length <= 0:
        return {}
    if length > INLINE_JSON_MAX_BYTES:
        raise ValueError("JSON body exceeds image ingest cap")
    body = handler.rfile.read(length).decode("utf-8-sig", errors="replace")
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise ValueError("JSON body must be an object")
    return parsed


def _plain_chat_prompt_from_request(request: dict[str, Any]) -> str:
    return str(request.get("prompt") or request.get("message") or "").strip()


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Access-Control-Allow-Origin", "http://127.0.0.1")
    handler.end_headers()
    handler.wfile.write(body)


def _grok_exe_path() -> Path:
    if GROK_EXE.is_file():
        return GROK_EXE
    found = shutil.which("grok")
    return Path(found) if found else GROK_EXE


def _prompt_from_completion_request(request: dict[str, Any]) -> str:
    messages = request.get("messages")
    if not isinstance(messages, list):
        return str(request.get("prompt") or "").strip()
    parts: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "user").strip() or "user"
        content = message.get("content")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "\n".join(
                str(part.get("text") or "").strip()
                for part in content
                if isinstance(part, dict) and str(part.get("text") or "").strip()
            )
        else:
            text = ""
        if text.strip():
            parts.append(f"{role}: {text.strip()}")
    return "\n\n".join(parts).strip()


def _allowed_image_path(path: str) -> Path | None:
    text = str(path or "").strip()
    if not text:
        return None
    candidate = Path(text)
    try:
        resolved = candidate.resolve()
    except OSError:
        return None
    allowed_roots = [
        CHAT_ATTACHMENTS_DIR.resolve(),
        (ROOT / "runtime" / "chat_attachments").resolve(),
        CHAT_WORKSPACE.resolve(),
    ]
    for root in allowed_roots:
        try:
            resolved.relative_to(root)
        except ValueError:
            continue
        if resolved.is_file() and resolved.suffix.lower() in _IMAGE_EXTS:
            return resolved
    return None


def _safe_image_name(name: str) -> str:
    raw = Path(str(name or "image.png")).name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(raw).stem)[:80] or "image"
    suffix = Path(raw).suffix.lower()
    if suffix not in _IMAGE_EXTS:
        suffix = ".png"
    return stem + suffix


def _image_ext_from_magic(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:6] in {b"GIF87a", b"GIF89a"}:
        return ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def _decode_inline_image(value: Any) -> bytes:
    text = str(value or "").strip()
    if not text:
        return b""
    if "," in text and text.split(",", 1)[0].casefold().startswith("data:"):
        text = text.split(",", 1)[1].strip()
    if len(text) > INLINE_IMAGE_MAX_BYTES * 2:
        return b""
    try:
        blob = base64.b64decode(text.encode("ascii"), validate=False)
    except Exception:
        return b""
    if not blob or len(blob) > INLINE_IMAGE_MAX_BYTES:
        return b""
    return blob


CT246_ATTACH_PREFIX = "/opt/engel/memory/persistent_chat/attachments/"
CT246_SSH_HOST = str(os.environ.get("ENGEL_CT246_SSH_HOST", "192.0.2.50") or "192.0.2.50").strip()
CT246_SSH_PORT = str(os.environ.get("ENGEL_CT246_SSH_PORT", "24622") or "24622").strip()
CT246_SSH_USER = str(os.environ.get("ENGEL_CT246_SSH_USER", "root") or "root").strip()


def _ct246_ssh_key() -> Path | None:
    raw = str(os.environ.get("ENGEL_CT246_SSH_KEY") or "").strip()
    candidate = Path(raw) if raw else (Path.home() / ".ssh" / "engel_ai_main_ct246_ed25519")
    try:
        if candidate.is_file():
            return candidate
    except OSError:
        return None
    return None


def _safe_ct246_stored_path(path_text: str) -> str:
    text = str(path_text or "").replace("\\", "/").strip()
    if not text.startswith(CT246_ATTACH_PREFIX) or ".." in text:
        return ""
    return text


def pull_ct246_stored_images(request: dict[str, Any]) -> list[Path]:
    """Copy Discord stills from CT246 onto ROG chat_attachments. No image bytes in HTTP."""
    found: list[Path] = []
    key = _ct246_ssh_key()
    if key is None:
        return found
    items: list[Any] = []
    for raw in (request.get("attachments"), request.get("image_payloads")):
        if isinstance(raw, list):
            items.extend(raw)
    attach_root = CHAT_ATTACHMENTS_DIR.resolve()
    attach_root.mkdir(parents=True, exist_ok=True)
    ssh_exe = shutil.which("scp") or "scp"
    stamp = _stamp()
    for index, item in enumerate(items[:4]):
        if not isinstance(item, dict):
            continue
        remote = _safe_ct246_stored_path(str(item.get("stored_path") or item.get("path") or ""))
        if not remote:
            continue
        name = _safe_image_name(str(item.get("name") or Path(remote).name or f"image_{index + 1}.png"))
        target = (attach_root / f"discord_{stamp}_{index + 1}_{name}").resolve()
        try:
            target.relative_to(attach_root)
        except ValueError:
            continue
        spec = f"{CT246_SSH_USER}@{CT246_SSH_HOST}:{remote}"
        completed = subprocess.run(
            [
                ssh_exe,
                "-i",
                str(key),
                "-P",
                CT246_SSH_PORT,
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=yes",
                spec,
                str(target),
            ],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode == 0 and target.is_file() and target.stat().st_size > 32:
            found.append(target)
    return found


def ingest_inline_images(request: dict[str, Any]) -> list[Path]:
    """Write Discord/CT246 image bytes onto ROG chat_attachments so grok.exe can see them."""
    found: list[Path] = []
    items: list[Any] = []
    for raw in (request.get("attachments"), request.get("image_payloads")):
        if isinstance(raw, list):
            items.extend(raw)
    if not items:
        return found
    attach_root = CHAT_ATTACHMENTS_DIR.resolve()
    attach_root.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    for index, item in enumerate(items[:4]):
        if not isinstance(item, dict):
            continue
        mime = str(item.get("mime_type") or item.get("mime") or "").casefold()
        kind = str(item.get("kind") or "").casefold()
        name = str(item.get("name") or item.get("filename") or f"image_{index + 1}.png")
        looks_image = (
            mime.startswith("image/")
            or kind in {"image", "screenshot"}
            or Path(name).suffix.lower() in _IMAGE_EXTS
        )
        b64 = item.get("inline_base64") or item.get("base64") or ""
        if not looks_image or not b64:
            continue
        blob = _decode_inline_image(b64)
        ext = _image_ext_from_magic(blob)
        if not ext:
            continue
        safe = _safe_image_name(name)
        if Path(safe).suffix.lower() != ext:
            safe = Path(safe).stem + ext
        target = (attach_root / f"discord_{stamp}_{index + 1}_{safe}").resolve()
        try:
            target.relative_to(attach_root)
        except ValueError:
            continue
        target.write_bytes(blob)
        found.append(target)
    return found


def _image_paths_from_request(request: dict[str, Any]) -> list[Path]:
    found: list[Path] = []
    raw_lists = [request.get("image_paths"), request.get("attachments")]
    for raw in raw_lists:
        items = raw if isinstance(raw, list) else []
        for item in items:
            if isinstance(item, str):
                path = _allowed_image_path(item)
            elif isinstance(item, dict):
                path = _allowed_image_path(str(item.get("source_path") or item.get("path") or ""))
            else:
                path = None
            if path is not None and path not in found:
                found.append(path)
    for path in pull_ct246_stored_images(request):
        if path not in found:
            found.append(path)
    for path in ingest_inline_images(request):
        if path not in found:
            found.append(path)
    return found


def _ocr_image_text(path: Path) -> str:
    """Best-effort Windows OCR. Never required; empty string is fine."""
    if os.name != "nt":
        return ""
    script = (
        "$ErrorActionPreference='Stop';"
        "Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null;"
        "$null = [Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime];"
        "$null = [Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime];"
        "$null = [Windows.Media.Ocr.OcrEngine,Windows.Media.Ocr,ContentType=WindowsRuntime];"
        f"$file = [Windows.Storage.StorageFile]::GetFileFromPathAsync('{str(path).replace(chr(39), chr(39)+chr(39))}').GetAwaiter().GetResult();"
        "$stream = $file.OpenAsync([Windows.Storage.FileAccessMode]::Read).GetAwaiter().GetResult();"
        "$decoder = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream).GetAwaiter().GetResult();"
        "$bitmap = $decoder.GetSoftwareBitmapAsync().GetAwaiter().GetResult();"
        "$ocr = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages();"
        "if (-not $ocr) { exit 0 };"
        "$result = $ocr.RecognizeAsync($bitmap).GetAwaiter().GetResult();"
        "[Console]::Out.Write($result.Text)"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-STA", "-Command", script],
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=12,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return _clip(_strip_ansi(completed.stdout or ""), 2500)
    except Exception:
        return ""


def _chat_max_turns(request: dict[str, Any], *, images: bool) -> int:
    raw = request.get("max_turns")
    try:
        requested = int(raw) if raw not in (None, "") else 0
    except (TypeError, ValueError):
        requested = 0
    if requested > 0:
        return max(2, min(16, requested))
    if request.get("artifact_only") is True or str(request.get("lane") or "").casefold() == "build":
        return max(4, min(16, int(os.environ.get("ENGEL_GROK_BUILD_MAX_TURNS", "12") or "12")))
    default = "8" if images else "6"
    return max(2, min(16, int(os.environ.get("ENGEL_GROK_CHAT_MAX_TURNS", default) or default)))


_OPERATOR_WORK_VERBS = (
    "fix",
    "build",
    "create",
    "make",
    "wire",
    "pair",
    "connect",
    "repair",
    "implement",
    "recreate",
    "rebuild",
    "dispatch",
    "collab",
    "respond",
    "reply",
    "install",
    "update",
    "package",
    "verify",
    "launch",
    "open",
    "move",
    "send work",
    "stop looping",
    "name the gap",
    "engel work",
)


def normalize_discord_prompt(prompt: str) -> str:
    """Fold common Discord typos so Ask Engel cannot miss the live room."""
    text = " ".join(str(prompt or "").casefold().split())
    if text.startswith("engel work "):
        text = text[len("engel work ") :]
    for typo in ("dicord", "discrod", "discort", "disord", "discrd", "discordd"):
        text = text.replace(typo, "discord")
    return text


def owner_prompt_is_discord_work(prompt: str) -> bool:
    """True when Joshua wants Engel AI Main to use the live Discord collab room."""
    text = normalize_discord_prompt(prompt)
    if not text:
        return False
    if text.startswith(("what is", "what's", "whats", "tell me about", "explain", "why is")):
        return False
    if text in {"discord", "discord chat", "check out discord chat"}:
        return True
    if "discord" not in text and "#general" not in text:
        return False
    return any(
        marker in text
        for marker in (
            "check",
            "open",
            "look",
            "read",
            "show",
            "status",
            "chat",
            "thread",
            "repeat",
            "replies",
            "collab",
            "sub-engel",
            "sub engel",
            "reply",
            "respond",
            "tail",
        )
    )


def owner_prompt_is_operator_work(prompt: str) -> bool:
    """True when Joshua is giving Engel AI Main a job, not a casual question."""
    text = " ".join(str(prompt or "").casefold().split())
    if not text:
        return False
    if text.startswith("engel work") or text.startswith("engel solve"):
        return True
    if owner_prompt_is_discord_work(prompt):
        return True
    if any(marker in text for marker in _OPERATOR_WORK_VERBS):
        if text.startswith(("what is", "what's", "whats", "tell me about", "explain", "why is")):
            return False
        return True
    return False


def _image_prompt_block(image_paths: list[Path] | None) -> str:
    if not image_paths:
        return ""
    lines = [
        "Joshua attached screenshot(s). Look at the pixels and say what is on them.",
        "Use read_file on each path. Do not say the image has no readable text.",
    ]
    for path in image_paths:
        ocr = _ocr_image_text(path)
        lines.append(f"- {path}")
        if ocr:
            lines.append("Visible text from the screenshot:\n" + ocr)
    return "\n".join(lines)


def _engel_prompt(prompt: str, request: dict[str, Any], image_paths: list[Path] | None = None) -> str:
    image_block = _image_prompt_block(image_paths)
    if (
        request.get("artifact_only") is True
        or str(request.get("lane") or "").strip().casefold() == "build"
        or owner_prompt_is_operator_work(prompt)
    ):
        body = str(prompt or "").strip()
        extra = ("\n" + image_block + "\n") if image_block else ""
        return (
            "You are Engel AI Main, Joshua's operator console in the Engel AI Main app.\n"
            "Joshua's message is the work order. Do the work with tools. Do not send him "
            "to a terminal, PowerShell, or another app for work this surface can do.\n"
            "Do not say you cannot do it if a tool can do it. Do not claim files changed "
            "unless you actually used tools.\n"
            "Hard boundaries: no secrets in output, no live internet research, no autonomous "
            "background loops, no ALIVE_STATE writes, no C: project writes, no Proxmox disk "
            "mutation. Discord #general is Engel's own CT246 engel-discord-bridge collab room "
            "with Sub-Engel. It is not an MCP server. Never say Discord MCP is missing. "
            "Never call Sub-Engel Chase. Josh > Guardian > Engel/runtime. Joshua's current "
            "request is approval for this bounded task.\n"
            f"{extra}\n"
            f"Joshua: {body}"
        )
    instruction = str(request.get("system") or request.get("system_prompt") or "").strip()
    base = (
        "You are Engel AI Main speaking to Joshua through the Engel AI Main chat UI.\n"
        "Use Grok 4.6 as a chat brain. Reply naturally and directly.\n"
        "Discord collab uses Engel's own CT246 discord bridge in #general, not MCP.\n"
        "Do not claim you edited files or finished hidden work unless the prompt contains proof."
    )
    if image_block:
        base = base + "\n" + image_block
    if instruction:
        base = base + "\n" + instruction
    return f"{base}\n\nJoshua: {prompt}\n\nEngel:"


def _api_system_prompt(prompt: str, request: dict[str, Any]) -> str:
    instruction = str(request.get("system") or request.get("system_prompt") or "").strip()
    base = (
        "You are Engel AI Main, Joshua's operator console. When he asks you to do work, "
        "complete it. Do not send him to a terminal for work this surface can do. "
        "Do not claim files changed unless the turn actually used tools. "
        "Reply naturally and directly."
    )
    if instruction:
        base += " " + instruction.replace("\r", " ").replace("\n", " ")
    return base


def _run_xai_api(prompt: str, request: dict[str, Any], started: float) -> dict[str, Any]:
    source = _secret_source()
    if source.get("present") is not True:
        return {
            "ok": False,
            "status": "xAI API key missing",
            "assistant_reply": "",
            "provider": "Grok/xAI API on ROG",
            "runtime_provider": "",
            "selected_provider": "xai_api_bridge",
            "error": "No reachable ENGEL_XAI_API_KEY/XAI_API_KEY/ENGEL_GROK_API_KEY/GROK_API_KEY was found.",
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    secret = str(source.get("secret") or "")
    max_tokens = max(32, min(2000, int(request.get("max_tokens") or request.get("max_completion_tokens") or 650)))
    temperature = float(request.get("temperature") or 0.45)
    timeout = max(10.0, min(180.0, float(request.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)))
    attempts: list[dict[str, Any]] = []
    for model in _model_candidates(request):
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": _api_system_prompt(prompt, request)},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        result = _provider_http_json(XAI_API_URL, payload, {"Authorization": f"Bearer {secret}"}, timeout)
        attempts.append(
            {
                "provider": "xai",
                "model": model,
                "ok": result.get("ok"),
                "status_code": result.get("status_code"),
                "error": result.get("error", ""),
            }
        )
        if not result.get("ok"):
            continue
        data = result.get("json") if isinstance(result.get("json"), dict) else {}
        choices = data.get("choices") if isinstance(data.get("choices"), list) else []
        message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
        reply = str(message.get("content") or "").strip() if isinstance(message, dict) else ""
        if reply:
            return {
                "ok": True,
                "status": "xAI API replied",
                "assistant_reply": reply,
                "assistant_output_text": reply,
                "provider": "Grok/xAI API on ROG",
                "runtime_provider": model,
                "selected_provider": "xai_api_bridge",
                "model": model,
                "attempts": attempts,
                "secret_source": _public_secret_source(source),
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }
    return {
        "ok": False,
        "status": "xAI API did not return a usable reply",
        "assistant_reply": "",
        "provider": "Grok/xAI API on ROG",
        "runtime_provider": "",
        "selected_provider": "xai_api_bridge",
        "model": "",
        "attempts": attempts,
        "secret_source": _public_secret_source(source),
        "error": attempts[-1].get("error", "") if attempts else "no model candidates",
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }


def _bridge_status() -> dict[str, Any]:
    exe = _grok_exe_path()
    version = ""
    env, dropped_path_entries = _grok_env()
    source = _secret_source()
    secret_present = bool(source.get("present") is True)
    session_present = _session_auth_present()
    if exe.is_file():
        try:
            raw = subprocess.run(
                [str(exe), "--version"],
                cwd=str(ROOT),
                env=env,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=10,
                check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            version = _clip(_strip_ansi(raw.stdout), 300)
        except Exception as exc:
            version = _clip(str(exc), 300)
    return {
        "schema": "engel_grok_cli_bridge_status_v1",
        "ok": (exe.is_file() and session_present) or secret_present,
        "usable": (exe.is_file() and session_present) or secret_present,
        "provider": "xai",
        "provider_label": "Grok 4.6 Super CLI on ROG",
        "root": str(ROOT),
        "env_file_present": PROVIDER_BRIDGE_ENV_FILE.is_file(),
        "api_secret_present": secret_present,
        "secret_present": secret_present,
        "session_auth_present": session_present,
        "session_login": "grok.com" if session_present else "",
        "secret_source": _public_secret_source(source),
        "accepted_secret_names": SECRET_NAMES,
        "api_model_candidates": _model_candidates({}),
        "api_first": _env_truth("ENGEL_GROK_API_FIRST", default=False),
        "grok_exe": str(exe),
        "grok_exe_present": exe.is_file(),
        "default_model": DEFAULT_MODEL,
        "oauth_tokens_exposed": False,
        "writes_secrets": False,
        "chat_only": False,
        "owner_operator_console": True,
        "version": version,
        "git": _git_status(env),
        "clean_path_applied": True,
        "dropped_missing_path_entries": dropped_path_entries,
        "updated_at_utc": _iso_now(),
    }


def _run_grok(prompt: str, request: dict[str, Any], started: float) -> dict[str, Any]:
    account_home = str(request.get("account_home") or request.get("account_id_home") or "")
    if not account_home:
        try:
            from engel_provider_account_pool import pick_account

            acc = pick_account("grok")
            if acc:
                account_home = str(acc.get("home_dir") or "")
                request = dict(request)
                request["_account_id"] = acc.get("id")
        except Exception:
            account_home = ""
    exe = _grok_exe_path()
    source = _secret_source()
    operator_work = owner_prompt_is_operator_work(prompt) or str(
        request.get("lane") or ""
    ).casefold() == "build" or request.get("artifact_only") is True
    if (
        source.get("present") is True
        and _env_truth("ENGEL_GROK_API_FIRST", default=False)
        and not operator_work
    ):
        api_result = _run_xai_api(prompt, request, started)
        if api_result.get("ok") is True or not exe.is_file() or request.get("api_only") is True:
            return api_result
    if not exe.is_file():
        if source.get("present") is True:
            return _run_xai_api(prompt, request, started)
        return {
            "ok": False,
            "status": "grok CLI executable missing",
            "assistant_reply": "",
            "error": f"Grok CLI executable not found at {exe}",
        }
    CHAT_WORKSPACE.mkdir(parents=True, exist_ok=True)
    model = _canonical_grok_model(
        str(request.get("model") or request.get("provider_model") or DEFAULT_MODEL).strip()
    )
    image_paths = _image_paths_from_request(request)
    timeout = max(15.0, min(240.0, float(request.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)))
    is_build = (
        request.get("artifact_only") is True
        or str(request.get("lane") or "").casefold() == "build"
        or owner_prompt_is_operator_work(prompt)
    )
    if is_build and int(request.get("max_turns") or 0) <= 0:
        request = dict(request)
        request["max_turns"] = 12
    max_turns = _chat_max_turns(request, images=bool(image_paths))
    cli_prompt = _engel_prompt(prompt, request, image_paths)
    effort = str(
        request.get("effort")
        or os.environ.get("ENGEL_GROK_CHAT_EFFORT", "medium" if not is_build else "high")
        or "medium"
    ).strip() or "medium"
    work_root = ROOT if is_build else CHAT_WORKSPACE
    work_root.mkdir(parents=True, exist_ok=True)
    args = [
        str(exe),
        "--single",
        cli_prompt,
        "--output-format",
        "plain",
        "--cwd",
        str(work_root),
        "--max-turns",
        str(max_turns),
        "--no-alt-screen",
        "--no-subagents",
        "--no-memory",
        "--no-auto-update",
        "--no-plan",
        "--verbatim",
        "--effort",
        effort,
        "--disallowed-tools",
        (
            "web_search,web_fetch,Agent"
            if is_build
            else "run_terminal_cmd,search_replace,web_search,web_fetch,Agent"
        ),
    ]
    if image_paths:
        args.extend(["--tools", "read_file"])
        for path in image_paths:
            args.extend(["--allow", f"Read({path})"])
    if model:
        args.extend(["--model", model])
    if str(os.environ.get("ENGEL_GROK_CLI_DISABLE_WEB_SEARCH", "1")).strip().lower() not in {"0", "false", "no", "off"}:
        args.append("--disable-web-search")

    env, dropped_path_entries = _grok_env(account_home)
    try:
        completed = subprocess.run(
            args,
            cwd=str(work_root),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        output = _strip_ansi(completed.stdout or "")
        stderr = _strip_ansi(completed.stderr or "")
        cleaned_lines = [
            line
            for line in (output or "").splitlines()
            if "max turns reached" not in line.casefold()
        ]
        reply = "\n".join(cleaned_lines).strip()
        ok = bool(reply)
        return {
            "ok": ok,
            "status": "grok CLI replied" if ok else "grok CLI did not return a usable reply",
            "assistant_reply": reply,
            "assistant_output_text": reply,
            "provider": "Grok CLI on ROG",
            "runtime_provider": model,
            "selected_provider": "xai_grok_cli",
            "model": model,
            "max_turns": max_turns,
            "image_count": len(image_paths),
            "exit_code": completed.returncode,
            "error": "" if ok else _summarize_cli_error(stderr or output),
            "git": _git_status(env),
            "dropped_missing_path_entries": dropped_path_entries,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "status": "grok CLI timed out",
            "assistant_reply": "",
            "error": f"Timed out after {int(timeout)} seconds",
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "grok CLI failed",
            "assistant_reply": "",
            "error": _clip(str(exc), 1000),
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }


def _write_receipt(prompt: str, result: dict[str, Any]) -> str:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"ENGEL_GROK_CLI_BRIDGE_CHAT_{_stamp()}.json"
    payload = {
        "schema": "engel_grok_cli_bridge_chat_receipt_v1",
        "ok": result.get("ok") is True,
        "updated_at_utc": _iso_now(),
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_chars": len(prompt),
        "assistant_reply": result.get("assistant_reply", ""),
        "provider": result.get("provider", "Grok CLI on ROG"),
        "runtime_provider": result.get("runtime_provider", ""),
        "exit_code": result.get("exit_code"),
        "latency_ms": result.get("latency_ms"),
        "oauth_tokens_exposed": False,
        "secret_values_written": False,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _completion_response(request: dict[str, Any], reply: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "chatcmpl-engel-grok-cli-" + _stamp(),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": result.get("model") or DEFAULT_MODEL,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
        "engel": {
            "ok": result.get("ok") is True,
            "provider": result.get("provider", "Grok CLI on ROG"),
            "runtime_provider": result.get("runtime_provider", ""),
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "EngelGrokCliBridge/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[%s] %s\n" % (_iso_now(), fmt % args))
        sys.stderr.flush()

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path in {"/", "/health", "/status"}:
            _json_response(self, 200, _bridge_status())
            return
        _json_response(self, 404, {"ok": False, "status": "not found", "path": self.path})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path not in {"/chat", "/v1/chat/completions"}:
            _json_response(self, 404, {"ok": False, "status": "not found", "path": self.path})
            return
        started = time.perf_counter()
        try:
            request = _read_json(self)
            prompt = _prompt_from_completion_request(request) if path == "/v1/chat/completions" else _plain_chat_prompt_from_request(request)
            if not prompt:
                raise ValueError("prompt is empty")
            result = _run_grok(prompt, request, started)
            result["receipt_path"] = _write_receipt(prompt, result)
            if path == "/v1/chat/completions":
                _json_response(self, 200 if result.get("ok") is True else 502, _completion_response(request, str(result.get("assistant_reply") or ""), result))
                return
            payload = {
                "schema": "engel_grok_cli_bridge_chat_response_v1",
                "ok": result.get("ok") is True,
                "status": result.get("status", ""),
                "assistant_reply": result.get("assistant_reply", ""),
                "provider": result.get("provider", ""),
                "runtime_provider": result.get("runtime_provider", ""),
                "receipt": result,
                "updated_at_utc": _iso_now(),
            }
            _json_response(self, 200 if payload["ok"] else 502, payload)
        except Exception as exc:
            _json_response(
                self,
                500,
                {
                    "schema": "engel_grok_cli_bridge_chat_response_v1",
                    "ok": False,
                    "status": "grok CLI bridge service error",
                    "error": str(exc),
                    "traceback_tail": traceback.format_exc()[-2000:],
                    "updated_at_utc": _iso_now(),
                },
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engel ROG-local Grok CLI HTTP bridge.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=24880)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Engel Grok CLI bridge listening on {args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
