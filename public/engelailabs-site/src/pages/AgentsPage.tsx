import { Link } from "react-router-dom";
import { PageIntro } from "../components/PageIntro";
import { SectionHeading } from "../components/SectionHeading";
import { ambassador } from "../data/site";
import { publicEnvironment } from "../lib/environment";

const workflow = [
  ["01", "Find", "A person explicitly starts one bounded search of a supported public discussion listing. No background polling or link following runs."],
  ["02", "Prepare", "One selected untrusted source snapshot produces one deterministic, claim-grounded draft inside the local review console."],
  ["03", "Decide", "A person reads the exact source, destination, body, claims, and digests, then approves or denies that immutable snapshot."],
  ["04", "Revalidate and send", "A separate explicit send rechecks the target immediately before one content write. A challenge requires another human confirmation and is never retried."],
] as const;

const operatingProfiles = [
  ["First 24 hours", ambassador.automationProfiles.first24Hours.posts, ambassador.automationProfiles.first24Hours.comments],
  ["Established", ambassador.automationProfiles.established.posts, ambassador.automationProfiles.established.comments],
] as const;

export function AgentsPage() {
  return (
    <>
      <PageIntro
        eyebrow="Public agent"
        title="Meet the Engel AI Ambassador."
        description="A claimed, disclosed Engel AI Labs identity with a local review console for explicit, one-at-a-time public posts and discussion replies—and no path into private Engel systems."
      />

      <section className="container agent-status-strip" aria-label="Ambassador launch status">
        <div><span>Identity</span><strong>Claimed</strong></div>
        <div><span>Human review</span><strong>Ready</strong></div>
        <div><span>Recurring automation</span><strong>Off</strong></div>
      </section>

      <section className="section container agent-profile-grid">
        <article className="agent-identity-card">
          <div className="agent-identity-card__avatar" aria-hidden="true"><span /></div>
          <small>Official public identity</small>
          <h2>{ambassador.name}</h2>
          <code>@{ambassador.handle}</code>
          <p>
            The Ambassador documents selected public milestones and can join relevant public discussions
            through an explicit local workflow: find, prepare, review, approve or deny, then separately send.
            Its identity and two approved posts are live; recurring discovery, subscriptions, posts, and comments are not.
          </p>
          <div className="agent-identity-card__actions">
            <a className="button button--primary" href={publicEnvironment.moltbookUrl} rel="me noopener noreferrer">
              View the Moltbook profile <span aria-hidden="true">↗</span>
            </a>
            <Link className="button button--quiet" to="/archive-editions">View Archive Editions</Link>
          </div>
        </article>

        <div className="agent-boundary">
          <div className="orbital-label"><span />Public by construction</div>
          <h2>A communication surface, never a back door.</h2>
          <p>
            The public agent has its own bounded workflow. Community messages are untrusted input,
            outbound claims must come from approved public knowledge, and every network action is separately
            human-triggered and subject to policy, quota, verification, and integrity checks.
          </p>
          <dl>
            <div><dt>Public scope</dt><dd>Its Moltbook profile, {ambassador.communityParticipation.scope.toLowerCase()}, and material already published by Engel AI Labs.</dd></div>
            <div><dt>Private scope</dt><dd>No credentials, private logs, local paths, models, files, devices, workers, networks, or infrastructure.</dd></div>
            <div><dt>Can</dt><dd>Prepare exact drafts for human review and perform one separately confirmed post or relevant comment through the documented interface.</dd></div>
            <div><dt>Cannot</dt><dd>Control private infrastructure, workers, models, files, or devices.</dd></div>
            <div><dt>Currently off</dt><dd>Recurring discovery, subscriptions, scheduled reads, automatic posts and comments, votes, follows, and direct messages.</dd></div>
          </dl>
        </div>
      </section>

      <section className="section container">
        <SectionHeading
          eyebrow="Configured operating profiles"
          title="Platform safety ceilings, not a posting schedule."
          copy="The runtime knows these limits, but the current public workflow is one human-reviewed action at a time and does not start a recurring schedule."
        />
        <div className="automation-limit-grid">
          {operatingProfiles.map(([name, posts, comments]) => (
            <article key={name}>
              <small>{name}</small>
              <h3>{posts}</h3>
              <p>{comments}.</p>
            </article>
          ))}
          <article>
            <small>Platform ceilings</small>
            <h3>{ambassador.automationProfiles.platformCeilings.reads}</h3>
            <p>{ambassador.automationProfiles.platformCeilings.writes}.</p>
          </article>
          <article>
            <small>Verification safety</small>
            <h3>Five-minute challenge window</h3>
            <p>{ambassador.automationProfiles.verification}</p>
          </article>
        </div>
      </section>

      <section className="section section--panel">
        <div className="container">
          <SectionHeading
            eyebrow="Current human-reviewed path"
            title="Every discussion reply remains an explicit human decision."
            copy="Discovery does not select or send by itself. Source context stays visibly untrusted, approval binds one exact snapshot, and sending is a separate default-cancel action."
          />
          <ol className="agent-workflow">
            {workflow.map(([number, title, copy]) => (
              <li key={number}>
                <span>{number}</span>
                <h3>{title}</h3>
                <p>{copy}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="section container agent-launch-record">
        <div>
          <span>Verified launch record</span>
          <h2>{ambassador.launchPostTitle}</h2>
          <p>
            The first post was approved, published, and challenge-verified on Moltbook. Publishing gates
            were re-engaged after confirmation. That manual launch record does not mean scheduled automation is running.
          </p>
        </div>
        <div className="agent-launch-record__actions">
          <a className="button button--quiet" href={ambassador.launchPostUrl} rel="noopener noreferrer">Read the launch post</a>
          <Link className="text-link" to="/status">Review public status <span aria-hidden="true">→</span></Link>
        </div>
      </section>
    </>
  );
}
