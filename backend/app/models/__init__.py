import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    scans: Mapped[list["Scan"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class Medicine(Base):
    __tablename__ = "medicines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(200))
    type: Mapped[str | None] = mapped_column(String(50))
    pack_size: Mapped[str | None] = mapped_column(String(120))
    composition: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    uses: Mapped[str | None] = mapped_column(Text)


class ScanStatus:
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    PENDING = (QUEUED, PROCESSING)


class ItemStatus:
    SUGGESTED = "suggested"
    CONFIRMED = "confirmed"
    EDITED = "edited"
    MANUAL = "manual"
    ALL = (SUGGESTED, CONFIRMED, EDITED, MANUAL)


class Scan(Base):
    __tablename__ = "scans"
    __table_args__ = (Index("ix_scans_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(16), default=ScanStatus.QUEUED)
    provider: Mapped[str] = mapped_column(String(20))
    image_key: Mapped[str] = mapped_column(String(80))
    image_width: Mapped[int] = mapped_column(Integer)
    image_height: Mapped[int] = mapped_column(Integer)
    raw_text: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    prescribed_on: Mapped[date | None] = mapped_column(Date)
    doctor: Mapped[str | None] = mapped_column(String(160))
    in_routine: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="scans")
    items: Mapped[list["ScanItem"]] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ScanItem.position",
    )


class ScanItem(Base):
    __tablename__ = "scan_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(300))
    medicine_id: Mapped[int | None] = mapped_column(
        ForeignKey("medicines.id", ondelete="SET NULL")
    )
    strength: Mapped[str | None] = mapped_column(String(60))
    dose: Mapped[str | None] = mapped_column(String(60))
    frequency: Mapped[str | None] = mapped_column(String(60))
    duration: Mapped[str | None] = mapped_column(String(60))
    timing: Mapped[str | None] = mapped_column(String(60))
    notes: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    source_line: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=ItemStatus.SUGGESTED)

    scan: Mapped[Scan] = relationship(back_populates="items")
    medicine: Mapped[Medicine | None] = relationship(lazy="joined")


class Slot:
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"
    AS_NEEDED = "as_needed"
    ALL = (MORNING, AFTERNOON, EVENING, NIGHT, AS_NEEDED)


class DoseLog(Base):
    """A dose the user ticked off. Absence means not taken."""

    __tablename__ = "dose_logs"
    __table_args__ = (UniqueConstraint("item_id", "day", "slot", name="uq_dose_logs_item_day_slot"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scan_items.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[date] = mapped_column(Date)
    slot: Mapped[str] = mapped_column(String(12))
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
