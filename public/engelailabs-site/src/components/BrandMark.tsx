import { Link } from "react-router-dom";

export function BrandMark() {
  return (
    <Link className="brand" to="/" aria-label="Engel AI Labs home">
      <span className="brand__mark" aria-hidden="true">
        <span className="brand__node brand__node--one" />
        <span className="brand__node brand__node--two" />
        <span className="brand__node brand__node--three" />
        <span className="brand__star" />
      </span>
      <span className="brand__type">
        <strong>Engel AI</strong>
        <small>Labs</small>
      </span>
    </Link>
  );
}
