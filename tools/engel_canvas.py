#!/usr/bin/env python3
"""
Engel AI Main — Canvas: agent-driven document workspace.

Ported concept from OpenClaw (MIT) Canvas (agent-driven live visual workspace,
served over the Gateway HTTP). The agent writes a document (HTML or Markdown);
Engel saves it under runtime/canvas/ and serves it over a small HTTP server so it
renders in a browser or a Flutter WebView panel. This is the backend + transport;
the Flutter Canvas panel is a thin viewer on top (opens the served URL).

Reimplemented natively in Python (stdlib only); MIT-attributed.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
import threading
import time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
CANVAS_DIR = ROOT / "runtime" / "canvas"
DEFAULT_PORT = 8791

_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
 body{{font:16px/1.6 system-ui,Segoe UI,sans-serif;max-width:820px;margin:2rem auto;padding:0 1rem;
   background:#0d1213;color:#e2efee}} a{{color:#00e5ff}}
 h1,h2,h3{{line-height:1.2}} code,pre{{font-family:ui-monospace,Consolas,monospace}}
 pre{{background:#070b0c;border:1px solid #223133;border-radius:8px;padding:12px;overflow:auto}}
 .engel-badge{{font:12px ui-monospace,monospace;color:#5f7373;border-top:1px solid #223133;margin-top:2rem;padding-top:1rem}}
</style></head><body>{body}
<div class="engel-badge">Engel AI Main · Canvas · {ts}</div></body></html>"""


def _md_to_html(md: str) -> str:
    out = []
    in_code = False
    for line in md.splitlines():
        if line.strip().startswith("```"):
            out.append("</pre>" if in_code else "<pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        m = re.match(r"^(#{1,3})\s+(.*)", line)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{html.escape(m.group(2))}</h{lvl}>")
            continue
        line = html.escape(line)
        line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
        line = re.sub(r"`(.+?)`", r"<code>\1</code>", line)
        line = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', line)
        out.append("<br>" if not line.strip() else f"<p>{line}</p>")
    if in_code:
        out.append("</pre>")
    return "\n".join(out)


def _safe_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-]+", "_", name).strip("_") or "canvas"


def write_canvas(name: str, content: str, kind: str = "html", title: str = "", port: int = DEFAULT_PORT) -> dict:
    """Write an agent document to the canvas and return its served URL."""
    CANVAS_DIR.mkdir(parents=True, exist_ok=True)
    name = _safe_name(name)
    body = content if kind == "html" else _md_to_html(content)
    page = _PAGE.format(title=title or name, body=body, ts=time.strftime("%Y-%m-%d %H:%M:%S"))
    path = CANVAS_DIR / f"{name}.html"
    path.write_text(page, encoding="utf-8")
    return {"ok": True, "name": name, "path": str(path), "url": f"http://127.0.0.1:{port}/{name}.html", "bytes": len(page)}


def list_canvases() -> list[dict]:
    if not CANVAS_DIR.exists():
        return []
    return [{"name": f.stem, "bytes": f.stat().st_size, "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(f.stat().st_mtime))}
            for f in sorted(CANVAS_DIR.glob("*.html"), key=lambda p: -p.stat().st_mtime)]


class _Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(CANVAS_DIR), **kw)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            items = "".join(f'<li><a href="/{c["name"]}.html">{c["name"]}</a> · {c["modified"]}</li>' for c in list_canvases())
            page = _PAGE.format(title="Engel Canvas", body=f"<h1>Engel Canvas</h1><ul>{items or '<li>(empty)</li>'}</ul>", ts=time.strftime("%H:%M:%S"))
            body = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def make_server(port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    CANVAS_DIR.mkdir(parents=True, exist_ok=True)
    return ThreadingHTTPServer(("127.0.0.1", port), _Handler)


def serve(port: int = DEFAULT_PORT) -> None:
    srv = make_server(port)
    print(f"[engel] Canvas serving runtime/canvas/ at http://127.0.0.1:{port}/ (Ctrl-C to stop)", file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


def _cli(argv: Optional[list[str]] = None) -> int:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Engel Canvas — agent document workspace (OpenClaw Canvas port).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write"); w.add_argument("--name", required=True); w.add_argument("--content", required=True); w.add_argument("--kind", default="html", choices=["html", "markdown"])
    sub.add_parser("list")
    s = sub.add_parser("serve"); s.add_argument("--port", type=int, default=DEFAULT_PORT)
    a = ap.parse_args(argv)
    import json
    if a.cmd == "write":
        print(json.dumps(write_canvas(a.name, a.content, a.kind), indent=2))
    elif a.cmd == "list":
        for c in list_canvases():
            print(f"  {c['name']:24} {c['bytes']:>7}b  {c['modified']}")
    elif a.cmd == "serve":
        serve(a.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
