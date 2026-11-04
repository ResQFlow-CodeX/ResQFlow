"""Road routing with a safety net.

Asks the free OSRM service for the real road route. If the internet is slow or down,
it falls back to a straight-line estimate, so the demo NEVER depends on Wi-Fi.
After one failure it stops trying for 60 seconds, so there are no repeated delays.
Set RESQFLOW_OFFLINE=1 to skip OSRM completely (used by the tests).
"""
import os
import time
from types import SimpleNamespace

import httpx

import engine as eng

OSRM_URL = os.getenv("OSRM_URL", "https://router.project-osrm.org")
TIMEOUT_SECONDS = 2.0
RETRY_AFTER_SECONDS = 60

_cache: dict = {}
_down_until = 0.0


def reset():
    global _down_until
    _cache.clear()
    _down_until = 0.0


def _estimate(a_lat, a_lng, b_lat, b_lng):
    km, minutes = eng.default_travel(SimpleNamespace(lat=a_lat, lng=a_lng), SimpleNamespace(lat=b_lat, lng=b_lng))
    return {"km": km, "minutes": minutes, "geometry": [[a_lat, a_lng], [b_lat, b_lng]], "source": "estimate"}


def get_route(a_lat, a_lng, b_lat, b_lng) -> dict:
    """Returns {km, minutes, geometry: [[lat, lng], ...], source: 'osrm' | 'estimate'}."""
    global _down_until
    key = tuple(round(x, 5) for x in (a_lat, a_lng, b_lat, b_lng))
    if key in _cache:
        return _cache[key]
    if os.getenv("RESQFLOW_OFFLINE") != "1" and time.time() >= _down_until:
        try:
            url = f"{OSRM_URL}/route/v1/driving/{a_lng},{a_lat};{b_lng},{b_lat}"
            resp = httpx.get(url, params={"overview": "simplified", "geometries": "geojson"}, timeout=TIMEOUT_SECONDS)
            resp.raise_for_status()
            route = resp.json()["routes"][0]
            result = {"km": round(route["distance"] / 1000, 1),
                      "minutes": round(route["duration"] / 60),
                      "geometry": [[lat, lng] for lng, lat in route["geometry"]["coordinates"]],
                      "source": "osrm"}
            _cache[key] = result
            return result
        except Exception:
            _down_until = time.time() + RETRY_AFTER_SECONDS
    return _estimate(a_lat, a_lng, b_lat, b_lng)      # not cached, so OSRM is retried later


def travel(a, b):
    """Adapter used by the decision engine: (distance_km, eta_minutes)."""
    r = get_route(a.lat, a.lng, b.lat, b.lng)
    return r["km"], r["minutes"]
