# Cloudflare production deployment

## Current production state

The Engel AI Labs public site and canonical-host redirect are deployed and verified.

- Canonical URL: https://engelailabs.com
- Canonical `www` behavior: permanent HTTP 308 redirect to the apex, preserving path and query
- Cloudflare Pages project: `engelailabs-site`
- Pages deployment method: Direct Upload
- Pages production branch: `main`
- Pages deployment ID: `dbe09d23`
- Pages preview URL: https://dbe09d23.engelailabs-site.pages.dev
- Redirect Worker: `engelailabs-www-redirect`
- Worker version: `c9e6a684-8cf7-4ffc-ba98-9a21f0b6c6c1`
- Worker route: `www.engelailabs.com/*`
- Worker version created: `2026-08-14T01:30:58.764Z`
- Production verification completed: `2026-09-28T17:02:00Z`

The apex is a static Pages deployment. The small redirect Worker has no bindings, secrets, storage, subrequests, or private-system connectivity.

## Publish a reviewed update

Requirements: Node.js 22.12 or newer and an authenticated Wrangler 4.x session for the intended Cloudflare account.

To verify and deploy both the Pages site and the `www` redirect:

```powershell
cd "D:\b.WorkSpace\Engel App\public\engelailabs-site"
npm ci
npm run deploy:production
```

To deploy each component separately:

```powershell
npm run deploy:cloudflare
npm run deploy:edge
```

The Pages command runs the complete local verification chain before uploading `dist/`. A failed typecheck, test, edge check, build, archive-integrity check, or public-boundary scan prevents publication.

Read-only deployment inspection:

```powershell
npx wrangler pages deployment list --project-name engelailabs-site
npx wrangler deployments list --config edge/www-redirect/wrangler.jsonc
```

## DNS and routing

- `engelailabs.com` serves the static Cloudflare Pages project.
- `www.engelailabs.com/*` is routed to the isolated redirect Worker and returns HTTP 308 to the equivalent apex URL.
- HTTPS and HSTS are active.

Do not route either hostname to private Engel hosts, local IP addresses, worker-device addresses, or internal service endpoints.

## Environment values

The site works without environment values. Optional public community links are documented in `.env.example`.

Every `VITE_*` value is embedded in the public browser bundle. Never put tokens, credentials, internal addresses, private API URLs, or personal data in a Vite variable.

## Verified production behavior

- The public company, Engel AI Main product, platform, archive, community, Agent, Status, documentation, legal, security, and contact routes return HTTP 200.
- `/engel-ai-main` presents version `1.1.0+2`, the five daily desks (Chat, Discord, Status, Settings, Advanced), the Advanced tool groups, the reviewed-work workflow, and the local-runtime availability boundary without publishing personal runtime state or a download link.
- `/engel-ai-main`, `/technology`, and `/genesis` present the qualified Rust-rewrite record: operator-reported 40+ hours, retained elapsed evidence windows, the historical migration and completion receipts, the untracked-source provenance caveat, deliberate service-lane exceptions, and an explicit statement that the current checkout was not freshly audited.
- `/agents` links to the claimed `engel-ai-main` Moltbook profile and describes the explicit human-review workflow.
- `/status` is an allowlisted, manually reviewed public snapshot; it performs no live probes.
- `/agents`, `/community`, and `/status` truthfully describe one explicitly requested, bounded discovery read leading to one exact local draft and a separate human decision; recurring discovery, posting, and commenting remain disabled.
- Unknown direct URLs return a real noindex HTTP 404 page.
- `/.well-known/security.txt` returns `text/plain`.
- Every route shell has a route-specific title, description, canonical URL, Open Graph URL, and social image.
- `/archive-editions` and its static assets carry both page metadata and an `X-Robots-Tag` noindex directive.
- The public Archive Editions manifest, artwork digests, schema, and concept-only state are checked during every deployment.
- CSP includes `connect-src 'none'` and blocks forms, frames, and external connections.
- HSTS, clickjacking, MIME-sniffing, referrer, permissions, opener, and resource-policy headers are active.
- No permissive `Access-Control-Allow-Origin` header is emitted.
- Fingerprinted JavaScript and CSS assets use one-year immutable caching.
- The live HTML, JavaScript, and CSS scan found no private addresses, local filesystem paths, server paths, or private-key material.
- `https://www.engelailabs.com/agents?source=verification` returns HTTP 308 to `https://engelailabs.com/agents?source=verification`.

## Rollback

Cloudflare Pages retains the prior production deployment `2c861144-cc3e-44be-97c6-06919591afff`. If a Pages rollback is needed, promote that known deployment in the Cloudflare dashboard. For the redirect Worker, use Wrangler's deployment history to restore a known version. Re-run the live route and header checks after either rollback.

Official references:

- https://developers.cloudflare.com/pages/get-started/direct-upload/
- https://developers.cloudflare.com/pages/configuration/headers/
- https://developers.cloudflare.com/pages/configuration/serving-pages/
- https://developers.cloudflare.com/pages/how-to/www-redirect/
- https://developers.cloudflare.com/workers/configuration/routing/routes/
- https://developers.cloudflare.com/workers/best-practices/workers-best-practices/
