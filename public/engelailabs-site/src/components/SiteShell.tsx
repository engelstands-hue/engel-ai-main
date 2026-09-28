import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { navigation } from "../data/site";
import { BrandMark } from "./BrandMark";
import { PageMeta } from "./PageMeta";

export function SiteShell({ children }: { children: ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const mainContent = useRef<HTMLElement>(null);
  const previousPath = useRef<string | null>(null);
  const location = useLocation();

  useEffect(() => {
    setMenuOpen(false);
    window.scrollTo({ top: 0, behavior: "auto" });
    if (previousPath.current !== null && previousPath.current !== location.pathname) {
      mainContent.current?.focus({ preventScroll: true });
    }
    previousPath.current = location.pathname;
  }, [location.pathname]);

  useEffect(() => {
    if (!menuOpen) return undefined;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
        menuButton.current?.focus();
      }
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [menuOpen]);

  return (
    <div className="site-shell">
      <PageMeta />
      <a className="skip-link" href="#main-content">Skip to content</a>
      <div className="ambient-grid" aria-hidden="true" />
      <header className="site-header">
        <div className="container site-header__inner">
          <BrandMark />
          <button
            ref={menuButton}
            className="menu-toggle"
            type="button"
            aria-expanded={menuOpen}
            aria-controls="primary-navigation"
            onClick={() => setMenuOpen((current) => !current)}
          >
            <span aria-hidden="true" />
            <span className="sr-only">Toggle navigation</span>
          </button>
          <nav
            className={`primary-nav${menuOpen ? " primary-nav--open" : ""}`}
            id="primary-navigation"
            aria-label="Primary navigation"
          >
            {navigation.map((item) => (
              <NavLink key={item.path} to={item.path}>{item.label}</NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main id="main-content" ref={mainContent} tabIndex={-1}>{children}</main>
      <footer className="site-footer">
        <div className="container site-footer__top">
          <div>
            <BrandMark />
            <p>Local intelligence. Connected workers. Human-guided automation.</p>
          </div>
          <div className="site-footer__links" aria-label="Footer navigation">
            <Link to="/engel-ai-main">Engel AI Main</Link>
            <Link to="/docs">Documentation</Link>
            <Link to="/community">Community</Link>
            <Link to="/status">Status</Link>
            <Link to="/privacy">Privacy</Link>
            <Link to="/terms">Terms</Link>
            <Link to="/security">Security</Link>
            <Link to="/contact">Contact</Link>
            <a href="https://github.com/engelstands-hue/engel-ai-main" rel="noopener noreferrer">Source</a>
            <a href="https://x.com/engelaimain" rel="noopener noreferrer">X</a>
          </div>
        </div>
        <div className="container site-footer__bottom">
          <span>© {new Date().getFullYear()} Engel AI Labs</span>
          <span>Public platform · No private systems connected</span>
        </div>
      </footer>
    </div>
  );
}
