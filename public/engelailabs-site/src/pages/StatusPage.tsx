import { Link } from "react-router-dom";
import { PageIntro } from "../components/PageIntro";
import { ambassador, engelMain, localIntelligence } from "../data/site";
import { publicEnvironment } from "../lib/environment";

const statusItems = [
  ["Public website", "Online", "engelailabs.com is served as a static Cloudflare Pages site."],
  ["Engel AI Main desktop", engelMain.state, `${engelMain.name} ${engelMain.version} is the current local Windows workspace. Runtime-dependent features report their own configured state.`],
  ["Ambassador identity", "Claimed", `The Moltbook profile is claimed with ${ambassador.confirmedPostCount} confirmed, human-approved posts, including its verified launch post.`],
  ["Ambassador review console", "Ready", "A person can explicitly find one supported discussion listing, prepare one exact draft, approve or deny it, and separately confirm a one-shot send."],
  ["Submolt participation", ambassador.communityParticipation.status, `${ambassador.communityParticipation.readiness} ${ambassador.communityParticipation.membership} ${ambassador.communityParticipation.inactivity}`],
  ["Scheduled reads", "Disabled", "No automatic community feed retrieval is running."],
  ["Automatic posts and comments", "Disabled", "No unattended writer is posting or commenting in any Submolt."],
  ["Private Engel systems", "Disconnected", "The website and Ambassador have no control path into private infrastructure."],
  [localIntelligence.tokenizer.name, localIntelligence.tokenizer.state, localIntelligence.tokenizer.detail],
  [localIntelligence.transformer.name, localIntelligence.transformer.state, localIntelligence.transformer.detail],
  [localIntelligence.slm.name, localIntelligence.slm.state, localIntelligence.slm.detail],
] as const;

export function StatusPage() {
  return (
    <>
      <PageIntro
        eyebrow="Reviewed public status"
        title="Clear state, without private probes."
        description={`This static launch snapshot was reviewed on ${ambassador.reviewedOn}. It does not run live health checks, call private services, or expose operational telemetry.`}
      />

      <section className="section container public-status-list" aria-label="Public launch status">
        {statusItems.map(([name, state, detail]) => (
          <article key={name}>
            <div>
              <span className="public-status-list__dot" aria-hidden="true" />
              <h2>{name}</h2>
            </div>
            <strong>{state}</strong>
            <p>{detail}</p>
          </article>
        ))}
      </section>

      <section className="section section--panel">
        <div className="container status-boundary-grid">
          <div>
            <div className="orbital-label"><span />How to read this page</div>
            <h2>Public facts only.</h2>
            <p>
              This page is a deliberately small, reviewed projection of launch state. It never embeds
              credentials, local paths, audit internals, device state, network topology, or private logs.
            </p>
          </div>
          <div className="status-boundary-grid__actions">
            <a className="button button--primary" href={publicEnvironment.moltbookUrl} rel="me noopener noreferrer">
              Visit @{ambassador.handle} <span aria-hidden="true">↗</span>
            </a>
            <Link className="button button--quiet" to="/agents">Read the agent boundary</Link>
          </div>
        </div>
      </section>
    </>
  );
}
