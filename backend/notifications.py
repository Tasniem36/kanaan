"""In-app notification helpers. Insert rows into `notifications` for the bell feed.
Never raises — a failed notification must never break the request that triggered it."""
from db import execute, fetch_all


def notify_users(user_ids, *, type, title, body=None, order_id=None):
    # de-duplicate (dict preserves order) and drop blanks — one insert for the lot,
    # so notifying every manager costs a single round-trip instead of one each
    ids = [str(u) for u in dict.fromkeys(user_ids) if u]
    if not ids:
        return
    try:
        execute(
            """insert into notifications (user_id, type, title, body, order_id)
               select unnest(%s::uuid[]), %s, %s, %s, %s""",
            [ids, type, title, body, order_id],
        )
    except Exception as e:  # noqa: BLE001 — auditing/notifying is best-effort
        print("[notify]", e)
    # also fire a device push (best-effort). Deep-link orders; messages open the app.
    try:
        import push
        url = ("/manager/orders" if type == "new_order"
               else "/account/orders" if type == "order_status"
               else "/manager/reviews" if type == "new_review"
               else "/#reviews" if type == "review_status"
               else "/")
        push.push_to_users(ids, title=title, body=body, url=url, tag=type)
    except Exception as e:  # noqa: BLE001
        print("[notify.push]", e)


def notify_managers(*, type, title, body=None, order_id=None):
    try:
        mgrs = fetch_all("select id from users where role = 'manager'")
    except Exception as e:  # noqa: BLE001
        print("[notify] managers lookup failed:", e)
        return
    notify_users([m["id"] for m in mgrs], type=type, title=title, body=body, order_id=order_id)
