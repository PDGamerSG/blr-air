// Same-origin /api proxy for the Vercel-hosted site.
//
// The planner calls /api/* on its own origin. Vercel rewrites those paths here and this
// function forwards them to the Python web service (blr_air/web.py) at BLR_AIR_API_ORIGIN,
// an always-on HTTPS backend. Set that backend's PUBLIC_ORIGIN to this site's exact origin
// (https://blrairwindow.vercel.app): the browser's Origin header is forwarded unchanged.
// Without a configured backend the API answers with JSON errors, so the planner reports
// itself unavailable while the rest of the page keeps working.

const REQUEST_HEADERS = ["accept", "accept-language", "content-type", "origin"];
const RESPONSE_HEADERS = ["content-type", "content-disposition", "cache-control", "retry-after"];
const PATH = /^\/api\/[A-Za-z0-9._~%\-/]*$/;

function fail(status, error) {
  return Response.json({ status: "error", error }, { status, headers: { "cache-control": "no-store" } });
}

function backendOrigin() {
  try {
    const url = new URL(process.env.BLR_AIR_API_ORIGIN ?? "");
    const loopback = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
    if (url.username || url.password) return null;
    return url.protocol === "https:" || (url.protocol === "http:" && loopback) ? url.origin : null;
  } catch {
    return null;
  }
}

export default {
  async fetch(request) {
    const origin = backendOrigin();
    if (!origin) {
      return fail(503, "The planning service isn't connected to this website yet. The quick forecast scan still works.");
    }
    const incoming = new URL(request.url);
    // Vercel keeps the original /api/... URL for rewritten requests; the ?path= copy from
    // the rewrite covers the case where only the destination is visible.
    let path = incoming.pathname;
    if (!path.startsWith("/api/") || path === "/api/proxy") path = `/api/${incoming.searchParams.get("path") ?? ""}`;
    incoming.searchParams.delete("path");
    if (!PATH.test(path) || path.includes("..")) return fail(400, "Invalid API path.");

    const headers = new Headers();
    for (const name of REQUEST_HEADERS) {
      const value = request.headers.get(name);
      if (value) headers.set(name, value);
    }
    const init = { method: request.method, headers, redirect: "manual", signal: AbortSignal.timeout(58_000) };
    if (request.method !== "GET" && request.method !== "HEAD") init.body = await request.arrayBuffer();

    let upstream;
    try {
      upstream = await fetch(new URL(path + incoming.search, origin), init);
    } catch (error) {
      return error?.name === "TimeoutError"
        ? fail(504, "The planning service took too long. Please try again.")
        : fail(502, "The planning service is unreachable. Please try again shortly.");
    }
    const out = new Headers();
    for (const name of RESPONSE_HEADERS) {
      const value = upstream.headers.get(name);
      if (value) out.set(name, value);
    }
    if (!out.has("cache-control")) out.set("cache-control", "no-store");
    return new Response(upstream.body, { status: upstream.status, headers: out });
  },
};
