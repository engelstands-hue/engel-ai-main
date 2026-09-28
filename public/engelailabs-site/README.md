# Engel AI Labs Public Platform

Public-facing company and technology website for `engelailabs.com`.

This project is deliberately isolated from Engel AI Main and every private runtime. It is a static React/Vite site. It has no API client, authentication provider, device discovery, health probing, private routes, or server credentials.

## What is included

- Responsive company site with a complete Engel AI Main product map, Home, About, Technology, Platform, Apps, Genesis Archive, Community, Agent, and reviewed Status pages
- Public-safe coverage of the current Engel AI Main daily side (Chat, Discord, Status, Settings, Advanced) and the Advanced tool groups, including explicit runtime-dependent readiness labels
- Public Privacy, Terms, Security, and Contact notices
- Claimed Moltbook Ambassador profile and verified launch-post links, rendered as static outbound links only
- Reviewed disclosure of the explicit one-at-a-time Moltbook workflow: human-started discovery, exact-draft review, approve or deny, separate send, and separate challenge confirmation
- Clear disclosure that recurring discovery, subscriptions, posts, and comments remain disabled
- Inert future-route placeholders at `/api`, `/auth`, and `/workers`
- Markdown-backed public documentation at `/docs`
- Cloudflare Pages configuration and security headers
- SVG and installable PNG brand assets under `public/brand-assets`, plus a bespoke social-sharing image
- Per-route static HTML shells with canonical URLs, route metadata, and a real noindex `404.html`
- A public-boundary verifier that rejects local addresses, private filesystem paths, network client code, and secret-like assignments

## Local development

Requirements: Node.js 22.12 or newer.

```powershell
cd "D:\b.WorkSpace\Engel App\public\engelailabs-site"
Copy-Item .env.example .env.local
npm install
npm run dev
```

The environment file is optional. The canonical Moltbook profile has a safe built-in fallback. Empty future-community URLs render as “Coming soon” and do not create outbound links.

## Verification

```powershell
npm run verify
```

This runs TypeScript checking, component and edge tests, redirect-Worker validation, a production build with route shells, archive verification, and the public-boundary verifier.

## Production build

```powershell
npm run build
```

The deployable static output is written to `dist/`.

## Cloudflare

The production deployment is live at [engelailabs.com](https://engelailabs.com). An isolated Cloudflare Worker permanently redirects `www.engelailabs.com` to the canonical apex while preserving the path and query string. It has no bindings, secrets, storage, subrequests, or private-system connectivity.

See [DEPLOYMENT.md](./DEPLOYMENT.md) for the verified production receipt and rollback procedure. `npm run build` remains local-only; `npm run deploy:production` verifies and publishes both the Pages site and canonical-host redirect. The components can also be deployed separately with `npm run deploy:cloudflare` and `npm run deploy:edge`.

## Content editing

- Company and product content: `src/data/site.ts`
- Long-form Markdown: `src/content/platform-overview.md`
- Page components: `src/pages/`
- Shared components: `src/components/`
- Brand source files: `public/brand-assets/`

## Security boundary

See [SECURITY.md](./SECURITY.md). The public site must never be connected directly to private Engel infrastructure.
