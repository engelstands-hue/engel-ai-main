import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <section className="placeholder container">
      <div className="placeholder__glyph" aria-hidden="true"><span /></div>
      <div className="orbital-label"><span />404 · Uncharted orbit</div>
      <h1>That page is beyond the current map.</h1>
      <p>The public platform has no route at this address.</p>
      <Link className="button button--primary" to="/">Return home</Link>
    </section>
  );
}
