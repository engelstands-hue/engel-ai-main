from pathlib import Path

p = Path("tools/engel_main_local_model_worker.py")
s = p.read_text(encoding="utf-8")

old = '''    if str(os.environ.get("ENGEL_MAIN_ALLOW_LAPTOP_LOCAL_FALLBACK") or "0").strip().lower() not in {"1", "true", "yes", "on"}:
        return {
            "id": request_id,
            "ok": False,
            "status": "ct246 server chat route unavailable; laptop fallback disabled",
            "schema": "engel_main_local_model_worker_response_v1",
            "assistant_reply": (
                "CT246 did not return a usable chat reply, and laptop fallback is disabled so Engel does not split into a separate local model."
            ),
            "assistant_output_text": (
                "CT246 did not return a usable chat reply, and laptop fallback is disabled so Engel does not split into a separate local model."
            ),
            "provider_api_enabled": False,
            "network_enabled": True,
            "model_service_server_enabled": True,
            "main_server_chat_service_required": True,
            "main_server_chat_url": _server_chat_url(),
        }
'''

new = '''    if str(os.environ.get("ENGEL_MAIN_ALLOW_LAPTOP_LOCAL_FALLBACK") or "0").strip().lower() not in {"1", "true", "yes", "on"}:
        try:
            from pathlib import Path as _EngelPath
            import subprocess as _engel_subprocess

            _root = _EngelPath(__file__).resolve().parents[1]
            _grok = _root / ".grok" / "bin" / "grok.exe"
            if _grok.exists():
                _grok_prompt = (
                    "You are Engel AI Main using Grok CLI as a no-API planning fallback. "
                    "Do not claim execution. Do not auto-run commands. Reply directly and concisely.\\\\n\\\\n"
                    "Joshua says:\\\\n" + str(prompt)
                )
                _grok_result = _engel_subprocess.run(
                    [
                        str(_grok),
                        "-p", _grok_prompt,
                        "--cwd", str(_root),
                        "--permission-mode", "plan",
                        "--max-turns", "3",
                        "--no-memory",
                        "--no-alt-screen",
                    ],
                    cwd=str(_root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=min(max(20, int(timeout)), 180),
                    shell=False,
                )
                _grok_text = (_grok_result.stdout or _grok_result.stderr or "").strip()
                if _grok_text:
                    return {
                        "id": request_id,
                        "ok": True,
                        "status": "grok cli no-api fallback reply",
                        "schema": "engel_main_local_model_worker_response_v1",
                        "assistant_reply": _grok_text,
                        "assistant_output_text": _grok_text,
                        "provider_api_enabled": False,
                        "network_enabled": False,
                        "model_service_server_enabled": False,
                        "fallback_provider": "grok-cli-plan-mode",
                        "ct246_primary_failed": True,
                    }
        except Exception:
            pass

        return {
            "id": request_id,
            "ok": False,
            "status": "ct246 server chat route unavailable; grok fallback unavailable; laptop fallback disabled",
            "schema": "engel_main_local_model_worker_response_v1",
            "assistant_reply": (
                "CT246 did not return a usable chat reply, and Grok fallback did not return a usable reply."
            ),
            "assistant_output_text": (
                "CT246 did not return a usable chat reply, and Grok fallback did not return a usable reply."
            ),
            "provider_api_enabled": False,
            "network_enabled": True,
            "model_service_server_enabled": True,
            "main_server_chat_service_required": True,
            "main_server_chat_url": _server_chat_url(),
        }
'''

if old not in s:
    raise SystemExit("Patch target not found. No file changed.")

p.write_text(s.replace(old, new), encoding="utf-8")
print("patched grok fallback")
