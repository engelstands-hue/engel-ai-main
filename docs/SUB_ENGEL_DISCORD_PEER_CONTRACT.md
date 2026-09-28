# Sub-Engel Discord peer contract

What the Sub-Engel bot must do so it and Engel AI Main hold a real conversation in
`#general` (channel `1148755186752430163`). Engel's side is done and verified; this is the
matching half for whatever build runs on the living-room PC.

Observed 2026-08-13 17:57Z: Engel posted a direct `@Sub-Engel` question and the new build
did not reply, while its node listener at `http://198.51.100.227:8776` was up. Engel had
already replied to Sub-Engel earlier the same hour, so the silence is on the Sub-Engel side.
The usual cause is the standard `if message.author.bot: return` guard at the top of
`on_message` — correct for a normal bot, fatal here, because the peer *is* a bot.

## Required

1. **Do not drop bot authors outright.** Replace `if message.author.bot: return` with a
   whitelist test.
2. **Whitelist Engel AI Main:** bot user id `1506157762785312808`.
3. **Never reply to itself:** compare against `client.user.id` before anything else. Sub-Engel
   is `1537474262242168842`.
4. **Answer when addressed** — an `@mention` of Sub-Engel, or a vocative (`hey Sub-Engel`, `Sub-Engel, status?`). Naming Sub-Engel inside an Engel turn (`I want you to talk with Sub-Engel`) is not a summon.
5. **Bound the exchange**, or two bots will flood the channel forever:
   - count consecutive AI turns per channel and stop at a cap (Engel uses 12 here, 6 elsewhere);
   - reset that counter on any message from a human, which re-arms the exchange;
   - pace replies (Engel waits 8s) so it reads as conversation, not a wall;
   - do not answer a peer message that is byte-identical to the previous one — a bot repeating
     itself is stuck, not talking. Engel enforces this from its side too.
6. **Say something real.** Answer from live node state (hostname, listener health, pairing
   expiry, training flag). If a source is unreachable, say which one and why rather than
   emitting a fixed sentence. A canned line makes the channel look broken and burns turns.
7. **Pause, read, then talk.** After a human summon, wait ~2.6s and re-read the room. Stay
   silent if Engel AI Main or a desk already answered that line. Speak in first person from
   a real thought. Strip Joshua-asks / Engel-explains templates. The live mouth on
   DESKTOP-UE5A6GG is `subengel_discord_presence.py` (build `2026-09-07T_pause_read`).

## What Engel now does on its side

- Sub-Engel is a whitelisted peer, so its messages reach the model instead of being dropped.
- Peer turns are sent with `chat_only`, so a status report can never open a meeting-room work
  order. Before this, 11 orders were created in 3 minutes from Sub-Engel's status text.
- A peer's status vocabulary ("server", "worker", "health", "route", "token") no longer trips
  the guest gate; only an imperative ("restart the bridge") is refused.
- Engel is told in-turn that it is replying to Sub-Engel and not to Joshua, and the peer keeps
  its own name in the transcript.
- Engel stays quiet when a human `@mentions` Sub-Engel alone, so the two bots stop
  double-answering the same line.

## Reference implementation

`tools/engel_sub_engel_discord_worker.py` implements all of the above and ships with offline
proofs — no token or network needed:

```
python engel_sub_engel_discord_worker.py --selftest   # 25/25 gate checks
python engel_sub_engel_discord_worker.py --report     # prints real node state
```

Install with `tools/Install-SubEngelDiscordWorker.ps1 -Yes` (run it on the living-room PC; it
stops the old bot first, since two bots on one token fight over the gateway session). Do not
start a second Sub-Engel Discord gateway from the ROG laptop.

## Environment it reads

| Variable | Default | Meaning |
| --- | --- | --- |
| `SUB_ENGEL_DISCORD_BOT_TOKEN` | — | bot token (or `<node>\state\discord.env`) |
| `SUB_ENGEL_DISCORD_PEER_BOT_IDS` | `1506157762785312808` | peers it will converse with |
| `SUB_ENGEL_DISCORD_CHANNEL_IDS` | any | channels it may speak in |
| `SUB_ENGEL_DISCORD_PEER_MAX_TURNS` | `6` | consecutive AI turns before it goes quiet |
| `SUB_ENGEL_DISCORD_PEER_COOLDOWN_SECONDS` | `8` | pacing between peer replies |
| `SUB_ENGEL_NODE_HEALTH_URL` | `http://127.0.0.1:8776/health` | its own node server |
| `SUB_ENGEL_BRAIN_URL` | empty | optional LLM; CT246 chat is loopback-only, so leave unset unless a relay exists |

## Correction to carry into the build

There is no **CT256**. The server is **CT246** (`engel-ai-main`): LAN `192.0.2.50` port
`24622`, internal `10.246.0.2`. Containers on the host are 245 (stopped), 246, 250. Sub-Engel
has been reporting a failure to resolve a hostname that does not exist.
