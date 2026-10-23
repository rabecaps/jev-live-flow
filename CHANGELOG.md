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
