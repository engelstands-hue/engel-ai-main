# ENGEL AI MAIN — SESSION HANDOFF 2026-07-27

Goal in force: **Conical Agentic Sentient Self Upgrading System**
(`memory/ENGEL_PRIMARY_GOAL_V1.json`). CT246 `/opt/engel` is the brain and source
of truth; ROG is the controller. Everything below is receipt-backed.

---

## 1. RIGHT NOW — live state at handoff

| Thing | State |
|---|---|
| EngelAIMain app | running **PID 21972**, chat-UI soak round 3 active |
| Soak round 3 | **~86/199 prompts done** (`ui_soak_20260727T121835`), deadline 300 min, self-completes |
| CT chat service | restarted, **active**, healthy |
| Production model | **UNCHANGED** — `98d45e94…` (the proven r3 model) |
| Latest LoRA | trained, **NOT deployed**, awaiting canary |
| RunPod | all pods terminated, API key temp deleted |
| GREEN | last full check exit 0 |

### The one thing waiting for a decision
`runtime/runpod/standalone_llm_training/artifacts/engel_standalone_lora_adapter_rc59qb9610cjw6_20260727T140541Z`
— the **identity-rebalanced** LoRA (identity anchor raised 3× → 12×, train 1296,
loss ~0.11, $0.30). It has **not** been merged, quantized, or canaried yet.

**Next step to finish it** (same path used all session):
1. scp `adapter_config.json` + `adapter_model.safetensors` →
   `/opt/engel/llm_training/selfupgrade_20260726/adapter_r2/`
2. run the merge+quantize script (merge → f16 → `llama-quantize q5_k_m` at
   `/opt/engel/llm_training/tools/llama.cpp/build/bin/llama-quantize`)
3. **canary head-to-head vs production** using `/opt/engel/.venv/bin/python` +
   `llama_cpp` (same runtime that serves) — must ask "Who are you?" and confirm
   NO identity regression (the last candidate said *"I'm Joshua"* + invented IPs
   and was correctly REFUSED)
4. only on pass: back up live GGUF to a `.pre_*_bak_<stamp>` sibling, swap,
   restart `engel-main-chat`, prove with a live `/chat` turn.

---

## 2. What shipped this session (all verified + hash-synced ROG↔CT246)

### Neuro system update (NT-1/2/3)
A 4-reader audit found 34 issues; the load-bearing ones are fixed and live:
- **NT-1**: ten zero-inference template routes were mislabelled depth-1 → now
  depth-0 (mapped-0 is authoritative); `local-llama-cpp-lora` added to big-lane
  markers in **both** implementations (it was mislabelled after the model swap);
  `runs_inference=False` now gates the fast heuristic.
- **NT-2**: the service's own 900-char clip no longer reads as model truncation
  (was force-escalating every long quick reply); empty replies force-escalate;
  style-grader failure = neutral 0.7 penalty (was silently 1.0);
  `ENGEL_QUICK_LANE_ESCALATION_ENABLED` is now a **real kill switch**.
- **Telemetry made durable**: confidence/tau/escalated/evidence/mode_gate/
  freshness now persist in every final memory record (they used to be destroyed
  for exactly the turns that escalated).
- **NT-3**: buffered streaming turn now runs in a copied contextvars context;
  failed cache reset hard-clears.
- Verifiers: `verify_engel_activation_depth_labelling` (extended with 16 real
  production strings), `verify_nt3_retrieve_once` — both registered in the
  **chat-surface verifier matrix**, so every future model swap re-runs them.

### Quality-gate over-blocking fix (today's last change)
**Root cause proven with a probe, not guessed**: the incomplete-input discipline
was judged against the *semantic-quality prompt*, which is
`PRIOR TURN … CURRENT USER TURN: <question>`. An unrelated earlier answer
containing generic words (`evidence`/`design`/`record` + `unknown`/`conflict`)
dragged the **next clean question** into construction-document discipline and
refused it — that is why a six-line briefing request and an ethics question were
both blocked during training.
- Fix: new `_current_turn_text()`; both `_prompt_has_incomplete_project_inputs`
  and `_incomplete_input_quality_report` now judge **only the current turn**.
- New verifier `tools/verify_engel_incomplete_input_gate_scope.py` — **7/7 on
  both machines**, and it proves genuine project questions STILL gate.
- Deployed to CT246, service restarted, hash-identical `1d6f27d19563e250`.

### Visibility
- `nt` section in `engel_self_upgrade_loop_stream.py` (depth histogram,
  escalations by origin, confidence stats) + a **Neuro line** in the Tasks-page
  *Self-Upgrade Loop* panel.
- Pipe probing fixed to be **side-aware** (bridges live on ROG even ports, CT
  reaches them on port+1 via reverse tunnels) — CT reported 0 pipes up before,
  now 5.

### Chat training (real UI, not scripted API calls)
Three soak rounds through the **actual chat box** (`ENGEL_UI_CHAT_SOAK_*` env →
types + submits like a user):
- R1 55/55, R2 40/40 (both complete), R3 199 expert prompts in flight.
- Templates are reusable: `runtime/engel_ui_chat_soak_*.json`.
- Live proof from R1/R2: **broker gate consulted on real chat builds, all three
  phones eligible AND returning**, Sub-Engel offline → honest 3/4 failures →
  auto-ingested as issues; a real meeting-room order that Engel later **cited as
  evidence** in its own synthesis.

---

## 3. Open items, honestly

1. **Sub-Engel desktop (DESKTOP-UE5A6GG) is offline.** This is the single
   biggest blocker — it fails every conical build at 3/4 and generates most of
   the issue backlog. Nothing converges 4/4 until it returns.
2. **Backlog driver not built (task "B").** 11+ issues sit as issues because
   nothing drafts routes/candidates for them. The gates aren't the problem —
   *movement through* them is. This was the agreed next build.
3. **Boilerplate bleed** (issue `e769c4a2`): the quality rewrite template still
   injects "Hold and owner / field survey lead" phrasing into general judgment
   answers. Separate from today's scope fix.
4. **Provider picker (Cursor/VS-Code style) not built.** Grounded already: the
   CT service **already honors** `provider`/`bridge`/`selected_provider` when a
   force flag is set (`_request_explicit_provider_allowed`). The missing piece is
   purely UI → send `force_provider` from a model dropdown in the chat box.
5. **Forbidden node DESKTOP-FIB17O7** still writes bus claims in the shared room.
   Dispatch hard-blocks it; retiring it at the source is unfinished.

---

## 4. Rules that bit me — do not relearn the hard way

- **ssh from PowerShell**: pipe scripts via `cmd /c "ssh … ""bash -s"" < file"`
  with a **BOM-free LF** file. PS pipelines re-add BOM/CRLF and break bash.
- **Training window**: always pass `--max-length 2048`. The aligned system
  prompt alone is ~1050 tokens; at the 768 default every assistant answer is
  silently truncated out of training (loss 0.03 = memorizing system prompts).
- **Seed weighting**: identity anchor must be ≥ any knowledge seed. Two ×12
  knowledge seeds against a ×3 identity anchor caused a real identity regression.
- **Chat lane is serial** — ONE client at a time. Concurrent drills 502 it.
- **Manifest pin chain**: the widget-suite string is pinned in *both*
  `verify_engel_objective_coverage_audit.py` and
  `verify_engel_current_release_manifest.py`, and each verifier's own hash is
  pinned in the manifest. Update all three together or GREEN fails.
- **Verifier fixtures must isolate one invariant.** A confounded fixture let a
  freshness-widening patch commit; the same class of mistake nearly made me
  "fix" the wrong function today until a probe disproved my hypothesis.

---

## 5. Key paths

- Catalog + router: `memory/ENGEL_SELF_UPGRADE_SYSTEM_CATALOG_V1.json`,
  `tools/engel_self_upgrade_catalog_router.py route --query "…"` (21 parts)
- Governed cycle: `tools/engel_conical_self_upgrade_cycle.py`
- Gates: `tools/engel_self_patch_quorum.py`,
  `tools/engel_deployment_rollback_automation.py`
- Visibility: `tools/engel_self_upgrade_loop_stream.py` → Tasks page panel
- Drills: `tools/run_engel_neuro_training_session.py`
- Receipts: `reports/self_upgrade/receipts/` (both machines) — today's:
  `ENGEL_NEURO_SYSTEM_UPDATE_20260727.json`,
  `ENGEL_UI_CHAT_TRAINING_SOAK_20260727.json`
- GREEN: `python tools\engel_health_check.py --full`

---

## 6. Suggested first moves in the new session

1. Check soak R3 finished (`reports/codex_bridge/ENGEL_CHAT_UI_SOAK_ui_soak_20260727T121835*.jsonl`).
2. **Canary + gate the rebalanced adapter** (section 1) — highest value, already paid for.
3. Build the **backlog driver** (issues → routes → candidate drafts).
4. Then the **provider picker** UI wiring.

---

## 7. ADDENDUM — late session 2026-07-27/28 (see `reports/codex_bridge/ENGEL_BACKLOG_DRIVER_AND_R2_CANARY_20260727.md`)

- Soak R3 self-completed at deadline, 198/199.
- **Rebalanced adapter: merged + quantized + canary PASS 6/6 + DEPLOYED.**
  Owner authorized the run at 03:21Z 20260728: rollback sibling
  `.pre_rebalance_bak_20260728T032130Z`, live GGUF now `df1a4ba0…`,
  `engel-main-chat` restarted healthy, live /chat identity proof captured.
  Receipt: `reports/llm_training/ENGEL_SELFUPGRADE_R2_DEPLOY_20260728T032130Z.json`
  (canary receipt: `ENGEL_SELFUPGRADE_R2_CANARY_20260727T234654Z.json`).
- **Backlog driver EXISTS now**: `tools/engel_self_upgrade_backlog_driver.py`
  (+ verifier 16/16 both machines, hash-synced). Real runs: CT246 backlog
  23 → 6 open, ROG 11 → 4 open, every closure evidence-cited. Draft lane is
  bounded dry-run only; two honest plan failures recorded on the issues.
- **GREEN restored on ROG**: rebuilt Flutter (81/81 tests), restarted
  (PID 18044), manifest re-pinned, release verifier ok:true.
- Afternoon Codex session (separate, receipted): Sub-Engel back 4/4
  (ThreadingHTTPServer fix + CT246-authoritative sessions), prompt→patch
  provenance stage live, ledger fixture repair.
- **Provider picker built** (open item 4 closed): dropdown in both chat
  composers → `provider` + `force_provider` through the worker to CT246;
  build lane ignores it; training sentinel still wins.
  `verify_engel_provider_picker.py` 11/11; worker hash-synced to CT246.
- **Live UI end-to-end proof (00:23–00:39Z 20260728)**: two one-prompt UI soak
  runs drove a real conical build through the chat composer — Meeting Room
  order, **4/4 workers**, full lifecycle, memory appended, honest visible
  verdict — but both ended `ct_build_lane_no_usable_generator`, filed as
  **`engel_issue_cb16588cfc1f0840`**.
- **That issue is now FIXED and closed with evidence (03:37–03:49Z)**: root
  cause was `_build_lane_reply_usable`'s `len>=2000` substantiality floor
  rejecting protocol-correct compact multi-file replies (not a dead model);
  replaced with extraction-grounded acceptance (strict widening), verifier
  `verify_engel_build_lane_usable_gate.py` 9/9 both machines, rollback backup
  kept, and the exact failing prompt now **verifies end-to-end through the UI**
  ("app build lifecycle verified", 4/4 workers). Residual local-coder protocol
  flakiness (build passed via recovered attached-Codex fallback, not the local
  lane) filed precisely as **`engel_issue_29be57ba025a6794`** — good draft-lane
  target. GREEN re-stamped PID 35032.
- Standing rule (owner, 2026-07-27): **RunPod only for big training jobs** —
  routine Engel training/inference stays on ROG GPU / CT246.
