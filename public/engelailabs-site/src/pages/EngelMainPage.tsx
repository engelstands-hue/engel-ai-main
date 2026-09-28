import { Link } from "react-router-dom";
import { PageIntro } from "../components/PageIntro";
import { SectionHeading } from "../components/SectionHeading";
import { engelMain, rustRewrite } from "../data/site";

const representativeNavigation = engelMain.dailyDesks.map((desk) => desk.name);

function InterfaceMap() {
  return (
    <figure className="main-interface" aria-labelledby="main-interface-caption">
      <div className="main-interface__chrome" aria-hidden="true">
        <div className="main-interface__windowbar">
          <span /><span /><span />
          <strong>Engel AI Main</strong>
          <small>{engelMain.platform}</small>
        </div>
        <div className="main-interface__workspace">
          <aside className="main-interface__rail">
            <div className="main-interface__search">Find a tool or setting</div>
            <small>Daily</small>
            <ol>
              {representativeNavigation.map((item, index) => (
                <li className={index === 0 ? "is-active" : undefined} key={item}>
                  <span>{String(index + 1).padStart(2, "0")}</span>{item}
                </li>
              ))}
            </ol>
          </aside>
          <div className="main-interface__content">
            <header>
              <strong>Engel</strong>
              <span>Chat ready</span>
              <i>Chat: {engelMain.chatRouteLabel}</i>
            </header>
            <div className="main-interface__canvas">
              <p className="main-interface__eyebrow">Chat with Engel</p>
              <h2>A local conversation, with the route and the connection shown in the header.</h2>
              <div className="main-interface__prompt"><span>Message Engel…</span><b>Send</b></div>
              <div className="main-interface__actions">
                {engelMain.quickActions.map(([name, copy], index) => (
                  <div key={name}>
                    <i className={`main-interface__accent main-interface__accent--${index + 1}`} />
                    <strong>{name}</strong>
                    <small>{copy}</small>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
      <figcaption id="main-interface-caption">
        Representative interface map — built from the current product structure, with no personal data or live telemetry.
      </figcaption>
    </figure>
  );
}

export function EngelMainPage() {
  return (
    <>
      <PageIntro
        eyebrow={`${engelMain.platform} · ${engelMain.state}`}
        title="One visible workspace for the whole Engel system."
        description={engelMain.summary}
      >
        <div className="main-release-line" aria-label="Current product facts">
          <span><small>Product</small><strong>{engelMain.name}</strong></span>
          <span><small>Build version</small><strong>{engelMain.version}</strong></span>
          <span><small>Daily desks</small><strong>{engelMain.dailyDesks.length}</strong></span>
          <span><small>Advanced groups</small><strong>{engelMain.advancedGroups.length}</strong></span>
        </div>
      </PageIntro>

      <section className="section container main-product-stage">
        <InterfaceMap />
        <aside className="main-product-stage__note">
          <div className="orbital-label"><span />Product boundary</div>
          <h2>Local-first does not mean invisible.</h2>
          <p>{engelMain.availability}</p>
          <p>
            The authored source is public under the MIT license. The Windows installer is not offered as a public download.
          </p>
          <div className="main-product-stage__actions">
            <a className="button button--primary" href={engelMain.sourceUrl} rel="noopener noreferrer">Read the source</a>
            <a className="button button--quiet" href="https://x.com/engelaimain/status/2104617169497493758" rel="noopener noreferrer">See the post</a>
          </div>
        </aside>
      </section>

      <section className="section container rust-proof" aria-labelledby="rust-proof-title">
        <div className="rust-proof__heading">
          <div>
            <div className="orbital-label"><span />Runtime foundation · retained evidence</div>
            <h2 id="rust-proof-title">A 40+ hour Rust rewrite beneath Engel AI Main.</h2>
          </div>
          <p>{rustRewrite.summary}</p>
        </div>

        <div className="rust-proof__duration" aria-label="Rewrite duration evidence">
          {rustRewrite.durationEvidence.map((fact) => (
            <article key={fact.label}>
              <strong>{fact.value}</strong>
              <h3>{fact.label}</h3>
              <p>{fact.note}</p>
            </article>
          ))}
        </div>

        <div className="rust-proof__completion">
          <div>
            <span>{rustRewrite.initialWindow}</span>
            <h3>Initial migration completion record</h3>
          </div>
          <dl>
            {rustRewrite.completionEvidence.map((fact) => (
              <div key={fact.label}>
                <dt>{fact.value}</dt>
                <dd><strong>{fact.label}</strong><small>{fact.note}</small></dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="rust-proof__notes">
          <p>{rustRewrite.provenanceNote}</p>
          <p>{rustRewrite.currentStateNote}</p>
        </div>
      </section>

      <section className="section section--panel">
        <div className="container">
          <SectionHeading
            eyebrow="Complete product map"
            title="Five daily desks. Advanced holds the rest."
            copy="The side rail stays short. Search still finds every tool. Reference items inside Advanced do not run tools."
          />
          <div className="main-area-grid">
            {engelMain.dailyDesks.map((area, index) => (
              <article key={area.name}>
                <header><span>{String(index + 1).padStart(2, "0")}</span><small>{area.role}</small></header>
                <h2>{area.name}</h2>
                <p>{area.copy}</p>
                <ul aria-label={`${area.name} views`}>
                  {area.views.map((view) => <li key={view}>{view}</li>)}
                </ul>
              </article>
            ))}
            {engelMain.advancedGroups.map((area) => (
              <article key={area.name}>
                <header><span>Advanced</span><small>{area.name}</small></header>
                <h2>{area.name}</h2>
                <p>{area.copy}</p>
                <ul aria-label={`${area.name} tools`}>
                  {area.views.map((view) => <li key={view}>{view}</li>)}
                </ul>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section container">
        <SectionHeading
          eyebrow="Human-guided system"
          title="From intent to evidence without losing the person in the middle."
          copy="Engel AI Main coordinates a visible path across local intelligence and explicitly approved connected capabilities."
        />
        <ol className="main-workflow">
          {engelMain.workFlow.map(([number, title, copy]) => (
            <li key={number}>
              <span>{number}</span>
              <div><h3>{title}</h3><p>{copy}</p></div>
            </li>
          ))}
        </ol>
      </section>

      <section className="section container main-readiness">
        <div>
          <div className="orbital-label"><span />Readiness, stated plainly</div>
          <h2>A real desktop product with deliberately conditional edges.</h2>
          <p>
            Chat, Discord, Status, Settings, and Advanced are the daily side.
            Models, phones, training, and external services depend on their own configured runtime state.
            The interface keeps that distinction visible.
          </p>
        </div>
        <dl>
          <div><dt>Current</dt><dd>Windows workspace, daily side of Chat, Discord, Status, Settings, and Advanced, plus the tools those desks open.</dd></div>
          <div><dt>Runtime-dependent</dt><dd>Local model execution, Meeting Room, Sub-Engel, device workers, companion processes, and configured providers.</dd></div>
          <div><dt>Governed</dt><dd>Training admission, risky tools, external actions, credentials, and meaningful writes require explicit gates or review.</dd></div>
          <div><dt>Not claimed</dt><dd>Universal provider connectivity, autonomous self-improvement, always-online workers, or a public installer.</dd></div>
        </dl>
      </section>
    </>
  );
}
