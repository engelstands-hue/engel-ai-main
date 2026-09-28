# Engel Remote Worker Android Contract V1

## Purpose

This Flutter app is a lightweight Android Remote Worker helper for Engel. It gives the phone a simple human-visible interface for viewing future approved task packets and preparing local draft result text for Engel review.

## Phase

Scaffold only.

## Phase 2 GUI And Packet I/O

Phase 2 improves the Flutter Remote Worker GUI and adds manual packet import/export only.

Added behavior:

- Polished Engel Remote Worker dashboard UI.
- Manual task/review packet JSON paste/import.
- Local packet validation and human-visible packet summary.
- Review-only display for Engel target packets.
- Review-only display for Super Swarm target packets.
- Local draft result JSON generation.
- Copy-to-clipboard result export.
- Example packet loaders for manual, Engel review, and Super Swarm review packets.

Phase 2 does not add a transport channel. Packet import and result export remain manual and human-visible.

Phase 2 result JSON remains untrusted until Engel verifier review and human approval.

Phase 2 blocked behavior:

- No direct fixing.
- No direct Engel control.
- No direct Super Swarm control.
- No trusted-memory write.
- No queue mutation.
- No source mutation.
- No route mutation.
- No network sync.
- No background sync.
- No provider/API calls.
- No WSL dependency.
- Hermes/Hermes-style runtimes rejected / blocked / do not install on this computer.
- No auto-apply behavior.

## Phase 3 PC-side Manual Result Intake

Phase 3 adds a PC-side manual intake lane for result JSON exported by the Flutter Remote Worker app.

The Flutter app still does not connect to Engel. A human manually copies/exported result JSON into Engel's local intake area or passes an explicit local path to the intake tool.

Phase 3 PC-side intake behavior:

- Engel reads one explicit local result JSON only when a human runs the intake command.
- Engel validates the result as untrusted review-only data.
- Engel writes a bounded intake receipt/report for human review.
- Engel requires `requires_review: true`.
- Engel requires `safe_to_auto_apply: false`.
- Engel flags risky command-like text without executing it.
- Engel does not auto-apply, promote, trust, route, queue, or mutate source from Remote Worker output.

Remote Worker result intake is manual, untrusted, review-only, and never auto-applies output.

## Phase 4 Local LAN Pairing / Status Handshake

Phase 4 adds Local LAN pairing/status only.

The Flutter app can make manual button-triggered `/health` and `/pair` requests to an Engel PC receiver that the human starts explicitly. The receiver defaults to `127.0.0.1`; LAN binding requires explicit `--allow-lan`.

Phase 4 behavior:

- Manual receiver start.
- Manual button-triggered Flutter requests.
- Short-lived pairing code generated on the Engel PC.
- Status-only pairing response.
- No packet transfer/result upload.
- No control.
- No auto-sync/background behavior.
- No trusted-memory write.
- No queue/route/source mutation.
- No command execution from response or request data.
- No provider/API/cloud relay behavior.

Android INTERNET permission is present only for manual LAN pairing/status requests. No cloud sync, provider/API behavior, background polling, or automatic reconnect is enabled.

## Phase 5 Communication Queen Approved Auto-Assignment

Phase 5 adds bounded automatic worker assignment after a successful LAN pairing/status handshake.

The Flutter app can run visible foreground Auto Mode only after the user pairs with the Engel PC receiver. Auto Mode polls for Communication Queen approved assignment packets and may return an untrusted acknowledgement result. The PC receiver must still be started manually by the human.

Phase 5 automatic behavior:

- Pairing required before worker endpoints are used.
- Auto Mode is user-enabled and visible in the UI.
- Auto Mode can be paused/stopped from the UI.
- Polling happens only while the app is open/foreground.
- Polling asks only for Communication Queen approved assignment packets.
- Returned results are untrusted, require Engel review, and use `safe_to_auto_apply: false`.
- Phase 5 returns bounded acknowledgement results only; no local AI/model reasoning is enabled.

Phase 5 blocked behavior:

- No direct Engel control.
- No route execution.
- No command execution.
- No arbitrary packet execution.
- No trusted-memory write.
- No source mutation.
- No route mutation.
- No trusted queue mutation.
- No auto-apply.
- No provider/API/cloud relay behavior.
- No Android background service, boot receiver, manifest wake-lock permission, or hidden worker.
- A visible foreground screen wakelock is allowed only while the Engel Remote Worker app is open, so long-running WiFi polling does not silently sleep.

## Phase 6 Long-Idle Wake Guard

Phase 6 adds a bounded long-idle wake guard for dedicated Engel phones.

Phone-side behavior:

- The app enables a visible foreground screen wakelock while the app is open.
- When Android resumes the app, it refreshes the wakelock, checks pairing, restarts discovery if needed, and polls once if Auto Mode is enabled.
- The phone still does not auto-start on boot and does not run a hidden background service.

PC-side behavior:

- Engel may detect stale worker last-seen times from the LAN link manager.
- If a known Engel phone is stale and physically USB-connected, Engel may refresh only the current pairing config in the worker app's own storage, wake the screen, stop only the stale Engel Remote Worker app package, and launch the visible Engel Remote Worker app.
- USB wake does not transfer job payloads. Jobs still move through the WiFi/LAN assignment queue.
- Pairing config refresh is token-only app configuration for the dedicated worker app; receipts and reports must redact the token and must not store it in source or reports.
- WiFi ADB remains disabled.

Phase 6 blocked behavior:

- No raw shell target.
- No job payload transfer over USB.
- No WiFi ADB.
- No hidden Android background worker.
- No Android-to-PC control.
- No trusted-memory write.
- No source, route, or queue mutation from the phone.

## Transport

Phase 4 includes manual local LAN pairing/status checks. Phase 5 adds paired, foreground-only polling for Communication Queen approved assignments and untrusted result return. Phase 6 adds bounded USB wake/visible-app relaunch for stale dedicated Engel phones only. The app still has no provider bridge, cloud sync, route execution, source mutation, trusted-memory write, or Android-to-PC control channel.

## Authority

Engel Core on the PC remains the authority. The Android phone is not a controller and cannot directly mutate Engel.

## Trust Level

All returned phone output is untrusted returned output until Engel verifier review and human approval.

## Allowed Now

- Local UI.
- Local draft state.
- Manual human-visible task text.
- Manual human-visible result text.
- Empty packet state for future approved task packets.

## Blocked Now

- Direct command execution.
- Queue mutation.
- Trusted memory writes.
- Provider or network calls.
- Hidden background sync.
- Auto-start services.
- Remote shell behavior.
- File-system bridge to Engel.
- Android-to-PC control.
- Engel route mutation.
- Engel source mutation.
- Model output execution as commands.
- Hermes/Hermes-style runtimes rejected / do not install on this computer.

## Safety Rule

The phone may help draft candidate work, but Engel remains the controlling safety membrane. All returned work requires Engel verifier review and human approval before it can affect trusted memory, routes, source, queues, or any controlled Engel state.
