import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import { ambassador, architecture, engelMain, genesisTimeline, localIntelligence, placeholders, products, rustRewrite } from "./data/site";
import { publicEnvironment, publicHttpsUrl } from "./lib/environment";

function renderPath(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("public platform routes", () => {
  it("renders the approved home headline and platform promise", () => {
    renderPath("/");

    expect(screen.getByRole("heading", { level: 1, name: /Engel AI Main/i })).toBeInTheDocument();
    expect(screen.getAllByText(/The daily side is Chat, Discord, Status, Settings, and Advanced/i).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /Explore Engel AI Main/i })).toHaveAttribute("href", "/engel-ai-main");
  });

  it("links the Built here row to the public sibling sites", () => {
    renderPath("/");

    const templates = screen.getByRole("link", { name: "Dev templates for Obsidian and Notion" });
    expect(templates).toHaveAttribute("href", "https://forge.engelailabs.com/?utm_source=engelailabs&utm_medium=homepage");
    expect(templates).toHaveAttribute("rel", "noopener noreferrer");

    const tees = screen.getByRole("link", { name: "VIBE // DROP — vibe-coding tees" });
    expect(tees).toHaveAttribute("href", "https://wearthecrash.printful.me/?utm_source=engelailabs&utm_medium=homepage");
    expect(tees).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("maps the complete current Engel AI Main surface without publishing live telemetry", () => {
    renderPath("/engel-ai-main");

    expect(screen.getByRole("heading", { level: 1, name: /One visible workspace for the whole Engel system/i })).toBeInTheDocument();
    expect(screen.getByText(engelMain.version)).toBeInTheDocument();
    expect(engelMain.dailyDesks).toHaveLength(5);
    expect(engelMain.advancedGroups).toHaveLength(5);
    expect(screen.getByText(/Chat: Auto Best/i)).toBeInTheDocument();
    for (const area of [...engelMain.dailyDesks, ...engelMain.advancedGroups]) {
      expect(screen.getByRole("heading", { level: 2, name: area.name })).toBeInTheDocument();
      for (const view of area.views) expect(screen.getAllByText(view).length).toBeGreaterThan(0);
    }
    expect(screen.getByText(/Representative interface map/i)).toBeInTheDocument();
    expect(screen.getByText(/not offered as a public download/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Read the source/i })).toHaveAttribute("href", engelMain.sourceUrl);
    expect(screen.queryByText(/Welcome back, Joshua/i)).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/[A-Z]:\\/);
  });

  it("publishes product-specific metadata for Engel AI Main", async () => {
    renderPath("/engel-ai-main");

    await waitFor(() => expect(document.title).toBe("Engel AI Main | Complete product map"));
    expect(document.head.querySelector('link[rel="canonical"]')).toHaveAttribute("href", "https://engelailabs.com/engel-ai-main");
    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute("content", "index, follow");
  });

  it("shows the qualified Engel Core Rust rewrite evidence in the product map", () => {
    renderPath("/engel-ai-main");

    expect(screen.getByRole("heading", { level: 2, name: /A 40\+ hour Rust rewrite beneath Engel AI Main/i })).toBeInTheDocument();
    for (const fact of rustRewrite.durationEvidence) {
      expect(screen.getByText(fact.value)).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: fact.label })).toBeInTheDocument();
    }
    for (const fact of rustRewrite.completionEvidence) {
      expect(screen.getByText(fact.value)).toBeInTheDocument();
    }
    expect(screen.getByText(/untracked by Git during the rewrite/i)).toBeInTheDocument();
    expect(screen.getByText(/not a freshly rerun live audit/i)).toBeInTheDocument();
    expect(screen.getByText(/intentional service-lane exceptions/i)).toBeInTheDocument();
  });

  it("presents the architecture in the approved order", () => {
    renderPath("/technology");

    const labels = architecture.map((layer) => layer.name);
    for (const label of labels) expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    expect(labels).toEqual(["Engel AI Main", "Engel Core", "Agents", "Remote Workers", "Applications"]);
  });

  it("publishes the retained Rust architecture scale without presenting it as live telemetry", () => {
    renderPath("/technology");

    expect(screen.getByRole("heading", { name: /From Python-backed routes to an evidence-recorded Rust core/i })).toBeInTheDocument();
    for (const fact of rustRewrite.currentScale) {
      expect(screen.getByText(fact.value)).toBeInTheDocument();
      expect(screen.getByText(fact.label)).toBeInTheDocument();
    }
    expect(screen.getByRole("heading", { name: /492 \/ 492 route features were Rust-native/i })).toBeInTheDocument();
    expect(screen.getByText(/historical, evidence-backed snapshot/i)).toBeInTheDocument();
  });

  it("names the local tokenizer, transformer, and advisory SLM roster without private paths", () => {
    renderPath("/technology");

    expect(screen.getByRole("heading", { name: localIntelligence.tokenizer.name })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: localIntelligence.transformer.name })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: localIntelligence.slm.name })).toBeInTheDocument();
    expect(screen.getByText(/Three heads serving, three not yet serving/i)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/[A-Z]:\\/);
    expect(document.body.textContent).not.toMatch(/\/opt\/engel/);
  });

  it("adds the Rust rewrite as a featured Genesis milestone", () => {
    renderPath("/genesis");

    expect(genesisTimeline).toHaveLength(7);
    expect(screen.getByRole("heading", { name: rustRewrite.title })).toBeInTheDocument();
    expect(screen.getByText(/40\+ hour, receipt-backed migration/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Examine the retained evidence/i })).toHaveAttribute("href", "/technology");
  });

  it("keeps every app separate and identifies Bible Companion correctly", () => {
    renderPath("/apps");

    for (const product of products) expect(screen.getByRole("heading", { name: product.name })).toBeInTheDocument();
    expect(screen.getByText(/It is not the Engel AI core or platform runtime/i)).toBeInTheDocument();
  });

  it.each(placeholders)("keeps $path inert and visibly reserved", (placeholder) => {
    renderPath(placeholder.path);

    expect(screen.getByRole("heading", { level: 1, name: placeholder.title })).toBeInTheDocument();
    expect(screen.getByText("Offline by design")).toBeInTheDocument();
    expect(screen.getByText(placeholder.copy)).toBeInTheDocument();
  });

  it("renders Markdown-backed documentation", () => {
    renderPath("/docs");

    expect(screen.getByRole("heading", { name: "Engel AI Labs public platform overview" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Public boundary" })).toHaveAttribute("id", "public-boundary");
    expect(screen.getByText(/explicit, one-at-a-time path for posts and relevant public-discussion replies/i)).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("publishes the claimed Ambassador identity and exact public boundary", () => {
    renderPath("/agents");

    expect(screen.getByRole("heading", { level: 1, name: /Meet the Engel AI Ambassador/i })).toBeInTheDocument();
    expect(screen.getByText(`@${ambassador.handle}`)).toBeInTheDocument();
    expect(screen.getByText("Claimed")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("Off")).toBeInTheDocument();
    expect(ambassador.confirmedPostCount).toBe(2);
    expect(screen.getByText(/recurring discovery, subscriptions, posts, and comments are not/i)).toBeInTheDocument();
    expect(screen.getByText(/Prepare exact drafts for human review/i)).toBeInTheDocument();
    expect(screen.getByText(/No credentials, private logs, local paths, models, files, devices, workers, networks, or infrastructure/i)).toBeInTheDocument();
    expect(screen.getByText(/Control private infrastructure, workers, models, files, or devices/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /View the Moltbook profile/i })).toHaveAttribute("href", ambassador.profileUrl);
    expect(screen.getByRole("link", { name: /View the Moltbook profile/i })).toHaveAttribute("rel", "me noopener noreferrer");
    expect(screen.getByRole("link", { name: /View Archive Editions/i })).toHaveAttribute("href", "/archive-editions");
    expect(screen.getByRole("link", { name: /Read the launch post/i })).toHaveAttribute("href", ambassador.launchPostUrl);
  });

  it("shows configured automation ceilings without implying they are live", () => {
    renderPath("/agents");

    expect(screen.getByRole("heading", { name: "Platform safety ceilings, not a posting schedule." })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: ambassador.automationProfiles.first24Hours.posts })).toBeInTheDocument();
    expect(screen.getByText(`${ambassador.automationProfiles.first24Hours.comments}.`)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: ambassador.automationProfiles.established.posts })).toBeInTheDocument();
    expect(screen.getByText(`${ambassador.automationProfiles.established.comments}.`)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: ambassador.automationProfiles.platformCeilings.reads })).toBeInTheDocument();
    expect(screen.getByText(`${ambassador.automationProfiles.platformCeilings.writes}.`)).toBeInTheDocument();
    expect(screen.getByText(ambassador.automationProfiles.verification)).toBeInTheDocument();
    expect(screen.getByText(/does not start a recurring schedule/i)).toBeInTheDocument();
  });

  it("reports only a static public status snapshot", () => {
    renderPath("/status");

    expect(screen.getByRole("heading", { level: 1, name: /Clear state, without private probes/i })).toBeInTheDocument();
    expect(screen.getByText("Claimed")).toBeInTheDocument();
    expect(screen.getByText(engelMain.state)).toBeInTheDocument();
    expect(screen.getByText(ambassador.communityParticipation.status)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Submolt participation" })).toBeInTheDocument();
    expect(screen.getByText(new RegExp(ambassador.communityParticipation.membership))).toBeInTheDocument();
    expect(screen.getAllByText("Disabled")).toHaveLength(2);
    expect(screen.getByText("Disconnected")).toBeInTheDocument();
    expect(screen.getByText(/does not run live health checks/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: localIntelligence.tokenizer.name })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: localIntelligence.transformer.name })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: localIntelligence.slm.name })).toBeInTheDocument();
  });

  it("describes human-reviewed Submolt participation without claiming membership or automation", () => {
    renderPath("/community");

    expect(screen.getByText(ambassador.communityParticipation.status)).toBeInTheDocument();
    expect(screen.getByText(/one-at-a-time human review workflow/i)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(ambassador.communityParticipation.membership))).toBeInTheDocument();
    expect(screen.getByText(new RegExp(ambassador.communityParticipation.inactivity))).toBeInTheDocument();
    expect(screen.getByText(/Each Submolt has its own rules/i)).toBeInTheDocument();
  });

  it("keeps the Archive Editions preview concept-only and non-transactional", () => {
    renderPath("/archive-editions");

    expect(screen.getByRole("heading", { level: 1, name: /archive-card design study/i })).toBeInTheDocument();
    expect(screen.getByText(/Design study · evidence pending/i)).toBeInTheDocument();
    expect(screen.getByText(/Nothing on this page is for sale/i)).toBeInTheDocument();
    expect(screen.getByText(/There is no token, contract, wallet, mint, price, supply, marketplace/i)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /dark glass aperture/i })).toHaveAttribute(
      "src",
      "/archive-editions/edition-i/v0.2.0/artifact-001-the-first-light-concept.d68c6142e8b94190.png",
    );
    expect(screen.getByRole("img", { name: /crystalline computing spine/i })).toHaveAttribute(
      "src",
      "/archive-editions/edition-i/v0.2.0/artifact-002-the-spine-concept.1fad820ed61e5b5e.png",
    );
    expect(screen.getAllByText(/Artistic interpretation · not historical evidence/i)).toHaveLength(2);
    expect(screen.getByRole("link", { name: "Return to Genesis" })).toHaveAttribute("href", "/genesis");
    expect(screen.queryByRole("link", { name: /connect wallet/i })).not.toBeInTheDocument();
  });

  it("keeps the Archive Editions design study out of search indexes", async () => {
    renderPath("/archive-editions");

    await waitFor(() => expect(document.title).toBe("Archive Editions Design Study | Engel AI Labs"));
    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute("content", "noindex, nofollow");
    expect(document.head.querySelector('link[rel="canonical"]')).toHaveAttribute("href", "https://engelailabs.com/archive-editions");
  });

  it.each([
    ["/privacy", /A small public footprint/i],
    ["/terms", /Public information, clearly bounded/i],
    ["/security", /public boundary is part of the product/i],
    ["/contact", /official public channel/i],
  ])("renders the public information route %s", (path, heading) => {
    renderPath(path);
    expect(screen.getByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
  });

  it("describes Cloudflare's delivery-time analytics boundary accurately", () => {
    renderPath("/privacy");

    expect(screen.getByText(/Cloudflare may inject a Web Analytics tag at delivery time/i)).toBeInTheDocument();
    expect(screen.getByText(/third-party analytics tag is not allowed to run or report/i)).toBeInTheDocument();
  });

  it("updates route metadata and the canonical URL", async () => {
    renderPath("/agents");

    await waitFor(() => expect(document.title).toBe("Engel AI Ambassador | Engel AI Labs"));
    expect(document.head.querySelector('link[rel="canonical"]')).toHaveAttribute("href", "https://engelailabs.com/agents");
    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute("content", "index, follow");
    expect(document.head.querySelector('meta[property="og:url"]')).toHaveAttribute("content", "https://engelailabs.com/agents");
  });

  it("publishes human-reviewed Submolt metadata for the community route", async () => {
    renderPath("/community");

    await waitFor(() => expect(document.title).toBe("Community | Engel AI Labs"));
    expect(document.head.querySelector('meta[name="description"]')).toHaveAttribute(
      "content",
      "See how the Engel AI Ambassador joins relevant public discussions through explicit discovery, exact-draft review, and separate human-confirmed sending.",
    );
    expect(document.head.querySelector('link[rel="canonical"]')).toHaveAttribute("href", "https://engelailabs.com/community");
    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute("content", "index, follow");
  });

  it("provides a keyboard skip link and labeled primary navigation", () => {
    renderPath("/");

    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main-content");
    expect(screen.getByRole("navigation", { name: "Primary navigation" })).toBeInTheDocument();
  });

  it("closes the mobile menu when Escape is pressed", () => {
    renderPath("/");
    const toggle = screen.getByRole("button", { name: "Toggle navigation" });
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  it("accepts only public HTTPS community links", () => {
    expect(publicHttpsUrl("https://github.com/engel-ai-labs")).toBe("https://github.com/engel-ai-labs");
    expect(publicHttpsUrl("http://example.com")).toBeNull();
    expect(publicHttpsUrl(`https://${"local" + "host"}/community`)).toBeNull();
    expect(publicHttpsUrl(`https://${[192, 168, 1, 50].join(".")}/community`)).toBeNull();
    expect(publicHttpsUrl("https://user:password@example.com")).toBeNull();
    expect(publicEnvironment.moltbookUrl).toBe(ambassador.profileUrl);
  });
});
