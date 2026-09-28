#!/bin/bash
set -u
echo "=== conflicting drop-ins ==="
for f in /etc/systemd/system/engel-main-chat.service.d/*.conf; do
  echo "-- $f --"
  cat "$f"
  echo
done

echo "=== effective env (masked) ==="
systemctl show engel-main-chat.service -p Environment --value | tr ' ' '\n' | grep -E 'LOCAL|FALLBACK|NVIDIA|NEMOTRON|QUICK|ORNI|PROVIDER|TIMEOUT|LARGE|GGUF|GPU' | while IFS= read -r line; do
  k=${line%%=*}
  v=${line#*=}
  case "$k" in
    *TOKEN*|*KEY*|*SECRET*|*PASSWORD*) echo "$k=***" ;;
    *)
      if [ ${#v} -gt 120 ]; then echo "$k=${v:0:120}..."; else echo "$k=$v"; fi
      ;;
  esac
done

echo "=== nemotron lightning unit ==="
systemctl cat engel-nemotron-lightning.service 2>/dev/null | head -40
ss -ltnp | grep -E 'python|llama|nemo' | head -30 || true

echo "=== recent fast-fail receipts ==="
ls -1t /opt/engel/run/chat_receipts 2>/dev/null | head -5
find /opt/engel/run -name '*FAST_FAIL*' -o -name '*local_llm*' 2>/dev/null | head -20
