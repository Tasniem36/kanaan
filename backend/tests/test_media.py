"""Image storage + compression.

Every product photo goes through save_image/make_thumb, so a regression here
either bloats the whole storefront or corrupts uploads. No DB involved.
"""
import base64
import io
import os

import pytest
from PIL import Image

import media


@pytest.fixture(autouse=True)
def _isolated_media_dir(tmp_path, monkeypatch):
    """Write into a temp dir instead of the real media volume."""
    monkeypatch.setattr(media, "MEDIA_DIR", str(tmp_path))
    return tmp_path


def _data_url(img, fmt="JPEG", **save):
    buf = io.BytesIO()
    img.save(buf, format=fmt, **save)
    mime = {"JPEG": "jpeg", "PNG": "png", "WEBP": "webp", "GIF": "gif"}[fmt]
    return f"data:image/{mime};base64," + base64.b64encode(buf.getvalue()).decode(), buf.getvalue()


def _photo(w=3000, h=2250):
    """A noisy image — a flat colour would compress so well it proves nothing."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(0, h, 3):
        for x in range(0, w, 3):
            px[x, y] = ((x * 7) % 256, (y * 13) % 256, (x + y) % 256)
    return img


def _stored(url):
    assert url.startswith("/media/"), url
    path = os.path.join(media.MEDIA_DIR, url[len("/media/"):])
    assert os.path.exists(path), f"{url} was not written"
    return path


# --- compression ------------------------------------------------------------
def test_large_upload_is_capped_and_shrunk():
    url, raw = _data_url(_photo(), quality=92)
    out = _stored(media.save_image(url))
    assert os.path.getsize(out) < len(raw) / 2, "a 3000px photo should shrink a lot"
    with Image.open(out) as f:
        assert max(f.size) == media.MAX_DIM, f"long edge should be capped, got {f.size}"
        assert f.format == "WEBP"


def test_small_image_is_not_upscaled():
    url, _ = _data_url(_photo(500, 400), quality=90)
    with Image.open(_stored(media.save_image(url))) as f:
        assert f.size == (500, 400)


def test_already_tiny_file_is_never_made_bigger():
    """Re-encoding can inflate an optimised file — we keep whichever is smaller."""
    _, raw = _data_url(Image.new("RGBA", (8, 8), (0, 0, 0, 0)), fmt="PNG")
    out, ext = media._compress(raw, "png")
    assert len(out) <= len(raw)
    assert (out, ext) == (raw, "png"), "should have kept the original bytes"


def test_exif_rotation_is_baked_in_not_lost():
    """Phone photos carry rotation in EXIF; re-encoding without applying it first
    would silently store every portrait photo sideways."""
    img = Image.new("RGB", (400, 200), (200, 40, 40))
    buf = io.BytesIO()
    exif = img.getexif()
    exif[274] = 6  # orientation: rotate 90° CW
    img.save(buf, format="JPEG", exif=exif)
    url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    with Image.open(_stored(media.save_image(url))) as f:
        assert f.size == (200, 400), "orientation tag should have been applied"


def test_transparency_survives_the_webp_conversion():
    img = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    img.putpixel((10, 10), (255, 0, 0, 255))
    url, _ = _data_url(img, fmt="PNG")
    with Image.open(_stored(media.save_image(url))) as f:
        assert f.mode in ("RGBA", "LA", "P"), f"alpha lost, mode={f.mode}"
        assert f.convert("RGBA").getpixel((0, 0))[3] == 0


# --- formats we must not touch ---------------------------------------------
def test_svg_is_stored_untouched():
    svg = b"<svg xmlns='http://www.w3.org/2000/svg'><circle r='5'/></svg>"
    url = media.save_image("data:image/svg+xml;base64," + base64.b64encode(svg).decode())
    assert url.endswith(".svg")
    with open(_stored(url), "rb") as f:
        assert f.read() == svg, "vector must not be rasterised"


def test_gif_is_stored_untouched():
    """GIF may be animated; re-encoding would flatten it to one frame."""
    _, raw = _data_url(Image.new("P", (20, 20)), fmt="GIF")
    url = media.save_image("data:image/gif;base64," + base64.b64encode(raw).decode())
    assert url.endswith(".gif")


# --- pass-through and failure handling -------------------------------------
@pytest.mark.parametrize("src", [
    "/media/products/existing.webp",   # already stored
    "/images/hero.jpg",                # bundled asset
    "https://example.com/a.jpg",       # external
    None,
    "",
])
def test_non_data_urls_pass_through_unchanged(src):
    assert media.save_image(src) == src


def test_corrupt_upload_is_dropped_not_stored(_isolated_media_dir):
    """Saving a product must never fail because of one bad image — and must not
    write a permanently broken file either, so the upload is dropped."""
    bad = "data:image/jpeg;base64," + base64.b64encode(b"not an image").decode()
    assert media.save_image(bad) is None
    assert not (_isolated_media_dir / "products").exists(), "nothing should be written"


def test_malformed_data_url_is_dropped():
    assert media.save_image("data:image/jpeg;base64") is None


def test_identical_uploads_dedupe_to_one_file(_isolated_media_dir):
    url, _ = _data_url(_photo(300, 300), quality=88)
    a, b = media.save_image(url), media.save_image(url)
    assert a == b, "content-hashed names should collide"
    assert len(list((_isolated_media_dir / "products").iterdir())) == 1


# --- thumbnails -------------------------------------------------------------
def test_thumbnail_is_small_and_bounded():
    url, _ = _data_url(_photo(2000, 1500), quality=90)
    stored = media.save_image(url)
    thumb = media.make_thumb(stored)
    assert thumb != stored, "thumb should be its own file"
    tpath = _stored(thumb)
    with Image.open(tpath) as f:
        assert max(f.size) <= 360
        assert f.format == "WEBP"
    assert os.path.getsize(tpath) < os.path.getsize(_stored(stored))


def test_thumbnail_of_an_external_url_is_left_alone():
    assert media.make_thumb("https://example.com/a.jpg") == "https://example.com/a.jpg"


def test_thumbnail_of_a_missing_file_is_left_alone():
    assert media.make_thumb("/media/products/nope.webp") == "/media/products/nope.webp"
