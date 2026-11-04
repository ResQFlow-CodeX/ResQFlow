"""ResQFlow v6.1 regression tests: capacity, targeted disasters and transfer accounting."""
import os
os.environ["RESQFLOW_OFFLINE"] = "1"
from fastapi.testclient import TestClient
from main import app


def stock(c, campus_id, resource="water"):
    campus = next(x for x in c.get("/api/campuses").json() if x["id"] == campus_id)
    return next(x for x in campus["stocks"] if x["resource"] == resource)


def test_disaster_is_campus_scoped_and_supports_types():
    with TestClient(app) as c:
        c.post("/api/simulate/reset")
        before_b = stock(c, 2)["consumption_rate"]
        r = c.post("/api/simulate/disaster", json={"campus_id": 1, "disaster_type": "earthquake"})
        assert r.status_code == 200
        assert stock(c, 1)["consumption_rate"] == 44
        assert stock(c, 2)["consumption_rate"] == before_b
        assert next(x for x in c.get("/api/campuses").json() if x["id"] == 1)["disaster_type"] == "earthquake"
        c.post("/api/simulate/disaster", json={"campus_id": 2, "disaster_type": "drought"})
        assert stock(c, 2)["consumption_rate"] == 400
        assert stock(c, 1)["consumption_rate"] == 44
        c.post("/api/simulate/reset")
        assert stock(c, 1)["consumption_rate"] == 22
        assert all(x["disaster_type"] is None for x in c.get("/api/campuses").json())


def test_capacity_enforced_for_inventory_and_donation_credits_stock():
    with TestClient(app) as c:
        c.post("/api/simulate/reset")
        assert stock(c, 1)["quantity"] <= stock(c, 1)["storage_capacity"]
        too_much = c.post("/api/inventory", json={"campus_id": 1, "resource": "water", "quantity": 3001})
        assert too_much.status_code == 400
        # Flood makes Campus A a legitimate recipient; donation is credited immediately.
        c.post("/api/simulate/disaster", json={"campus_id": 1, "disaster_type": "flood"})
        before = stock(c, 1)["quantity"]
        result = c.post("/api/donations", json={"donor_name": "Test donor", "resource": "water",
                                                "quantity": 100, "intended_campus_id": 1})
        assert result.status_code == 200
        assert stock(c, 1)["quantity"] == before + 100
        assert stock(c, 1)["quantity"] <= stock(c, 1)["storage_capacity"]
        # Over-capacity offers are rejected without changing stock.
        free = stock(c, 1)["storage_capacity"] - stock(c, 1)["quantity"]
        too_large = c.post("/api/donations", json={"donor_name": "Test donor", "resource": "water",
                                                    "quantity": free + 1, "intended_campus_id": 1})
        assert too_large.status_code in (400, 409)


def test_transfer_debits_once_on_dispatch_and_credits_once_on_receive():
    with TestClient(app) as c:
        c.post("/api/simulate/reset")
        c.post("/api/simulate/disaster")
        rec = c.get("/api/recommendations").json()[0]
        t = c.post("/api/transfers", json={"from_campus_id": 2, "to_campus_id": 1,
                    "resource": "water", "quantity": rec["quantity"]})
        assert t.status_code == 200
        before_src, before_dst = stock(c, 2)["quantity"], stock(c, 1)["quantity"]
        dispatched = c.post(f"/api/transfers/{t.json()['id']}/advance").json()
        assert dispatched["status"] == "dispatched" and dispatched["dispatched_at"]
        assert stock(c, 2)["quantity"] == before_src - rec["quantity"]
        assert stock(c, 1)["quantity"] == before_dst
        received = c.post(f"/api/transfers/{t.json()['id']}/advance").json()
        assert received["status"] == "received" and received["received_at"]
        assert stock(c, 2)["quantity"] == before_src - rec["quantity"]
        assert stock(c, 1)["quantity"] == before_dst + rec["quantity"]
        assert c.post(f"/api/transfers/{t.json()['id']}/advance").status_code == 400
        c.post("/api/simulate/reset")


def test_transfer_capacity_and_duplicate_reservation_validation():
    with TestClient(app) as c:
        c.post("/api/simulate/reset")
        # A's water has 2340 L free; a larger incoming transfer is rejected.
        bad = c.post("/api/transfers", json={"from_campus_id": 2, "to_campus_id": 1,
                    "resource": "water", "quantity": 2400})
        assert bad.status_code == 400
        # A transfer can reserve donor inventory; a second reservation cannot oversubscribe it.
        first = c.post("/api/transfers", json={"from_campus_id": 2, "to_campus_id": 1,
                    "resource": "water", "quantity": 2000})
        assert first.status_code == 200
        second = c.post("/api/transfers", json={"from_campus_id": 2, "to_campus_id": 3,
                    "resource": "water", "quantity": 4500})
        assert second.status_code == 400
        c.post("/api/simulate/reset")


def test_approved_transfer_exposes_estimated_arrival_and_route_method():
    with TestClient(app) as c:
        c.post("/api/simulate/reset")
        created = c.post("/api/transfers", json={
            "from_campus_id": 2, "to_campus_id": 1, "resource": "water", "quantity": 100
        })
        assert created.status_code == 200
        transfer = created.json()
        assert transfer["distance_km"] > 0
        assert transfer["eta_minutes"] >= 0
        assert transfer["estimated_arrival_at"]
        assert transfer["route_source"] in ("osrm", "estimate")
        assert transfer["route"]
        c.post("/api/simulate/reset")


def test_simulated_consumption_decreases_stock_without_going_negative():
    with TestClient(app) as c:
        c.post("/api/simulate/reset")
        before = stock(c, 1)["quantity"]
        result = c.post("/api/inventory/consume", json={"campus_id": 1, "resource": "water", "hours": 2})
        assert result.status_code == 200
        assert result.json()["consumed"] == 44
        assert stock(c, 1)["quantity"] == before - 44
        empty = c.post("/api/inventory/consume", json={"campus_id": 1, "resource": "water", "hours": 168})
        assert empty.status_code == 200
        assert stock(c, 1)["quantity"] == 0
        assert empty.json()["depleted"] is True
        c.post("/api/simulate/reset")
