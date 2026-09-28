#!/bin/bash
set -euo pipefail
echo "=== UNIT STATUS ==="
systemctl is-active engel-main-chat.service engel-discord-bridge.service \
  engel-discord-desk-research.service engel-discord-desk-product.service \
  engel-discord-desk-community.service engel-discord-desk-support.service \
  engel-discord-desk-sales.service engel-discord-desk-ops.service || true
echo "=== RECENT DISCORD MAIN (no tokens) ==="
journalctl -u engel-discord-bridge.service --since "18 hours ago" --no-pager \
  | grep -iE 'ERROR|suppress|peer-storm|standing-watch|collab|claim lost|prompt-leak|chat turn|timeout|503|admission|brain|NIM|nvidia|local|desk|should_answer|GIF|offline|failed' \
  | grep -viE 'token|authorization|Bearer|api[_-]?key|password|secret' \
  | tail -120
echo "=== DESK JOURNALS SAMPLE ==="
for d in research product community support sales ops; do
  echo "--- desk=$d ---"
  journalctl -u "engel-discord-desk-${d}.service" --since "18 hours ago" --no-pager \
    | grep -iE 'ERROR|suppress|peer-storm|standing|collab|claim lost|prompt-leak|chat turn|timeout|failed|device|android|Main|off-charter|NIM|brain' \
    | grep -viE 'token|authorization|Bearer|api[_-]?key|password|secret' \
    | tail -40
done
echo "=== STATUS JSON (sanitized) ==="
python3 - <<'PY'
import json,re
from pathlib import Path
roots=[Path('/opt/engel/run/discord_bridge')]
desks=Path('/opt/engel/desks')
if desks.is_dir():
    for d in desks.iterdir():
        roots.append(d/'run'/'discord_bridge')
secret=re.compile(r'(token|authorization|bearer|api[_-]?key|password|secret)', re.I)
for root in roots:
    for name in ('status.json','state.json','proactive_state.json'):
        p=root/name
        if not p.is_file():
            continue
        try:
            data=json.loads(p.read_text(encoding='utf-8'))
        except Exception as e:
            print(p, 'READ_FAIL', e)
            continue
        text=json.dumps(data, indent=2)[:4000]
        if secret.search(text):
            text=secret.sub('[REDACTED]', text)
        print('FILE', p)
        print(text[:2500])
        print('---')
PY
echo "=== CHAT RECEIPTS TAIL (discord sources) ==="
python3 - <<'PY'
from pathlib import Path
import json
base=Path('/opt/engel/reports/engel_standalone_chat_llm/chat_receipts')
if not base.is_dir():
    print('no chat receipts dir')
    raise SystemExit
files=sorted(base.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:80]
count=0
for p in files:
    try:
        d=json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        continue
    src=str(d.get('source') or d.get('request_source') or d.get('metadata',{}) if isinstance(d.get('metadata'),dict) else '')
    meta=d.get('metadata') if isinstance(d.get('metadata'),dict) else {}
    blob=json.dumps({k:d.get(k) for k in ('ok','status','provider','runtime_provider','error','source')})
    desk=meta.get('discord_desk_name') or meta.get('desk') or ''
    if 'discord' in blob.lower() or 'discord' in str(meta).lower() or desk:
        print(p.name, 'ok=', d.get('ok'), 'provider=', d.get('provider') or d.get('runtime_provider'), 'desk=', desk, 'status=', str(d.get('status') or '')[:120])
        err=str(d.get('error') or d.get('failure') or '')[:180]
        if err:
            print('  err=', err)
        count+=1
        if count>=25:
            break
print('discord_receipts_shown', count)
PY
echo "=== ANDROID / DEVICE STATUS ROUTES ON CT ==="
ls -la /opt/engel/tools/engel_adb_worker_manager.py /opt/engel/tools/engel_discord_bridge.py 2>/dev/null || true
grep -n 'android\|device\|phone\|worker' /opt/engel/tools/engel_discord_bridge.py | head -40 || true
echo "REVIEW_DONE"
