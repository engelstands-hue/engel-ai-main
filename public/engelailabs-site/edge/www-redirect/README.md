# `www` canonical redirect

This isolated Cloudflare Worker permanently redirects `www.engelailabs.com` to the canonical apex origin while preserving the request path and query string.

It has no bindings, secrets, subrequests, storage, private-system connectivity, or request-body processing. The Worker route applies only to `www.engelailabs.com/*`; the apex remains the static Cloudflare Pages deployment.

Validate and deploy from the public site root:

```powershell
npx wrangler types edge/www-redirect/worker-configuration.d.ts --config edge/www-redirect/wrangler.jsonc
npx tsc --noEmit -p edge/www-redirect/tsconfig.json
npx vitest run edge/www-redirect/src/index.test.ts
npx wrangler deploy --config edge/www-redirect/wrangler.jsonc
```
