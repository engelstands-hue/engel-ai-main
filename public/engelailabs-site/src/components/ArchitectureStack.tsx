import { architecture } from "../data/site";

export function ArchitectureStack() {
  return (
    <ol className="architecture-stack" aria-label="Engel AI Labs technology architecture">
      {architecture.map((layer, index) => (
        <li key={layer.name} className={`architecture-stack__layer architecture-stack__layer--${index}`}>
          <span className="architecture-stack__index">0{index + 1}</span>
          <div>
            <strong>{layer.name}</strong>
            <small>{layer.note}</small>
          </div>
        </li>
      ))}
    </ol>
  );
}
