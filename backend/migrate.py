"""Apply db/schema.sql + db/seed.sql, and optionally seed the first manager
from SEED_MANAGER_EMAIL / SEED_MANAGER_PASSWORD. Run: python migrate.py"""
import os
import secrets

from dotenv import load_dotenv

load_dotenv()

from psycopg.types.json import Json

from db import pool
from security import hash_password
from media import save_image, make_thumb, is_data_url
from routers.orders import new_ref


def _run_file(conn, path):
    with open(path, encoding="utf-8") as f:
        conn.execute(f.read())
    print(f"✓ applied {path}")


def _backfill_media(conn):
    """One-time: move products whose images are still inline base64 to files, and
    (re)generate a thumbnail file. Idempotent — products already on /media URLs
    are skipped. Preserves the image data (writes the file before updating the row)."""
    rows = conn.execute("select id, image_url, images, thumb_url from products").fetchall()
    done = 0
    for row in rows:
        old_images = row["images"] if isinstance(row["images"], list) else []
        images = [u for u in (save_image(i) for i in old_images) if u]
        image_url = save_image(row["image_url"]) or (images[0] if images else None)
        thumb = row["thumb_url"]
        # Thumbnails created before the WebP switch are still JPEG, and they're what
        # every product list loads — so regenerate them once and the existing
        # catalogue gets the same size win as new uploads. A thumbnail is derived
        # data, so rebuilding it is safe; the original photo is never touched.
        # Idempotent: a .webp thumb is skipped, and the local-path check keeps
        # external/preset URLs from being retried on every deploy.
        stale_format = bool(thumb) and not thumb.endswith(".webp") and str(image_url or "").startswith("/media/")
        if not thumb or is_data_url(thumb) or stale_format:
            thumb = make_thumb(image_url)
        if images != old_images or image_url != row["image_url"] or thumb != row["thumb_url"]:
            conn.execute(
                "update products set images = %s, image_url = %s, thumb_url = %s where id = %s",
                [Json(images), image_url, thumb, row["id"]],
            )
            done += 1
    if done:
        print(f"✓ migrated {done} product image(s) to files")


def _backfill_order_tracking(conn):
    """Orders placed before the tracking link existed have no number and no token, so
    their customers couldn't use the order lookup. Give every one of them both.
    Idempotent: rows that already have them are skipped."""
    rows = conn.execute("select id, ref, track_token from orders "
                        "where ref is null or track_token is null").fetchall()
    if not rows:
        return
    taken = {r["ref"] for r in conn.execute("select ref from orders where ref is not null").fetchall()}
    for row in rows:
        ref = row["ref"]
        if not ref:
            ref = new_ref(lambda candidate: candidate in taken)
            taken.add(ref)
        conn.execute(
            "update orders set ref = %s, track_token = coalesce(track_token, %s) where id = %s",
            [ref, secrets.token_urlsafe(16), row["id"]],
        )
    print(f"✓ numbered {len(rows)} existing order(s) for tracking")


def main():
    with pool.connection() as conn:
        _run_file(conn, "db/schema.sql")
        _run_file(conn, "db/seed.sql")
        _backfill_media(conn)
        _backfill_order_tracking(conn)
        email = os.getenv("SEED_MANAGER_EMAIL")
        password = os.getenv("SEED_MANAGER_PASSWORD")
        if email and password:
            conn.execute(
                """insert into users (email, password_hash, full_name, role)
                   values (%s, %s, 'المدير', 'manager')
                   on conflict (email) do update set role = 'manager', password_hash = excluded.password_hash""",
                [email.lower().strip(), hash_password(password)],
            )
            print(f"✓ manager account ready: {email}")
    print("Migration complete.")


if __name__ == "__main__":
    main()
