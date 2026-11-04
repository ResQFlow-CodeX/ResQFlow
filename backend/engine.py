"""ResQFlow decision engine.

Pure Python: no database, no web framework. It takes plain data in and returns
recommendations with readable reasons. That makes it easy to test and explain.

Core rules (the answers to "how does it decide?"):
  1. hours_to_empty  = stock / consumption rate
  2. a campus NEEDS a resource if it has < 24 h left OR has an open request
  3. transferable surplus = stock - safety reserve - own 24 h consumption
  4. priority score = 60% urgency (time left) + 40% criticality (medicine > water)
  5. donor = campus with enough surplus, then the closest one
  6. a transfer is feasible only if a vehicle is free, the road is open,
     and the delivery arrives before the receiving campus runs out
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field, replace

HORIZON_HOURS = 24          # how far ahead we plan
GREEN_HOURS = 24            # > 24 h left  -> green
AMBER_HOURS = 12            # 12-24 h left -> amber, < 12 h -> red
ROUND_STEP = {"water": 100, "medicine": 10}   # send practical, round quantities
AVG_SPEED_KMH = 30.0        # assumed average speed in disaster conditions
ROAD_FACTOR = 1.3           # straight-line distance -> approximate road distance


# ---------- plain data containers ----------
@dataclass
class Stock:
    campus_id: int
    campus_name: str
    lat: float
    lng: float
    resource: str
    unit: str
    criticality: int
    quantity: float
    safety_reserve: float
    consumption_rate: float      # per hour


@dataclass
class OpenRequest:
    campus_id: int
    resource: str
    quantity: float
    deadline_hours: float


@dataclass
class Vehicle:
    name: str
    campus_id: int
    capacity: float
    available: bool = True


@dataclass
class PendingTransfer:
    """An approved/dispatched transfer that hasn't arrived yet."""
    from_campus_id: int
    to_campus_id: int
    resource: str
    quantity: float
    source_deducted: bool = False


@dataclass
class Need:
    stock: Stock
    quantity: float
    hours_to_empty: float
    effective_hours: float       # time left, considering request deadlines
    score: float


@dataclass
class Recommendation:
    key: str
    resource: str
    unit: str
    quantity: float
    from_campus_id: int
    from_campus_name: str
    from_lat: float
    from_lng: float
    to_campus_id: int
    to_campus_name: str
    to_lat: float
    to_lng: float
    distance_km: float
    eta_minutes: float
    priority_score: float
    feasible: bool
    vehicle: str | None
    reasons: list[str] = field(default_factory=list)


@dataclass
class Redirect:
    accepted_as_intended: bool
    campus_id: int | None
    campus_name: str | None
    message: str


# ---------- basic calculations ----------
def hours_to_empty(quantity: float, rate: float) -> float:
    return math.inf if rate <= 0 else quantity / rate


def status_for(hours: float) -> str:
    if hours < AMBER_HOURS:
        return "red"
    if hours < GREEN_HOURS:
        return "amber"
    return "green"


def transferable_surplus(s: Stock) -> float:
    """What a campus can give away without touching its reserve or its own 24 h need."""
    return max(0.0, s.quantity - s.safety_reserve - s.consumption_rate * HORIZON_HOURS)


def shortfall(s: Stock) -> float:
    """How much is missing to cover 24 h of use plus the safety reserve."""
    return max(0.0, s.consumption_rate * HORIZON_HOURS + s.safety_reserve - s.quantity)


def priority_score(effective_hours: float, criticality: int) -> float:
    urgency = max(0.0, HORIZON_HOURS - effective_hours) / HORIZON_HOURS * 100   # 0-100
    return round(0.6 * urgency + 0.4 * criticality * 20, 1)


def default_travel(a: Stock, b: Stock) -> tuple[float, float]:
    """(distance_km, eta_minutes) from straight-line distance. Routing API replaces this later."""
    r = 6371.0
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp, dl = p2 - p1, math.radians(b.lng - a.lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    km = 2 * r * math.asin(math.sqrt(h)) * ROAD_FACTOR
    return round(km, 1), round(km / AVG_SPEED_KMH * 60, 0)


# ---------- pending transfers ----------
def apply_pending(stocks, requests, pending):
    """Count approved-but-not-yet-received transfers as if they had arrived."""
    stocks = [replace(s) for s in stocks]
    requests = [replace(r) for r in requests]
    for p in pending:
        for s in stocks:
            if s.resource == p.resource and s.campus_id == p.to_campus_id:
                s.quantity += p.quantity
            if s.resource == p.resource and s.campus_id == p.from_campus_id and not p.source_deducted:
                s.quantity -= p.quantity
        left = p.quantity
        for r in requests:
            if r.campus_id == p.to_campus_id and r.resource == p.resource and left > 0:
                used = min(r.quantity, left)
                r.quantity -= used
                left -= used
    return stocks, [r for r in requests if r.quantity > 0]


# ---------- needs ----------
def find_needs(stocks, requests) -> list[Need]:
    needs = []
    for s in stocks:
        h = hours_to_empty(s.quantity, s.consumption_rate)
        reqs = [r for r in requests if r.campus_id == s.campus_id and r.resource == s.resource]
        if h >= HORIZON_HOURS and not reqs:
            continue
        qty = max(shortfall(s), sum(r.quantity for r in reqs))
        eff = min([h] + [r.deadline_hours for r in reqs])
        needs.append(Need(s, qty, h, eff, priority_score(eff, s.criticality)))
    return sorted(needs, key=lambda n: -n.score)


# ---------- vehicles ----------
def best_vehicle(vehicles, donor_campus_id):
    free = [v for v in vehicles if v.available]
    if not free:
        return None
    at_donor = [v for v in free if v.campus_id == donor_campus_id]
    return max(at_donor or free, key=lambda v: v.capacity)


# ---------- the "why" text ----------
def build_reasons(need: Need, donor: Stock, qty, km, eta, vehicle, blocked, in_time, has_request):
    s, unit, res = need.stock, need.stock.unit, need.stock.resource
    out = []
    if need.hours_to_empty < HORIZON_HOURS:
        out.append(f"{s.campus_name} {res} is projected to last about {need.hours_to_empty:.0f} hours.")
    if has_request:
        out.append(f"{s.campus_name} has an open {res} request needed within {need.effective_hours:.0f} hours.")
    if s.criticality >= 5:
        out.append(f"{res.capitalize()} is a critical supply, so it is ranked higher.")
    out.append(f"{donor.campus_name} can supply {qty:,.0f} {unit} while keeping its "
               f"{donor.safety_reserve:,.0f} {unit} safety reserve and its own 24-hour need.")
    if blocked:
        out.append("The road between these campuses is reported blocked.")
    elif vehicle is None:
        out.append("No vehicle is currently available.")
    elif not in_time:
        out.append(f"Delivery (ETA {eta:.0f} min) would arrive too late.")
    else:
        out.append(f"Road reported open; {vehicle.name} ({vehicle.capacity:,.0f} capacity) available; "
                   f"{km:.1f} km, ETA {eta:.0f} min.")
    return out


# ---------- main entry: recommendations ----------
def recommend(stocks, requests, vehicles, pending=(), blocked_roads=(), travel_fn=default_travel):
    stocks, requests = apply_pending(stocks, requests, pending)
    needs = find_needs(stocks, requests)
    surplus = {(s.campus_id, s.resource): transferable_surplus(s) for s in stocks}
    blocked_set = {frozenset(p) for p in blocked_roads}
    recs = []

    for need in needs:
        res, to = need.stock.resource, need.stock
        has_request = any(r.campus_id == to.campus_id and r.resource == res for r in requests)
        options = []
        for d in stocks:
            if d.resource != res or d.campus_id == to.campus_id:
                continue
            avail = surplus[(d.campus_id, res)]
            if avail > 0:
                km, eta = travel_fn(d, to)
                options.append((d, avail, km, eta))
        if not options:
            continue
        # prefer the donor that covers most of the need, then the closest one
        options.sort(key=lambda o: (-min(o[1], need.quantity), o[3]))
        donor, avail, km, eta = options[0]

        vehicle = best_vehicle(vehicles, donor.campus_id)
        qty = min(need.quantity, avail)
        if vehicle:
            qty = min(qty, vehicle.capacity)
        step = ROUND_STEP.get(res, 1)
        rounded = math.floor(qty / step) * step
        qty = rounded if rounded > 0 else qty
        if qty <= 0:
            continue

        blocked = frozenset((donor.campus_id, to.campus_id)) in blocked_set
        in_time = eta / 60 < need.effective_hours
        feasible = vehicle is not None and not blocked and in_time
        surplus[(donor.campus_id, res)] -= qty

        recs.append(Recommendation(
            key=f"{res}:{donor.campus_id}->{to.campus_id}", resource=res, unit=to.unit, quantity=qty,
            from_campus_id=donor.campus_id, from_campus_name=donor.campus_name,
            from_lat=donor.lat, from_lng=donor.lng,
            to_campus_id=to.campus_id, to_campus_name=to.campus_name, to_lat=to.lat, to_lng=to.lng,
            distance_km=km, eta_minutes=eta, priority_score=need.score, feasible=feasible,
            vehicle=vehicle.name if vehicle else None,
            reasons=build_reasons(need, donor, qty, km, eta, vehicle, blocked, in_time, has_request)))
    return sorted(recs, key=lambda r: -r.priority_score)


# ---------- donor redirect ----------
def redirect_donation(stocks, requests, resource, intended_campus_id, pending=()):
    stocks, requests = apply_pending(stocks, requests, pending)
    needs = [n for n in find_needs(stocks, requests) if n.stock.resource == resource]
    by_id = {s.campus_id: s for s in stocks if s.resource == resource}
    intended = by_id.get(intended_campus_id)

    if intended_campus_id in {n.stock.campus_id for n in needs}:
        return Redirect(True, intended.campus_id, intended.campus_name,
                        f"{intended.campus_name} still needs {resource}. Donation accepted as intended.")
    if needs:
        t = needs[0].stock
        why = f"{intended.campus_name}'s {resource} need is already covered. " if intended else ""
        return Redirect(False, t.campus_id, t.campus_name,
                        f"{why}{t.campus_name} still needs {resource} (about {needs[0].hours_to_empty:.0f} hours left).")
    others = [s for c, s in by_id.items() if c != intended_campus_id]
    if not others:
        return Redirect(False, None, None, f"No campus currently needs {resource}. Consider holding the donation.")
    low = min(others, key=lambda s: hours_to_empty(s.quantity, s.consumption_rate))
    h = hours_to_empty(low.quantity, low.consumption_rate)
    why = f"{intended.campus_name}'s {resource} is already covered. " if intended else ""
    return Redirect(False, low.campus_id, low.campus_name,
                    f"{why}No campus is in shortage; {low.campus_name} has the lowest cover ({h:.0f} hours).")
