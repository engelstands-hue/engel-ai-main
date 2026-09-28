#!/usr/bin/env python3
"""NVIDIA Nemotron 3.5 Lightning 30B-A3B runtime for Engel AI Main on CT 246.

The GGUF is a hybrid Mamba-2 + MoE (nemotron_h_moe). The stock llama-cpp-python
lane cannot load it. This module talks to the dedicated llama.cpp b10423
llama-server on 127.0.0.1:8905, with llama-cli as a one-shot fallback.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.request
from typing import Any


ROOT = Path(os.environ.get("ENGEL_ROOT", "/opt/engel"))
DEFAULT_MODEL = (
    ROOT
    / "models-active"
    / "llm"
    / "nemotron-3.5-lightning-30b-a3b"
    / "NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_M.gguf"
)
DEFAULT_BIN_DIR = ROOT / "tools" / "llama-cpp-b10423" / "llama-b10423"
DEFAULT_URL = os.environ.get("ENGEL_NEMOTRON_SERVER_URL", "http://127.0.0.1:8905")
EXPECTED_BYTES = 25266255936
EXPECTED_SHA256_PREFIX = "edcb5d4650796ed2"
RECEIPT_PATH = ROOT / "memory" / "models" / "ENGEL_NEMOTRON_3_5_LIGHTNING_30B_A3B_INSTALL.json"
TRAINING_PAUSE_FLAG = ROOT / "run" / "nemotron_paused_for_training"
STATS_LINE = re.compile(r"^\[ Prompt: .*t/s.*\]\s*$")
THINK_BLOCK = re.compile(r"\[Start thinking\].*?\[End thinking\]\s*", re.S)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def model_path() -> Path:
    return Path(
        os.environ.get("ENGEL_NEMOTRON_MODEL")
        or os.environ.get("ENGEL_NEMOTRON_GGUF")
        or DEFAULT_MODEL
    )


def bin_dir() -> Path:
    return Path(os.environ.get("ENGEL_NEMOTRON_BIN_DIR") or DEFAULT_BIN_DIR)


def llama_cli() -> Path:
    return bin_dir() / "llama-cli"


def llama_server() -> Path:
    return bin_dir() / "llama-server"


def server_url() -> str:
    return str(DEFAULT_URL).rstrip("/")


def _file_ok(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _http_json(url: str, payload: dict[str, Any] | None = None, timeout: float = 8.0) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="GET" if data is None else "POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    if not raw.strip():
        return {"ok": True, "empty": True}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": True, "text": raw[:400]}
    return parsed if isinstance(parsed, dict) else {"ok": True, "value": parsed}


def server_healthy() -> bool:
    try:
        data = _http_json(server_url() + "/health", timeout=3.0)
    except Exception:
        try:
            data = _http_json(server_url() + "/v1/models", timeout=3.0)
        except Exception:
            return False
    status = str(data.get("status") or "").casefold()
    if status in {"ok", "ready", ""} and data.get("error") in {None, ""}:
        return True
    return bool(data.get("ok") is True or data.get("data") or data.get("models"))


def training_pause_active() -> bool:
    """Weekly LoRA is using the memory a second Nemotron load would fill."""
    return TRAINING_PAUSE_FLAG.is_file()


def dedicated_server_resident() -> bool:
    """True when llama-server is already holding the 30B weights on :8905.

    A health timeout under swap pressure is not "server down". Spawning llama-cli
    beside that process loads the same GGUF a second time (~25-30 GiB) and fills
    host swap. The one-shot CLI path is only for when nothing is listening.
    """
    if server_healthy():
        return True
    raw = server_url()
    hostport = raw.split("://", 1)[-1].split("/", 1)[0]
    if hostport.startswith("["):
        host, _, rest = hostport[1:].partition("]")
        port_s = rest[1:] if rest.startswith(":") else "8905"
    elif ":" in hostport:
        host, port_s = hostport.rsplit(":", 1)
    else:
        host, port_s = hostport or "127.0.0.1", "8905"
    try:
        port = int(port_s)
    except ValueError:
        port = 8905
    import socket

    try:
        with socket.create_connection((host or "127.0.0.1", port), timeout=1.0):
            return True
    except OSError:
        return False


def model_present() -> dict[str, Any]:
    path = model_path()
    present = path.is_file()
    size = path.stat().st_size if present else 0
    return {
        "ok": present and size == EXPECTED_BYTES,
        "path": str(path),
        "present": present,
        "size_bytes": size,
        "expected_bytes": EXPECTED_BYTES,
        "size_ok": size == EXPECTED_BYTES,
        "cli_present": _file_ok(llama_cli()),
        "server_bin_present": _file_ok(llama_server()),
    }


def status() -> dict[str, Any]:
    files = model_present()
    loaded = bool(files.get("ok") and server_healthy())
    receipt: dict[str, Any] = {}
    if RECEIPT_PATH.is_file():
        try:
            loaded_receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded_receipt, dict):
                receipt = loaded_receipt
        except Exception:
            receipt = {}
    return {
        "schema": "engel_nemotron_3_5_lightning_status_v1",
        "ok": bool(files.get("ok")),
        "loaded": loaded,
        "status": (
            "Nemotron 3.5 Lightning loaded on CT246"
            if loaded
            else (
                "Nemotron 3.5 Lightning present but not loaded"
                if files.get("present")
                else "Nemotron 3.5 Lightning GGUF missing"
            )
        ),
        "model_family": "NVIDIA Nemotron 3.5 Lightning",
        "architecture": "nemotron_h_moe",
        "quant": "UD-Q4_K_M",
        "total_parameters_billions": 30.0,
        "active_parameters_billions_per_token": 3.0,
        "server_url": server_url(),
        "server_healthy": loaded,
        "receipt_wired_into_chat": receipt.get("wired_into_chat") is True,
        "receipt_sha256_prefix": str(receipt.get("sha256") or "")[:16],
        "expected_sha256_prefix": EXPECTED_SHA256_PREFIX,
        **files,
        "updated_at_utc": iso_now(),
    }


def parse_llama_cli_output(stdout: str) -> str:
    lines = str(stdout or "").replace("\r", "\n").split("\n")
    last_echo = -1
    for index, line in enumerate(lines):
        if line.startswith("> ") and len(line) > 2:
            last_echo = index
    if last_echo < 0:
        return str(stdout or "").strip()
    reply: list[str] = []
    for line in lines[last_echo + 1 :]:
        if STATS_LINE.match(line.strip()) or line.strip() in {">", "Exiting..."}:
            break
        reply.append(line)
    return "\n".join(reply).strip()


def strip_thinking(reply: str) -> str:
    text = THINK_BLOCK.sub("", str(reply or ""))
    text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.S)
    if "</think>" in text:
        text = text.split("</think>", 1)[-1]
    low = text.casefold()
    # Lightning often dumps a "thinking process" outline instead of the answer.
    markers = (
        "here's a thinking process:",
        "here is a thinking process:",
        "thinking process:",
        "final answer:",
        "final response:",
    )
    for marker in markers:
        idx = low.rfind(marker)
        if idx >= 0:
            after = text[idx + len(marker) :].strip()
            if after and marker.startswith("final"):
                text = after
                break
            # Prefer content after the last "Final answer/response" if present.
    for marker in ("final answer:", "final response:"):
        idx = low.rfind(marker)
        if idx >= 0:
            after = text[idx + len(marker) :].strip()
            if after:
                return after
    if low.startswith("here's a thinking process") or low.startswith("here is a thinking process"):
        # No explicit final marker: drop the outline and keep the last non-bullet paragraph.
        parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        usable = [
            p
            for p in parts
            if not p.casefold().startswith("here's a thinking process")
            and not p.casefold().startswith("here is a thinking process")
            and not re.match(r"^\d+\.\s+\*\*", p)
            and not p.startswith("- ")
        ]
        if usable:
            text = usable[-1]
    return text.strip()


def _reject_thinking_only(text: str) -> str:
    cleaned = strip_thinking(text)
    low = cleaned.casefold()
    if (
        not cleaned
        or low.startswith("here's a thinking process")
        or low.startswith("here is a thinking process")
        or low.startswith("[start thinking]")
        or "thinking process:" in low[:200]
        or "[start thinking]" in low[:80]
    ):
        raise RuntimeError("Nemotron returned thinking-only content")
    return cleaned


def _generate_via_server(prompt: str, max_tokens: int, timeout: float) -> dict[str, Any]:
    # Prefer OpenAI-style chat completions so Lightning emits an answer instead of
    # raw prompt-continuation fragments from /completion.
    chat_payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Engel on engel-ai-main. Answer Josh directly, honestly, "
                    "and briefly. Do not invent working features. If something is broken, say so. "
                    "Never show a thinking process, analysis outline, or chain-of-thought. "
                    "Reply with only the final answer."
                ),
            },
            {"role": "user", "content": str(prompt)},
        ],
        "max_tokens": max(32, int(max_tokens)),
        "temperature": float(os.environ.get("ENGEL_NEMOTRON_TEMPERATURE", "0.6") or "0.6"),
        "top_p": float(os.environ.get("ENGEL_NEMOTRON_TOP_P", "0.95") or "0.95"),
    }
    content = ""
    via = "llama-server-chat"
    try:
        data = _http_json(server_url() + "/v1/chat/completions", chat_payload, timeout=timeout)
        choice0 = {}
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            choice0 = choices[0] if isinstance(choices[0], dict) else {}
        message = choice0.get("message") if isinstance(choice0.get("message"), dict) else {}
        content = str(
            message.get("content")
            or choice0.get("text")
            or data.get("content")
            or data.get("response")
            or ""
        ).strip()
        # Never surface reasoning_content as the user-facing Engel reply.
        # Lightning parks chain-of-thought there; using it made Chat look insane.
    except Exception:
        content = ""
    if not content:
        payload = {
            "prompt": (
                "You are Engel on engel-ai-main. Answer directly and honestly.\n"
                "Reply with only the final answer. No thinking process.\n\n"
                f"User: {prompt}\n\nEngel:"
            ),
            "n_predict": max(32, int(max_tokens)),
            "temperature": float(os.environ.get("ENGEL_NEMOTRON_TEMPERATURE", "0.6") or "0.6"),
            "top_p": float(os.environ.get("ENGEL_NEMOTRON_TOP_P", "0.95") or "0.95"),
            "stop": ["User:", "\nUser:", "[Start thinking]"],
        }
        data = _http_json(server_url() + "/completion", payload, timeout=timeout)
        content = str(
            data.get("content")
            or data.get("response")
            or ((data.get("choices") or [{}])[0].get("text") if isinstance(data.get("choices"), list) else "")
            or ""
        ).strip()
        via = "llama-server-completion"
    if not content:
        raise RuntimeError("Nemotron server returned empty content")
    return {"ok": True, "text": _reject_thinking_only(content), "via": via}


def _generate_via_cli(prompt: str, max_tokens: int, timeout: float) -> dict[str, Any]:
    cli = llama_cli()
    model = model_path()
    if not cli.is_file() or not model.is_file():
        raise RuntimeError("Nemotron llama-cli or GGUF missing")
    cmd = [
        str(cli),
        "-m",
        str(model),
        "-st",
        "-p",
        str(prompt),
        "-n",
        str(max(8, int(max_tokens))),
        "--temp",
        os.environ.get("ENGEL_NEMOTRON_TEMPERATURE", "1.0") or "1.0",
        "--top-p",
        os.environ.get("ENGEL_NEMOTRON_TOP_P", "0.95") or "0.95",
        "-t",
        os.environ.get("ENGEL_NEMOTRON_THREADS", "6") or "6",
        "--no-display-prompt",
    ]
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = str(bin_dir()) + (
        os.pathsep + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else ""
    )
    proc = subprocess.run(
        cmd,
        cwd=str(bin_dir()),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    reply = strip_thinking(parse_llama_cli_output(proc.stdout))
    if proc.returncode != 0 and not reply:
        raise RuntimeError((proc.stderr or proc.stdout or "llama-cli failed")[:300])
    if not reply:
        raise RuntimeError("Nemotron llama-cli returned empty content")
    return {"ok": True, "text": _reject_thinking_only(reply), "via": "llama-cli"}


def generate(prompt: str, *, max_tokens: int = 256, timeout: float | None = None) -> dict[str, Any]:
    text = str(prompt or "").strip() or "Hello Engel"
    wait = float(timeout or os.environ.get("ENGEL_NEMOTRON_TIMEOUT_SECONDS", "180") or "180")
    started = datetime.now(timezone.utc)
    error = ""
    if dedicated_server_resident():
        try:
            result = _generate_via_server(text, max_tokens, wait)
            result["seconds"] = (datetime.now(timezone.utc) - started).total_seconds()
            return result
        except Exception as exc:
            # Do not fall through to llama-cli. The resident server already holds
            # the weights; a second process is what filled host swap.
            return {
                "ok": False,
                "text": "",
                "error": f"server: {exc}",
                "via": "llama-server",
                "seconds": (datetime.now(timezone.utc) - started).total_seconds(),
            }
    if training_pause_active():
        return {
            "ok": False,
            "text": "",
            "error": "Nemotron is paused so weekly training can finish without filling memory",
            "via": "paused-for-training",
            "seconds": (datetime.now(timezone.utc) - started).total_seconds(),
        }
    try:
        result = _generate_via_cli(text, max_tokens, wait)
        result["seconds"] = (datetime.now(timezone.utc) - started).total_seconds()
        if error:
            result["server_error"] = error
        return result
    except Exception as exc:
        return {
            "ok": False,
            "text": "",
            "error": " | ".join(item for item in (error, str(exc)) if item),
            "seconds": (datetime.now(timezone.utc) - started).total_seconds(),
        }


def mark_wired(loaded: bool) -> None:
    if not RECEIPT_PATH.is_file():
        return
    try:
        data = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return
        data["wired_into_chat"] = bool(loaded)
        data["wired_at_utc"] = iso_now()
        data["runtime_note"] = (
            "Wired through tools/engel_nemotron_lightning_runtime.py and "
            "engel-nemotron-lightning.service (llama.cpp b10423)."
        )
        RECEIPT_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except Exception:
        return


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Engel Nemotron 3.5 Lightning runtime")
    parser.add_argument("command", choices=["status", "generate"])
    parser.add_argument("--prompt", default="Say ready in five words.")
    parser.add_argument("--max-tokens", type=int, default=32)
    args = parser.parse_args()
    if args.command == "status":
        print(json.dumps(status(), indent=2, sort_keys=True))
        return 0 if status().get("ok") is True else 1
    result = generate(args.prompt, max_tokens=args.max_tokens)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
