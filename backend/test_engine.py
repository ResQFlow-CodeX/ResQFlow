"""Run with:  pytest -v   (from the backend folder)"""
from dataclasses import replace
import engine as e

A, B, C = 1, 2, 3


def make_stocks(a_water_rate=22):
    def s(cid, name, lat, lng, res, unit, crit, qty, reserve, rate):
        return e.Stock(cid, name, lat, lng, res, unit, crit, qty, reserve, rate)
    return [
        s(A, "Campus A", 12.9386, 77.7220, "water", "L", 3, 660, 200, a_water_rate),
        s(B, "Campus B", 12.9719, 77.6412, "water", "L", 3, 5900, 1500, 100),
        s(C, "Campus C", 12.9141, 77.6101, "water", "L", 3, 2500, 500, 80),
        s(A, "Campus A", 12.9386, 77.7220, "medicine", "units", 5, 200, 40, 2),
        s(B, "Campus B", 12.9719, 77.6412, "medicine", "units", 5, 300, 60, 2),
        s(C, "Campus C", 12.9141, 77.6101, "medicine", "units", 5, 40, 20, 1),
    ]


VEHICLES = [e.Vehicle("Tanker 1", B, 3000), e.Vehicle("Van 1", B, 500), e.Vehicle("Van 2", C, 400)]
DISASTER = make_stocks(a_water_rate=110)   # Campus A water use x5


def test_hours_and_status():
    assert e.hours_to_empty(660, 110) == 6
    assert e.status_for(6) == "red" and e.status_for(15) == "amber" and e.status_for(30) == "green"
    assert e.hours_to_empty(100, 0) == float("inf")


def test_surplus_keeps_safety_reserve():
    b_water = make_stocks()[1]
    assert e.transferable_surplus(b_water) == 5900 - 1500 - 100 * 24   # 2000


def test_healthy_network_has_no_recommendations():
    assert e.recommend(make_stocks(), [], VEHICLES) == []


def test_water_disaster_scenario_sends_2000L_from_B_to_A():
    recs = e.recommend(DISASTER, [], VEHICLES)
    assert len(recs) == 1
    r = recs[0]
    assert (r.from_campus_name, r.to_campus_name, r.resource) == ("Campus B", "Campus A", "water")
    assert r.quantity == 2000 and r.feasible
    assert any("6 hours" in line for line in r.reasons)
    assert any("safety reserve" in line for line in r.reasons)


def test_donor_is_never_pushed_below_reserve():
    r = e.recommend(DISASTER, [], VEHICLES)[0]
    donor = make_stocks()[1]
    left = donor.quantity - r.quantity
    assert left >= donor.safety_reserve + donor.consumption_rate * 24   # reserve + own 24 h need intact


def test_urgent_medicine_request_ranks_first():
    reqs = [e.OpenRequest(C, "medicine", 30, 4)]
    recs = e.recommend(DISASTER, reqs, VEHICLES)
    assert [r.resource for r in recs] == ["medicine", "water"]
    assert recs[0].to_campus_name == "Campus C" and recs[0].quantity == 30
    assert recs[0].priority_score > recs[1].priority_score
    assert any("critical supply" in line for line in recs[0].reasons)


def test_blocked_road_or_no_vehicle_is_not_feasible():
    blocked = e.recommend(DISASTER, [], VEHICLES, blocked_roads=[(B, A)])[0]
    assert not blocked.feasible and any("blocked" in l for l in blocked.reasons)
    no_veh = e.recommend(DISASTER, [], [replace(v, available=False) for v in VEHICLES])[0]
    assert not no_veh.feasible


def test_pending_transfer_stops_duplicate_recommendation():
    pending = [e.PendingTransfer(B, A, "water", 2000)]
    assert e.recommend(DISASTER, [], VEHICLES, pending=pending) == []


def test_donor_redirect_after_need_is_covered():
    pending = [e.PendingTransfer(B, A, "water", 2000)]
    out = e.redirect_donation(DISASTER, [], "water", A, pending)
    assert not out.accepted_as_intended and out.campus_name == "Campus C"
    assert "already covered" in out.message


def test_donor_accepted_when_still_needed():
    out = e.redirect_donation(DISASTER, [], "water", A)
    assert out.accepted_as_intended
