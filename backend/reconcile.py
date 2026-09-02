"""Settle Ziina payments that the customer's browser never came back to report.

An order only becomes paid when /pay/return loads and calls confirm-payment. That is
one page load on one device, and it is the only thing in the system that ever writes
payment_status = 'paid' — there is no Ziina webhook. Every way that page load can go
missing is money the shop has taken and has no record of:

  · the phone died, the tab was closed, the app was backgrounded and killed
  · the redirect arrived before Ziina had marked the intent completed, and the page
    gave up after its few seconds of polling
  · the customer pressed cancel, and the payment they had already made settled after

This asks Ziina about every recent unresolved order and finishes the job. It is the
mechanism that lets cancel_payment be careful: because this runs, an unresolved
payment can be left alone in the request path instead of being cancelled on a guess.

Running it by hand REPORTS ONLY unless you pass --apply, like maintenance.py. Nothing
here should be able to move money-adjacent state just by being run to see what it does:

    python reconcile.py            # says what it would settle, changes nothing
    python reconcile.py --apply    # actually settles it

Cron it every few minutes — this is not a nightly job. A customer waiting on a
WhatsApp confirmation is waiting on this:

    */5 * * * * cd /root/app && docker compose -f docker-compose.prod.yml exec -T api python reconcile.py --apply
"""
import os
import sys

from fastapi import HTTPException

from db import fetch_all
from ziina import get_payment_intent
from routers.orders import FAILED_STATUSES, cancel_and_restore, mark_paid

# How long an order may sit with an unresolved intent before that is read as
# abandoned and its stock goes back on the shelf. Pressing cancel on Ziina's page
# doesn't fail the intent, so an ordinary abandoned checkout looks exactly like a card
# still being authorised — only time tells them apart. Long enough that no real
# payment is still in flight; short enough that the last jar of za'atar isn't held all
# afternoon for someone who wandered off.
STALE_MINUTES = 30
# Nothing shorter, whatever the environment says: a mistyped 1 would start cancelling
# orders out from under payments that are still going through.
MIN_STALE_MINUTES = 10
# Older than this and it is not this job's business — a months-old pending order is a
# question for a human, and Ziina won't have much to say about the intent either.
LOOKBACK_DAYS = 7


def _stale_minutes() -> int:
    try:
        return max(MIN_STALE_MINUTES, int(os.getenv("PAYMENT_STALE_MINUTES", STALE_MINUTES)))
    except (TypeError, ValueError):
        return STALE_MINUTES


def unresolved_orders(lookback_days: int = LOOKBACK_DAYS):
    """Ziina orders that never reached paid — including cancelled ones, which is the
    whole point: an order cancelled while its payment was in flight is exactly the
    case worth catching."""
    return fetch_all(
        """select *, created_at < now() - (%s || ' minutes')::interval as stale
           from orders
           where payment_method = 'ziina' and ziina_payment_id is not null
             and payment_status is distinct from 'paid'
             and created_at > now() - (%s || ' days')::interval
           order by created_at""",
        [_stale_minutes(), lookback_days],
    )


def reconcile(*, apply: bool = False) -> dict:
    """Ask Ziina about each unresolved order and act on the answer.

    Returns what it did (or would do), so a cron log is a record of the shop's
    payments and not just a heartbeat.
    """
    counts = {"paid": 0, "cancelled": 0, "waiting": 0, "unreachable": 0}
    for order in unresolved_orders():
        oid = str(order["id"])
        try:
            status = get_payment_intent(order["ziina_payment_id"]).get("status")
        except HTTPException as e:
            # Ziina is down or the key is wrong. Nothing is decided on silence — the
            # order keeps its stock and the next run asks again.
            counts["unreachable"] += 1
            print(f"· {oid[:8]} could not be checked: {e.detail}")
            continue

        if status == "completed":
            counts["paid"] += 1
            was = " (had been cancelled)" if order["status"] == "cancelled" else ""
            print(f"{'✓ settling' if apply else '· would settle'} {oid[:8]} · {order['total']}{was}")
            if apply:
                mark_paid(order)
            continue

        if order["status"] == "cancelled":
            continue  # already dealt with; Ziina agrees the money isn't coming

        if status in FAILED_STATUSES or order["stale"]:
            counts["cancelled"] += 1
            why = status if status in FAILED_STATUSES else f"unresolved for over {_stale_minutes()}m"
            print(f"{'✓ releasing' if apply else '· would release'} {oid[:8]} · {why}")
            if apply:
                cancel_and_restore(oid)
            continue

        counts["waiting"] += 1  # young and undecided: ask again next run
    return counts


if __name__ == "__main__":
    live = "--apply" in sys.argv[1:]
    c = reconcile(apply=live)
    print(f"\n{c['paid']} paid · {c['cancelled']} released · "
          f"{c['waiting']} still waiting · {c['unreachable']} unreachable")
    if not live and (c["paid"] or c["cancelled"]):
        print("nothing was changed — run with --apply to do it")
