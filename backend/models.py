from datetime import datetime, timezone
from sqlalchemy import ForeignKey, String, Float, Integer, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Campus(Base):
    __tablename__ = "campuses"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    disaster_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    inventory: Mapped[list["Inventory"]] = relationship(back_populates="campus")


class Resource(Base):
    __tablename__ = "resources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)   # "water", "medicine"
    unit: Mapped[str] = mapped_column(String(10))                # "L", "units"
    criticality: Mapped[int] = mapped_column(Integer)            # 1-5, used in priority score


class Inventory(Base):
    """Stock of one resource at one campus."""
    __tablename__ = "inventory"
    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int] = mapped_column(ForeignKey("campuses.id"))
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))
    quantity: Mapped[float] = mapped_column(Float)
    storage_capacity: Mapped[float | None] = mapped_column(Float, nullable=True)
    safety_reserve: Mapped[float] = mapped_column(Float)
    base_consumption_rate: Mapped[float] = mapped_column(Float)  # per hour, normal times
    consumption_rate: Mapped[float] = mapped_column(Float)       # per hour, current (changes in disaster)
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    campus: Mapped[Campus] = relationship(back_populates="inventory")
    resource: Mapped[Resource] = relationship()


class Request(Base):
    __tablename__ = "requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int] = mapped_column(ForeignKey("campuses.id"))
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))
    quantity: Mapped[float] = mapped_column(Float)
    deadline_hours: Mapped[float] = mapped_column(Float)         # needed within N hours
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | fulfilled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    campus: Mapped[Campus] = relationship()
    resource: Mapped[Resource] = relationship()


class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    campus_id: Mapped[int] = mapped_column(ForeignKey("campuses.id"))  # home base
    capacity: Mapped[float] = mapped_column(Float)               # in litres-equivalent
    available: Mapped[bool] = mapped_column(default=True)


class Donation(Base):
    __tablename__ = "donations"
    id: Mapped[int] = mapped_column(primary_key=True)
    donor_name: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))
    quantity: Mapped[float] = mapped_column(Float)
    intended_campus_id: Mapped[int | None] = mapped_column(ForeignKey("campuses.id"), nullable=True)
    redirected_campus_id: Mapped[int | None] = mapped_column(ForeignKey("campuses.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Transfer(Base):
    __tablename__ = "transfers"
    id: Mapped[int] = mapped_column(primary_key=True)
    from_campus_id: Mapped[int] = mapped_column(ForeignKey("campuses.id"))
    to_campus_id: Mapped[int] = mapped_column(ForeignKey("campuses.id"))
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))
    quantity: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="suggested")
    # suggested -> approved -> dispatched -> received   (or declined)
    reasons: Mapped[str] = mapped_column(Text)                   # the "why" text, stored as JSON list
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    eta_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DecisionLog(Base):
    """Audit trail: every coordinator action with its reason (promised in the deck)."""
    __tablename__ = "decision_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    transfer_id: Mapped[int] = mapped_column(ForeignKey("transfers.id"))
    action: Mapped[str] = mapped_column(String(20))              # approve | modify | decline | dispatch | receive
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
