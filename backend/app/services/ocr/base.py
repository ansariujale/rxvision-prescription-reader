from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


@dataclass
class ExtractedMedicine:
    name: str
    strength: str | None = None
    dose: str | None = None
    frequency: str | None = None
    duration: str | None = None
    timing: str | None = None
    notes: str | None = None
    source_line: str | None = None


@dataclass
class OcrResult:
    text: str
    lines: list[str] = field(default_factory=list)
    # None means a text-only provider; the pipeline then parses lines itself.
    medicines: list[ExtractedMedicine] | None = None
    doctor: str | None = None
    prescribed_on: date | None = None


class ProviderError(Exception):
    """A provider failed in a way worth showing the user."""

    def __init__(self, user_message: str, detail: str | None = None):
        super().__init__(detail or user_message)
        self.user_message = user_message


class OcrProvider(Protocol):
    name: str

    async def read(self, image: bytes, mime: str) -> OcrResult: ...
