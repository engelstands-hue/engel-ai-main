import { PageIntro } from "../components/PageIntro";
import { SectionHeading } from "../components/SectionHeading";
import { aboutPrinciples } from "../data/site";

export function AboutPage() {
  return (
    <>
      <PageIntro
        eyebrow="About Engel AI Labs"
        title="Building personal AI on a foundation people can understand."
        description="Engel AI Labs develops Engel AI Main and a broader family of local-first systems focused on coordinated agents, approved devices, verification, and privacy-focused workflows."
      />
      <section className="section container about-layout">
        <div>
          <SectionHeading eyebrow="Our focus" title="A more personal computing relationship." />
          <p className="large-copy">
            We believe useful AI can be ambitious without removing human authority. Our work
            brings models, tools, agents, and approved worker devices into Engel AI Main with clear boundaries.
          </p>
        </div>
        <div className="principle-list">
          {aboutPrinciples.map(([title, copy], index) => (
            <article key={title}>
              <span>0{index + 1}</span>
              <div><h3>{title}</h3><p>{copy}</p></div>
            </article>
          ))}
        </div>
      </section>
      <section className="section section--panel">
        <div className="container manifesto">
          <span className="manifesto__mark">✦</span>
          <blockquote>
            “The future of personal AI is not a black box somewhere else. It is a relationship
            built close to the person, with visible systems and meaningful control.”
          </blockquote>
        </div>
      </section>
    </>
  );
}
