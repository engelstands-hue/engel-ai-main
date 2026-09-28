import { Link } from "react-router-dom";
import { ArchitectureStack } from "../components/ArchitectureStack";
import { PageIntro } from "../components/PageIntro";
import { SectionHeading } from "../components/SectionHeading";
import { engelMain, localIntelligence, rustRewrite } from "../data/site";

export function TechnologyPage() {
  return (
    <>
      <PageIntro
        eyebrow="Technology"
        title="A connected architecture with human intent at the top."
        description={`The Engel technology model starts with the current ${engelMain.name} Windows workspace, then moves through local coordination, specialized agents, bounded workers, and independent applications.`}
      />
      <section className="section container technology-layout">
        <div>
          <SectionHeading
            eyebrow="Public architecture"
            title="One understandable path from intent to application."
            copy="This is a conceptual view of the product ecosystem—not a map of private infrastructure."
          />
          <div className="boundary-note">
            <strong>Public boundary</strong>
            <p>No addresses, credentials, internal APIs, or operational topology are exposed here.</p>
          </div>
        </div>
        <ArchitectureStack />
      </section>
      <section className="section container local-intelligence" aria-label="Local intelligence stack">
        <SectionHeading
          eyebrow={`Reviewed ${localIntelligence.reviewedOn}`}
          title="Tokenizer, transformer, and SLM roster — named and gated."
          copy={localIntelligence.summary}
        />
        <div className="feature-grid">
          {[localIntelligence.tokenizer, localIntelligence.transformer, localIntelligence.slm].map((piece) => (
            <article className="feature-card" key={piece.name}>
              <small>{piece.state}</small>
              <h3>{piece.name}</h3>
              <p>{piece.detail}</p>
            </article>
          ))}
        </div>
      </section>
      <section className="section container architecture-principles">
        <article><span>01</span><h3>Local by design</h3><p>Keep intelligence close to the person and their chosen systems.</p></article>
        <article><span>02</span><h3>Modular by nature</h3><p>Give agents, workers, and applications focused responsibilities.</p></article>
        <article><span>03</span><h3>Governed by people</h3><p>Preserve review and authority across meaningful actions.</p></article>
      </section>
      <section className="section section--panel rust-technology">
        <div className="container">
          <SectionHeading
            eyebrow="Engel Core · Rust"
            title="From Python-backed routes to an evidence-recorded Rust core."
            copy={`${rustRewrite.initialWindow} marks the initial migration window. ${rustRewrite.continuedThrough}.`}
          />
          <div className="rust-technology__grid">
            {rustRewrite.currentScale.map((fact) => (
              <article key={fact.label}>
                <strong>{fact.value}</strong>
                <span>{fact.label}</span>
              </article>
            ))}
          </div>
          <div className="rust-technology__record">
            <div>
              <small>Recorded completion proof</small>
              <h2>492 / 492 route features were Rust-native in the June 1 migration inventory.</h2>
            </div>
            <p>
              The June 2 completion report recorded 517 native routes, 264 passing Rust tests with
              zero failures, and a passing 260-step workflow. Later records retain deliberate
              service-lane exceptions, so this is a Rust-core claim—not a claim that every Engel
              ecosystem component uses Rust.
            </p>
          </div>
          <p className="rust-technology__qualification">{rustRewrite.provenanceNote} {rustRewrite.currentStateNote}</p>
        </div>
      </section>
      <section className="section container inline-cta">
        <div><span>See the human-facing layer</span><h2>Explore the current Engel AI Main shell: {engelMain.dailyDesks.length} daily desks, and Advanced for the rest.</h2></div>
        <Link className="button button--quiet" to="/engel-ai-main">Open product map</Link>
      </section>
    </>
  );
}
