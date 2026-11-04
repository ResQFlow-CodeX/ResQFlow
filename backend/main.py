"""ResQFlow API. Run: uvicorn main:app --reload   then open http://127.0.0.1:8000/docs"""
import json
import re
from datetime import timedelta
from contextlib import asynccontextmanager
from dataclasses import asdict
from types import SimpleNamespace
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import engine as eng
import routing
import models as m
import seed
from database import Base, SessionLocal, engine as db_engine, get_db

BLOCKED_ROADS: set[tuple[int, int]] = set()      # reported road closures (in memory)


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(db_engine)
    # Lightweight additive migration for existing v6 SQLite databases.
    if db_engine.dialect.name == "sqlite":
        with db_engine.begin() as conn:
            for table, column, ddl in [
                ("campuses", "disaster_type", "ALTER TABLE campuses ADD COLUMN disaster_type VARCHAR(20)"),
                ("inventory", "storage_capacity", "ALTER TABLE inventory ADD COLUMN storage_capacity FLOAT"),
                ("transfers", "dispatched_at", "ALTER TABLE transfers ADD COLUMN dispatched_at DATETIME"),
                ("transfers", "received_at", "ALTER TABLE transfers ADD COLUMN received_at DATETIME"),
            ]:
                columns = [row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")]
                if column not in columns:
                    conn.exec_driver_sql(ddl)
            # v6 had no capacity column. Give legacy water records headroom for
            # their existing stock plus a standard demo transfer buffer.
            conn.exec_driver_sql("""
                UPDATE inventory
                SET storage_capacity = quantity + CASE WHEN quantity > 2000 THEN quantity ELSE 2000 END
                WHERE storage_capacity IS NULL
                  AND resource_id IN (SELECT id FROM resources WHERE name = 'water')
            """)
    with SessionLocal() as db:
        empty = db.query(m.Campus).count() == 0
    if empty:
        seed.reset()
    yield


app = FastAPI(title="ResQFlow API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
api = APIRouter(prefix="/api")


# ---------- helpers: database rows -> engine inputs ----------
def load_stocks(db: Session):
    return [eng.Stock(i.campus.id, i.campus.name, i.campus.lat, i.campus.lng, i.resource.name,
                      i.resource.unit, i.resource.criticality, i.quantity, i.safety_reserve,
                      i.consumption_rate) for i in db.query(m.Inventory).all()]


def load_requests(db: Session):
    rows = db.query(m.Request).filter(m.Request.status == "open").all()
    return [eng.OpenRequest(r.campus_id, r.resource.name, r.quantity, r.deadline_hours) for r in rows]


def load_vehicles(db: Session):
    return [eng.Vehicle(v.name, v.campus_id, v.capacity, v.available) for v in db.query(m.Vehicle).all()]


def load_pending(db: Session):
    names = {r.id: r.name for r in db.query(m.Resource).all()}
    rows = db.query(m.Transfer).filter(m.Transfer.status.in_(["approved", "dispatched"])).all()
    return [eng.PendingTransfer(t.from_campus_id, t.to_campus_id, names[t.resource_id], t.quantity, t.status == "dispatched") for t in rows]


def get_resource(db: Session, name: str) -> m.Resource:
    r = db.query(m.Resource).filter_by(name=name).first()
    if not r:
        raise HTTPException(404, f"Unknown resource '{name}'")
    return r


def get_campus(db: Session, cid: int) -> m.Campus:
    c = db.get(m.Campus, cid)
    if not c:
        raise HTTPException(404, f"Unknown campus id {cid}")
    return c


def route_fields(a_lat, a_lng, b_lat, b_lng) -> dict:
    info = routing.get_route(a_lat, a_lng, b_lat, b_lng)
    return {"route": info["geometry"], "route_source": info["source"]}


def transfer_out(db: Session, t: m.Transfer) -> dict:
    res = db.get(m.Resource, t.resource_id)
    src, dst = db.get(m.Campus, t.from_campus_id), db.get(m.Campus, t.to_campus_id)
    live = t.status != "declined"          # retain route geometry for transfer history and tracking
    route = route_fields(src.lat, src.lng, dst.lat, dst.lng) if live else {"route": [], "route_source": None}
    return {"id": t.id, "status": t.status,
            "from_campus_id": src.id, "from_campus": src.name, "to_campus_id": dst.id, "to_campus": dst.name,
            "resource": res.name, "unit": res.unit, "quantity": t.quantity,
            "reasons": json.loads(t.reasons), "distance_km": t.distance_km,
            "eta_minutes": t.eta_minutes, "estimated_arrival_at": ((t.dispatched_at or t.created_at) + timedelta(minutes=t.eta_minutes)).isoformat() if t.eta_minutes is not None and t.status in ("approved", "dispatched", "received") else None, "created_at": t.created_at.isoformat(), "dispatched_at": t.dispatched_at.isoformat() if t.dispatched_at else None, "received_at": t.received_at.isoformat() if t.received_at else None, **route}


def log(db: Session, transfer_id: int, action: str, note: str | None = None):
    db.add(m.DecisionLog(transfer_id=transfer_id, action=action, note=note))


# ---------- read endpoints ----------
@api.get("/campuses")
def campuses(db: Session = Depends(get_db)):
    out = []
    for c in db.query(m.Campus).order_by(m.Campus.id).all():
        stocks = []
        for i in c.inventory:
            h = eng.hours_to_empty(i.quantity, i.consumption_rate)
            h = 999.0 if h == float("inf") else round(h, 1)
            exp = None if i.expiry_date is None else (i.expiry_date - m.utcnow()).days
            stocks.append({"resource": i.resource.name, "unit": i.resource.unit, "quantity": i.quantity, "storage_capacity": i.storage_capacity,
                           "safety_reserve": i.safety_reserve, "consumption_rate": i.consumption_rate,
                           "hours_to_empty": h, "status": eng.status_for(h), "expiry_days": exp})
        out.append({"id": c.id, "name": c.name, "lat": c.lat, "lng": c.lng, "disaster_type": c.disaster_type, "stocks": stocks})
    return out


@api.get("/recommendations")
def recommendations(db: Session = Depends(get_db)):
    recs = eng.recommend(load_stocks(db), load_requests(db), load_vehicles(db),
                         pending=load_pending(db), blocked_roads=BLOCKED_ROADS, travel_fn=routing.travel)
    return [{"key": r.key, "priority_score": r.priority_score, "resource": r.resource, "unit": r.unit,
             "quantity": r.quantity,
             "from_campus": {"id": r.from_campus_id, "name": r.from_campus_name, "lat": r.from_lat, "lng": r.from_lng},
             "to_campus": {"id": r.to_campus_id, "name": r.to_campus_name, "lat": r.to_lat, "lng": r.to_lng},
             "distance_km": r.distance_km, "eta_minutes": r.eta_minutes,
             **route_fields(r.from_lat, r.from_lng, r.to_lat, r.to_lng),
             "feasible": r.feasible, "vehicle": r.vehicle, "reasons": r.reasons} for r in recs]


@api.get("/transfers")
def list_transfers(db: Session = Depends(get_db)):
    rows = db.query(m.Transfer).order_by(m.Transfer.id.desc()).all()
    return [transfer_out(db, t) for t in rows]


@api.get("/requests")
def list_requests(db: Session = Depends(get_db)):
    rows = db.query(m.Request).filter(m.Request.status == "open").order_by(m.Request.id.desc()).all()
    return [{"id": r.id, "campus_id": r.campus_id, "campus": r.campus.name, "resource": r.resource.name,
             "unit": r.resource.unit, "quantity": r.quantity, "deadline_hours": r.deadline_hours} for r in rows]


@api.get("/log")
def decision_log(db: Session = Depends(get_db)):
    out = []
    for e in db.query(m.DecisionLog).order_by(m.DecisionLog.id.desc()).all():
        t = transfer_out(db, db.get(m.Transfer, e.transfer_id))
        out.append({"transfer_id": e.transfer_id, "action": e.action, "note": e.note,
                    "summary": f"{t['quantity']:,.0f} {t['unit']} {t['resource']}: {t['from_campus']} -> {t['to_campus']}",
                    "created_at": e.created_at.isoformat()})
    return out


# ---------- coordinator actions ----------
class TransferIn(BaseModel):
    from_campus_id: int
    to_campus_id: int
    resource: str
    quantity: float = Field(gt=0)
    reasons: list[str] = Field(default_factory=list)
    action: Literal["approve", "modify", "decline"] = "approve"   # modify = approve with an edited quantity
    note: str | None = None


@api.post("/transfers")
def create_transfer(body: TransferIn, db: Session = Depends(get_db)):
    if body.from_campus_id == body.to_campus_id:
        raise HTTPException(400, "Source and destination must be different campuses")
    src, dst, res = get_campus(db, body.from_campus_id), get_campus(db, body.to_campus_id), get_resource(db, body.resource)
    donor = db.query(m.Inventory).filter_by(campus_id=src.id, resource_id=res.id).first()
    if body.action == "decline":
        km, eta = routing.travel(src, dst)
        t = m.Transfer(from_campus_id=src.id, to_campus_id=dst.id, resource_id=res.id, quantity=body.quantity,
                       status="declined", reasons=json.dumps(body.reasons), distance_km=km, eta_minutes=eta)
        db.add(t)
        db.flush()
        log(db, t.id, "decline", body.note)
        db.commit()
        return transfer_out(db, t)
    if not donor or body.quantity > donor.quantity:
        raise HTTPException(400, f"{src.name} does not have {body.quantity:,.0f} {res.unit} of {res.name}")
    receiver = db.query(m.Inventory).filter_by(campus_id=dst.id, resource_id=res.id).first()
    if not receiver:
        raise HTTPException(400, f"{dst.name} does not track {res.name}")
    if receiver.storage_capacity is not None:
        already_inbound = sum(x.quantity for x in db.query(m.Transfer).filter(
            m.Transfer.to_campus_id == dst.id, m.Transfer.resource_id == res.id,
            m.Transfer.status.in_(["approved", "dispatched"])).all())
        if receiver.quantity + already_inbound + body.quantity > receiver.storage_capacity:
            raise HTTPException(400, f"{dst.name} has insufficient storage capacity; available space is {max(0, receiver.storage_capacity - receiver.quantity - already_inbound):,.0f} {res.unit}")
    reserved_out = sum(x.quantity for x in db.query(m.Transfer).filter(
        m.Transfer.from_campus_id == src.id, m.Transfer.resource_id == res.id,
        m.Transfer.status == "approved").all())
    if body.quantity + reserved_out > donor.quantity:
        raise HTTPException(400, f"{src.name} has only {max(0, donor.quantity-reserved_out):,.0f} {res.unit} unreserved")
    km, eta = routing.travel(src, dst)
    if not (km > 0 and eta >= 0):
        raise HTTPException(502, "Routing service returned an invalid route estimate")
    status = "declined" if body.action == "decline" else "approved"
    t = m.Transfer(from_campus_id=src.id, to_campus_id=dst.id, resource_id=res.id, quantity=body.quantity,
                   status=status, reasons=json.dumps(body.reasons), distance_km=km, eta_minutes=eta)
    db.add(t)
    db.flush()
    log(db, t.id, body.action, body.note)
    db.commit()
    return transfer_out(db, t)


@api.post("/transfers/{transfer_id}/advance")
def advance_transfer(transfer_id: int, db: Session = Depends(get_db)):
    try:
        t = db.query(m.Transfer).filter(m.Transfer.id == transfer_id).with_for_update().first()
        if not t:
            raise HTTPException(404, "Transfer not found")
        if t.status == "approved":
            src_inv = db.query(m.Inventory).filter_by(campus_id=t.from_campus_id, resource_id=t.resource_id).with_for_update().one()
            reserved_other = sum(x.quantity for x in db.query(m.Transfer).filter(
                m.Transfer.from_campus_id == t.from_campus_id, m.Transfer.resource_id == t.resource_id,
                m.Transfer.id != t.id, m.Transfer.status == "approved").all())
            if src_inv.quantity - reserved_other < t.quantity:
                raise HTTPException(409, "Donor stock is no longer sufficient")
            src_inv.quantity -= t.quantity
            t.status = "dispatched"
            t.dispatched_at = m.utcnow()
            log(db, t.id, "dispatch")
        elif t.status == "dispatched":
            dst_inv = db.query(m.Inventory).filter_by(campus_id=t.to_campus_id, resource_id=t.resource_id).with_for_update().one()
            if dst_inv.storage_capacity is not None and dst_inv.quantity + t.quantity > dst_inv.storage_capacity:
                raise HTTPException(409, "Receiving campus no longer has enough storage capacity")
            dst_inv.quantity += t.quantity
            t.status = "received"
            t.received_at = m.utcnow()
            left = t.quantity
            open_reqs = (db.query(m.Request).filter_by(campus_id=t.to_campus_id, resource_id=t.resource_id, status="open")
                         .order_by(m.Request.id).all())
            for r in open_reqs:
                used = min(r.quantity, left)
                r.quantity -= used
                left -= used
                if r.quantity <= 0:
                    r.status = "fulfilled"
            log(db, t.id, "receive")
        else:
            raise HTTPException(400, f"Cannot advance a transfer that is '{t.status}'")
        db.commit()
        return transfer_out(db, t)
    except Exception:
        db.rollback()
        raise


class RequestIn(BaseModel):
    campus_id: int
    resource: str
    quantity: float = Field(gt=0)
    deadline_hours: float = Field(gt=0)


@api.post("/requests")
def create_request(body: RequestIn, db: Session = Depends(get_db)):
    c, res = get_campus(db, body.campus_id), get_resource(db, body.resource)
    r = m.Request(campus_id=c.id, resource_id=res.id, quantity=body.quantity, deadline_hours=body.deadline_hours)
    db.add(r)
    db.commit()
    return {"id": r.id, "campus_id": c.id, "campus": c.name, "resource": res.name, "unit": res.unit,
            "quantity": r.quantity, "deadline_hours": r.deadline_hours, "status": r.status}


class DonationIn(BaseModel):
    donor_name: str
    resource: str
    quantity: float = Field(gt=0)
    intended_campus_id: int | None = None


@api.post("/donations")
def create_donation(body: DonationIn, db: Session = Depends(get_db)):
    if not body.donor_name.strip():
        raise HTTPException(400, "Donor name is required")
    try:
        res = get_resource(db, body.resource)
        out = eng.redirect_donation(load_stocks(db), load_requests(db), body.resource,
                                    body.intended_campus_id, pending=load_pending(db))
        if out.campus_id is None:
            raise HTTPException(409, out.message)
        campus = get_campus(db, out.campus_id)
        inv = db.query(m.Inventory).filter_by(campus_id=campus.id, resource_id=res.id).with_for_update().first()
        if not inv:
            raise HTTPException(400, f"{campus.name} does not track {res.name}")
        accepted_qty = body.quantity
        if inv.storage_capacity is not None:
            inbound_reserved = sum(x.quantity for x in db.query(m.Transfer).filter(
                m.Transfer.to_campus_id == campus.id, m.Transfer.resource_id == res.id,
                m.Transfer.status.in_(["approved", "dispatched"])).all())
            free = max(0.0, inv.storage_capacity - inv.quantity - inbound_reserved)
            if accepted_qty > free:
                raise HTTPException(400, f"{campus.name} can accept only {free:,.0f} {res.unit}; offered {accepted_qty:,.0f}")
        inv.quantity += accepted_qty
        db.add(m.Donation(donor_name=body.donor_name.strip(), resource_id=res.id, quantity=accepted_qty,
                          intended_campus_id=body.intended_campus_id, redirected_campus_id=out.campus_id))
        db.commit()
        return {"accepted_as_intended": out.accepted_as_intended,
                "redirected_campus": {"id": out.campus_id, "name": out.campus_name},
                "quantity_accepted": accepted_qty, "message": out.message}
    except Exception:
        db.rollback()
        raise


class RoadIn(BaseModel):
    from_campus_id: int
    to_campus_id: int
    blocked: bool = True


@api.post("/roads")
def report_road(body: RoadIn):
    pair = tuple(sorted((body.from_campus_id, body.to_campus_id)))
    BLOCKED_ROADS.discard(pair) if not body.blocked else BLOCKED_ROADS.add(pair)
    return {"ok": True, "blocked_roads": [list(p) for p in BLOCKED_ROADS]}


# ---------- demo controls ----------
class DisasterIn(BaseModel):
    campus_id: int
    disaster_type: Literal["flood", "earthquake", "cyclone", "drought"]


DISASTER_MULTIPLIERS = {"flood": 5.0, "earthquake": 2.0, "cyclone": 2.5, "drought": 4.0}


@api.post("/simulate/disaster")
def simulate_disaster(body: DisasterIn | None = None, db: Session = Depends(get_db)):
    # Legacy no-body calls retain the original Campus A flood demo behaviour.
    body = body or DisasterIn(campus_id=1, disaster_type="flood")
    c = get_campus(db, body.campus_id)
    c.disaster_type = body.disaster_type
    multiplier = DISASTER_MULTIPLIERS[body.disaster_type]
    # Only water demand is impacted by this demo's disaster model.
    for inv in db.query(m.Inventory).filter_by(campus_id=c.id).all():
        inv.consumption_rate = inv.base_consumption_rate * (multiplier if inv.resource.name == "water" else 1.0)
    db.commit()
    return {"ok": True, "campus_id": c.id, "campus": c.name, "disaster_type": body.disaster_type,
            "consumption_multiplier": multiplier}


@api.post("/simulate/reset")
def simulate_reset():
    BLOCKED_ROADS.clear()
    routing.reset()
    seed.reset()
    return {"ok": True}


# ---------- capture: stock updates, vehicles, SMS fallback ----------
class InventoryIn(BaseModel):
    campus_id: int
    resource: str
    quantity: float | None = Field(default=None, ge=0)
    consumption_rate: float | None = Field(default=None, ge=0)
    safety_reserve: float | None = Field(default=None, ge=0)
    expiry_days: int | None = Field(default=None, ge=0)


def update_inventory(db: Session, campus_id, resource, quantity=None, consumption_rate=None,
                     safety_reserve=None, expiry_days=None):
    c, res = get_campus(db, campus_id), get_resource(db, resource)
    inv = db.query(m.Inventory).filter_by(campus_id=c.id, resource_id=res.id).first()
    if not inv:
        raise HTTPException(404, f"{c.name} does not track {res.name}")
    if all(v is None for v in (quantity, consumption_rate, safety_reserve, expiry_days)):
        raise HTTPException(400, "Enter at least one value to update")
    if quantity is not None:
        inbound_reserved = sum(x.quantity for x in db.query(m.Transfer).filter(
            m.Transfer.to_campus_id == c.id, m.Transfer.resource_id == res.id,
            m.Transfer.status.in_(["approved", "dispatched"])).all())
        outbound_reserved = sum(x.quantity for x in db.query(m.Transfer).filter(
            m.Transfer.from_campus_id == c.id, m.Transfer.resource_id == res.id,
            m.Transfer.status == "approved").all())
        if quantity < outbound_reserved:
            raise HTTPException(400, f"Stock cannot be set below {outbound_reserved:,.0f} {res.unit} already reserved for approved transfers")
        if inv.storage_capacity is not None and quantity + inbound_reserved > inv.storage_capacity:
            raise HTTPException(400, f"Stock plus inbound transfers cannot exceed storage capacity ({inv.storage_capacity:,.0f} {res.unit})")
        inv.quantity = quantity
    if consumption_rate is not None:
        inv.consumption_rate = inv.base_consumption_rate = consumption_rate
    if safety_reserve is not None:
        inv.safety_reserve = safety_reserve
    if expiry_days is not None:
        inv.expiry_date = m.utcnow() + timedelta(days=expiry_days)
    db.commit()
    h = eng.hours_to_empty(inv.quantity, inv.consumption_rate)
    return {"campus": c.name, "resource": res.name, "unit": res.unit, "quantity": inv.quantity,
            "hours_to_empty": 999.0 if h == float("inf") else round(h, 1)}


@api.post("/inventory")
def post_inventory(body: InventoryIn, db: Session = Depends(get_db)):
    return update_inventory(db, **body.model_dump())


class ConsumeIn(BaseModel):
    campus_id: int
    resource: str = "water"
    hours: float = Field(gt=0, le=168)


@api.post("/inventory/consume")
def consume_inventory(body: ConsumeIn, db: Session = Depends(get_db)):
    """Instantly simulate a period of consumption; stock is clamped at zero."""
    campus, resource = get_campus(db, body.campus_id), get_resource(db, body.resource)
    inv = db.query(m.Inventory).filter_by(campus_id=campus.id, resource_id=resource.id).with_for_update().first()
    if not inv:
        raise HTTPException(404, f"{campus.name} does not track {resource.name}")
    requested = inv.consumption_rate * body.hours
    consumed = min(inv.quantity, requested)
    inv.quantity = max(0.0, inv.quantity - consumed)
    db.commit()
    return {"campus": campus.name, "resource": resource.name, "unit": resource.unit,
            "hours_simulated": body.hours, "consumed": round(consumed, 2),
            "quantity": round(inv.quantity, 2), "depleted": inv.quantity <= 0}


SMS_PATTERN = re.compile(r"^\s*(?:campus\s+)?([a-z])\s+(water|medicine)\s+(\d+(?:\.\d+)?)\s*$", re.I)


class SmsIn(BaseModel):
    text: str


@api.post("/sms")
def receive_sms(body: SmsIn, db: Session = Depends(get_db)):
    """SMS fallback (mock): a text like 'A water 500' sets Campus A's water stock to 500."""
    hit = SMS_PATTERN.match(body.text)
    if not hit:
        raise HTTPException(400, "Could not read that text. Use the format: A water 500")
    campus = db.query(m.Campus).filter_by(name=f"Campus {hit.group(1).upper()}").first()
    if not campus:
        raise HTTPException(404, f"No campus '{hit.group(1).upper()}'")
    out = update_inventory(db, campus.id, hit.group(2).lower(), quantity=float(hit.group(3)))
    return {"ok": True, "message": f"{out['campus']} {out['resource']} stock set to {out['quantity']:,.0f} {out['unit']}. "
                                   f"About {out['hours_to_empty']} hours of cover."}


class AvailabilityIn(BaseModel):
    available: bool


@api.get("/vehicles")
def list_vehicles(db: Session = Depends(get_db)):
    return [{"id": v.id, "name": v.name, "campus_id": v.campus_id, "campus": db.get(m.Campus, v.campus_id).name,
             "capacity": v.capacity, "available": v.available} for v in db.query(m.Vehicle).order_by(m.Vehicle.id)]


@api.post("/vehicles/{vehicle_id}/availability")
def set_vehicle(vehicle_id: int, body: AvailabilityIn, db: Session = Depends(get_db)):
    v = db.get(m.Vehicle, vehicle_id)
    if not v:
        raise HTTPException(404, "Vehicle not found")
    v.available = body.available
    db.commit()
    return {"id": v.id, "name": v.name, "available": v.available}


@api.get("/roads")
def list_roads():
    return {"blocked_roads": [list(p) for p in sorted(BLOCKED_ROADS)]}


@api.get("/donations")
def list_donations(db: Session = Depends(get_db)):
    def name(cid):
        return db.get(m.Campus, cid).name if cid else None
    out = []
    for d in db.query(m.Donation).order_by(m.Donation.id.desc()).all():
        out.append({"id": d.id, "donor_name": d.donor_name, "resource": db.get(m.Resource, d.resource_id).name,
                    "quantity": d.quantity, "intended_campus": name(d.intended_campus_id),
                    "redirected_campus": name(d.redirected_campus_id),
                    "redirected": bool(d.redirected_campus_id and d.redirected_campus_id != d.intended_campus_id),
                    "created_at": d.created_at.isoformat()})
    return out


# ---------- insights: impact summary and stock forecast ----------
@api.get("/impact")
def impact(db: Session = Depends(get_db)):
    names = {r.id: r.name for r in db.query(m.Resource).all()}
    totals: dict[str, float] = {}
    received = db.query(m.Transfer).filter_by(status="received").all()
    for t in received:
        totals[names[t.resource_id]] = totals.get(names[t.resource_id], 0) + t.quantity
    donations = db.query(m.Donation).all()
    return {"water_redirected_l": totals.get("water", 0), "medicine_redirected_units": totals.get("medicine", 0),
            "transfers_completed": len(received),
            "transfers_in_progress": db.query(m.Transfer).filter(m.Transfer.status.in_(["approved", "dispatched"])).count(),
            "transfers_declined": db.query(m.Transfer).filter_by(status="declined").count(),
            "donations_total": len(donations),
            "requests_fulfilled": db.query(m.Request).filter_by(status="fulfilled").count(),
            "donations_redirected": sum(1 for d in donations if d.redirected_campus_id and d.redirected_campus_id != d.intended_campus_id),
            "decisions_logged": db.query(m.DecisionLog).count()}


@api.get("/forecast")
def forecast(hours: int = Query(24, ge=1, le=72), db: Session = Depends(get_db)):
    """Projected stock hour by hour at the current consumption rate (simple, explainable)."""
    series = []
    for i in db.query(m.Inventory).order_by(m.Inventory.campus_id, m.Inventory.resource_id).all():
        h = eng.hours_to_empty(i.quantity, i.consumption_rate)
        series.append({"campus_id": i.campus_id, "campus": i.campus.name, "resource": i.resource.name,
                       "unit": i.resource.unit, "safety_reserve": i.safety_reserve,
                       "runs_out_in": round(h, 1) if h <= hours else None,
                       "values": [round(max(0.0, i.quantity - i.consumption_rate * t), 1) for t in range(hours + 1)]})
    return {"hours": list(range(hours + 1)), "series": series}


@app.get("/")
def home():
    return {"app": "ResQFlow API", "docs": "/docs"}


app.include_router(api)
