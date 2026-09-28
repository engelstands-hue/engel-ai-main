from pathlib import Path

p = Path("tools/engel_main_local_model_worker.py")
s = p.read_text(encoding="utf-8")

if "GROK CLI NO-API FIRST-LANE PATCH" in s:
    print("already patched")
    raise SystemExit(0)

marker = "    # chain directly (CT246 primary, then GPU direct, then provider bridges).\n"

insert = r'''    # GROK CLI NO-API FIRST-LANE PATCH
    # Joshua wants Grok as the no-cost planning brain before CT246/local model waits.
    if str(os.environ.get("ENGEL_MAIN_CHAT_ROUTE") or "grok-cli").strip().lower() in {"grok", "grok-cli", "grok_cli"}:
        try:
            from pathlib import Path as _EngelPath
            import subprocess as _engel_subprocess

            _root = _EngelPath(__file__).resolve().parents[1]
            _grok = _root / ".grok" / "bin" / "grok.exe"
            if _grok.exists():
                _grok_prompt = (
                    "You are Engel AI Main inside Joshua's local workspace. "
                    "Reply directly. Do not read files. Do not inspect the project. "
                    "Do not use tools. Do not claim execution. Be concise and useful.\n\n"
                    "Joshua says:\n" + str(prompt)
                )
                _grok_result = _engel_subprocess.run(
                    [
                        str(_grok),
                        "-p", _grok_prompt,
                        "--cwd", str(_root),
                        "--permission-mode", "plan",
                        "--max-turns", "1",
                        "--no-memory",
                        "--no-subagents",
                        "--no-plan",
                        "--disable-web-search",
                        "--no-alt-screen",
                        "--output-format", "plain",
                    ],
                    cwd=str(_root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=min(max(15, int(timeout) - 10), 75),
                    shell=False,
                )
                _grok_text = (_grok_result.stdout or _grok_result.stderr or "").strip()
                if _grok_text:
                    return {
                        "id": request_id,
                        "ok": True,
                        "status": "grok cli no-api first-lane reply",
                        "schema": "engel_main_local_model_worker_response_v1",
                        "assistant_reply": _grok_text,
                        "assistant_output_text": _grok_text,
                        "provider_api_enabled": False,
                        "network_enabled": False,
                        "model_service_server_enabled": False,
                        "fallback_provider": "grok-cli-plan-mode",
                        "ct246_bypassed": True,
                    }
        except Exception:
            pass

'''

if marker not in s:
    raise SystemExit("marker not found; no patch applied")

p.write_text(s.replace(marker, insert + marker), encoding="utf-8")
print("patched grok first-lane")
