"""Housekeeping for the customer activity log.

The activity log is the ONLY table this file is allowed to delete from. Everything
else — orders, reviews, messages, users, pending signups — is left alone, whatever
the reason: nothing here decides on its own that data has stopped being useful.

Running it by hand REPORTS ONLY unless you pass --apply. Nobody, script or assistant,
should be able to remove data from this database by running a file to see what it
does:

    python maintenance.py            # says what it would remove, deletes nothing
    python maintenance.py --apply    # actually removes it

migrate.py calls prune(apply=True) on deploy, which is the intended automatic path.
Nightly cron, if you deploy rarely:

    0 3 * * * cd /root/app && docker compose -f docker-compose.prod.yml exec -T api python maintenance.py --apply

Each rule is deliberately narrow and has a floor: a mistyped retention can shorten
the window, never empty a table.
"""
import os
import sys

from db import fetch_one

# How long the customer activity trail is kept. Long enough to answer "what happened
# last quarter", short enough that the table stays quick and the IPs in it don't
# accumulate indefinitely.
AUDIT_DAYS = 90
# Nothing below this, whatever the environment says — a typo shouldn't wipe the log.
MIN_DAYS = 7


def _days(env_name: str, default: int) -> int:
    try:
        return max(MIN_DAYS, int(os.getenv(env_name, default)))
    except (TypeError, ValueError):
        return default


def prune_audit_logs(days: int | None = None, *, apply: bool = False) -> int:
    """Activity older than the retention window. Counts it unless apply=True.

    Note this also trims what the dashboard's "most opened products" and "where
    visitors come from" panels can look back over — they read the same rows.
    """
    days = days or _days("AUDIT_RETENTION_DAYS", AUDIT_DAYS)
    where = "created_at < now() - (%s || ' days')::interval"
    if not apply:
        row = fetch_one(f"select count(*)::int as n from audit_logs where {where}", [days])
        return (row or {}).get("n", 0)
    row = fetch_one(
        f"""with gone as (
                delete from audit_logs where {where} returning 1
            ) select count(*)::int as n from gone""",
        [days],
    )
    return (row or {}).get("n", 0)


def prune(*, apply: bool = False) -> dict:
    """The one rule, reported so a deploy log says what it removed (or would remove).
    A dict rather than a number so adding a table later is a visible decision."""
    return {"audit_logs": prune_audit_logs(apply=apply)}


if __name__ == "__main__":
    live = "--apply" in sys.argv[1:]
    counts = prune(apply=live)
    for table, n in counts.items():
        print(f"{'✓ removed' if live else '· would remove'} {n} row(s) from {table}")
    if not live and any(counts.values()):
        print("\nnothing was deleted — run with --apply to do it")
