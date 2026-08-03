"""In-app notifications (bell feed) + two-way customer<->shop support messages.

- notif_router  -> /api/notifications
- msg_router    -> /api/messages
A message thread is all rows sharing user_id (the customer); `sender` says who
wrote each line. Managers list threads and reply into a customer's thread.
"""
from fastapi import APIRouter, Body, Depends, HTTPException

from db import fetch_all, fetch_one, execute
from security import current_user, require_manager
from notifications import notify_managers, notify_users

notif_router = APIRouter()
msg_router = APIRouter()


# ---------------------------------------------------------------- notifications
@notif_router.get("")
def list_notifications(user=Depends(current_user)):
    rows = fetch_all(
        """select id, type, title, body, order_id, read, created_at
           from notifications where user_id = %s order by created_at desc limit 50""",
        [user["id"]],
    )
    unread = fetch_one(
        "select count(*)::int as n from notifications where user_id = %s and not read", [user["id"]]
    )["n"]
    return {"notifications": rows, "unread": unread}


@notif_router.post("/read")
def mark_notifications_read(user=Depends(current_user)):
    execute("update notifications set read = true where user_id = %s and not read", [user["id"]])
    return {"ok": True}


# --------------------------------------------------------------------- messages
@msg_router.get("")
def my_thread(user=Depends(current_user)):
    """The signed-in customer's own thread with the shop."""
    rows = fetch_all(
        """select id, sender, body, order_id, created_at
           from messages where user_id = %s order by created_at""",
        [user["id"]],
    )
    execute(
        "update messages set read_by_customer = true where user_id = %s and sender = 'manager' and not read_by_customer",
        [user["id"]],
    )
    return {"messages": rows}


@msg_router.post("")
def send_message(user=Depends(current_user), payload: dict = Body(default={})):
    text = (payload.get("body") or "").strip()
    if not text:
        raise HTTPException(400, "Empty message")
    text = text[:2000]
    order_id = payload.get("order_id") or None
    if order_id:  # only accept an order id the customer actually owns
        own = fetch_one("select id from orders where id = %s and user_id = %s", [order_id, user["id"]])
        order_id = str(own["id"]) if own else None
    msg = fetch_one(
        """insert into messages (user_id, order_id, sender, body, read_by_customer)
           values (%s, %s, 'customer', %s, true)
           returning id, sender, body, order_id, created_at""",
        [user["id"], order_id, text],
    )
    name = user.get("full_name") or user.get("email") or "عميل"
    notify_managers(type="message", title=f"رسالة من {name}", body=text[:80], order_id=order_id)
    return {"message": msg}


@msg_router.get("/threads")
def list_threads(_m=Depends(require_manager)):
    """All customer threads, newest activity first, with unread counts (for the admin)."""
    rows = fetch_all(
        """select m.user_id, u.full_name, u.email,
                  max(m.created_at) as last_at,
                  count(*) filter (where m.sender = 'customer' and not m.read_by_manager) as unread,
                  (select body from messages x where x.user_id = m.user_id order by x.created_at desc limit 1) as last_body
           from messages m join users u on u.id = m.user_id
           group by m.user_id, u.full_name, u.email
           order by last_at desc"""
    )
    total_unread = fetch_one(
        "select count(*)::int as n from messages where sender = 'customer' and not read_by_manager"
    )["n"]
    return {"threads": rows, "unread": total_unread}


@msg_router.get("/thread/{uid}")
def get_thread(uid: str, _m=Depends(require_manager)):
    customer = fetch_one("select id, full_name, email from users where id = %s", [uid])
    if not customer:
        raise HTTPException(404, "Customer not found")
    rows = fetch_all(
        "select id, sender, body, order_id, created_at from messages where user_id = %s order by created_at", [uid]
    )
    execute(
        "update messages set read_by_manager = true where user_id = %s and sender = 'customer' and not read_by_manager",
        [uid],
    )
    return {"messages": rows, "customer": customer}


@msg_router.post("/thread/{uid}")
def reply_thread(uid: str, _m=Depends(require_manager), payload: dict = Body(default={})):
    text = (payload.get("body") or "").strip()
    if not text:
        raise HTTPException(400, "Empty message")
    text = text[:2000]
    customer = fetch_one("select id from users where id = %s", [uid])
    if not customer:
        raise HTTPException(404, "Customer not found")
    msg = fetch_one(
        """insert into messages (user_id, sender, body, read_by_manager)
           values (%s, 'manager', %s, true)
           returning id, sender, body, order_id, created_at""",
        [uid, text],
    )
    notify_users([uid], type="reply", title="ردٌّ من دكّان كنعان", body=text[:80])
    return {"message": msg}
