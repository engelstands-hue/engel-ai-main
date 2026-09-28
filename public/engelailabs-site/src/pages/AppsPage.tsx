import { Link } from "react-router-dom";
import { PageIntro } from "../components/PageIntro";
import { engelMain, products } from "../data/site";

export function AppsPage() {
  return (
    <>
      <PageIntro
        eyebrow="Applications"
        title="Separate products. Shared commitment to useful intelligence."
        description="Engel AI Main is the workspace. These are the other Engel products: the ones running now, the independent study app, and the portfolio concepts."
      />
      <section className="section container flagship-app">
        <div>
          <small>Current flagship · {engelMain.platform}</small>
          <h2>{engelMain.name}</h2>
          <p>{engelMain.summary}</p>
        </div>
        <dl>
          <div><dt>Version</dt><dd>{engelMain.version}</dd></div>
          <div><dt>Daily desks</dt><dd>{engelMain.dailyDesks.length}</dd></div>
          <div><dt>Distribution</dt><dd>Public source · no public installer</dd></div>
        </dl>
        <Link className="button button--primary" to="/engel-ai-main">Open the product map</Link>
      </section>
      <section className="section container app-catalog">
        {products.map((product, index) => (
          <article key={product.name}>
            <header><span>{String(index + 1).padStart(2, "0")}</span><small>{product.type}</small></header>
            <h2>{product.name}</h2>
            <p>{product.copy}</p>
            <div className={`app-catalog__status${product.type === "Current" ? " app-catalog__status--current" : ""}`}><i />{product.type}</div>
          </article>
        ))}
      </section>
    </>
  );
}
