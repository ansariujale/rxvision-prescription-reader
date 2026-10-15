from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

ItemStatusLiteral = Literal["suggested", "confirmed", "edited", "manual"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# -- auth ------------------------------------------------------------------

class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name is required")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class PasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class DeleteAccountIn(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class UserOut(ORM):
    id: uuid.UUID
    email: str
    name: str
    created_at: datetime


# -- medicines -------------------------------------------------------------

class MedicineBrief(ORM):
    id: int
    name: str
    manufacturer: str | None = None
    composition: str | None = None


class MedicineOut(MedicineBrief):
    type: str | None = None
    pack_size: str | None = None
    price: Decimal | None = None
    uses: str | None = None


class MedicineHit(BaseModel):
    id: int
    name: str
    score: float


# -- scans -----------------------------------------------------------------

class ItemOut(ORM):
    id: uuid.UUID
    position: int
    name: str
    medicine: MedicineBrief | None
    strength: str | None
    dose: str | None
    frequency: str | None
    duration: str | None
    timing: str | None
    notes: str | None
    confidence: float | None
    source_line: str | None
    status: ItemStatusLiteral


def _short():
    return Field(default=None, max_length=60)


class ItemFields(BaseModel):
    strength: str | None = _short()
    dose: str | None = _short()
    frequency: str | None = _short()
    duration: str | None = _short()
    timing: str | None = _short()
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("strength", "dose", "frequency", "duration", "timing", "notes")
    @classmethod
    def _blank_is_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class ItemCreate(ItemFields):
    name: str | None = Field(default=None, max_length=300)
    medicine_id: int | None = None


class ItemUpdate(ItemFields):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    medicine_id: int | None = None
    status: Literal["suggested", "confirmed", "edited"] | None = None


class ScanSummary(ORM):
    id: uuid.UUID
    title: str
    status: str
    provider: str
    prescribed_on: date | None
    doctor: str | None
    in_routine: bool
    created_at: datetime
    item_count: int
    preview: list[str]


class ScanOut(ORM):
    id: uuid.UUID
    title: str
    status: str
    provider: str
    created_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    error: str | None
    raw_text: str | None
    prescribed_on: date | None
    doctor: str | None
    in_routine: bool
    image_width: int
    image_height: int
    image_url: str
    items: list[ItemOut]


class ScanAccepted(BaseModel):
    id: uuid.UUID
    status: str


class ScanUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    prescribed_on: date | None = None
    doctor: str | None = Field(default=None, max_length=160)
    in_routine: bool | None = None


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class CropIn(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)


# -- system ----------------------------------------------------------------

class ProvidersOut(BaseModel):
    active: str
    configured: dict[str, bool]


class StatsOut(BaseModel):
    scans: int
    medicines_found: int
    confirmed: int
    needs_review: int
    catalogue_size: int


# -- routine ---------------------------------------------------------------

SlotLiteral = Literal["morning", "afternoon", "evening", "night", "as_needed"]


class RoutineEntryOut(BaseModel):
    item_id: uuid.UUID
    scan_id: uuid.UUID
    scan_title: str
    name: str
    medicine_id: int | None
    strength: str | None
    dose: str | None
    frequency: str | None
    timing: str | None
    notes: str | None
    slot: SlotLiteral
    quantity: str | None
    taken: bool
    day_of_course: int
    total_days: int
    ends_on: date
    flags: list[str]


class RoutineSlotOut(BaseModel):
    slot: SlotLiteral
    entries: list[RoutineEntryOut]


class DayCount(BaseModel):
    day: date
    total: int
    taken: int


class RoutineOut(BaseModel):
    day: date
    slots: list[RoutineSlotOut]
    as_needed: list[RoutineEntryOut]
    ending_soon: list[RoutineEntryOut]
    taken: int
    total: int
    week: list[DayCount]
    prescriptions: int


class DoseIn(BaseModel):
    item_id: uuid.UUID
    day: date
    slot: SlotLiteral
    taken: bool


# -- my medicines ----------------------------------------------------------

class MedicineUse(BaseModel):
    scan_id: uuid.UUID
    scan_title: str
    prescribed_on: date
    item_id: uuid.UUID
    strength: str | None
    dose: str | None
    frequency: str | None
    duration: str | None
    timing: str | None
    in_routine: bool


class MyMedicineOut(BaseModel):
    key: str
    name: str
    medicine: MedicineBrief | None
    times: int
    last_prescribed: date
    active: bool
    uses: list[MedicineUse]


class AlternativeOut(MedicineBrief):
    price: Decimal | None = None
    pack_size: str | None = None
