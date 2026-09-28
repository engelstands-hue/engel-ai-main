import { Link } from "react-router-dom";
import { PageIntro } from "../components/PageIntro";
import { ambassador } from "../data/site";
import { publicEnvironment } from "../lib/environment";

const reviewed = "August 14, 2026";

export function PrivacyPage() {
  return (
    <>
      <PageIntro
        eyebrow="Privacy"
        title="A small public footprint."
        description={`This notice describes the public website as reviewed on ${reviewed}.`}
      />
      <article className="section container public-info">
        <h2>What this site does</h2>
        <p>
          Engel AI Labs currently serves a static informational website. Its published application has no
          account system, contact form, advertising tracker, analytics client, payment flow, or browser-side API client.
        </p>
        <h2>Hosting data</h2>
        <p>
          Cloudflare hosts the site and may process standard request information needed to deliver and
          protect it, such as an IP address, requested URL, browser details, and request time, under
          Cloudflare's own terms and privacy practices.
        </p>
        <p>
          Cloudflare may inject a Web Analytics tag at delivery time as a hosting setting. Engel's current
          browser policy permits only same-origin scripts and blocks browser network connections, so that
          third-party analytics tag is not allowed to run or report from this site.
        </p>
        <h2>Third-party destinations</h2>
        <p>
          Links to Moltbook and any future public community service leave this site. Those services set
          their own data practices. No Moltbook credential or private Engel data is embedded here.
        </p>
        <h2>Changes</h2>
        <p>If the public site later adds forms, accounts, an allowed analytics flow, or another data flow, this notice will be updated before launch.</p>
      </article>
    </>
  );
}

export function TermsPage() {
  return (
    <>
      <PageIntro
        eyebrow="Terms"
        title="Public information, clearly bounded."
        description={`These website terms describe the informational public surface as reviewed on ${reviewed}.`}
      />
      <article className="section container public-info">
        <h2>Informational use</h2>
        <p>
          This site presents the direction, public products, documentation, and verified launch state of
          Engel AI Labs. It does not provide access to private systems, a hosted AI service, or an account.
        </p>
        <h2>Accuracy and change</h2>
        <p>
          Build notes distinguish current public facts from concepts and future direction. Content may be
          corrected or updated as the work changes.
        </p>
        <h2>Third-party services</h2>
        <p>
          Moltbook and other external destinations operate under their own terms. A link does not grant
          those services access to private Engel infrastructure.
        </p>
        <h2>Respectful use</h2>
        <p>Do not misuse the site, attempt to bypass its public boundary, or impersonate Engel AI Labs or its disclosed Ambassador.</p>
      </article>
    </>
  );
}

export function SecurityPage() {
  return (
    <>
      <PageIntro
        eyebrow="Security"
        title="The public boundary is part of the product."
        description="The website is presentation-only, and the public Ambassador is isolated from private Engel systems."
      />
      <article className="section container public-info">
        <h2>Current boundary</h2>
        <p>
          The site has no Pages Functions, API client, authentication provider, device discovery, health
          probes, remote commands, or private-system credentials. Its browser policy blocks network connections and forms.
        </p>
        <h2>Public agent controls</h2>
        <p>
          The Moltbook review console supports an explicit one-at-a-time path: a person starts discovery,
          reviews untrusted source context and an exact draft, approves or denies the immutable snapshot,
          and separately confirms any send. Recurring reads, posts, and comments remain disabled. Writes
          stay bounded by approved public knowledge, policy, cadence, quotas, verification safety, and
          integrity checks. The agent cannot control private infrastructure.
        </p>
        <h2>Reporting a concern</h2>
        <p>
          Use the official public contact route. Please do not include secrets, personal data, exploit payloads,
          or private-system information in a public message.
        </p>
        <Link className="button button--quiet" to="/contact">Open contact guidance</Link>
      </article>
    </>
  );
}

export function ContactPage() {
  return (
    <>
      <PageIntro
        eyebrow="Contact"
        title="Start with the official public channel."
        description="Engel AI Labs is opening communication deliberately, beginning with the verified Moltbook Ambassador."
      />
      <section className="section container contact-card">
        <div>
          <small>Verified public identity</small>
          <h2>@{ambassador.handle}</h2>
          <p>
            Follow public build notes or start a public conversation on Moltbook. Do not send credentials,
            private system details, sensitive personal information, or urgent security material in a public post.
          </p>
        </div>
        <a className="button button--primary" href={publicEnvironment.moltbookUrl} rel="me noopener noreferrer">
          Visit the official profile <span aria-hidden="true">↗</span>
        </a>
      </section>
    </>
  );
}
