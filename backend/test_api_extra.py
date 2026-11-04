import os
os.environ["RESQFLOW_OFFLINE"] = "1"

from fastapi.testclient import TestClient
from main import app

A, B, C = 1, 2, 3


def stock(c, cid, res="water"):
    camp = next(x for x in c.get("/api/campuses").json() if x["id"] == cid)
    return next(s for s in camp["stocks"] if s["resource"] == res)


def test_stock_update_and_expiry():
    with TestClient(app) as c:
        c.post("/api/simulate/reset")
        out = c.post("/api/inventory", json={"campus_id": C, "resource": "water", "quantity": 400, "expiry_days": 5}).json()
        assert out["quantity"] == 400 and out["hours_to_empty"] == 5.0
        assert stock(c, C)["expiry_days"] in (4, 5)
        assert c.post("/api/inventory", json={"campus_id": C, "resource": "water"}).status_code == 400
        assert c.post("/api/inventory", json={"campus_id": C, "resource": "water", "quantity": -1}).status_code == 422


def test_sms_fallback():
    with TestClient(app) as c:
        c.post("/api/simulate/reset")
        ok = c.post("/api/sms", json={"text": "A water 330"}).json()
        assert ok["ok"] and "Campus A water stock set to 330" in ok["message"]
        assert stock(c, A)["quantity"] == 330
        assert c.post("/api/sms", json={"text": "hello there"}).status_code == 400
        assert c.post("/api/sms", json={"text": "Z water 5"}).status_code == 404


def test_vehicle_availability_changes_feasibility():
    with TestClient(app) as c:
        c.post("/api/simulate/reset")
        c.post("/api/simulate/disaster")
        vehicles = c.get("/api/vehicles").json()
        assert len(vehicles) == 3
        for v in vehicles:
            c.post(f"/api/vehicles/{v['id']}/availability", json={"available": False})
        rec = c.get("/api/recommendations").json()[0]
        assert rec["feasible"] is False and any("No vehicle" in r for r in rec["reasons"])
        c.post("/api/simulate/reset")


def test_roads_forecast_impact_donations():
    with TestClient(app) as c:
        c.post("/api/simulate/reset")
        c.post("/api/roads", json={"from_campus_id": A, "to_campus_id": B, "blocked": True})
        assert c.get("/api/roads").json()["blocked_roads"] == [[1, 2]]
        c.post("/api/simulate/reset")
        assert c.get("/api/roads").json()["blocked_roads"] == []

        c.post("/api/simulate/disaster")
        f = c.get("/api/forecast").json()
        a_water = next(s for s in f["series"] if s["campus"] == "Campus A" and s["resource"] == "water")
        assert len(f["hours"]) == 25 and a_water["runs_out_in"] == 6.0 and a_water["values"][6] == 0

        rec = c.get("/api/recommendations").json()[0]
        t = c.post("/api/transfers", json={"from_campus_id": B, "to_campus_id": A, "resource": "water",
                                           "quantity": rec["quantity"], "reasons": rec["reasons"]}).json()
        c.post("/api/donations", json={"donor_name": "Acme", "resource": "water", "quantity": 500, "intended_campus_id": A})
        c.post(f"/api/transfers/{t['id']}/advance")
        c.post(f"/api/transfers/{t['id']}/advance")
        im = c.get("/api/impact").json()
        assert im["water_redirected_l"] == 2000 and im["transfers_completed"] == 1 and im["donations_redirected"] == 1
        d = c.get("/api/donations").json()
        assert d[0]["redirected"] is True and d[0]["redirected_campus"] == "Campus C"
        c.post("/api/simulate/reset")
