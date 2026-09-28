# Public boundary

This repository is presentation-only.

## Never include

- Local or private IP addresses
- Private hostnames, ports, tunnels, or service topology
- Server, worker, device, SSH, or provider credentials
- Private API routes or schemas
- Personal files, paths, logs, receipts, prompts, memories, or training data
- Health probes, device discovery, remote commands, or background connections

## Engel AI Main, public agent, and status

`/engel-ai-main`, `/agents`, and `/status` contain a reviewed, static projection of public product and launch facts. They do not call Engel AI Main, Moltbook, the local agent database, or any private runtime, and they do not expose audit internals.

The public facts distinguish a claimed identity and explicit human-review console from recurring network activity. A person may initiate one bounded discovery, review and decide one exact draft, and separately confirm one send outside this website. Scheduled reads, automatic posts, and automatic comments remain disabled. The site contains no control surface that can discover, approve, send, activate a runtime, or release a gate.

Engel AI Main feature descriptions are an interface map, not live telemetry. The site does not publish local paths, worker counts, device state, model inventories, credentials, provider state, receipts, or training data. Runtime-dependent features are labeled as such, and no unsigned or incomplete desktop binary is offered for download.

The Moltbook credential is stored outside this project and must never appear in source, `VITE_*` values, build output, deployment logs, or Cloudflare environment variables.

## Reserved routes

`/api`, `/auth`, and `/workers` are visual placeholders. They do not have Pages Functions and must not proxy to private systems.

Any future backend should be a purpose-built public service with its own threat model, authentication, rate limits, logging policy, privacy review, and deployment approval. It must not expose Engel AI Main or worker devices directly.

## Release gate

Run `npm run verify` before publishing. It checks component behavior, route-specific shells, required public artifacts, HSTS, the no-connection CSP, and the public/private boundary scan.

Unknown direct URLs are served by a standalone, noindex `404.html`. The public disclosure pointer is available at `/.well-known/security.txt`.
