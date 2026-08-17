"""Product image storage.

Uploaded images arrive as base64 data-URLs. We persist them as real files under
MEDIA_DIR (served at /media/...) and derive a compact thumbnail file, so:
  - pages/DB stay light (no giant base64 blobs), and
  - product images have real URLs usable as og:image for share previews.

Uploads are re-encoded to WebP and capped at MAX_DIM on the long edge before
being written. A 4 MB phone photo typically lands around 150–300 KB with no
visible loss, which is the single biggest factor in how fast product pages feel.

Every function degrades gracefully — on any failure it returns the input
unchanged, so saving a product never breaks on a bad image.
"""
import base64
import hashlib
import io
import os
import re

try:
    from PIL import Image, ImageOps
    _HAS_PIL = True
except Exception:  # Pillow missing (local dev) — images are stored as uploaded
    _HAS_PIL = False

MEDIA_DIR = os.getenv("MEDIA_DIR", "/app/media")
_DATA_URL_RE = re.compile(r"^data:image/([a-zA-Z0-9.+-]+);base64,(.+)$", re.DOTALL)
_EXT = {"jpeg": "jpg", "jpg": "jpg", "png": "png", "webp": "webp", "gif": "gif", "svg+xml": "svg"}

# Long-edge cap for a stored product photo. The detail page shows it in a square
# well under 800 CSS px, so 1600 still covers retina zoom with room to spare.
MAX_DIM = 1600
FULL_QUALITY = 82   # WebP quality for the full-size image (visually lossless here)
# Formats we never re-encode: vector stays vector, and GIF may be animated.
_KEEP_AS_IS = ("svg", "gif")


def is_data_url(s):
    return isinstance(s, str) and s.startswith("data:")


def _write(raw, subdir, ext):
    # content-hashed name → dedupes identical uploads and lets us cache forever
    name = hashlib.sha1(raw).hexdigest()[:16] + "." + ext
    d = os.path.join(MEDIA_DIR, subdir)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, name)
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(raw)
    return f"/media/{subdir}/{name}"


def _open(raw):
    """Decode bytes to an upright RGB/RGBA image. Phone photos carry their
    rotation in EXIF, which would otherwise render sideways once re-encoded."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
    keep_alpha = img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)
    return img.convert("RGBA" if keep_alpha else "RGB")


def _compress(raw, ext):
    """Cap the dimensions and re-encode as WebP. Returns (bytes, ext).

    Keeps the original whenever re-encoding wouldn't actually help — an already
    optimised small image can come out *larger*, and there's no point paying
    quality for that."""
    if not _HAS_PIL or ext in _KEEP_AS_IS:
        return raw, ext
    try:
        img = _open(raw)
        if max(img.size) > MAX_DIM:
            img.thumbnail((MAX_DIM, MAX_DIM), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="WEBP", quality=FULL_QUALITY, method=6)
        data = out.getvalue()
        return (data, "webp") if len(data) < len(raw) else (raw, ext)
    except Exception:
        return raw, ext


def _is_decodable(raw):
    """True if Pillow recognises these bytes as an image."""
    if not _HAS_PIL:
        return True   # can't tell — assume the client sent something sane
    try:
        Image.open(io.BytesIO(raw)).verify()
        return True
    except Exception:
        return False


def save_image(src, subdir="products"):
    """base64 data-URL → compressed file, returns its /media URL. Anything already
    a URL/path (existing /media file, preset /images/.., external http) is left as-is.

    Returns None when the payload isn't a usable image. Writing undecodable bytes
    would leave the product pointing at a permanently broken file, and echoing the
    data-URL back would park a multi-megabyte blob in the database — so a bad
    upload is dropped and the product simply has no photo. Callers filter None.
    """
    if not is_data_url(src):
        return src
    m = _DATA_URL_RE.match(src.strip())
    if not m:
        return None
    try:
        ext = _EXT.get(m.group(1).lower(), "jpg")
        raw = base64.b64decode(m.group(2))
        # SVG is text, so Pillow can't vet it; raster formats must decode.
        if ext != "svg" and not _is_decodable(raw):
            return None
        raw, ext = _compress(raw, ext)
        return _write(raw, subdir, ext)
    except Exception:
        return None


def _source_bytes(src):
    """Raw bytes for a primary image given a data-URL or a stored /media path."""
    if is_data_url(src):
        m = _DATA_URL_RE.match(src.strip())
        return base64.b64decode(m.group(2)) if m else None
    if isinstance(src, str) and src.startswith("/media/"):
        path = os.path.join(MEDIA_DIR, src[len("/media/"):])
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
    return None


def make_thumb(src, max_size=360, quality=62):
    """Small WebP thumbnail file from the primary image; returns its /media URL.
    This is what product lists load, so it stays as small as it can while still
    looking sharp on a retina card. External/preset URLs come back unchanged."""
    if not _HAS_PIL:
        return src
    raw = _source_bytes(src)
    if raw is None:
        return src  # external URL or unreadable — leave it
    try:
        img = _open(raw)
        img.thumbnail((max_size, max_size), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="WEBP", quality=quality, method=6)
        return _write(out.getvalue(), "thumbs", "webp")
    except Exception:
        return src
