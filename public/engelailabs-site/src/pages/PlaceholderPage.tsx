import { Link } from "react-router-dom";

type Placeholder = { path: string; title: string; copy: string };

export function PlaceholderPage({ placeholder }: { placeholder: Placeholder }) {
  return (
    <section className="placeholder container">
      <div className="placeholder__glyph" aria-hidden="true"><span /></div>
      <div className="orbital-label"><span />Future integration placeholder</div>
      <code>{placeholder.path}</code>
      <h1>{placeholder.title}</h1>
      <p>{placeholder.copy}</p>
      <div className="placeholder__state"><i />Offline by design</div>
      <Link className="button button--quiet" to="/">Return home</Link>
    </section>
  );
}
