const CANONICAL_ORIGIN = "https://engelailabs.com";
const WWW_HOSTNAME = "www.engelailabs.com";

const responseHeaders = {
  "Cache-Control": "public, max-age=3600",
  "Referrer-Policy": "no-referrer",
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
} as const;

export default {
  fetch(request: Request): Response {
    const incoming = new URL(request.url);
    if (incoming.hostname !== WWW_HOSTNAME) {
      return new Response("Misdirected Request", {
        status: 421,
        headers: { ...responseHeaders, "Content-Type": "text/plain; charset=utf-8" },
      });
    }

    const destination = new URL(`${incoming.pathname}${incoming.search}`, CANONICAL_ORIGIN);
    return new Response(null, {
      status: 308,
      headers: { ...responseHeaders, Location: destination.toString() },
    });
  },
} satisfies ExportedHandler;
