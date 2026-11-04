"""Reset the DB to the demo starting state. Run: python seed.py
Numbers are tuned so the demo works:
  - Normal: every campus has 30+ hours of water.
  - After 'simulate disaster' (Campus A water consumption x5 = 110 L/h): A has 6 hours.
  - Campus B surplus = 5900 - 1500 reserve - (100/h * 24h horizon) = 2000 L  ->  can send 2,000 L.
"""
from datetime import datetime, timedelta, timezone
from database import Base, engine, SessionLocal
import models as m


def reset():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()

    water = m.Resource(name="water", unit="L", criticality=3)
    medicine = m.Resource(name="medicine", unit="units", criticality=5)
    a = m.Campus(name="Campus A", lat=12.9386, lng=77.7220)
    b = m.Campus(name="Campus B", lat=12.9719, lng=77.6412)
    c = m.Campus(name="Campus C", lat=12.9141, lng=77.6101)
    db.add_all([water, medicine, a, b, c])
    db.flush()

    exp = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=90)
    rows = [
        # campus, resource, qty, reserve, rate
        (a, water, 660, 200, 22, 3000),
        (b, water, 5900, 1500, 100, 7000),
        (c, water, 2500, 500, 80, 3500),
        (a, medicine, 200, 40, 2, None),
        (b, medicine, 300, 60, 2, None),
        (c, medicine, 40, 20, 1, None),
    ]
    for campus, res, qty, reserve, rate, capacity in rows:
        db.add(m.Inventory(campus_id=campus.id, resource_id=res.id, quantity=qty, storage_capacity=capacity,
                           safety_reserve=reserve, base_consumption_rate=rate,
                           consumption_rate=rate, expiry_date=exp))

    db.add_all([
        m.Vehicle(name="Tanker 1", campus_id=b.id, capacity=3000, available=True),
        m.Vehicle(name="Van 1", campus_id=b.id, capacity=500, available=True),
        m.Vehicle(name="Van 2", campus_id=c.id, capacity=400, available=True),
    ])
    db.commit()
    db.close()
    print("Demo data reset: 3 campuses, water + medicine, 3 vehicles.")


if __name__ == "__main__":
    reset()
