#!/bin/bash
set -u
echo "=== last chat err log ==="
tail -n 80 /opt/engel/logs/engel_main_chat.service.err.log 2>/dev/null || true
echo "=== last chat out log ==="
tail -n 80 /opt/engel/logs/engel_main_chat.service.log 2>/dev/null || true
echo "=== chat with verbose ==="
curl -sS -m 120 -X POST http://127.0.0.1:8765/chat \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Say only ENGEL_MAIN_OK","max_tokens":16}' \
  -D /tmp/_chat_headers.txt -o /tmp/_chat_body.json -w "HTTP=%{http_code} TIME=%{time_total}\n" || echo CURL_FAIL
echo "=== headers ==="
cat /tmp/_chat_headers.txt 2>/dev/null || true
echo "=== body ==="
python3 - <<'PY'
from pathlib import Path
import json
p=Path('/tmp/_chat_body.json')
print('size', p.stat().st_size if p.exists() else 0)
raw=p.read_text(encoding='utf-8', errors='replace') if p.exists() else ''
print(raw[:2000])
if raw:
  try:
    d=json.loads(raw)
    print('KEYS', sorted(d.keys())[:40])
  except Exception as e:
    print('not json', e)
PY
echo "=== nemotron lightning ==="
systemctl is-active engel-nemotron-lightning.service || true
curl -sS -m 5 http://127.0.0.1:8080/health 2>/dev/null | head -c 200; echo
curl -sS -m 5 http://127.0.0.1:8899/health 2>/dev/null | head -c 200; echo
ss -ltnp | grep -E '8899|8080|11434' || true
