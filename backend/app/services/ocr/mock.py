from __future__ import annotations

import asyncio

from app.services.ocr.base import OcrResult

SAMPLE = """Dr. A. Mehta, MBBS MD
City Care Clinic, 14 Park Road
Rx
1. Tab Augmentin 625 Duo 1-0-1 x 5 days after food
2. Tab Pan 40 1-0-0 before breakfast x 7 days
3. Tab Dolo 650 SOS for fever
4. Syp Ascoril LS 10 ml TDS x 5d
5. Cap Becosules 1-0-0 x 1 month
Review after 1 week"""


class MockProvider:
    """Offline stand-in. Returns the same realistic prescription for any image.

    Lets the whole app be exercised with no API keys. The UI labels results from
    this provider so they are never mistaken for a real reading.
    """

    name = "mock"

    def __init__(self, delay: float = 1.2):
        self.delay = delay

    async def read(self, image: bytes, mime: str) -> OcrResult:
        await asyncio.sleep(self.delay)
        lines = SAMPLE.splitlines()
        return OcrResult(text=SAMPLE, lines=lines, medicines=None, doctor="Dr. A. Mehta")
