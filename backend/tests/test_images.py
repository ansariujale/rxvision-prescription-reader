import io

import pytest
from PIL import Image

from app.core.errors import ApiError
from app.services.images import Crop, normalise
from tests.conftest import jpeg_bytes


def test_crop_uses_fractions():
    out = normalise(jpeg_bytes(1000, 500), Crop(0.5, 0.0, 0.5, 0.5))
    assert (out.width, out.height) == (500, 250)


def test_crop_is_clamped():
    out = normalise(jpeg_bytes(1000, 1000), Crop(0.9, 0.9, 0.5, 0.5))
    assert out.width == 100 and out.height == 100


def test_large_images_are_downscaled():
    out = normalise(jpeg_bytes(4800, 2400))
    assert max(out.width, out.height) == 2400


def test_png_with_alpha_becomes_jpeg():
    buf = io.BytesIO()
    Image.new("RGBA", (50, 40), (0, 0, 0, 0)).save(buf, format="PNG")
    out = normalise(buf.getvalue())
    assert Image.open(io.BytesIO(out.data)).format == "JPEG"


def test_exif_is_stripped_and_rotation_applied():
    img = Image.new("RGB", (300, 100), "white")
    exif = Image.Exif()
    exif[0x0112] = 6  # orientation: rotate 90 when displayed
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    out = normalise(buf.getvalue())
    assert (out.width, out.height) == (100, 300)
    assert not Image.open(io.BytesIO(out.data)).getexif()


def test_non_image_rejected():
    with pytest.raises(ApiError) as e:
        normalise(b"definitely not an image")
    assert e.value.status == 415


def test_gif_rejected():
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="GIF")
    with pytest.raises(ApiError) as e:
        normalise(buf.getvalue())
    assert e.value.status == 415
