#!/usr/bin/env bash
set -euo pipefail

if [[ "$(hostname)" != "engel-ai-main" ]]; then
  echo "Refusing deployment outside engel-ai-main" >&2
  exit 2
fi

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
rollback="/opt/engel/run/self_update/rollback/server_only_transport_${stamp}"
transport="/opt/engel/run/sub_engel_transport"
stage="/tmp/engel_server_transport_stage"
files=(
  engel_main_server_chat_http_service.py
  engel_main_local_model_worker.py
  engel_build_lane.py
  engel_workspace_scaffold.py
  engel_phone_presence.py
  engel_local_model_service.py
  engel_local_self_upgrade_planner.py
  engel_conical_self_upgrade_cycle.py
  engel_self_upgrade_loop_stream.py
  engel_codebase_inventory.py
  engel_self_patch_quorum.py
  engel_prompt_patch_provenance.py
  engel_deployment_rollback_automation.py
  engel_self_upgrade_system.py
  verify_engel_local_self_upgrade_planner.py
  verify_engel_self_upgrade_http_api.py
  verify_engel_self_upgrade_chat_lane.py
  verify_engel_self_upgrade_system.py
  verify_engel_conical_self_upgrade_cycle.py
  verify_engel_prompt_patch_provenance.py
  ENGEL_SELF_UPGRADE_SYSTEM_CONTRACT_V1.md
  ENGEL_SELF_UPGRADE_SYSTEM_CATALOG_V1.json
  ENGEL_SELF_UPGRADE_VERIFIER_MATRIX_V1.json
  engel_meeting_room_lan_server.py
  engel_meeting_room_event_stream.py
  engel_device_broker.py
  verify_engel_device_broker.py
  verify_engel_dispatch_broker_wiring.py
  verify_engel_sub_engel_session_renewal.py
  watch_windows_sub_engel_pairing.py
  engel_renew_sub_sessions.py
  engel_communication_queen_assignment_producer.py
  engel_ct_assignment_queue_consumer.py
  android_worker_alpha_worker_capabilities.json
  android_worker_alpha_queen_choice_policy.json
  android_worker_beta_worker_capabilities.json
  android_worker_beta_queen_choice_policy.json
  android_worker_gamma_worker_capabilities.json
  android_worker_gamma_queen_choice_policy.json
  engel_ct246_sub_engel_direct_work.py
  engel_pair_windows_sub_from_stdin.py
  run_engel_ui_chat_meeting_room_llm.py
  verify_engel_sub_direct_fallback.py
  verify_engel_sub_concurrent_control.py
  verify_engel_conical_build_orchestration.py
  run_engel_standalone_chat_llm.py
  engel_sub_node_remote_control.py
  engel_windows_sub_node_agent.py
  engel_sub_node_meeting_bridge.py
  engel_agent_meeting_room.py
)

for name in "${files[@]}"; do
  if [[ ! -f "$stage/$name" ]]; then
    echo "Missing staged runtime file: $stage/$name" >&2
    exit 3
  fi
done

mkdir -p "$rollback" \
  "$transport/SUB_ENGEL_SENT_WORK" \
  "$transport/callbacks" \
  "$transport/receipts" \
  /etc/systemd/system/engel-main-chat.service.d \
  /etc/systemd/system/engel-agent-meeting-room.service.d \
  /opt/engel/reports/sub_engel_remote_control
mkdir -p \
  /opt/engel/remote_workers/android_worker_alpha/config \
  /opt/engel/remote_workers/android_worker_beta/config \
  /opt/engel/remote_workers/android_worker_gamma/config

for name in "${files[@]}"; do
  case "$name" in
    ENGEL_SELF_UPGRADE_SYSTEM_CONTRACT_V1.md|ENGEL_SELF_UPGRADE_SYSTEM_CATALOG_V1.json|ENGEL_SELF_UPGRADE_VERIFIER_MATRIX_V1.json)
      file="/opt/engel/memory/$name"
      ;;
    engel_sub_node_remote_control.py|engel_windows_sub_node_agent.py|engel_sub_node_meeting_bridge.py|engel_agent_meeting_room.py|engel_self_upgrade_system.py|engel_communication_queen_assignment_producer.py)
      file="/opt/engel/$name"
      ;;
    android_worker_alpha_worker_capabilities.json)
      file="/opt/engel/remote_workers/android_worker_alpha/config/worker_capabilities.json"
      ;;
    android_worker_alpha_queen_choice_policy.json)
      file="/opt/engel/remote_workers/android_worker_alpha/config/queen_choice_policy.json"
      ;;
    android_worker_beta_worker_capabilities.json)
      file="/opt/engel/remote_workers/android_worker_beta/config/worker_capabilities.json"
      ;;
    android_worker_beta_queen_choice_policy.json)
      file="/opt/engel/remote_workers/android_worker_beta/config/queen_choice_policy.json"
      ;;
    android_worker_gamma_worker_capabilities.json)
      file="/opt/engel/remote_workers/android_worker_gamma/config/worker_capabilities.json"
      ;;
    android_worker_gamma_queen_choice_policy.json)
      file="/opt/engel/remote_workers/android_worker_gamma/config/queen_choice_policy.json"
      ;;
    *)
      file="/opt/engel/tools/$name"
      ;;
  esac
  if [[ -f "$file" ]]; then
    cp -a "$file" "$rollback/$name"
  fi
  install -m 0644 "$stage/$name" "$file"
done

dropin='[Service]
Environment=ENGEL_SUB_ENGEL_TRANSPORT_ROOT=/opt/engel/run/sub_engel_transport
Environment=ENGEL_LOCAL_MODEL_CACHE_MAX_MODELS=1
Environment=ENGEL_LOCAL_MODEL_CACHE_MAX_GGUF_BYTES=25769803776
Environment=ENGEL_LOCAL_MODEL_MIN_ACTIVE_CTX=1024
Environment=ENGEL_LOCAL_MODEL_CONTEXT_RESERVE_TOKENS=192
Environment=ENGEL_LOCAL_MODEL_THREADS=16
Environment=ENGEL_LOCAL_MODEL_BATCH_THREADS=16
Environment=ENGEL_CODE_LANE_GGUF_MODEL=/opt/engel/models-active/llm/qwen2.5-coder-3b-instruct/qwen2.5-coder-3b-instruct-q5_k_m.gguf
Environment=ENGEL_BUILD_LOCAL_N_PREDICT_CAP=1800
Environment=ENGEL_BUILD_LOCAL_CTX=6144
Environment=ENGEL_BUILD_LOCAL_PROMPT_CHAR_CAP=12000
Environment=ENGEL_BUILD_LOCAL_ALL_STAGES=1
Environment=ENGEL_BUILD_BOUNDED_PER_FILE_ENABLED=1
Environment=ENGEL_DEEP_REASON_LANE_ENABLED=1
Environment=ENGEL_DEEP_REASON_GGUF_MODEL=/opt/engel/models-active/llm/qwen2.5-14b-instruct/qwen2.5-14b-instruct-Q4_K_M.gguf
Environment=ENGEL_MOE_REASON_LANE_ENABLED=1
Environment=ENGEL_MOE_REASON_AUTO_ROUTE=1
Environment=ENGEL_MOE_REASON_GGUF_MODEL=/opt/engel/models-active/llm/qwen3-30b-a3b/Qwen3-30B-A3B-Q4_K_M.gguf
Environment=ENGEL_MOE_REASON_CTX=6144
Environment=ENGEL_MOE_REASON_N_PREDICT=1024
'
printf '%s' "$dropin" > /etc/systemd/system/engel-main-chat.service.d/80-server-only-sub-transport.conf
printf '%s' "$dropin" > /etc/systemd/system/engel-agent-meeting-room.service.d/80-server-only-sub-transport.conf

for unit in engel-sub-session-renewal.service engel-sub-session-renewal.timer; do
  if [[ -f "/etc/systemd/system/$unit" ]]; then
    cp -a "/etc/systemd/system/$unit" "$rollback/$unit"
  fi
done
cat > /etc/systemd/system/engel-sub-session-renewal.service <<'EOF'
[Unit]
Description=Engel AI Main CT246 Sub-Engel Session Renewal
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/opt/engel
ExecStart=/opt/engel/.venv/bin/python /opt/engel/tools/engel_renew_sub_sessions.py
EOF
cat > /etc/systemd/system/engel-sub-session-renewal.timer <<'EOF'
[Unit]
Description=Check CT246 Sub-Engel sessions twice daily

[Timer]
OnBootSec=10min
OnUnitActiveSec=12h
RandomizedDelaySec=5min
Persistent=true
Unit=engel-sub-session-renewal.service

[Install]
WantedBy=timers.target
EOF

python3 -m py_compile \
  /opt/engel/tools/engel_main_server_chat_http_service.py \
  /opt/engel/tools/engel_main_local_model_worker.py \
  /opt/engel/tools/engel_build_lane.py \
  /opt/engel/tools/engel_workspace_scaffold.py \
  /opt/engel/tools/engel_phone_presence.py \
  /opt/engel/tools/engel_local_model_service.py \
  /opt/engel/tools/engel_local_self_upgrade_planner.py \
  /opt/engel/tools/engel_conical_self_upgrade_cycle.py \
  /opt/engel/tools/engel_self_upgrade_loop_stream.py \
  /opt/engel/tools/engel_codebase_inventory.py \
  /opt/engel/tools/engel_self_patch_quorum.py \
  /opt/engel/tools/engel_prompt_patch_provenance.py \
  /opt/engel/tools/engel_deployment_rollback_automation.py \
  /opt/engel/engel_self_upgrade_system.py \
  /opt/engel/tools/verify_engel_local_self_upgrade_planner.py \
  /opt/engel/tools/verify_engel_self_upgrade_http_api.py \
  /opt/engel/tools/verify_engel_self_upgrade_chat_lane.py \
  /opt/engel/tools/verify_engel_self_upgrade_system.py \
  /opt/engel/tools/verify_engel_conical_self_upgrade_cycle.py \
  /opt/engel/tools/verify_engel_prompt_patch_provenance.py \
  /opt/engel/tools/engel_meeting_room_lan_server.py \
  /opt/engel/tools/engel_meeting_room_event_stream.py \
  /opt/engel/tools/engel_device_broker.py \
  /opt/engel/tools/verify_engel_device_broker.py \
  /opt/engel/tools/verify_engel_dispatch_broker_wiring.py \
  /opt/engel/tools/verify_engel_sub_engel_session_renewal.py \
  /opt/engel/tools/watch_windows_sub_engel_pairing.py \
  /opt/engel/tools/engel_renew_sub_sessions.py \
  /opt/engel/engel_communication_queen_assignment_producer.py \
  /opt/engel/tools/engel_ct_assignment_queue_consumer.py \
  /opt/engel/tools/engel_ct246_sub_engel_direct_work.py \
  /opt/engel/tools/engel_pair_windows_sub_from_stdin.py \
  /opt/engel/tools/run_engel_ui_chat_meeting_room_llm.py \
  /opt/engel/tools/verify_engel_sub_direct_fallback.py \
  /opt/engel/tools/verify_engel_sub_concurrent_control.py \
  /opt/engel/tools/verify_engel_conical_build_orchestration.py \
  /opt/engel/tools/run_engel_standalone_chat_llm.py \
  /opt/engel/engel_sub_node_remote_control.py \
  /opt/engel/engel_windows_sub_node_agent.py \
  /opt/engel/engel_sub_node_meeting_bridge.py \
  /opt/engel/engel_agent_meeting_room.py

systemctl daemon-reload
systemctl enable --now engel-sub-session-renewal.timer
systemctl restart engel-agent-meeting-room.service
systemctl restart engel-main-chat.service
systemctl is-active --quiet engel-agent-meeting-room.service
systemctl is-active --quiet engel-main-chat.service

wait_http() {
  local url="$1"
  local attempt
  for attempt in $(seq 1 30); do
    if curl -fsS --connect-timeout 2 --max-time 5 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "Service did not become healthy: $url" >&2
  return 1
}

wait_http http://127.0.0.1:8790/health
wait_http http://127.0.0.1:8765/health

cat > /opt/engel/reports/sub_engel_remote_control/ENGEL_SERVER_ONLY_TRANSPORT_LATEST.json <<EOF
{
  "schema": "engel_server_only_transport_v1",
  "ok": true,
  "deployed_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "container": "CT246",
  "hostname": "engel-ai-main",
  "transport_root": "$transport",
  "transport": "authenticated_direct_http",
  "google_drive_used": false,
  "rollback_root": "$rollback"
}
EOF

cat /opt/engel/reports/sub_engel_remote_control/ENGEL_SERVER_ONLY_TRANSPORT_LATEST.json
