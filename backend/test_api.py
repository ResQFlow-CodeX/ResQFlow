"""End-to-end test of the whole demo story. Run: python -m pytest -v
NOTE: this resets the demo database, which is fine."""
import os
os.environ["RESQFLOW_OFFLINE"] = "1"      # tests never touch the internet

from fastapi.testclient import TestClient
from main import app

A, B, C = 1, 2, 3


def water(client, cid):
    camp = next(c for c in client.get("/api/campuses").json() if c["id"] == cid)
    return next(s for s in camp["stocks"] if s["resource"] == "water")


def test_full_demo_story():
    with TestClient(app) as c:
        c.post("/api/simulate/reset")
        assert c.get("/api/recommendations").json() == []                 # 1. all healthy
        assert water(c, A)["status"] == "green"

        c.post("/api/simulate/disaster")                                  # 2. disaster
        assert water(c, A)["hours_to_empty"] == 6.0 and water(c, A)["status"] == "red"

        recs = c.get("/api/recommendations").json()                       # 3. recommendation
        assert len(recs) == 1
        r = recs[0]
        assert (r["from_campus"]["name"], r["to_campus"]["name"], r["quantity"]) == ("Campus B", "Campus A", 2000)

        assert len(r["route"]) >= 2 and r["route_source"] == "estimate"
        t = c.post("/api/transfers", json={                               # 4. approve
            "from_campus_id": B, "to_campus_id": A, "resource": "water",
            "quantity": r["quantity"], "reasons": r["reasons"], "action": "approve"}).json()
        assert t["status"] == "approved" and len(t["route"]) >= 2
        assert c.get("/api/recommendations").json() == []                 # no duplicate suggestion

        d = c.post("/api/donations", json={"donor_name": "Acme CSR", "resource": "water",
                                           "quantity": 1000, "intended_campus_id": A}).json()
        assert not d["accepted_as_intended"] and d["redirected_campus"]["name"] == "Campus C"   # 6. redirect

        assert c.post(f"/api/transfers/{t['id']}/advance").json()["status"] == "dispatched"
        assert c.post(f"/api/transfers/{t['id']}/advance").json()["status"] == "received"
        assert water(c, A)["quantity"] == 2660 and water(c, B)["quantity"] == 3900
        assert c.post(f"/api/transfers/{t['id']}/advance").status_code == 400

        c.post("/api/requests", json={"campus_id": C, "resource": "medicine",   # 5. urgent medicine
                                      "quantity": 30, "deadline_hours": 4})
        top = c.get("/api/recommendations").json()[0]
        assert top["resource"] == "medicine" and top["to_campus"]["name"] == "Campus C"

        actions = [e["action"] for e in c.get("/api/log").json()]
        assert {"approve", "dispatch", "receive"} <= set(actions)


def test_decline_and_validation():
    with TestClient(app) as c:
        c.post("/api/simulate/reset")
        body = {"from_campus_id": B, "to_campus_id": A, "resource": "water", "quantity": 500, "action": "decline"}
        assert c.post("/api/transfers", json=body).json()["status"] == "declined"
        body.update(action="approve", quantity=999999)
        assert c.post("/api/transfers", json=body).status_code == 400     # donor can't give more than it has
        body.update(quantity=500, resource="gold")
        assert c.post("/api/transfers", json=body).status_code == 404


def test_blocked_road_makes_transfer_infeasible():
    with TestClient(app) as c:
        c.post("/api/simulate/reset")
        c.post("/api/simulate/disaster")
        c.post("/api/roads", json={"from_campus_id": B, "to_campus_id": A, "blocked": True})
        assert c.get("/api/recommendations").json()[0]["feasible"] is False
        c.post("/api/simulate/reset")                                     # reset also clears closures
