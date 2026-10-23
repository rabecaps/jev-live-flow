"""FastAPI router for the jev-live-flow dashboard plugin.

Mounted by the Hermes web dashboard at ``/api/plugins/jev-live-flow/*``.

Routes
------
- ``GET /live.json``      → current events + titles + config (same shape as the
                            standalone server)
- ``GET /app``            → the flow UI (index.html) for the tab iframe
- ``GET /vendor/{name}``  → vendored assets (d3)

The UI is served through the dashboard origin, so the iframe works from any
client that can reach the dashboard — no hardcoded host or port.
"""
from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
_STATIC = _PLUGIN_ROOT / "static"

# The web server loads this file standalone (no parent package), so import the
# plugin's own server module by path under a unique alias to avoid collisions.
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

_spec = importlib.util.spec_from_file_location("_jev_live_flow_server", _PLUGIN_ROOT / "server.py")
_server = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_server)  # safe: server.py guards main() behind __main__

router = APIRouter()


@router.get("/live.json")
def live() -> Any:
    cfg = _server.load_config()
    return {
        "events": _server.load_live(cfg),
        "titles": _server.load_titles(),
        "config": {
            "window_minutes": cfg.window_minutes,
            "max_arms": cfg.max_arms,
            "poll_seconds": cfg.poll_seconds,
        },
        "generated_at": time.time(),
    }


@router.get("/app")
def app() -> FileResponse:
    index = _STATIC / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="UI not found")
    return FileResponse(index, media_type="text/html", headers={"Cache-Control": "no-store"})


@router.get("/vendor/{name}")
def vendor(name: str) -> FileResponse:
    # single flat segment only — no traversal
    if "/" in name or "\\" in name or name.startswith("."):
        raise HTTPException(status_code=400, detail="bad asset name")
    path = _STATIC / "vendor" / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="asset not found")
    media = "text/javascript" if name.endswith(".js") else "text/plain"
    return FileResponse(path, media_type=media, headers={"Cache-Control": "no-store"})
