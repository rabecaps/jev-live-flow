## 1.0.7 - 2026-10-24
Keep the user's view across the auto-refresh.

- The embedded-data branch restored the saved d3 transform, then the first
  render's auto-fit() overwrote it. It now sets hasFit=true so the restored
  pan/zoom is kept.
- Verified: identical transform before/after a refresh cycle while data updated.

## 1.0.6 — 2026-10-24
Make the tab truly self-contained (no external requests at all).

- The server now renders `dashboard/dist/index.html` every 2s with BOTH d3 and
  the data payload inlined. The page makes zero subresource requests, so it
  cannot be broken by the web UI's sandboxed-plugin CSP (opaque origin: fetch
  is CORS-blocked, subresources lose the session cookie).
- Page auto-refreshes every 5s and restores the pan/zoom view from
  sessionStorage, so the refresh is not jarring.
- Bundled `systemd/jev-live-flow.service` (user unit, %h paths) for durable
  operation.
- README documents required vs optional dependencies (Hermes required, Jev
  optional, Python stdlib only, D3 inlined).

## 1.0.5 — 2026-10-24
Fix the WebUI tab for real (verified against the server access log).

- d3 is now INLINED into dashboard/dist/index.html. The web UI serves plugin
  pages under `CSP: sandbox`, so subresource requests lose the session cookie
  and were 302-redirected to /login — the page received HTML instead of JS and
  threw "d3 is not defined".
- Data is published as a same-origin, unauthenticated snapshot at
  `/static/jev-live-flow.json` (the web UI serves /static/* without auth), so
  it works from the sandboxed frame and over https (no mixed content).
- The server now runs as a systemd user service with Restart=always instead of
  a bare spawned process.

# Changelog

## 1.0.0 — 2026-10-23
Initial packaged release.

- Live left→right flow: origin → recent turn cards → per-chat running total.
- Model shown is the served model (`real_model`) when the provider reports it,
  otherwise the requested model. No timestamp-based guessing.
- Free-tier models cost $0.000.
- Paid turns carry a chip with the actual **reused vs new** prompt tokens.
- Free-router turns carry a chip naming the upstream provider that served them.
- Chat labels are a 1–2 keyword summary of the real session title.
- Arm stack advances only on a real new turn; passive chats stay still.
- Deterministic layout, d3 zoom/pan/fit, no physics simulation.
- Configurable host/port/window/arms/timezone + editable price table.
