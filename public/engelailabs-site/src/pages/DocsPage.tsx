import ReactMarkdown from "react-markdown";
import type { ReactNode } from "react";
import { PageIntro } from "../components/PageIntro";
import platformOverview from "../content/platform-overview.md?raw";

function headingId(children: ReactNode): string {
  return String(children)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function DocsPage() {
  return (
    <>
      <PageIntro
        eyebrow="Public documentation"
        title="Platform notes, written for people."
        description="Markdown-backed documentation keeps the public story clear, portable, and easy to expand."
      />
      <section className="section container docs-layout">
        <aside>
          <span>In this document</span>
          <a href="#engel-ai-labs-public-platform-overview">Overview</a>
          <a href="#platform-direction">Platform direction</a>
          <a href="#operating-principles">Operating principles</a>
          <a href="#public-ambassador">Public Ambassador</a>
          <a href="#public-boundary">Public boundary</a>
        </aside>
        <article className="markdown-body">
          <ReactMarkdown
            components={{
              h1: ({ children }) => <h2 id={headingId(children)}>{children}</h2>,
              h2: ({ children }) => <h2 id={headingId(children)}>{children}</h2>,
              h3: ({ children }) => <h3 id={headingId(children)}>{children}</h3>,
            }}
          >
            {platformOverview}
          </ReactMarkdown>
        </article>
      </section>
    </>
  );
}
