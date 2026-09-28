#!/bin/bash
# Keep Chat's login alive while the weekly LoRA runs.
# Nemotron 3.5 Lightning holds about 29 GB. The 40 GB container cannot
# keep that resident and also train. Pause it for the run, then bring it back.
set -u
flag=/opt/engel/run/nemotron_paused_for_training
mode="${1:-}"

if [ "$mode" = "begin" ]; then
  mkdir -p /opt/engel/run
  touch "$flag"
  systemctl stop engel-nemotron-lightning.service
  exit 0
fi

if [ "$mode" = "end" ]; then
  systemctl start engel-nemotron-lightning.service || true
  ready=0
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24; do
    if curl -fsS -m 2 http://127.0.0.1:8905/health >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 10
  done
  if [ "$ready" = "1" ]; then
    rm -f "$flag"
    echo "Nemotron is back. Training pause cleared."
  else
    echo "Nemotron did not become healthy. Training pause flag left in place."
  fi
  exit 0
fi

echo "usage: engel_weekly_retrain_memory_guard.sh begin|end" >&2
exit 2
