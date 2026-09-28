#!/bin/bash
set -u
echo "=== LARGE drop-ins ==="
cat /etc/systemd/system/engel-main-chat.service.d/zzzz-large-chat-ornith-fast-ssd.conf
echo
cat /etc/systemd/system/engel-main-chat.service.d/zzzzz-large-chat-aligned-lora.conf
echo
echo "=== nemotron health ==="
curl -sS -m 8 http://127.0.0.1:8905/health || echo NEMO_HEALTH_FAIL
echo
python3 - <<'PY'
import json, urllib.request
body = json.dumps({
  "messages": [{"role": "user", "content": "Say only OK"}],
  "max_tokens": 8,
  "temperature": 0.1,
}).encode()
req = urllib.request.Request(
  "http://127.0.0.1:8905/v1/chat/completions",
  data=body,
  headers={"Content-Type": "application/json"},
  method="POST",
)
try:
  with urllib.request.urlopen(req, timeout=60) as resp:
    raw = resp.read().decode()
    print("nemo_http", resp.status)
    print(raw[:600])
except Exception as e:
  print("nemo_fail", type(e).__name__, e)
PY

echo "=== force quick via chat flag if supported ==="
python3 - <<'PY'
import json, urllib.request
# Try normal short chat with higher timeout
payload = {
  "prompt": "Say only: ENGEL_MAIN_OK",
  "max_tokens": 24,
  "timeout": 90,
  "force_quick_casual": True,
  "_force_quick_casual": True,
}
body = json.dumps(payload).encode()
req = urllib.request.Request(
  "http://127.0.0.1:8765/chat",
  data=body,
  headers={"Content-Type": "application/json"},
  method="POST",
)
try:
  with urllib.request.urlopen(req, timeout=120) as resp:
    raw = resp.read().decode()
    print("chat_http", resp.status)
    d = json.loads(raw)
    print({k: (str(d.get(k))[:240] if d.get(k) is not None else None) for k in ("ok","status","provider","runtime_provider","reply","error")})
    rec = d.get("receipt") if isinstance(d.get("receipt"), dict) else {}
    print("receipt_keys", sorted(rec.keys())[:25])
    print("quick", rec.get("quick_casual_model_used"), "runtime", rec.get("runtime_provider"), "fail", rec.get("failure_class"))
except Exception as e:
  print("chat_fail", type(e).__name__, e)
  if hasattr(e, 'read'):
    try:
      print(e.read().decode()[:800])
    except Exception:
      pass
PY
