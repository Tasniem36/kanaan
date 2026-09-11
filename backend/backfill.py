"""One-time repairs for rows that predate a column, run on every deploy by migrate.py.

Kept out of db/schema.sql on purpose. Anything here needs a value the application
already knows how to mint — an order number from new_ref(), a token from `secrets` —
and writing a second version of that in PL/pgSQL gives the shop two implementations
of one rule, which drift without anything failing. schema.sql adds and indexes the
columns; this fills them.

Kept out of migrate.py so it can be tested: importing migrate runs load_dotenv() at
module scope, which would pull the real .env into whatever process imported it.
"""
import secrets

from routers.orders import new_ref


def backfill_order_tracking(conn):
    """Orders placed before the tracking link existed have no number and no token, so
    their customers couldn't use the order lookup. Give every one of them both.
    Idempotent: rows that already have them are skipped."""
    rows = conn.execute("select id, ref, track_token from orders "
                        "where ref is null or track_token is null").fetchall()
    if not rows:
        return 0
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
    return len(rows)
