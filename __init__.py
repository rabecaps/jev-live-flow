"""jev-live-flow — Hermes plugin entry point.

Registers four tools that manage a local-only web UI showing live chat turns:
which model served each turn, tokens, cost, and cached-vs-new context.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

from config import FlowConfig, data_dir, load_config, public_config, save_config

PLUGIN_NAME = "jev-live-flow"


def _pid_file() -> Path:
    return data_dir() / "server.pid"


def _read_pid() -> int | None:
    try:
        return int(_pid_file().read_text().strip())
    except Exception:
        return None


def _alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _probe(url: str) -> bool:
    try:
        with urllib.request.urlopen(url + "live.json", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def _start(**kwargs) -> str:
    cfg = load_config()
    if kwargs.get("host"):
        cfg.host = kwargs["host"]
    if kwargs.get("port"):
        cfg.port = int(kwargs["port"])

    pid = _read_pid()
    if _alive(pid):
        return json.dumps({"ok": True, "already_running": True, "pid": pid,
                           "url": cfg.local_url}, indent=2)

    log = data_dir() / "server.log"
    with log.open("ab") as fh:
        proc = subprocess.Popen(
            [sys.executable, str(_PLUGIN_DIR / "server.py"),
             "--host", cfg.host, "--port", str(cfg.port)],
            stdout=fh, stderr=fh, start_new_session=True, cwd=str(_PLUGIN_DIR),
            env={**os.environ, "PYTHONPATH": str(_PLUGIN_DIR)},
        )
    _pid_file().write_text(str(proc.pid))

    for _ in range(30):
        if _probe(cfg.local_url):
            return json.dumps({"ok": True, "pid": proc.pid, "url": cfg.local_url,
                               "log": str(log)}, indent=2)
        time.sleep(0.2)
    return json.dumps({"ok": False, "pid": proc.pid,
                       "error": "server did not answer within 6s",
                       "log": str(log)}, indent=2)


def _stop(**_) -> str:
    pid = _read_pid()
    if not _alive(pid):
        _pid_file().unlink(missing_ok=True)
        return json.dumps({"ok": True, "already_stopped": True}, indent=2)
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(25):
            if not _alive(pid):
                break
            time.sleep(0.2)
        else:
            os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    _pid_file().unlink(missing_ok=True)
    return json.dumps({"ok": True, "stopped": pid}, indent=2)


def _status(**_) -> str:
    cfg = load_config()
    pid = _read_pid()
    running = _alive(pid)
    return json.dumps({
        "ok": True,
        "running": running,
        "pid": pid if running else None,
        "url": cfg.local_url if running else None,
        "answering": _probe(cfg.local_url) if running else False,
        **public_config(cfg),
    }, indent=2)


def _config(**kwargs) -> str:
    cfg = load_config()
    changed = False
    for key in ("host", "port", "window_minutes", "max_arms", "timezone", "poll_seconds"):
        if key in kwargs and kwargs[key] is not None:
            try:
                setattr(cfg, key, type(getattr(cfg, key))(kwargs[key]))
                changed = True
            except Exception:
                pass
    if changed:
        save_config(cfg)
    return json.dumps({"ok": True, "changed": changed, **public_config(cfg),
                       "note": "restart the server (stop then start) to apply host/port"},
                      indent=2)


def register(ctx):
    cfg = load_config()
    ctx.register_tool(
        name="jev_live_flow_start",
        toolset=PLUGIN_NAME,
        schema={"name": "jev_live_flow_start",
                "description": "Start the local live chat-flow dashboard (model per turn, tokens, cost).",
                "parameters": {"type": "object", "properties": {
                    "host": {"type": "string", "default": cfg.host,
                             "description": "Bind address; use 0.0.0.0 for LAN."},
                    "port": {"type": "integer", "default": cfg.port}}}},
        handler=_start, check_fn=lambda: True, requires_env=[],
        description="Start live flow dashboard", emoji="🌊",
    )
    ctx.register_tool(
        name="jev_live_flow_stop",
        toolset=PLUGIN_NAME,
        schema={"name": "jev_live_flow_stop",
                "description": "Stop the live chat-flow dashboard.",
                "parameters": {"type": "object", "properties": {}}},
        handler=_stop, check_fn=lambda: True, requires_env=[],
        description="Stop live flow dashboard", emoji="🛑",
    )
    ctx.register_tool(
        name="jev_live_flow_status",
        toolset=PLUGIN_NAME,
        schema={"name": "jev_live_flow_status",
                "description": "Check whether the live flow dashboard is running and at which URL.",
                "parameters": {"type": "object", "properties": {}}},
        handler=_status, check_fn=lambda: True, requires_env=[],
        description="Live flow dashboard status", emoji="📊",
    )
    ctx.register_tool(
        name="jev_live_flow_config",
        toolset=PLUGIN_NAME,
        schema={"name": "jev_live_flow_config",
                "description": "Read or update jev-live-flow settings (host, port, window, arms, timezone).",
                "parameters": {"type": "object", "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                    "window_minutes": {"type": "integer"},
                    "max_arms": {"type": "integer"},
                    "timezone": {"type": "string"},
                    "poll_seconds": {"type": "integer"}}}},
        handler=_config, check_fn=lambda: True, requires_env=[],
        description="Configure live flow dashboard", emoji="⚙️",
    )
