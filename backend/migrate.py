"""Apply db/schema.sql + db/seed.sql, and optionally seed the first manager
from SEED_MANAGER_EMAIL / SEED_MANAGER_PASSWORD. Run: python migrate.py"""
import os

from dotenv import load_dotenv

load_dotenv()

from db import pool
from security import hash_password
from thumbs import make_thumb


def _run_file(conn, path):
    with open(path, encoding="utf-8") as f:
        conn.execute(f.read())
    print(f"✓ applied {path}")


def _backfill_thumbnails(conn):
    """Generate small thumbnails for existing products that never had one (or
    whose thumb is still the full-size image). Runs server-side, once, so old
    products load as light in lists as new ones."""
    rows = conn.execute(
        "select id, image_url from products "
        "where image_url like 'data:%' and (thumb_url is null or thumb_url = image_url)"
    ).fetchall()
    done = 0
    for row in rows:
        thumb = make_thumb(row["image_url"])
        if thumb and thumb != row["image_url"]:
            conn.execute("update products set thumb_url = %s where id = %s", [thumb, row["id"]])
            done += 1
    if done:
        print(f"✓ backfilled {done} product thumbnail(s)")


def main():
    with pool.connection() as conn:
        _run_file(conn, "db/schema.sql")
        _run_file(conn, "db/seed.sql")
        _backfill_thumbnails(conn)
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
