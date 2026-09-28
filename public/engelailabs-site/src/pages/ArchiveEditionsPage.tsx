import { Link } from "react-router-dom";
import { PageIntro } from "../components/PageIntro";
import { SectionHeading } from "../components/SectionHeading";

const candidates = [
  ["01", "The First Light", "The first visible Engel interface and the beginning of a human-facing system."],
  ["02", "The Spine", "The computing foundation that allowed Engel to grow beyond a single surface."],
  ["03", "The Hive", "Independent worker surfaces becoming one coordinated, human-readable system."],
  ["04", "The First Worker", "The first dedicated device used for bounded worker experiments."],
  ["05", "The Companion", "An independent application milestone, separate from the Engel platform runtime."],
] as const;

const studies = [
  {
    record: "EGA-EI-001",
    title: "The First Light",
    image: "/archive-editions/edition-i/v0.2.0/artifact-001-the-first-light-concept.d68c6142e8b94190.png",
    alt: "A fictional dark glass aperture opening around a small warm light and abstract luminous planes",
    copy: "This sanitized concept imagines the first visible Engel interface as an opening from darkness into a human-readable surface. It does not depict a real screen, dashboard, device, or private system.",
    hash: "d68c6142e8b941906ee3e21898f6fa14ef91eb4a28b3e99f29f983aa30a13b33",
  },
  {
    record: "EGA-EI-002",
    title: "The Spine",
    image: "/archive-editions/edition-i/v0.2.0/artifact-002-the-spine-concept.1fad820ed61e5b5e.png",
    alt: "A fictional crystalline computing spine connected to a ring of small abstract nodes",
    copy: "This sanitized concept imagines the computing foundation behind Engel as an archival object. It does not depict a real server, reveal private infrastructure, or establish the underlying milestone.",
    hash: "1fad820ed61e5b5e9deecd20648b037147e8bf024448768a84fb61192c9f8444",
  },
] as const;

export function ArchiveEditionsPage() {
  return (
    <>
      <PageIntro
        eyebrow="Engel Archive Editions · Concept only"
        title="An archive-card design study, before any collectible decision."
        description="Edition I explores how verified public milestones could become a coherent visual archive. The evidence and rights workflow comes first; no blockchain asset exists."
      />

      <section className="section container archive-studies" aria-labelledby="archive-studies-heading">
        <div className="archive-studies__intro">
          <span className="archive-study-state">Design study · evidence pending</span>
          <h2 id="archive-studies-heading">Two interpretations. Zero historical claims.</h2>
          <p>Each image is a fictional visual study. Source evidence, chronology, factual claims, and rights remain separate review work.</p>
        </div>
        {studies.map((study, index) => (
          <article className={`archive-study-grid${index % 2 ? " archive-study-grid--reverse" : ""}`} key={study.record}>
            <figure className="archive-study-art">
              <img src={study.image} alt={study.alt} />
              <figcaption>Artistic interpretation · not historical evidence</figcaption>
            </figure>
            <div className="archive-study-copy">
              <span className="archive-study-state">Concept {String(index + 1).padStart(2, "0")} · evidence pending</span>
              <h2>{study.title}</h2>
              <p>{study.copy}</p>
              <dl>
                <div><dt>Working record</dt><dd>{study.record}</dd></div>
                <div><dt>Evidence</dt><dd>Not yet verified</dd></div>
                <div><dt>Rights</dt><dd>Human review pending</dd></div>
                <div><dt>Collectible</dt><dd>Not eligible</dd></div>
              </dl>
              <p className="archive-study-hash">
                Public artwork SHA-256<br />
                <code>{study.hash}</code>
              </p>
            </div>
          </article>
        ))}
      </section>

      <section className="section section--panel">
        <div className="container">
          <SectionHeading
            eyebrow="Edition I · working sequence"
            title="Five candidates, all still drafts."
            copy="These labels and their order can change. Chronology, source evidence, public claims, rights, and redaction must be reviewed before a candidate becomes a verified archive record."
          />
          <div className="app-catalog archive-candidate-grid">
            {candidates.map(([sequence, title, copy]) => (
              <article key={title}>
                <header><small>Working candidate</small><span>{sequence}</span></header>
                <h2>{title}</h2>
                <p>{copy}</p>
                <div className="app-catalog__status"><i /> Evidence pending · not permanent</div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section container archive-study-boundary">
        <div>
          <span>Current boundary</span>
          <h2>Archive first. No offer, transaction, or access promise.</h2>
          <p>
            Nothing on this page is for sale. There is no token, contract, wallet, mint, price, supply, marketplace, release date, ownership right, access right, or investment right. The page is static and has no connection to private Engel systems.
          </p>
        </div>
        <nav aria-label="Archive study links">
          <Link className="button button--primary" to="/genesis">Return to Genesis</Link>
          <Link className="button button--quiet" to="/terms">Website terms</Link>
          <Link className="button button--quiet" to="/security">Security boundary</Link>
        </nav>
      </section>
    </>
  );
}
