import type { ReactNode } from "react";

export function PageIntro({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <section className="page-intro container">
      <div className="orbital-label"><span />{eyebrow}</div>
      <h1>{title}</h1>
      <p>{description}</p>
      {children}
    </section>
  );
}
