# jev-live-flow

Live, left-to-right visualisation of Hermes ⇄ Jev chat turns.

For each active chat you see:

- the chat (a short keyword summary of its real title)
- the last few turns as rounded cards: **which model served it**, total tokens, and estimated cost
- a **chip** per turn — for free-router turns, the provider that actually served it
  (the OpenRouter upstream name, e.g. `DigitalOcean`, `Poolside`); for paid turns, the
  **reused vs new** token split
  (`reused 280.2K / new 284`) taken from the provider's own cache report
- a **running total** per chat (turns, tokens, cost)

Design rules baked in:

- The stack only advances when a genuinely new turn arrives — a passive chat never moves.
- Only nodes whose position changed animate.
- Free models cost `$0.000`.
- The model shown is what actually ran; it is never guessed from a timestamp match.

## Requirements

- Hermes Agent with `$HERMES_HOME` populated (defaults to `~/.hermes`).
- Python 3.9+ (stdlib only — no pip dependencies).
- Nothing else: D3 is vendored, no CDN at runtime.

## Install

1. Copy this folder to `$HERMES_HOME/plugins/jev-live-flow/`.
2. Add `jev-live-flow` to `plugins.enabled` in `config.yaml`:

   ```bash
   hermes config set plugins.enabled '["...existing...", "jev-live-flow"]'
   ```

   (or let `hermes plugins install` manage it).
3. Restart the gateway so the tools register.

## Use

```
jev_live_flow_start     → starts the UI, returns the URL
jev_live_flow_status    → is it running, and where
jev_live_flow_stop      → stop it
jev_live_flow_config    → change host/port/window/arms/timezone
```

Defaults: `127.0.0.1:8780`, 15-minute window, 5 turn cards per chat.

To expose it on the LAN: `jev_live_flow_config` with `host: 0.0.0.0`, then stop/start.
There is **no authentication** — keep it loopback unless you understand the exposure.

## Data sources

| Source | Used for |
|---|---|
| `$HERMES_HOME/logs/agent.log` | per-turn model, tokens, cache, upstream, id |
| `$HERMES_HOME/state.db` (`sessions.title`) | chat keyword labels |
| `$HERMES_HOME/logs/jev-decisions.jsonl` | reserved (routing reason) |

## Configuration file

`$HERMES_HOME/plugin-data/jev-live-flow/config.json`

```json
{
  "host": "127.0.0.1",
  "port": 8780,
  "window_minutes": 15,
  "max_arms": 5,
  "timezone": "Australia/Perth",
  "poll_seconds": 3,
  "rates": {
    "deepseek/deepseek-v4.1-flash-1017": {"in": 0.022, "out": 0.09}
  },
  "default_rate": {"in": 0.2, "out": 0.8}
}
```

`rates` are **$ per 1M tokens** and are estimates — set them to your provider's
current prices. Any model whose name contains `free` is costed at `$0`.

## Known limitations

- **Cost is an estimate** derived from the token counts in `agent.log` and the
  rate table. It is not billed cost. For exact numbers use the provider's API.
- **No tools-vs-memory-vs-context split.** The provider reports one aggregate
  prompt-token count plus a cache figure. Only *cached (reused)* vs *fresh* is
  real; a three-way split would be fabricated.
- **No `real_model` on some transports.** If the response object does not expose
  the served model, the arm falls back to the requested model.
- Single-user, no auth, in-memory layout state on the browser side.

## License

Plugin code: MIT.
Vendored D3: MIT — see `static/vendor/LICENSE-d3.txt`.
