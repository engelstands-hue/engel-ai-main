# Engel conversation work memory

## What changed

Discord and Engel AI Main were posting status ledgers: training pid/log lines, and Meeting Room `Assigned` lists. Each desk could start its own training runner. The Proxmox host was already using swap.

- Spoken training replies no longer include a runner pid or log path. Those stay on the receipt.
- A second training runner is refused while one pid is still alive.
- A new training runner is refused while `/proc/meminfo` shows swap in use.
- Meeting Room chat speaks returned work (`station_outcomes`, previews, dialogue). Assignment status stays in the receipt.
- Discord drops a status-log reply before it is posted and replaces it with the work line.
- Chat context skips status logs. Each append overwrites one compressed digest at `runtime/compaction/maintained_engel-main-chat.json`. The raw jsonl corpus is unchanged. The digest is not trusted memory.

## Files

- `organs/core/engel_context_compaction.py`
- `tools/engel_main_server_chat_http_service.py`
- `tools/engel_discord_bridge.py`
- `tools/verify_engel_conversation_work_memory.py`
- `wiki/ONE.md`
- `wiki/organs.json`

## Verifiers

- `python3 tools/verify_engel_conversation_work_memory.py` — 17/17 passed
- `python3 tools/verify_engel_training_turn_context_exclusion.py` — 8/8 passed
- Chat service meeting-room reply and context filter checked in-process
- `compact_messages` still writes a local receipt

`tools/verify_engel_landscape_gaps_p0.py` still stops on missing repo-root shims (`engel_routines.py`). That failure is outside this change.

Discord bridge import needs `aiohttp` and `discord`, which are not installed in this Cloud Agent VM, so `repair_real_chat_reply` was not executed here. The guard is the `looks_like_status_log` branch in that function.

## Blocker

This VM cannot change swap on `engel-spine-01`. The process gate only stops new runners while swap is already in use. Turning swap off on the Proxmox host is still a host action.

## Next

Deploy the chat service and Discord bridge on CT 246, then confirm `#general` shows work text and only one training pid.
