import { Link } from "react-router-dom";
import { PageIntro } from "../components/PageIntro";
import { engelMain, platformCapabilities } from "../data/site";

export function PlatformPage() {
  return (
    <>
      <PageIntro
        eyebrow="Engel AI Platform"
        title="The coordination layer for a personal AI ecosystem."
        description="Engel AI Platform brings local intelligence, routing, memory boundaries, verification, and approved worker coordination into the current Engel AI Main workspace and the broader product direction."
      />
      <section className="section container capability-grid">
        {platformCapabilities.map((capability, index) => (
          <article key={capability.name}>
            <div className="capability-grid__icon" aria-hidden="true"><span>{index + 1}</span></div>
            <small>Platform capability</small>
            <h2>{capability.name}</h2>
            <p>{capability.copy}</p>
          </article>
        ))}
      </section>
      <section className="section container trust-strip">
        <div><span>Local-first</span><strong>Keep the center of gravity close.</strong></div>
        <div><span>Evidence-minded</span><strong>Make important checks visible.</strong></div>
        <div><span>Human-guided</span><strong>Reserve authority for people.</strong></div>
      </section>
      <section className="section container inline-cta">
        <div><span>Current human-facing surface</span><h2>See the {engelMain.dailyDesks.length} daily desks and the Advanced groups behind them.</h2></div>
        <Link className="button button--primary" to="/engel-ai-main">Explore Engel AI Main</Link>
      </section>
      <section className="section container inline-cta">
        <div><span>Read the public overview</span><h2>Explore the platform principles in Markdown-backed documentation.</h2></div>
        <Link className="button button--quiet" to="/docs">Open docs</Link>
      </section>
    </>
  );
}
