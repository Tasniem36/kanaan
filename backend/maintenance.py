"""Housekeeping for the tables that grow forever.

Run on every deploy (migrate.py calls prune()) and, ideally, nightly from cron:

    0 3 * * * cd /root/app && docker compose -f docker-compose.prod.yml exec -T api python maintenance.py

Everything here is a deletion, so each rule is deliberately narrow and has a floor:
a mistyped retention can shorten the window, never empty a table.
"""
import os

from db import execute, fetch_one

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


def prune_audit_logs(days: int | None = None) -> int:
    """Drop activity older than the retention window.

    Note this also trims what the dashboard's "most opened products" and "where
    visitors come from" panels can look back over — they read the same rows.
    """
    days = days or _days("AUDIT_RETENTION_DAYS", AUDIT_DAYS)
    row = fetch_one(
        """with gone as (
               delete from audit_logs
                where created_at < now() - (%s || ' days')::interval
             returning 1
           ) select count(*)::int as n from gone""",
        [days],
    )
    return (row or {}).get("n", 0)


def prune_dead_signups() -> int:
    """Remove abandoned signups whose codes have expired.

    These matter more than their size suggests: each row holds the password hash the
    person typed, so an abandoned signup leaves one sitting in the database forever.
    A verification that has expired can never be completed, so the row is only risk.
    """
    row = fetch_one(
        """with gone as (
               delete from signup_verifications
                where expires_at < now() - interval '1 day'
             returning 1
           ) select count(*)::int as n from gone""",
    )
    return (row or {}).get("n", 0)


def prune() -> dict:
    """Every rule, reported so a deploy log says what it removed."""
    return {
        "audit_logs": prune_audit_logs(),
        "signup_verifications": prune_dead_signups(),
    }


if __name__ == "__main__":
    for table, removed in prune().items():
        print(f"✓ {table}: removed {removed} row(s)")
