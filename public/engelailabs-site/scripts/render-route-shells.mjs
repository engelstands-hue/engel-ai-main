import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const dist = join(root, "dist");
const routeMetadata = JSON.parse(await readFile(join(root, "src", "data", "route-metadata.json"), "utf8"));
const base = await readFile(join(dist, "index.html"), "utf8");

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function routeShell(metadata) {
  const title = escapeHtml(metadata.title);
  const description = escapeHtml(metadata.description);
  const canonical = new URL(metadata.path, "https://engelailabs.com").toString();
  const robots = metadata.index ? "index, follow" : "noindex, nofollow";

  return base
    .replace(/<title>[^<]*<\/title>/i, `<title>${title}</title>`)
    .replace(/<meta name="description"[^>]*>/i, `<meta name="description" content="${description}" />`)
    .replace(/<meta name="robots"[^>]*>/i, `<meta name="robots" content="${robots}" />`)
    .replace(/<link rel="canonical"[^>]*>/i, `<link rel="canonical" href="${canonical}" />`)
    .replace(/<meta property="og:title"[^>]*>/i, `<meta property="og:title" content="${title}" />`)
    .replace(/<meta property="og:description"[^>]*>/i, `<meta property="og:description" content="${description}" />`)
    .replace(/<meta property="og:url"[^>]*>/i, `<meta property="og:url" content="${canonical}" />`)
    .replace(/<meta name="twitter:title"[^>]*>/i, `<meta name="twitter:title" content="${title}" />`)
    .replace(/<meta name="twitter:description"[^>]*>/i, `<meta name="twitter:description" content="${description}" />`);
}

for (const metadata of routeMetadata) {
  const output = metadata.path === "/" ? join(dist, "index.html") : join(dist, `${metadata.path.slice(1)}.html`);
  await mkdir(dirname(output), { recursive: true });
  await writeFile(output, routeShell(metadata), "utf8");
}

console.log(`ENGEL_ROUTE_SHELLS_WRITTEN (${routeMetadata.length} routes)`);
