"""Product image storage.

Uploaded images arrive as base64 data-URLs. We persist them as real files under
MEDIA_DIR (served at /media/...) and derive a compact JPEG thumbnail file, so:
  - pages/DB stay light (no giant base64 blobs), and
  - product images have real URLs usable as og:image for share previews.

Every function degrades gracefully — on any failure it returns the input
unchanged, so saving a product never breaks on a bad image.
"""
import base64
import hashlib
import io
import os
import re

try:
    from PIL import Image
    _HAS_PIL = True
except Exception:  # Pillow missing (local dev) — thumbnails just fall back
    _HAS_PIL = False

MEDIA_DIR = os.getenv("MEDIA_DIR", "/app/media")
_DATA_URL_RE = re.compile(r"^data:image/([a-zA-Z0-9.+-]+);base64,(.+)$", re.DOTALL)
_EXT = {"jpeg": "jpg", "jpg": "jpg", "png": "png", "webp": "webp", "gif": "gif", "svg+xml": "svg"}


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


def save_image(src, subdir="products"):
    """base64 data-URL → saved file, returns its /media URL. Anything already a
    URL/path (existing /media file, preset /images/.., external http) is left as-is."""
    if not is_data_url(src):
        return src
    m = _DATA_URL_RE.match(src.strip())
    if not m:
        return src
    try:
        ext = _EXT.get(m.group(1).lower(), "jpg")
        return _write(base64.b64decode(m.group(2)), subdir, ext)
    except Exception:
        return src


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


def make_thumb(src, max_size=360, quality=60):
    """Small JPEG thumbnail file from the primary image; returns its /media URL.
    External/preset URLs are already light and returned unchanged."""
    if not _HAS_PIL:
        return src
    raw = _source_bytes(src)
    if raw is None:
        return src  # external URL or unreadable — leave it
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        img.thumbnail((max_size, max_size))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=quality, optimize=True)
        return _write(out.getvalue(), "thumbs", "jpg")
    except Exception:
        return src
