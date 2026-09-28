from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


DEFAULT_MEMORY_ROOT = Path(__file__).resolve().parents[1] / "runtime"
DEFAULT_ENGEL_HOME = DEFAULT_MEMORY_ROOT / "engel-home"
DEFAULT_RUNPOD_CONFIG = DEFAULT_MEMORY_ROOT / "runpod" / "engel_runpod_config.json"
DEFAULT_SECRET_PATH = DEFAULT_MEMORY_ROOT / "secrets" / "runpod_api_key.txt"
DEFAULT_PROVIDER_KEY = "runpod-engel"
DEFAULT_PROVIDER_NAME = "RunPod Engel"
DEFAULT_CONTEXT_LENGTH = 32768
LATEST_CONFIG_VERSION = 23


class ConfigError(RuntimeError):
    pass


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def is_os_drive(path: Path) -> bool:
    text = str(path).replace("/", "\\").lower()
    return text.startswith("c:\\") or text.startswith("\\\\?\\c:\\")


def require_off_c(path: Path, label: str) -> None:
    if is_os_drive(path):
        raise ConfigError(f"refusing {label} on C: because C: is OS-only: {path}")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"missing RunPod config: {path}")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ConfigError(f"RunPod config is not a JSON object: {path}")
    return data


def resolve_endpoint(config: dict[str, Any]) -> tuple[str, str, str, str]:
    endpoint_id = str(config.get("endpoint_id") or "").strip()
    openai_base_url = str(config.get("openai_base_url") or "").strip().rstrip("/")
    if not openai_base_url and endpoint_id:
        openai_base_url = f"https://api.runpod.ai/v2/{endpoint_id}/openai/v1"
    if not openai_base_url.startswith("https://api.runpod.ai/v2/"):
        raise ConfigError(
            "RunPod OpenAI-compatible URL is missing or unexpected. "
            "Expected https://api.runpod.ai/v2/{endpoint_id}/openai/v1"
        )

    model = (
        str(config.get("openai_model_id") or "").strip()
        or str(config.get("model") or "").strip()
        or str(config.get("huggingface_model_id") or "").strip()
    )
    if not model:
        raise ConfigError("RunPod model id is missing from config")

    run_url = str(config.get("run_url") or "").strip()
    if not run_url and endpoint_id:
        run_url = f"https://api.runpod.ai/v2/{endpoint_id}/run"
    return endpoint_id, openai_base_url, model, run_url


def read_secret(secret_path: Path) -> str:
    env_value = os.environ.get("RUNPOD_API_KEY", "").strip()
    if env_value:
        return env_value
    if not secret_path.exists():
        raise ConfigError(f"missing RunPod secret file: {secret_path}")
    secret = secret_path.read_text(encoding="utf-8-sig").strip()
    if not secret:
        raise ConfigError(f"RunPod secret file is empty: {secret_path}")
    return secret


def quote_dotenv(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "")
        .replace("\n", "\\n")
    )
    return f'"{escaped}"'


def update_env_file(
    env_path: Path,
    *,
    api_key: str,
    endpoint_id: str,
    openai_base_url: str,
    model: str,
    runpod_config_path: Path,
    secret_path: Path,
) -> None:
    managed = {
        "RUNPOD_API_KEY": api_key,
        "ENGEL_RUNPOD_ENDPOINT_ID": endpoint_id,
        "ENGEL_RUNPOD_OPENAI_BASE_URL": openai_base_url,
        "ENGEL_RUNPOD_MODEL": model,
        "ENGEL_RUNPOD_CONFIG": str(runpod_config_path),
        "ENGEL_RUNPOD_API_KEY_FILE": str(secret_path),
    }
    existing = env_path.read_text(encoding="utf-8-sig").splitlines() if env_path.exists() else []
    filtered: list[str] = []
    managed_keys = set(managed)
    for line in existing:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            filtered.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key not in managed_keys:
            filtered.append(line)

    if filtered and filtered[-1].strip():
        filtered.append("")
    filtered.append("# Managed by tools/configure_engel_runpod_agent.py")
    for key, value in managed.items():
        filtered.append(f"{key}={quote_dotenv(value)}")
    env_path.write_text("\n".join(filtered) + "\n", encoding="utf-8")


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"Engel config must be a YAML mapping: {path}")
    return data


def backup_file(path: Path) -> str:
    if not path.exists():
        return ""
    backup = path.with_name(f"{path.name}.before-runpod-{utc_stamp()}.bak")
    shutil.copy2(path, backup)
    return str(backup)


def update_config_yaml(
    config_path: Path,
    *,
    provider_key: str,
    provider_name: str,
    openai_base_url: str,
    model: str,
    context_length: int,
) -> str:
    backup = backup_file(config_path)
    config = load_yaml(config_path)
    config["_config_version"] = int(config.get("_config_version") or LATEST_CONFIG_VERSION)

    providers = config.get("providers")
    if not isinstance(providers, dict):
        providers = {}
    provider_entry = providers.get(provider_key)
    if not isinstance(provider_entry, dict):
        provider_entry = {}
    provider_entry.update(
        {
            "name": provider_name,
            "api": openai_base_url,
            "key_env": "RUNPOD_API_KEY",
            "transport": "chat_completions",
            "default_model": model,
            "models": {
                model: {
                    "context_length": context_length,
                }
            },
        }
    )
    providers[provider_key] = provider_entry
    config["providers"] = providers

    model_cfg = config.get("model")
    if not isinstance(model_cfg, dict):
        model_cfg = {}
    model_cfg.update(
        {
            "provider": provider_key,
            "default": model,
            "api_mode": "chat_completions",
        }
    )
    model_cfg.pop("base_url", None)
    model_cfg.pop("api_key", None)
    config["model"] = model_cfg

    rendered = yaml.safe_dump(config, sort_keys=False, allow_unicode=False)
    config_path.write_text(rendered, encoding="utf-8")
    return backup


def write_launch_env(
    path: Path,
    *,
    engel_home: Path,
    runpod_root: Path,
    secret_path: Path,
) -> None:
    lines = [
        "$ErrorActionPreference = \"Stop\"",
        f"$env:ENGEL_HOME = \"{engel_home}\"",
        f"$env:ENGEL_RUNPOD_ROOT = \"{runpod_root}\"",
        f"$env:ENGEL_RUNPOD_API_KEY_FILE = \"{secret_path}\"",
        "if (Test-Path -LiteralPath $env:ENGEL_RUNPOD_API_KEY_FILE) {",
        "    $env:RUNPOD_API_KEY = ((Get-Content -LiteralPath $env:ENGEL_RUNPOD_API_KEY_FILE -Raw) -as [string]).Trim()",
        "}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def configure(args: argparse.Namespace) -> dict[str, Any]:
    engel_home = Path(args.engel_home)
    runpod_config_path = Path(args.runpod_config)
    secret_path = Path(args.secret_path)
    runpod_root = runpod_config_path.parent

    for label, path in [
        ("Engel home", engel_home),
        ("RunPod config", runpod_config_path),
        ("RunPod root", runpod_root),
        ("RunPod secret", secret_path),
    ]:
        require_off_c(path, label)

    config = read_json(runpod_config_path)
    endpoint_id, openai_base_url, model, run_url = resolve_endpoint(config)
    api_key = read_secret(secret_path)

    engel_home.mkdir(parents=True, exist_ok=True)
    config_path = engel_home / "config.yaml"
    env_path = engel_home / ".env"
    launch_env_path = engel_home / "runpod-agent-env.ps1"

    config_backup = update_config_yaml(
        config_path,
        provider_key=args.provider_key,
        provider_name=args.provider_name,
        openai_base_url=openai_base_url,
        model=model,
        context_length=args.context_length,
    )
    update_env_file(
        env_path,
        api_key=api_key,
        endpoint_id=endpoint_id,
        openai_base_url=openai_base_url,
        model=model,
        runpod_config_path=runpod_config_path,
        secret_path=secret_path,
    )
    write_launch_env(
        launch_env_path,
        engel_home=engel_home,
        runpod_root=runpod_root,
        secret_path=secret_path,
    )

    return {
        "ok": True,
        "engel_home": str(engel_home),
        "config_path": str(config_path),
        "config_backup": config_backup,
        "env_path": str(env_path),
        "env_contains_runpod_key": True,
        "api_key_value_visible": False,
        "launch_env_path": str(launch_env_path),
        "provider": args.provider_key,
        "model": model,
        "endpoint_id": endpoint_id,
        "run_url": run_url,
        "openai_base_url": openai_base_url,
        "context_length": args.context_length,
        "c_drive_used": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Wire RunPod into Engel Agent config.")
    parser.add_argument("--engel-home", default=str(DEFAULT_ENGEL_HOME))
    parser.add_argument("--runpod-config", default=str(DEFAULT_RUNPOD_CONFIG))
    parser.add_argument("--secret-path", default=str(DEFAULT_SECRET_PATH))
    parser.add_argument("--provider-key", default=DEFAULT_PROVIDER_KEY)
    parser.add_argument("--provider-name", default=DEFAULT_PROVIDER_NAME)
    parser.add_argument("--context-length", type=int, default=DEFAULT_CONTEXT_LENGTH)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = configure(args)
    except ConfigError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "api_key_value_visible": False}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
