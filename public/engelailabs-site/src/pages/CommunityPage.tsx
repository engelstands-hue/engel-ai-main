import { PageIntro } from "../components/PageIntro";
import { ambassador } from "../data/site";
import { publicEnvironment } from "../lib/environment";

const channels = [
  { name: "Moltbook", label: ambassador.communityParticipation.status, copy: `View @${ambassador.handle}. ${ambassador.communityParticipation.readiness} ${ambassador.communityParticipation.membership} ${ambassador.communityParticipation.inactivity}`, url: publicEnvironment.moltbookUrl, live: true },
  { name: "GitHub", label: "Open development", copy: "A future home for approved public projects and developer collaboration.", url: publicEnvironment.githubUrl, live: false },
  { name: "Developer community", label: "Build together", copy: "A future gathering point for documentation, experiments, and shared learning.", url: publicEnvironment.communityUrl, live: false },
] as const;

export function CommunityPage() {
  return (
    <>
      <PageIntro
        eyebrow="Community"
        title="A place for builders, explorers, and thoughtful AI users."
        description="The claimed Engel AI Ambassador can prepare a reply to a relevant public discussion through a one-at-a-time human review workflow. No unattended discovery, subscription, post, or comment activity is running."
      />
      <section className="section container community-grid">
        {channels.map((channel, index) => (
          <article key={channel.name}>
            <span className="community-grid__index">0{index + 1}</span>
            <small>{channel.label}</small>
            <h2>{channel.name}</h2>
            <p>{channel.copy}</p>
            {channel.url ? (
              <a href={channel.url} rel={channel.name === "Moltbook" ? "me noopener noreferrer" : "noopener noreferrer"}>
                {channel.live ? "Visit live channel" : "Visit channel"} <span aria-hidden="true">↗</span>
              </a>
            ) : (
              <span className="coming-soon"><i />Coming soon</span>
            )}
          </article>
        ))}
      </section>
      <section className="section container community-note">
        <div className="orbital-label"><span />Open carefully</div>
        <h2>Public participation should expand the conversation—not weaken the boundary.</h2>
        <p>Each Submolt has its own rules. A person chooses the discussion, reviews the untrusted source and exact reply, and separately confirms any send.</p>
      </section>
    </>
  );
}
