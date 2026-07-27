"""Server-side product thumbnail generation.

Product galleries are stored as base64 data-URL images (often large). Lists only
need a small preview, so we derive a compact JPEG `thumb_url` from the primary
image automatically whenever a product is created or its image changes. Managers
never set this directly — it keeps the storefront/product-list API light.
"""
import base64
import io
import re

try:
    from PIL import Image
    _HAS_PIL = True
except Exception:  # Pillow missing (e.g. local dev without it) — degrade gracefully
    _HAS_PIL = False

_DATA_URL_RE = re.compile(r"^data:image/[^;]+;base64,(.+)$", re.DOTALL)


def make_thumb(src, max_size=360, quality=60):
    """Downscale a base64 data-URL image to a small JPEG data URL.

    Non-data-URL sources (remote/file URLs) are already light and returned as-is.
    Any decode/resize failure returns the input unchanged, so a bad image never
    blocks saving a product.
    """
    if not _HAS_PIL or not isinstance(src, str):
        return src
    m = _DATA_URL_RE.match(src.strip())
    if not m:
        return src
    try:
        raw = base64.b64decode(m.group(1))
        img = Image.open(io.BytesIO(raw))
        img = img.convert("RGB")
        img.thumbnail((max_size, max_size))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=quality, optimize=True)
        b64 = base64.b64encode(out.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception:
        return src
