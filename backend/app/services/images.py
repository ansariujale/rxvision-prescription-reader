"""Validate and normalise an uploaded prescription photo.

The file is trusted only after Pillow has decoded it. It is then rotated
upright, optionally cropped, downscaled and re-encoded, which also drops EXIF
metadata such as GPS location.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.errors import ApiError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "MPO"}  # MPO: some phone JPEGs
MAX_PIXELS = 40_000_000
MAX_EDGE = 2400
MIN_CROP = 0.05


@dataclass(frozen=True)
class Crop:
    x: float
    y: float
    width: float
    height: float

    def clamped(self) -> "Crop":
        x = min(max(self.x, 0.0), 1.0 - MIN_CROP)
        y = min(max(self.y, 0.0), 1.0 - MIN_CROP)
        w = min(max(self.width, MIN_CROP), 1.0 - x)
        h = min(max(self.height, MIN_CROP), 1.0 - y)
        return Crop(x, y, w, h)


@dataclass(frozen=True)
class NormalisedImage:
    data: bytes
    width: int
    height: int
    mime: str = "image/jpeg"


def normalise(raw: bytes, crop: Crop | None = None) -> NormalisedImage:
    try:
        probe = Image.open(io.BytesIO(raw))
        fmt = probe.format
        if fmt not in ALLOWED_FORMATS:
            raise ApiError(415, "Upload a JPEG, PNG or WebP image")
        if probe.width * probe.height > MAX_PIXELS:
            raise ApiError(413, "That image is too large to process")
        probe.load()
    except ApiError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ApiError(415, "That file is not a readable image")

    img = ImageOps.exif_transpose(probe)

    if crop is not None:
        c = crop.clamped()
        box = (
            round(c.x * img.width),
            round(c.y * img.height),
            round((c.x + c.width) * img.width),
            round((c.y + c.height) * img.height),
        )
        img = img.crop(box)

    if max(img.size) > MAX_EDGE:
        img.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)

    if img.mode != "RGB":
        background = Image.new("RGB", img.size, "white")
        rgba = img.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        img = background

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90, optimize=True)
    return NormalisedImage(out.getvalue(), img.width, img.height)
