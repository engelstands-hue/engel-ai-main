import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import routeMetadata from "../data/route-metadata.json";

type RouteMetadata = (typeof routeMetadata)[number];

const fallback: RouteMetadata = {
  path: "/404",
  title: "Page not found | Engel AI Labs",
  description: "The public Engel AI Labs platform has no route at this address.",
  index: false,
};

function canonicalPath(pathname: string): string {
  if (pathname === "/") return pathname;
  return pathname.replace(/\/+$/, "") || "/";
}

function setMeta(selector: string, attributes: Record<string, string>) {
  let element = document.head.querySelector<HTMLMetaElement>(selector);
  if (!element) {
    element = document.createElement("meta");
    document.head.append(element);
  }
  for (const [name, value] of Object.entries(attributes)) element.setAttribute(name, value);
}

export function PageMeta() {
  const location = useLocation();

  useEffect(() => {
    const path = canonicalPath(location.pathname);
    const metadata = routeMetadata.find((candidate) => candidate.path === path) ?? fallback;
    const canonical = new URL(metadata.path === "/404" ? path : metadata.path, "https://engelailabs.com").toString();

    document.title = metadata.title;
    setMeta('meta[name="description"]', { name: "description", content: metadata.description });
    setMeta('meta[name="robots"]', { name: "robots", content: metadata.index ? "index, follow" : "noindex, nofollow" });
    setMeta('meta[property="og:title"]', { property: "og:title", content: metadata.title });
    setMeta('meta[property="og:description"]', { property: "og:description", content: metadata.description });
    setMeta('meta[property="og:url"]', { property: "og:url", content: canonical });
    setMeta('meta[name="twitter:title"]', { name: "twitter:title", content: metadata.title });
    setMeta('meta[name="twitter:description"]', { name: "twitter:description", content: metadata.description });

    let link = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!link) {
      link = document.createElement("link");
      link.rel = "canonical";
      document.head.append(link);
    }
    link.href = canonical;
  }, [location.pathname]);

  return null;
}
