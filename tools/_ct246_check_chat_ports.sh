#!/bin/bash
set -u
echo "=== listen 8765/24680 ==="
ss -ltnp | grep -E '8765|24680|8790' || true
echo "=== health on 8765 ==="
curl -sS -m 8 http://127.0.0.1:8765/health | head -c 400; echo
echo "=== nginx refs ==="
grep -RIn "24680\|8765\|engel.*chat" /etc/nginx 2>/dev/null | head -40 || true
echo "=== unit exec ==="
systemctl cat engel-main-chat.service | sed -n '1,80p'
echo "=== drop-ins port ==="
grep -RIn "PORT\|8765\|24680\|ExecStart" /etc/systemd/system/engel-main-chat.service* 2>/dev/null | head -40
echo "=== chat ping 8765 ==="
curl -sS -m 90 -X POST http://127.0.0.1:8765/chat \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Reply with exactly ENGEL_MAIN_CHAT_PING_OK","max_tokens":24}' \
  -o /tmp/_chat8765.json -w "HTTP=%{http_code} TIME=%{time_total}\n" || echo FAIL
python3 - <<'PY'
import json
from pathlib import Path
p=Path('/tmp/_chat8765.json')
if p.exists() and p.stat().st_size:
    d=json.loads(p.read_text())
    print({k:(str(d.get(k))[:220] if d.get(k) is not None else None) for k in ('ok','status','error','provider','model','reply')})
else:
    print('no body')
PY
