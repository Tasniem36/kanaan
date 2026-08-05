"""In-app notification helpers. Insert rows into `notifications` for the bell feed.
Never raises — a failed notification must never break the request that triggered it."""
from db import execute, fetch_all


def notify_users(user_ids, *, type, title, body=None, order_id=None):
    for uid in user_ids:
        if not uid:
            continue
        try:
            execute(
                "insert into notifications (user_id, type, title, body, order_id) values (%s, %s, %s, %s, %s)",
                [uid, type, title, body, order_id],
            )
        except Exception as e:  # noqa: BLE001 — auditing/notifying is best-effort
            print("[notify]", e)
    # also fire a device push (best-effort). Deep-link orders; messages open the app.
    try:
        import push
        url = "/manager/orders" if type == "new_order" else "/account/orders" if type == "order_status" else "/"
        push.push_to_users(user_ids, title=title, body=body, url=url, tag=type)
    except Exception as e:  # noqa: BLE001
        print("[notify.push]", e)


def notify_managers(*, type, title, body=None, order_id=None):
    try:
        mgrs = fetch_all("select id from users where role = 'manager'")
    except Exception as e:  # noqa: BLE001
        print("[notify] managers lookup failed:", e)
        return
    notify_users([m["id"] for m in mgrs], type=type, title=title, body=body, order_id=order_id)
