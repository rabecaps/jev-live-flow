"""Configuration for the jev-live-flow plugin.

Every path resolves from $HERMES_HOME so the plugin works on any Hermes install
without editing code. Defaults are deliberately loopback-only.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PLUGIN_NAME = "jev-live-flow"

# Pricing is per 1M tokens and is an ESTIMATE. Prices move often, so this lives
# in config so a user can change it without touching code.
DEFAULT_RATES: dict[str, dict[str, float]] = {
    "deepseek/deepseek-v4.1-flash-1017": {"in": 0.022, "out": 0.09},
    "deepseek/deepseek-v4-flash-0731": {"in": 0.022, "out": 0.09},
    "qwen/qwen3.8-flash": {"in": 0.12, "out": 0.5},
    "google/gemini-2.5-flash-lite": {"in": 0.3, "out": 1.5},
    "nvidia/nemotron-3.5-lightning": {"in": 0.1, "out": 0.4},
}
DEFAULT_RATE = {"in": 0.2, "out": 0.8}

# Anything containing this substring is treated as free tier ($0).
FREE_MATCHERS = ("free",)


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))


def data_dir() -> Path:
    path = hermes_home() / "plugin-data" / PLUGIN_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    override = os.environ.get("JEV_LIVE_FLOW_CONFIG")
    return Path(override).expanduser() if override else data_dir() / "config.json"


@dataclass
class FlowConfig:
    host: str = "127.0.0.1"
    port: int = 8780
    window_minutes: int = 15
    max_arms: int = 5
    timezone: str = "Australia/Perth"
    # seconds between browser polls (UI side)
    poll_seconds: int = 3
    # max chats rendered in the graph (keeps it readable)
    max_chats: int = 3
    # dir served by the web UI as /static/; empty = auto-detect
    publish_dir: str = ""
    # Directory (or file) where the same-origin data file is published for the
    # web UI plugin tab. Empty = auto-detect a Hermes web UI static dir.
    snapshot_path: str = ""

    @property
    def local_url(self) -> str:
        host = "127.0.0.1" if self.host in ("0.0.0.0", "", "::") else self.host
        return f"http://{host}:{self.port}/"


def load_config() -> FlowConfig:
    cfg = FlowConfig()
    path = config_path()
    if path.exists():
        try:
            raw = json.loads(path.read_text() or "{}")
        except Exception:
            raw = {}
        for key in ("host", "port", "window_minutes", "max_arms", "timezone",
                    "poll_seconds", "max_chats"):
            if key in raw and raw[key] is not None:
                try:
                    setattr(cfg, key, type(getattr(cfg, key))(raw[key]))
                except Exception:
                    pass
        if raw.get("publish_dir"):
            cfg.publish_dir = str(raw["publish_dir"])
    return cfg


def save_config(cfg: FlowConfig) -> None:
    config_path().write_text(json.dumps(asdict(cfg), indent=2) + "\n")


def load_rates() -> tuple[dict[str, dict[str, float]], dict[str, float]]:
    """Return (per-model rates, default rate), overridable via config.json."""
    rates = dict(DEFAULT_RATES)
    default = dict(DEFAULT_RATE)
    path = config_path()
    if path.exists():
        try:
            raw: dict[str, Any] = json.loads(path.read_text() or "{}")
        except Exception:
            raw = {}
        if isinstance(raw.get("rates"), dict):
            for model, r in raw["rates"].items():
                if isinstance(r, dict) and "in" in r and "out" in r:
                    rates[str(model)] = {"in": float(r["in"]), "out": float(r["out"])}
        if isinstance(raw.get("default_rate"), dict):
            d = raw["default_rate"]
            if "in" in d and "out" in d:
                default = {"in": float(d["in"]), "out": float(d["out"])}
    return rates, default


def public_config(cfg: FlowConfig) -> dict[str, Any]:
    return {
        "host": cfg.host,
        "port": cfg.port,
        "window_minutes": cfg.window_minutes,
        "max_arms": cfg.max_arms,
        "timezone": cfg.timezone,
        "local_url": cfg.local_url,
        "hermes_home": str(hermes_home()),
    }
