#!/usr/bin/env python3
"""jev-live-flow data + UI server.

Serves the static flow UI and one JSON endpoint (/live.json) built from:
  * $HERMES_HOME/logs/agent.log          — per-turn API call lines
  * $HERMES_HOME/state.db                — session titles
  * $HERMES_HOME/logs/jev-decisions.jsonl — (optional) routing reason

No hardcoded machine paths: everything derives from $HERMES_HOME.
Run:  python3 server.py [--host H] [--port P]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sqlite3
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from config import FlowConfig, hermes_home, load_config, load_rates

# ── data locations (all HERMES_HOME-relative) ────────────────────────────────
HOME = hermes_home()
AGENT_LOG = HOME / "logs" / "agent.log"
JEV_DECISIONS = HOME / "logs" / "jev-decisions.jsonl"
STATE_DB = HOME / "state.db"
STATIC_DIR = Path(__file__).resolve().parent / "static"

# 2026-10-19 21:50:49,528 INFO [sessionid] agent.conversation_loop: API call #N:
#   model=X provider=Y in=A out=B total=C latency=D.Xs cache=E/F (P%) id=... upstream=PROV [rmodel=M]
API_CALL_RE = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+\s+\S+\s+\[([0-9a-f]{12})\]\s+'
    r'agent\.conversation_loop:\s+API call #(\d+):\s+'
    r'model=(\S+)\s+provider=(\S+)\s+in=(\d+)\s+out=(\d+)\s+total=(\d+)\s+'
    r'latency=([\d.]+)s.*?id=(\S+)\s+upstream=(\S+)(?:\s+rmodel=(\S+))?'
)
CACHE_RE = re.compile(r'cache=(\d+)/(\d+) \((\d+)%\)')


def _tz(cfg: FlowConfig):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(cfg.timezone)
    except Exception:
        return _dt.timezone(_dt.timedelta(hours=8))


def parse_ts(value: str, cfg: FlowConfig) -> float:
    try:
        return _dt.datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_tz(cfg)).timestamp()
    except Exception:
        return time.time()


def tail_lines(path: Path, limit: int) -> list[str]:
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            block = min(size, max(limit * 400, 65536))
            fh.seek(size - block)
            data = fh.read().decode("utf-8", "replace")
        return data.splitlines()[-limit:]
    except Exception:
        return []


def estimate_cost(model: str, in_tok: int, out_tok: int) -> float:
    rates, default = load_rates()
    low = (model or "").lower()
    if any(m in low for m in ("free",)):
        return 0.0
    rate = rates.get(model, default)
    return (in_tok * rate["in"] + out_tok * rate["out"]) / 1_000_000


def load_live(cfg: FlowConfig) -> list[dict]:
    events: list[dict] = []
    for line in tail_lines(AGENT_LOG, 6000):
        m = API_CALL_RE.search(line)
        if not m:
            continue
        ts_s, sid, n, model, provider, in_tok, out_tok, total, lat, rid, upstream, rmodel = m.groups()
        cm = CACHE_RE.search(line)
        events.append({
            "src": "log",
            "ts": parse_ts(ts_s, cfg),
            "session": sid,
            "call": int(n),
            "requested_model": model,
            "provider": provider,
            "prompt_tokens": int(in_tok),
            "completion_tokens": int(out_tok),
            "total_tokens": int(total),
            "latency_s": float(lat),
            "request_id": rid,
            "upstream": upstream,
            "real_model": rmodel,
            "cache_read_tokens": int(cm.group(1)) if cm else 0,
            "cache_pct": int(cm.group(3)) if cm else None,
            "effective_model": model,
            "cost_usd": 0.0,
            "cost_est": True,
        })

    for e in events:
        # real_model (what the provider served) is authoritative; never guess.
        e["effective_model"] = e["real_model"] or e["requested_model"]
        e["cost_usd"] = estimate_cost(e["effective_model"], e["prompt_tokens"], e["completion_tokens"])

    cutoff = time.time() - cfg.window_minutes * 60
    events = [e for e in events if e["ts"] >= cutoff]
    events.sort(key=lambda e: e["ts"], reverse=True)
    return events


def load_titles() -> dict[str, str]:
    titles: dict[str, str] = {}
    try:
        conn = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True)
        try:
            for sid, title in conn.execute(
                    "SELECT id, title FROM sessions WHERE title IS NOT NULL AND title != ''"):
                titles[sid] = title
        finally:
            conn.close()
    except Exception:
        pass
    return titles


def build_payload(cfg: FlowConfig) -> dict:
    return {
        "events": load_live(cfg),
        "titles": load_titles(),
        "config": {"window_minutes": cfg.window_minutes,
                   "max_arms": cfg.max_arms,
                   "max_chats": cfg.max_chats,
                   "poll_seconds": cfg.poll_seconds},
        "generated_at": time.time(),
    }


def publish_dir() -> Path | None:
    """Directory the web UI serves publicly as /static/ (no auth, no CSP sandbox).

    Plugin pages under /dashboard-plugins/ are served with `CSP: sandbox`, which
    makes the frame an opaque origin: fetch() is CORS-blocked and subresources
    lose the session cookie. /static/ has neither restriction, so the flow page
    lives there and polls normally (no page reloads).
    """
    override = os.environ.get("JEV_LIVE_FLOW_PUBLISH_DIR") or (
        load_config().publish_dir or "")
    if override:
        return Path(override).expanduser()
    for candidate in (hermes_home() / "webui-static",
                      Path.home() / "hermes-webui" / "static",
                      Path.home() / ".hermes" / "hermes-webui" / "static",
                      Path("/opt/hermes-webui/static"),
                      Path("/opt/hermes/webui/static")):
        if candidate.is_dir():
            return candidate
    return None


def build_page() -> str:
    """The flow UI as a single file: d3 inlined, data fetched relatively."""
    src = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    d3 = (STATIC_DIR / "vendor" / "d3.min.js").read_text(encoding="utf-8")
    src = src.replace('<script src="vendor/d3.min.js"></script>',
                      "<script>\n" + d3 + "\n</script>", 1)
    return src.replace("const LIVE_URL='./live.json'", "const LIVE_URL='./data.json'", 1)


def publish_loop(cfg: FlowConfig, interval: float = 2.0) -> None:
    base = publish_dir()
    if base is None:
        return
    out = base / "jev-live-flow"
    out.mkdir(parents=True, exist_ok=True)
    page_written = False
    while True:
        try:
            if not page_written:
                tmp = out / "index.html.tmp"
                tmp.write_text(build_page(), encoding="utf-8")
                tmp.replace(out / "index.html")
                page_written = True
            data = json.dumps(build_payload(cfg)).encode("utf-8")
            tmpd = out / "data.json.tmp"
            tmpd.write_bytes(data)
            tmpd.replace(out / "data.json")
        except Exception:
            page_written = False
        time.sleep(interval)


class Handler(SimpleHTTPRequestHandler):
    cfg: FlowConfig = FlowConfig()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, fmt, *args):
        pass

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        # The dashboard-plugin iframe runs in a sandboxed (opaque) origin, so
        # its fetch is cross-origin even on the same host. Allow it explicitly.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        # never serve stale UI while iterating
        if self.path.endswith((".html", ".js", ".css")):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        super().end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/live.json":
            try:
                self._json(build_payload(self.cfg))
            except Exception as exc:  # never 500 silently
                self._json({"error": str(exc), "events": [], "titles": {}}, status=500)
            return
        if path in ("/", ""):
            self.path = "/index.html"
        return super().do_GET()


def main() -> None:
    cfg = load_config()
    ap = argparse.ArgumentParser(description="jev-live-flow server")
    ap.add_argument("--host", default=cfg.host)
    ap.add_argument("--port", type=int, default=cfg.port)
    args = ap.parse_args()
    cfg.host, cfg.port = args.host, args.port

    Handler.cfg = cfg
    threading.Thread(target=publish_loop, args=(cfg,), daemon=True).start()
    httpd = ThreadingHTTPServer((cfg.host, cfg.port), Handler)
    print(f"jev-live-flow serving {STATIC_DIR} on http://{cfg.host}:{cfg.port}/", flush=True)
    print(f"  agent.log: {AGENT_LOG}", flush=True)
    print(f"  state.db : {STATE_DB}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
