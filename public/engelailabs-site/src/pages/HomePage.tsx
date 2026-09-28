import { Link } from "react-router-dom";
import { ConnectionField } from "../components/ConnectionField";
import { SectionHeading } from "../components/SectionHeading";
import { engelMain, focusAreas, products } from "../data/site";

export function HomePage() {
  return (
    <>
      <section className="hero container">
        <div className="hero__copy">
          <div className="orbital-label"><span />{engelMain.platform} · {engelMain.state}</div>
          <h1>Engel <em>AI Main</em></h1>
          <p>{engelMain.summary}</p>
          <div className="hero__actions">
            <Link className="button button--primary" to="/engel-ai-main">Explore Engel AI Main <span>↗</span></Link>
            <a className="button button--quiet" href={engelMain.sourceUrl} rel="noopener noreferrer">Read the source</a>
          </div>
          <div className="hero__signals" aria-label="Platform principles">
            <span><i />Version {engelMain.version}</span>
            <span><i />{engelMain.dailyDesks.length} daily desks</span>
            <span><i />Human-guided</span>
          </div>
        </div>
        <ConnectionField />
      </section>

      <section className="section container flagship-strip">
        <div>
          <span>Current flagship workspace</span>
          <h2>{engelMain.name}</h2>
        </div>
        <p>{engelMain.summary} {engelMain.availability}</p>
        <Link className="text-link" to="/engel-ai-main">See every work area <span>→</span></Link>
      </section>

      <section className="section container">
        <SectionHeading
          eyebrow="Built around trust"
          title="Intelligence that works with people—not around them."
          copy="Engel AI Labs explores a practical path between isolated AI tools and opaque automation."
        />
        <div className="feature-grid">
          {focusAreas.map((area, index) => (
            <article className="feature-card" key={area.title}>
              <span className="feature-card__number">0{index + 1}</span>
              <small>{area.eyebrow}</small>
              <h3>{area.title}</h3>
              <p>{area.copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section section--panel">
        <div className="container split-callout">
          <div>
            <div className="orbital-label"><span />One ecosystem, many surfaces</div>
            <h2>A platform designed to connect intelligence, agents, devices, and applications.</h2>
          </div>
          <div className="system-path" aria-label="Public platform flow">
            <span>Intelligence</span><i />
            <span>Agents</span><i />
            <span>Workers</span><i />
            <span>Apps</span>
          </div>
        </div>
      </section>

      <section className="section container">
        <SectionHeading
          eyebrow="Daily side"
          title="Five desks on the side. Search finds the rest."
          copy="The open window starts on Chat. Discord, Status, Settings, and Advanced stay one click away."
        />
        <div className="feature-grid">
          {engelMain.dailyDesks.map((desk, index) => (
            <article className="feature-card" key={desk.name}>
              <span className="feature-card__number">0{index + 1}</span>
              <small>{desk.role}</small>
              <h3>{desk.name}</h3>
              <p>{desk.copy}</p>
            </article>
          ))}
        </div>
        <Link className="text-link" to="/engel-ai-main">See Advanced behind those desks <span>→</span></Link>
      </section>

      <section className="section container">
        <SectionHeading
          eyebrow="Independent products"
          title="Applications shaped around real work."
          copy="Each app is its own product within the Engel AI Labs portfolio."
        />
        <div className="product-preview-grid">
          {products.slice(0, 3).map((product) => (
            <article key={product.name}>
              <small>{product.type}</small>
              <h3>{product.name}</h3>
              <p>{product.copy}</p>
            </article>
          ))}
        </div>
        <Link className="text-link" to="/apps">See all applications <span>→</span></Link>
      </section>

      <section className="section container closing-callout">
        <div className="closing-callout__glow" aria-hidden="true" />
        <span>Engel AI Labs</span>
        <h2>Personal intelligence should feel powerful, private, and understandable.</h2>
        <Link className="button button--primary" to="/about">Why we’re building Engel <span>↗</span></Link>
      </section>
    </>
  );
}
