#!/bin/bash
set -u
echo "=== process ==="
ps -fp 728337 || echo "PID gone"
pgrep -af engel_main_server_chat || true
pgrep -af '24680|main_server_chat' || true

echo "=== listeners ==="
ss -ltnp | grep -E '24680|8790|8899|8080' || true
ss -ltnp | head -40

echo "=== unit status ==="
systemctl status engel-main-chat.service --no-pager -l | head -40

echo "=== restart chat ==="
systemctl restart engel-main-chat.service
sleep 3
systemctl is-active engel-main-chat.service
ss -ltnp | grep 24680 || echo "STILL_NO_24680"
curl -sS -m 8 http://127.0.0.1:24680/health | head -c 300; echo
curl -sS -m 60 -X POST http://127.0.0.1:24680/chat \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Reply with exactly ENGEL_MAIN_CHAT_PING_OK","max_tokens":24}' \
  -o /tmp/_engel_chat2.json -w "CHAT_HTTP=%{http_code} TIME=%{time_total}\n" || echo CHAT_FAIL
python3 - <<'PY'
import json
from pathlib import Path
p=Path('/tmp/_engel_chat2.json')
print('exists', p.exists(), 'size', p.stat().st_size if p.exists() else 0)
if p.exists() and p.stat().st_size:
    d=json.loads(p.read_text())
    print({k: (str(d.get(k))[:200] if d.get(k) is not None else None) for k in ('ok','status','error','provider','model','reply')})
PY

echo "=== enable watchdog if present ==="
systemctl start engel-chat-health-watchdog.service 2>/dev/null || true
systemctl is-active engel-chat-health-watchdog.service || true
systemctl status engel-chat-health-watchdog.service --no-pager -l | head -20 || true
