import { Link } from "react-router-dom";
import { PageIntro } from "../components/PageIntro";
import { genesisTimeline } from "../data/site";

export function GenesisPage() {
  return (
    <>
      <PageIntro
        eyebrow="Genesis Archive"
        title="From one interface to a connected AI platform."
        description="A public history of the ideas and milestones that shaped the Engel AI Labs ecosystem."
      />
      <section className="section container genesis-timeline">
        {genesisTimeline.map((event, index) => (
          <article className={event.featured ? "genesis-timeline__event--featured" : undefined} key={event.title}>
            <div className="genesis-timeline__axis"><span>{index + 1}</span></div>
            <div>
              <small>{event.era}</small>
              <h2>{event.title}</h2>
              <p>{event.copy}</p>
              {event.featured && <Link className="text-link" to="/technology">Examine the retained evidence <span aria-hidden="true">→</span></Link>}
            </div>
          </article>
        ))}
      </section>
      <section className="section container archive-note">
        <span>Archive principle</span>
        <div>
          <p>The Genesis Archive records the public evolution of Engel AI Labs without exposing private systems, files, or operational details.</p>
          <Link className="text-link" to="/archive-editions">View the Edition I design study <span aria-hidden="true">→</span></Link>
        </div>
      </section>
    </>
  );
}
