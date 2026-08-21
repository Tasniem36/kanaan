import os
import secrets
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from db import pool, fetch_all, fetch_one, execute
from messaging import send_email
from ratelimit import rate_limit
from security import current_user, optional_user, require_manager
from validate import is_email, normalize_uae_phone
from audit import log_action
from ziina import create_payment_intent, get_payment_intent
from notify import notify_new_order
from notifications import notify_managers, notify_users
from delivery import compute_fee as compute_delivery_fee
from routers.discounts import error_body, evaluate_code
from routers.settings import get_checkout_config

router = APIRouter()

# customer-facing Arabic labels for order status changes
STATUS_LABELS = {
    "pending": "قيد المعالجة",
    "paid": "تمّ الدفع",
    "preparing": "قيد التجهيز 🧑‍🍳",
    "fulfilled": "تمّ الشحن 🚚",
    "delivered": "تمّ التوصيل ✅",
    "cancelled": "أُلغي الطلب",
}


def _notify_new_order_admins(order):
    oid = str(order["id"])
    notify_managers(
        type="new_order",
        title="طلبٌ جديد 🛒",
        body=f"#{oid[:8]} · {order.get('customer_name', '')} · {order.get('total', '')}",
        order_id=oid,
    )


def cancel_and_restore(order_id):
    """Restore reserved stock and mark an order cancelled (payment couldn't start/complete)."""
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
        # One statement puts every line's stock back — was a read plus an update
        # per line item. Grouping by product keeps it correct even if the same
        # product somehow landed on two lines.
        cur.execute(
            """update products p set stock = p.stock + s.qty
               from (select product_id, sum(qty) as qty from order_items
                     where order_id = %s and product_id is not null
                     group by product_id) s
               where p.id = s.product_id""",
            [order_id],
        )
        cur.execute("update orders set status = 'cancelled' where id = %s", [order_id])
        cur.execute("insert into order_status_events (order_id, status) values (%s, 'cancelled')", [order_id])


# Order-number alphabet: no 0/O/1/I, so a customer reading it out over the phone
# or typing it from an e-mail can't land on the wrong order.
_REF_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
_REF_LEN = 7


def new_ref(exists):
    """A free order number. `exists(ref)` tells us whether one is taken — checked in
    the caller's transaction, so two orders can't be handed the same number."""
    for _ in range(8):
        ref = "".join(secrets.choice(_REF_ALPHABET) for _ in range(_REF_LEN))
        if not exists(ref):
            return ref
    raise HTTPException(503, "Could not allocate an order number — please try again")


def display_ref(ref, oid):
    """What the customer sees. Orders from before ref existed fall back to the id."""
    return f"DK-{ref}" if ref else f"#{str(oid)[:8]}"


def _order_email_body(order, track_url):
    """Plain-text confirmation. Deliberately no prices per line — the total and the
    live status live on the tracking page, which can't go stale the way an e-mail can."""
    number = display_ref(order.get("ref"), order["id"])
    return (
        f"مرحباً {order['customer_name']},\n\n"
        f"استلمنا طلبك رقم {number} في دكّان كنعان.\n"
        f"الإجمالي: {order['total']} درهم\n"
        f"طريقة الدفع: {'الدفع عند الاستلام' if order['payment_method'] == 'cod' else 'مدفوع إلكترونياً'}\n\n"
        f"تابع حالة طلبك من هنا:\n{track_url}\n\n"
        f"احفظ هذا الرابط — يفتح صفحة طلبك دون تسجيل دخول.\n"
        f"وإن فقدته، ابحث عن طلبك برقمه ({number}) ورقم هاتفك أو بريدك من صفحة تتبّع الطلب.\n\n"
        f"لأي استفسار راسلنا على واتساب: +971 52 298 1187\n"
        f"دكّان كنعان"
    )


def _send_order_email(order, email, request):
    """Best-effort: a failed e-mail must never fail the order that triggered it."""
    if not email:
        return
    try:
        base = os.getenv("APP_URL") or request.headers.get("origin") or ""
        track_url = f"{base}/track/{order['id']}?t={order['track_token']}"
        send_email(email, f"تأكيد طلبك {display_ref(order.get('ref'), order['id'])} — دكّان كنعان",
                   _order_email_body(order, track_url))
    except Exception as e:  # noqa: BLE001 — never break checkout over a mail failure
        print("[order-email]", e)


def _checkout_failed(request, user, reason, **extra):
    """Record a checkout that didn't go through. These are the moments a customer
    gives up, and they're invisible unless written down."""
    log_action(user_id=(user or {}).get("id"), action="checkout_failed",
               detail={"reason": reason, **extra}, request=request)


def _guest_account(run, email, full_name, phone, request):
    """The account a guest order hangs off.

    Reuses the row for that e-mail when there is one — so a customer who once
    ordered as a guest, or who already has a real account, keeps a single history.
    Otherwise creates one with an empty password_hash: unusable for login until
    they claim it through /register (see routers/auth.py).
    """
    rows = run("select id, email, full_name, phone, role, password_hash from users where email = %s", [email])
    if rows:
        u = rows[0]
        # fill in details the row is missing (an earlier guest order may have had none)
        if not (u["full_name"] or "").strip() or not (u["phone"] or "").strip():
            run("""update users set full_name = coalesce(nullif(full_name, ''), %s),
                                    phone = coalesce(nullif(phone, ''), %s) where id = %s""",
                [full_name, phone, u["id"]])
        return u
    u = run("""insert into users (email, password_hash, full_name, phone)
               values (%s, '', %s, %s) returning id, email, full_name, phone, role""",
            [email, full_name, phone])[0]
    log_action(user_id=u["id"], action="guest_account_created", detail={"email": email}, request=request)
    return u


@router.post("")
def create_order(request: Request, user=Depends(optional_user), payload: dict = Body(default={})):
    """Place an order. A session is optional: a guest supplies an e-mail instead and
    the order is attached to an account created (or reused) for that address, so the
    shop keeps its in-app channel to them even if the phone number turns out wrong."""
    customer_name = payload.get("customer_name")
    city, street, house = payload.get("city"), payload.get("street"), payload.get("house")
    payment_method = "ziina" if payload.get("payment_method") == "ziina" else "cod"
    if not customer_name or not payload.get("phone") or not city or not street or not house:
        _checkout_failed(request, user, "missing_fields")
        raise HTTPException(400, "Please complete the required fields")
    phone_norm = normalize_uae_phone(payload.get("phone"))
    if not phone_norm:
        _checkout_failed(request, user, "bad_phone")
        raise HTTPException(400, "Invalid UAE phone number")
    guest_email = None
    if not user:
        # Guest checkout is off unless the manager turned it on (Dashboard → delivery
        # settings). This is the backstop: the storefront also checks the flag before
        # it opens the form, and sends the shopper to sign in instead.
        if not get_checkout_config()["guest_allowed"]:
            _checkout_failed(request, user, "sign_in_required")
            raise HTTPException(401, "Please sign in to place your order")
        # The e-mail is the second way to reach them and the key their order history
        # hangs off, so it has to be real-looking.
        guest_email = (payload.get("email") or "").strip().lower()
        if not is_email(guest_email):
            _checkout_failed(request, user, "bad_email")
            raise HTTPException(400, "A valid e-mail address is required")
        # ordering reserves stock, so throttle it now that no login stands in the way
        rate_limit(request, bucket="guest_order", limit=6, window=60)
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise HTTPException(400, "Your cart is empty")

    with pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
        def run(sql, params=None):
            cur.execute(sql, params or [])
            return cur.fetchall() if cur.description else []

        # A guest's account is resolved in the same transaction as the order, so a
        # failure later can't leave an account behind with no order.
        account = user or _guest_account(run, guest_email, customer_name, phone_norm, request)
        user_id = account["id"]

        # Collapse duplicate lines for the same product BEFORE checking stock.
        # Two lines of qty 1 would each pass the check on a product with 1 left,
        # and the basket would oversell it.
        wanted = {}
        for item in items:
            pid = item.get("product_id")
            try:
                qty = int(item.get("qty"))
            except (TypeError, ValueError):
                qty = 0
            try:
                uuid.UUID(str(pid))   # a malformed id must be a 400, not a cast error
            except (TypeError, ValueError):
                raise HTTPException(400, "Product not found")
            if qty <= 0:
                raise HTTPException(400, "Invalid quantity")
            wanted[pid] = wanted.get(pid, 0) + qty

        products = run("select id, name, price, stock from products where id = any(%s::uuid[]) for update",
                       [list(wanted)])
        by_id = {str(p["id"]): p for p in products}

        total = 0.0
        lines = []
        for pid, qty in wanted.items():
            p = by_id.get(pid)
            if not p:
                raise HTTPException(400, "Product not found")
            if p["stock"] < qty:
                # its own action: a sale lost to the shop's stock, not to the customer
                log_action(user_id=(user or {}).get("id"), action="out_of_stock",
                           detail={"product_id": str(p["id"]), "name": p["name"],
                                   "wanted": qty, "left": p["stock"]}, request=request)
                raise HTTPException(409, f"Not enough stock for “{p['name']}”")
            total += float(p["price"]) * qty
            lines.append({"product_id": str(p["id"]), "name": p["name"], "price": float(p["price"]), "qty": qty})

        discount, discount_code = 0, None
        if payload.get("code"):
            r = evaluate_code(run, payload["code"], user_id, total)
            if r.get("error"):
                log_action(user_id=user_id, action="promo_invalid",
                           detail={"code": str(payload["code"])[:40], "reason": r["error"],
                                   "at": "checkout"}, request=request)
                # same shape as /discounts/validate — a basket that shrank after the
                # code was applied lands here, and the page phrases it the same way
                raise HTTPException(400, error_body(r))
            discount, discount_code = r["discount"], r["dc"]["code"]
        # delivery fee (recomputed server-side from the delivery city + subtotal)
        delivery_fee = compute_delivery_fee(city, total)
        final_total = max(0, round((total - discount + delivery_fee) * 100) / 100)

        order = run(
            """insert into orders (user_id, customer_name, phone, city, street, house, notes, total,
                                   payment_method, discount_code, discount_amount, delivery_fee,
                                   track_token, ref)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning *""",
            [user_id, customer_name, phone_norm, city, street, house, payload.get("notes"),
             final_total, payment_method, discount_code, discount, delivery_fee,
             secrets.token_urlsafe(16),
             new_ref(lambda r: bool(run("select 1 from orders where ref = %s", [r])))],
        )[0]
        # Write the whole basket in two statements instead of two per line item.
        pids = [x["product_id"] for x in lines]
        qtys = [x["qty"] for x in lines]
        run("""insert into order_items (order_id, product_id, name, price, qty)
               select %s, * from unnest(%s::uuid[], %s::text[], %s::numeric[], %s::int[])""",
            [order["id"], pids, [x["name"] for x in lines], [x["price"] for x in lines], qtys])
        run("""update products p set stock = p.stock - u.qty
               from unnest(%s::uuid[], %s::int[]) as u(product_id, qty)
               where p.id = u.product_id""",
            [pids, qtys])
        if discount_code:
            run("update discount_codes set used_count = used_count + 1 where code = %s", [discount_code])
        # first point on the customer's tracking timeline
        run("insert into order_status_events (order_id, status) values (%s, %s)", [order["id"], order["status"]])
        order["items"] = lines

    log_action(user_id=user_id, action="order_placed",
               detail={"order_id": str(order["id"]), "total": order["total"],
                       "payment_method": payment_method, "discount_code": discount_code}, request=request)

    if payment_method == "ziina":
        app_url = os.getenv("APP_URL") or request.headers.get("origin") or ""
        oid = str(order["id"])
        tok = order["track_token"]
        try:
            intent = create_payment_intent(
                amount_fils=round(final_total * 100),
                success_url=f"{app_url}/pay/return?order={oid}&t={tok}",
                cancel_url=f"{app_url}/pay/return?order={oid}&t={tok}&cancel=1",
                message=f"دكّان كنعان — طلب #{oid[:8]}",
            )
            execute("update orders set ziina_payment_id = %s where id = %s", [intent.get("id"), oid])
            _send_order_email(order, guest_email, request)
            return {"order": order, "redirect_url": intent.get("redirect_url")}
        except HTTPException:
            cancel_and_restore(oid)
            raise

    notify_new_order(order)  # COD: alert the manager now (Ziina alerts once paid)
    _notify_new_order_admins(order)  # in-app bell for managers
    # A guest has no order history to come back to, so the tracking link in this
    # e-mail is their only route to the order. Signed-in customers find it in حسابي.
    _send_order_email(order, guest_email, request)
    return {"order": order}


@router.get("")
def list_orders(user=Depends(current_user)):
    is_manager = user["role"] == "manager"
    if is_manager:
        # the manager's order card also shows the account e-mail, so they can
        # reach the customer when the phone doesn't answer
        orders = fetch_all(
            """select o.*, u.email as customer_email from orders o
               left join users u on u.id = o.user_id
               where not o.hidden order by o.created_at desc""")
    else:
        orders = fetch_all("select * from orders where user_id = %s and not hidden order by created_at desc", [user["id"]])
    if orders:
        # Two batched lookups for the whole page (items + tracking events), rather
        # than a pair of queries per order.
        ids = [o["id"] for o in orders]
        items = fetch_all("select order_id, name, price, qty from order_items where order_id = any(%s::uuid[])", [ids])
        events = fetch_all(
            """select order_id, status, created_at from order_status_events
               where order_id = any(%s::uuid[]) order by created_at""", [ids])
        by_items, by_events = {}, {}
        for it in items:
            by_items.setdefault(str(it["order_id"]), []).append(it)
        for ev in events:
            by_events.setdefault(str(ev["order_id"]), []).append(ev)
        for o in orders:
            oid = str(o["id"])
            o["items"] = by_items.get(oid, [])
            o["events"] = by_events.get(oid, [])
    return {"orders": orders}


# POST /api/orders/lookup — public: find your own order without an account, from the
# number on the confirmation e-mail plus the phone or e-mail it was placed with.
#
# The number alone is not enough to open an order (it's short, and printed on paper),
# so it must be paired with a contact detail that matches the order. Every failure
# returns the same 404 — a wrong number and a wrong contact are indistinguishable, so
# this can't be used to discover which numbers exist. Rate-limited on top.
@router.post("/lookup")
def lookup_order(request: Request, payload: dict = Body(default={})):
    rate_limit(request, bucket="order_lookup", limit=10, window=60)
    raw = str((payload or {}).get("ref") or "").strip().upper()
    ref = raw.replace("DK-", "").replace("#", "").replace(" ", "")
    contact = str((payload or {}).get("contact") or "").strip().lower()
    if not ref or not contact:
        raise HTTPException(400, "Order number and phone or e-mail are required")

    order = fetch_one(
        """select o.id, o.phone, o.track_token, u.email from orders o
           left join users u on u.id = o.user_id
           where o.ref = %s""", [ref])
    not_found = HTTPException(404, "We could not find an order with those details")
    if not order or not order["track_token"]:
        raise not_found
    # the contact may be the phone in any local format, or the e-mail on the account
    phone = normalize_uae_phone(contact)
    matches = (phone and phone == order["phone"]) or (contact == (order["email"] or "").lower())
    if not matches:
        raise not_found
    return {"id": order["id"], "token": order["track_token"]}


def _own_order_or_404(oid, user, token=None):
    """Fetch an order the caller is allowed to act on. 404 (not 403) for orders
    that aren't theirs, so order ids can't be probed for existence.

    Three ways to qualify: a manager, the customer it belongs to, or anyone holding
    its tracking token — which is how a guest with no session returns from Ziina.
    """
    try:
        uuid.UUID(str(oid))   # a malformed id is a 404, not a cast error
    except (ValueError, TypeError):
        raise HTTPException(404, "Order not found")
    order = fetch_one("select * from orders where id = %s", [oid])
    if not order:
        raise HTTPException(404, "Order not found")
    if user and (user["role"] == "manager" or str(order["user_id"]) == str(user["id"])):
        return order
    # compare_digest keeps a wrong token from being narrowed down by timing
    if token and order["track_token"] and secrets.compare_digest(str(token), order["track_token"]):
        return order
    raise HTTPException(404, "Order not found")


# GET /api/orders/track/{oid}?t=… — public: the status page for whoever placed the
# order. The token is the credential, so this returns only what that page shows and
# never the customer's e-mail or account id.
@router.get("/track/{oid}")
def track_order(oid: str, request: Request, t: str = Query(""), user=Depends(optional_user)):
    order = _own_order_or_404(oid, user, token=t)
    fields = ("id", "customer_name", "city", "street", "house", "notes", "status", "total",
              "payment_method", "payment_status", "delivery_fee", "discount_amount", "created_at")
    safe = {k: order[k] for k in fields}
    safe["number"] = display_ref(order.get("ref"), order["id"])
    # the phone is shown back partially, so they can check what they typed without
    # the full number sitting behind a link that might be forwarded
    phone = order["phone"] or ""
    safe["phone_hint"] = (phone[:4] + "*" * (len(phone) - 8) + phone[-4:]) if len(phone) > 8 else phone
    safe["items"] = fetch_all("select name, price, qty from order_items where order_id = %s", [oid])
    safe["events"] = fetch_all(
        "select status, created_at from order_status_events where order_id = %s order by created_at", [oid])
    return {"order": safe}


@router.post("/{oid}/confirm-payment")
def confirm_payment(oid: str, request: Request, t: str = Query(""), user=Depends(optional_user)):
    if not user and not t:
        raise HTTPException(401, "Authentication required")
    order = _own_order_or_404(oid, user, token=t)
    if order["payment_status"] == "paid":
        return {"paid": True, "status": order["status"]}
    if order["payment_method"] != "ziina" or not order["ziina_payment_id"]:
        return {"paid": False, "status": order["status"]}
    intent = get_payment_intent(order["ziina_payment_id"])
    if intent.get("status") == "completed":
        upd = fetch_one("update orders set payment_status = 'paid', status = 'paid' where id = %s returning *", [oid])
        execute("insert into order_status_events (order_id, status) values (%s, 'paid')", [oid])
        its = fetch_all("select name, price, qty from order_items where order_id = %s", [oid])
        notify_new_order({**upd, "items": its})
        _notify_new_order_admins(upd)  # in-app bell for managers (Ziina paid = real order)
        log_action(user_id=order["user_id"], action="payment_confirmed",
                   detail={"order_id": oid, "total": order["total"]}, request=request)
        return {"paid": True, "status": "paid"}
    if intent.get("status") == "failed":
        cancel_and_restore(oid)
        return {"paid": False, "status": "failed"}
    return {"paid": False, "status": intent.get("status")}


@router.post("/{oid}/cancel-payment")
def cancel_payment(oid: str, t: str = Query(""), user=Depends(optional_user)):
    if not user and not t:
        raise HTTPException(401, "Authentication required")
    order = _own_order_or_404(oid, user, token=t)
    if order["payment_status"] == "paid":
        return {"cancelled": False, "paid": True}
    if order["payment_method"] == "ziina" and order["ziina_payment_id"]:
        try:
            intent = get_payment_intent(order["ziina_payment_id"])
            if intent.get("status") == "completed":
                upd = fetch_one("update orders set payment_status = 'paid', status = 'paid' where id = %s returning *", [oid])
                its = fetch_all("select name, price, qty from order_items where order_id = %s", [oid])
                notify_new_order({**upd, "items": its})
                return {"cancelled": False, "paid": True}
        except HTTPException:
            pass
    cancel_and_restore(oid)
    return {"cancelled": True}


@router.patch("/{oid}/status")
def set_status(oid: str, _m=Depends(require_manager), payload: dict = Body(default={})):
    status = payload.get("status")
    if status not in ("pending", "paid", "preparing", "fulfilled", "delivered", "cancelled"):
        raise HTTPException(400, "Invalid status")
    row = fetch_one("update orders set status = %s where id = %s returning *", [status, oid])
    if not row:
        raise HTTPException(404, "Order not found")
    # add the point the customer's tracking timeline reads
    execute("insert into order_status_events (order_id, status) values (%s, %s)", [oid, status])
    # notify the customer their order status changed
    if row.get("user_id"):
        notify_users([row["user_id"]], type="order_status",
                     title="تحديث حالة طلبك",
                     body=f"طلب #{oid[:8]}: {STATUS_LABELS.get(status, status)}", order_id=oid)
    return {"order": row}


@router.delete("/{oid}")
def hide_order(oid: str, _m=Depends(require_manager)):
    """Soft-delete: hide the order from every list without erasing it (kept for
    records/accounting). It simply stops showing."""
    row = fetch_one("update orders set hidden = true where id = %s returning id", [oid])
    if not row:
        raise HTTPException(404, "Order not found")
    return {"hidden": True}
