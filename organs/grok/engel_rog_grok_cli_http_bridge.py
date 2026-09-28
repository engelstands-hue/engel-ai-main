import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
GROK_EXE = ROOT / ".grok" / "bin" / "grok.exe"
RUN_ROOT = ROOT / "runtime" / "grok_cli_safe_cwd"
RUN_ROOT.mkdir(parents=True, exist_ok=True)
HOST = "127.0.0.1"
PORT = 24881
TIMEOUT_SECONDS = 45


def send_json(handler, code, payload):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def content_to_text(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()
    return ""


def extract_prompt(data):
    if isinstance(data, dict):
        messages = data.get("messages")
        if isinstance(messages, list):
            for msg in reversed(messages):
                if isinstance(msg, dict) and str(msg.get("role", "")).lower() == "user":
                    text = content_to_text(msg.get("content"))
                    if text:
                        return text[-3000:]

            for msg in reversed(messages):
                if isinstance(msg, dict):
                    text = content_to_text(msg.get("content"))
                    if text:
                        return text[-3000:]

        for key in ("prompt", "message", "input", "text"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[-3000:]

    return ""


def kill_tree(pid):
    try:
        subprocess.run(
            ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except Exception:
        pass


def run_grok(user_prompt):
    if not GROK_EXE.exists():
        return False, f"Grok executable not found: {GROK_EXE}"

    user_prompt = (user_prompt or "").strip()
    if not user_prompt:
        return False, "No user prompt received."

    prompt = (
        "You are Grok CLI connected as a helper lane behind CT246 Engel AI Main. "
        "CT246 remains the backbone/source of truth. Answer only the current user message. "
        "Do not claim you executed tools or changed files unless the prompt includes proof.\n\n"
        "Current user message:\n"
        f"{user_prompt[-3000:]}"
    )

    cmd = [
        str(GROK_EXE),
        "-p", prompt,
        "--cwd", str(RUN_ROOT),
        "--permission-mode", "plan",
        "--max-turns", "1",
        "--no-memory",
        "--no-subagents",
        "--disable-web-search",
        "--no-alt-screen",
        "--output-format", "plain",
    ]

    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(RUN_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        out, err = proc.communicate(timeout=TIMEOUT_SECONDS)

        if proc.returncode != 0:
            text = (err or out or "").strip()
            return False, text[-2000:] or f"Grok exited with code {proc.returncode}."

        reply = (out or "").strip()
        return True, reply or "[Grok returned empty output.]"

    except subprocess.TimeoutExpired:
        if proc is not None:
            kill_tree(proc.pid)
        return False, "Grok/xAI timed out. I killed the stuck Grok/Git child process tree instead of leaving it running."

    except Exception as exc:
        if proc is not None:
            kill_tree(proc.pid)
        return False, f"Grok bridge error: {exc}"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        send_json(self, 200, {
            "ok": True,
            "schema": "engel_rog_grok_cli_bridge_health_v1",
            "provider": "xai",
            "provider_label": "Grok CLI on ROG",
            "host": HOST,
            "port": PORT,
            "grok_exe_present": GROK_EXE.exists(),
            "ct246_is_backbone": True,
            "mode": "no-api-cli-bridge",
            "timeout_seconds": TIMEOUT_SECONDS,
            "kills_child_tree_on_timeout": True,
        })

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            data = json.loads(raw) if raw.strip() else {}
        except Exception:
            send_json(self, 400, {"ok": False, "error": "Invalid JSON."})
            return

        user_prompt = extract_prompt(data)
        ok, reply = run_grok(user_prompt)

        payload = {
            "ok": ok,
            "provider": "xai",
            "provider_label": "Grok CLI on ROG",
            "assistant_reply": reply,
            "reply": reply,
            "content": reply,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": reply,
                    },
                    "finish_reason": "stop" if ok else "error",
                }
            ],
        }

        send_json(self, 200 if ok else 504, payload)


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    print(f"Engel ROG Grok CLI bridge listening on http://{HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
