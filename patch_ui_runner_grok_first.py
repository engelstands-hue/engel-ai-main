from pathlib import Path

p = Path("tools/run_engel_ui_chat_meeting_room_llm.py")
s = p.read_text(encoding="utf-8")

if "GROK UI FIRST ROUTE PATCH" in s:
    print("already patched")
    raise SystemExit(0)

marker = "def _main_server_chat_url(server_merge: dict[str, Any]) -> str:\n"

helper = r'''
# GROK UI FIRST ROUTE PATCH
def _grok_ui_first_reply(prompt: str, timeout: int, max_tokens: int, temperature: float) -> dict[str, Any] | None:
    if str(os.environ.get("ENGEL_MAIN_CHAT_ROUTE") or "grok-cli").strip().lower() not in {"grok", "grok-cli", "grok_cli"}:
        return None
    try:
        import subprocess as _sp
        grok = ROOT / ".grok" / "bin" / "grok.exe"
        if not grok.exists():
            return None
        grok_prompt = (
            "You are Engel AI Main inside Joshua's local workspace. "
            "Reply directly. Do not read files. Do not inspect the project. "
            "Do not use tools. Do not claim execution. Keep it concise.\n\n"
            "Joshua says:\n" + str(prompt)
        )
        result = _sp.run(
            [
                str(grok),
                "-p", grok_prompt,
                "--cwd", str(ROOT),
                "--permission-mode", "plan",
                "--max-turns", "1",
                "--no-memory",
                "--no-subagents",
                "--no-plan",
                "--disable-web-search",
                "--no-alt-screen",
                "--output-format", "plain",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=min(max(15, int(timeout) - 10), 75),
            shell=False,
        )
        text = (result.stdout or result.stderr or "").strip()
        if not text:
            return None
        return {
            "schema": "engel_ui_chat_meeting_room_llm_reply_v1",
            "ok": True,
            "status": "grok cli no-api ui first reply",
            "updated_at_utc": iso_now(),
            "run_id": "ui_chat_grok_first_" + stamp(),
            "prompt": prompt,
            "ui_entry_path": "Engel Main chat -> Grok CLI no-API first route",
            "assistant_reply": text,
            "assistant_output_text": text,
            "visible_reply_source": "grok_cli_no_api",
            "provider_api_enabled": False,
            "network_enabled": False,
            "model_service_server_enabled": False,
            "ct246_bypassed": True,
            "main_server_chat_url": "",
        }
    except Exception as exc:
        return None

'''

s = s.replace(marker, helper + "\n" + marker)

run_marker = "def run(prompt: str, timeout: int, max_tokens: int, temperature: float) -> dict[str, Any]:\n"
if run_marker not in s:
    raise SystemExit("run function marker not found")

insert = '''def run(prompt: str, timeout: int, max_tokens: int, temperature: float) -> dict[str, Any]:
    grok_first = _grok_ui_first_reply(prompt, timeout, max_tokens, temperature)
    if grok_first is not None:
        return grok_first
'''

s = s.replace(run_marker, insert)
p.write_text(s, encoding="utf-8")
print("patched UI runner Grok first")
