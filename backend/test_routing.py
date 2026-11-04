import routing


class FakeResponse:
    def raise_for_status(self): pass
    def json(self):
        return {"routes": [{"distance": 12400, "duration": 1500,
                            "geometry": {"coordinates": [[77.72, 12.93], [77.68, 12.95], [77.64, 12.97]]}}]}


def test_offline_falls_back_to_estimate(monkeypatch):
    monkeypatch.setenv("RESQFLOW_OFFLINE", "1")
    routing.reset()
    r = routing.get_route(12.9386, 77.7220, 12.9719, 77.6412)
    assert r["source"] == "estimate" and len(r["geometry"]) == 2 and r["km"] > 0


def test_osrm_response_is_parsed_and_cached(monkeypatch):
    monkeypatch.delenv("RESQFLOW_OFFLINE", raising=False)
    routing.reset()
    calls = []
    monkeypatch.setattr(routing.httpx, "get", lambda *a, **k: calls.append(1) or FakeResponse())
    r = routing.get_route(12.9386, 77.7220, 12.9719, 77.6412)
    assert r["source"] == "osrm" and r["km"] == 12.4 and r["minutes"] == 25
    assert r["geometry"][0] == [12.93, 77.72]          # flipped to [lat, lng] for the map
    routing.get_route(12.9386, 77.7220, 12.9719, 77.6412)
    assert len(calls) == 1                              # second call came from the cache


def test_network_failure_falls_back_and_backs_off(monkeypatch):
    monkeypatch.delenv("RESQFLOW_OFFLINE", raising=False)
    routing.reset()
    calls = []

    def boom(*a, **k):
        calls.append(1)
        raise ConnectionError("no wifi")
    monkeypatch.setattr(routing.httpx, "get", boom)
    assert routing.get_route(12.9, 77.7, 12.97, 77.64)["source"] == "estimate"
    assert routing.get_route(12.9, 77.7, 12.97, 77.64)["source"] == "estimate"
    assert len(calls) == 1                              # did not hammer the network again
    routing.reset()
