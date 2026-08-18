"""General shop reviews (not per-product).

Reading is open to everyone; writing needs an account, so every review is tied to a
real customer. One review per account — re-submitting edits theirs rather than adding
a second, and sends it back through moderation.

Nothing reaches the storefront until a manager approves it, so neither the text nor
an attached photo can reach shoppers on its own.
"""
import re
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response

from audit import log_action
from db import fetch_all, fetch_one
from media import is_data_url, make_thumb, save_image
from notifications import notify_managers, notify_users
from ratelimit import rate_limit
from security import current_user, require_manager

router = APIRouter()

BODY_MAX = 600
BODY_MIN = 3
CITY_MAX = 60
# A 1400px WebP from the browser lands well under this; the cap is here so a
# hand-rolled request can't stream megabytes into the JSON body.
IMAGE_MAX_CHARS = 8 * 1024 * 1024
STATUSES = ("pending", "approved", "rejected")

# What the storefront card needs — never the reviewer's id or email. `author` is
# null when the account has no name; the frontend shows its own placeholder so the
# wording follows the reader's language.
_PUBLIC_COLS = ("r.id, r.rating, r.body, r.city, r.image_url, r.thumb_url, r.created_at, "
                "nullif(btrim(u.full_name), '') as author")
# What the customer sees of their own review (status included — it may be pending)
_OWN_COLS = "id, rating, body, city, image_url, thumb_url, status, created_at"


def _as_uuid(rid: str) -> str:
    """Reject a malformed id here so it 404s instead of blowing up in Postgres."""
    try:
        return str(uuid.UUID(rid))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(404, "Review not found")


def _clean(payload: dict):
    """Validate and normalize a submitted review, or raise 400."""
    try:
        # via float so a JSON 5.0 is accepted; str() first so None/objects raise
        # ValueError here rather than TypeError
        rating = int(float(str(payload.get("rating")).strip()))
    except ValueError:
        raise HTTPException(400, "Rating must be a whole number from 1 to 5")
    if not 1 <= rating <= 5:
        raise HTTPException(400, "Rating must be a whole number from 1 to 5")

    # keep paragraph breaks, but a wall of blank lines can't stretch the card
    body = re.sub(r"\n{3,}", "\n\n", str(payload.get("body") or "").strip())
    if len(body) < BODY_MIN:
        raise HTTPException(400, "Please write your review")
    if len(body) > BODY_MAX:
        raise HTTPException(400, f"Reviews are limited to {BODY_MAX} characters")

    city = str(payload.get("city") or "").strip()[:CITY_MAX] or None
    return rating, body, city


def _clean_image(src):
    """The reviewer's optional photo, as an uploaded data-URL.

    Only a data-URL is accepted: a plain URL would let a review point at any remote
    image, which the shop can neither vouch for nor keep alive. Returns
    (image_url, thumb_url), or (None, None) for no photo — which is also how an
    existing photo is removed, since submitting replaces the whole review.
    """
    if not src:
        return None, None
    if not is_data_url(src):
        raise HTTPException(400, "Unsupported image")
    if len(src) > IMAGE_MAX_CHARS:
        raise HTTPException(400, "That image is too large")
    stored = save_image(src, subdir="reviews")
    if not stored or is_data_url(stored):
        # media.py hands back its input when it can't decode the bytes, and a base64
        # blob must never end up in the row
        raise HTTPException(400, "Could not read that image")
    return stored, make_thumb(stored)



# GET /api/reviews — public: the approved reviews the storefront shows. Best-rated
# first (newest breaking ties), so the default page is the three best ones; every
# page shares that order, which keeps offset paging stable as "show all" walks it.
@router.get("")
def list_reviews(limit: int = Query(3, ge=1, le=50), offset: int = Query(0, ge=0)):
    # count(*)/avg() as window functions ride along on the same scan — they're
    # applied before LIMIT, so they describe every approved review, not just this
    # page. One round-trip for the page, the total and the average rating.
    rows = fetch_all(
        f"""select {_PUBLIC_COLS},
                   count(*) over ()::int as total_count,
                   round(avg(r.rating) over (), 1)::float as avg_rating
              from reviews r join users u on u.id = r.user_id
             where r.status = 'approved'
             order by r.rating desc, r.created_at desc
             limit %s offset %s""",
        [limit, offset],
    )
    total = rows[0]["total_count"] if rows else 0
    average = rows[0]["avg_rating"] if rows else None
    for r in rows:
        del r["total_count"], r["avg_rating"]
    return {"reviews": rows, "total": total, "average": average}


# GET /api/reviews/mine — the caller's own review, whatever its status
@router.get("/mine")
def my_review(user=Depends(current_user)):
    return {"review": fetch_one(f"select {_OWN_COLS} from reviews where user_id = %s", [user["id"]])}


# POST /api/reviews — write (or rewrite) the caller's review; always back to pending
@router.post("")
def submit_review(request: Request, response: Response, user=Depends(current_user), payload: dict = Body(default={})):
    rate_limit(request, bucket="review", limit=6, window=60)
    rating, body, city = _clean(payload)
    image_url, thumb_url = _clean_image(payload.get("image"))
    row = fetch_one(
        f"""insert into reviews (user_id, rating, body, city, image_url, thumb_url)
                 values (%s, %s, %s, %s, %s, %s)
            on conflict (user_id) do update
               set rating = excluded.rating, body = excluded.body, city = excluded.city,
                   image_url = excluded.image_url, thumb_url = excluded.thumb_url,
                   status = 'pending', updated_at = now()
            returning {_OWN_COLS}""",
        [user["id"], rating, body, city, image_url, thumb_url],
    )
    log_action(user_id=user["id"], action="review_submitted",
               detail={"rating": rating, "photo": bool(image_url)}, request=request)
    notify_managers(type="new_review", title="تقييمٌ جديد بانتظار المراجعة",
                    body=f"{'★' * rating} {body[:80]}")
    response.status_code = 201
    return {"review": row}


# DELETE /api/reviews/{rid} — the author removes their own; a manager removes any
@router.delete("/{rid}")
def delete_review(rid: str, request: Request, response: Response, user=Depends(current_user)):
    rid = _as_uuid(rid)
    if user.get("role") == "manager":
        row = fetch_one("delete from reviews where id = %s returning id", [rid])
    else:
        row = fetch_one("delete from reviews where id = %s and user_id = %s returning id", [rid, user["id"]])
    if not row:
        raise HTTPException(404, "Review not found")
    log_action(user_id=user["id"], action="review_deleted", detail={"id": rid}, request=request)
    response.status_code = 204
    return None


# --- moderation (managers only) ----------------------------------------------

# GET /api/reviews/pending-count — just the badge number, cheap enough to poll
@router.get("/pending-count")
def pending_count(_m=Depends(require_manager)):
    row = fetch_one("select count(*)::int as n from reviews where status = 'pending'")
    return {"pending": (row or {}).get("n", 0)}


# GET /api/reviews/all?status=pending — the moderation queue
@router.get("/all")
def list_all(_m=Depends(require_manager), status: str = "",
             limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    where, params = "", []
    if status in STATUSES:
        where = "where r.status = %s"
        params.append(status)
    rows = fetch_all(
        f"""select {_PUBLIC_COLS}, r.status, r.updated_at, u.email as author_email,
                   count(*) over ()::int as total_count
              from reviews r join users u on u.id = r.user_id
              {where}
             order by (r.status = 'pending') desc, r.created_at desc
             limit %s offset %s""",
        params + [limit, offset],
    )
    total = rows[0]["total_count"] if rows else 0
    for r in rows:
        del r["total_count"]
    return {"reviews": rows, "total": total}


# PATCH /api/reviews/{rid} — approve or reject
@router.patch("/{rid}")
def set_status(rid: str, request: Request, m=Depends(require_manager), payload: dict = Body(default={})):
    rid = _as_uuid(rid)
    status = str((payload or {}).get("status") or "")
    if status not in STATUSES:
        raise HTTPException(400, "Unknown status")
    row = fetch_one(
        f"update reviews set status = %s, updated_at = now() where id = %s returning {_OWN_COLS}, user_id",
        [status, rid],
    )
    if not row:
        raise HTTPException(404, "Review not found")
    log_action(user_id=m["id"], action=f"review_{status}", detail={"id": rid}, request=request)
    # Tell the customer their review went live. A rejection stays silent — no value
    # in a "we turned yours down" notification.
    if status == "approved":
        notify_users([row["user_id"]], type="review_status", title="تمّ نشر تقييمك — شكرًا لك!",
                     body=row["body"][:80])
    del row["user_id"]
    return {"review": row}
