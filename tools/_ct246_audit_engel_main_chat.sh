#!/bin/bash
set -u
echo "=== chat unit ==="
systemctl is-active engel-main-chat.service || true
systemctl show engel-main-chat.service -p ActiveEnterTimestamp -p MainPID -p NRestarts --no-pager || true

echo "=== recent journal ==="
journalctl -u engel-main-chat.service --since "90 min ago" --no-pager 2>/dev/null | grep -E "ERROR|503|busy|Traceback|timeout|unavailable|WARNING|POST /chat|model_busy|llama" | tail -60 || true

echo "=== engel services ==="
systemctl list-units --type=service --all --no-pager 'engel*' 2>/dev/null | head -80 || true

echo "=== health snippet ==="
curl -sS -m 8 http://127.0.0.1:24680/health > /tmp/_engel_health.json || echo HEALTH_CURL_FAIL
python3 - <<'PY'
import json
from pathlib import Path
p = Path('/tmp/_engel_health.json')
if not p.exists() or p.stat().st_size == 0:
    print('no health file')
    raise SystemExit
d = json.loads(p.read_text())
print('ok', d.get('ok'), 'status', d.get('status'))
mr = d.get('model_runtime') or {}
print('lora_ready', ((mr.get('lora_runtime_status') or {}).get('ready')))
large = mr.get('large_chat_llm') or {}
print('large_ok', large.get('ok'), 'largest', large.get('largest_installed_gguf_path'))
# print busy/load hints if present
for k in ('chat_busy','model_busy','inflight','active_turns','local_model_service'):
    if k in d:
        print(k, d.get(k))
print('keys_sample', sorted(d.keys())[:30])
PY

echo "=== direct chat on CT (45s) ==="
curl -sS -m 45 -X POST http://127.0.0.1:24680/chat \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Reply with exactly ENGEL_MAIN_CHAT_PING_OK","max_tokens":24}' \
  -o /tmp/_engel_chat.json -w "HTTP=%{http_code} TIME=%{time_total}\n" || echo CHAT_CURL_FAIL
python3 - <<'PY'
import json
from pathlib import Path
p = Path('/tmp/_engel_chat.json')
if not p.exists() or p.stat().st_size == 0:
    print('no chat body')
    raise SystemExit
raw = p.read_text(encoding='utf-8', errors='replace')
print('body_len', len(raw))
try:
    d = json.loads(raw)
except Exception as e:
    print('json_fail', type(e).__name__, raw[:400])
    raise SystemExit
keep = {}
for k in ('ok','status','error','provider','model','reply','message','detail','http_status_hint','route'):
    if k in d:
        v = d[k]
        if isinstance(v, str) and len(v) > 240:
            v = v[:240] + '...'
        keep[k] = v
print(json.dumps(keep, sort_keys=True))
PY
