import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const readText = (path) => readFile(resolve(root, path), "utf8");
const readJson = async (path) => JSON.parse(await readText(path));
const failures = [];
const requireState = (condition, message) => { if (!condition) failures.push(message); };

const manifest = await readJson("public/archive-editions/edition-i/manifest.json");
const schema = await readJson("public/schemas/genesis-archive-record-v1.json");
const routeMetadata = await readJson("src/data/route-metadata.json");
const pageSource = await readText("src/pages/ArchiveEditionsPage.tsx");
const headers = await readText("public/_headers");
const sitemap = await readText("public/sitemap.xml");

requireState(manifest.schema_version === "1.0", "manifest schema_version must remain 1.0");
requireState(manifest.revision === "0.2.0", "manifest revision must be 0.2.0");
requireState(manifest.phase === "design_study", "archive must remain a design study");
requireState(manifest.indexed === false, "archive manifest must remain unindexed");
requireState(manifest.for_sale === false, "archive must not be for sale");
requireState(manifest.collectible_eligible === false, "archive must not be collectible eligible");
requireState(manifest.candidate_sequence_is_permanent === false, "candidate sequence must remain non-permanent");
requireState(Array.isArray(manifest.candidates) && manifest.candidates.length === 5, "exactly five draft candidates are required");
requireState(manifest.candidates?.every((candidate) => candidate.status === "evidence_pending"), "every candidate must remain evidence pending");

const artworks = manifest.artworks ?? [];
requireState(artworks.length === 2, "exactly two public concept artworks are required");
for (const artwork of artworks) {
  requireState(artwork.role === "artistic_interpretation", `${artwork.record_id}: role must be artistic_interpretation`);
  requireState(/^EGA-EI-00[12]$/.test(artwork.record_id), `${artwork.record_id}: unexpected artwork record`);
  requireState(/^\/archive-editions\/edition-i\/v0\.2\.0\/[a-z0-9-]+\.[a-f0-9]{16}\.png$/.test(artwork.path), `${artwork.record_id}: invalid immutable artwork path`);
  requireState(/^[a-f0-9]{64}$/.test(artwork.sha256), `${artwork.record_id}: invalid SHA-256`);
  const bytes = await readFile(resolve(root, "public", artwork.path.slice(1)));
  const digest = createHash("sha256").update(bytes).digest("hex");
  requireState(digest === artwork.sha256, `${artwork.record_id}: artwork digest mismatch`);
  requireState(artwork.path.includes(`.${artwork.sha256.slice(0, 16)}.png`), `${artwork.record_id}: filename digest prefix mismatch`);
  requireState(pageSource.includes(artwork.path), `${artwork.record_id}: page does not reference artwork path`);
  requireState(pageSource.includes(artwork.sha256), `${artwork.record_id}: page does not disclose artwork digest`);
}

requireState(manifest.artwork?.sha256 === artworks[1]?.sha256, "legacy artwork field must mirror The Spine during compatibility window");
requireState(schema.$id === "https://engelailabs.com/schemas/genesis-archive-record-v1.json", "public schema $id mismatch");
requireState(schema.required?.includes("sequence_is_permanent"), "schema must require sequence_is_permanent");
requireState(schema.properties?.sequence_is_permanent?.const === false, "schema must keep sequence_is_permanent false");
requireState(schema.properties?.collectible?.properties?.eligible?.const === false, "schema must keep collectible eligibility false");
requireState(!schema.properties?.workflow_state?.enum?.includes("collectible_eligible"), "workflow must not contain collectible_eligible");

const archiveRoute = routeMetadata.find((route) => route.path === "/archive-editions");
requireState(archiveRoute?.index === false, "archive route must remain noindex");
requireState(!sitemap.includes("/archive-editions"), "archive route must remain absent from sitemap");
requireState(headers.includes("/archive-editions\n  X-Robots-Tag: noindex, nofollow"), "archive root X-Robots-Tag missing");
requireState(headers.includes("/archive-editions/*\n  X-Robots-Tag: noindex, nofollow"), "archive subtree X-Robots-Tag missing");
requireState(pageSource.includes("Nothing on this page is for sale"), "non-sale disclosure missing");
requireState(pageSource.includes("Artistic interpretation · not historical evidence"), "artistic-interpretation disclosure missing");

if (failures.length) {
  console.error("ENGEL_ARCHIVE_SITE_VERIFY_FAIL");
  failures.forEach((failure) => console.error(`- ${failure}`));
  process.exit(1);
}

console.log(`ENGEL_ARCHIVE_SITE_VERIFY_PASS artworks=${artworks.length} candidates=${manifest.candidates.length}`);
