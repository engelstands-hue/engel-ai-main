import { readFile, readdir, stat } from "node:fs/promises";
import { extname, join, relative, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const scanRoots = ["src", "public", "docs"];
const textExtensions = new Set([".ts", ".tsx", ".css", ".html", ".md", ".txt", ".xml", ".json", ".svg"]);

const forbidden = [
  { label: "private IPv4 address", pattern: /\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b/g },
  { label: "loopback host", pattern: /\b(?:localhost|127\.0\.0\.1|0\.0\.0\.0)\b/gi },
  { label: "private Windows filesystem path", pattern: /\b[A-Z]:\\(?:Users|b\.WorkSpace|EngelPublic|ProgramData|WindowsApps)\\/gi },
  { label: "private runtime path", pattern: /\/(?:opt|mnt)\/engel\b/gi },
  { label: "network client call", pattern: /\b(?:fetch|XMLHttpRequest|WebSocket|EventSource)\s*\(/g },
  { label: "secret-like assignment", pattern: /\b(?:api[_-]?key|secret|password|private[_-]?key|access[_-]?token)\s*[:=]\s*["'][^"']+["']/gi },
  { label: "Moltbook credential material", pattern: /\bmoltbook_[A-Za-z0-9_-]{16,}\b/g },
];

async function filesUnder(directory) {
  const absolute = join(root, directory);
  const entries = await readdir(absolute, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const path = join(absolute, entry.name);
    if (entry.isDirectory()) files.push(...await filesUnder(relative(root, path)));
    else if (entry.isFile() && textExtensions.has(extname(entry.name))) files.push(path);
  }
  return files;
}

const files = (await Promise.all(scanRoots.map(filesUnder))).flat();
const failures = [];

for (const file of files) {
  const content = await readFile(file, "utf8");
  for (const rule of forbidden) {
    rule.pattern.lastIndex = 0;
    if (rule.pattern.test(content)) failures.push(`${relative(root, file)}: ${rule.label}`);
  }
}

const required = [
  "dist/index.html",
  "dist/_headers",
  "dist/brand-assets/engel-mark.svg",
  "dist/engel-ai-main.html",
  "dist/agents.html",
  "dist/status.html",
  "dist/privacy.html",
  "dist/terms.html",
  "dist/security.html",
  "dist/contact.html",
  "dist/404.html",
  "dist/.well-known/security.txt",
  "dist/og.png",
  "dist/site.webmanifest",
];

for (const requiredPath of required) {
  try {
    const info = await stat(join(root, requiredPath));
    if (!info.isFile() || info.size === 0) failures.push(`${requiredPath}: missing or empty build artifact`);
  } catch {
    failures.push(`${requiredPath}: missing build artifact`);
  }
}

const routeMetadata = JSON.parse(await readFile(join(root, "src", "data", "route-metadata.json"), "utf8"));
for (const metadata of routeMetadata) {
  const shell = metadata.path === "/" ? "dist/index.html" : `dist/${metadata.path.slice(1)}.html`;
  try {
    const html = await readFile(join(root, shell), "utf8");
    const canonical = new URL(metadata.path, "https://engelailabs.com").toString();
    if (!html.includes(`<title>${metadata.title}</title>`)) failures.push(`${shell}: route title missing`);
    if (!html.includes(`<link rel="canonical" href="${canonical}" />`)) failures.push(`${shell}: canonical URL missing`);
    if (!html.includes(`content="${metadata.index ? "index, follow" : "noindex, nofollow"}"`)) failures.push(`${shell}: robots directive missing`);
  } catch {
    failures.push(`${shell}: route shell missing`);
  }
}

const headers = await readFile(join(root, "public", "_headers"), "utf8");
if (!headers.includes("connect-src 'none'")) failures.push("public/_headers: browser connection boundary weakened");
if (!headers.includes("Strict-Transport-Security")) failures.push("public/_headers: HSTS missing");

if (failures.length) {
  console.error("ENGEL_PUBLIC_BOUNDARY_FAIL");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log(`ENGEL_PUBLIC_BOUNDARY_PASS (${files.length} source files scanned)`);
