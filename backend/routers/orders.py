import os
import secrets
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

import background
from db import pool, fetch_all, fetch_one, execute
from messaging import send_email
from ratelimit import rate_limit
from security import current_user, optional_user, require_manager
from validate import is_email, normalize_uae_phone
from audit import log_action
from ziina import create_payment_intent, get_payment_intent
from notify import notify_new_order
from notifications import notify_managers, notify_users
import whatsapp
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


def _alert_managers(order):
    """The managers' new-order alert (Telegram, CallMeBot), off the request path.

    Each channel is a twenty-second timeout away, and TELEGRAM_CHAT_ID may now hold
    several recipients, which notify.py sends to one after another — so this is up to
    twenty seconds per recipient, and it was being held open by the request that takes
    the customer's money: the COD checkout, and the settle that follows a card payment.
    A shop that alerts three phones would have added a minute to a checkout the first
    time Telegram was unreachable.

    The device push and the customer's WhatsApp were moved off for exactly this reason
    (see push.py and _send_order_whatsapp, measured at 20.9s); this was the last sender
    still on the request. Returns the thread so a test can wait for it.
    """
    def _safe():
        try:
            notify_new_order(order)
        except Exception as e:  # noqa: BLE001 — never break an order over an alert
            print("[order-alert]", e)

    return background.spawn(_safe, name="order-alert")


def _notify_new_order_admins(order):
    oid = str(order["id"])
    notify_managers(
        type="new_order",
        title="طلبٌ جديد 🛒",
        body=f"#{oid[:8]} · {order.get('customer_name', '')} · {order.get('total', '')}",
        order_id=oid,
    )


# Ziina statuses that mean the money is not coming, in two kinds.
#
# REFUSED is a decision: the card was declined, or the customer withdrew. Nothing is
# going to change, so the order can be released and its stock freed at once.
#
# EXPIRED is only a clock running out on one attempt. It used to sit in the same set,
# which meant an order died the moment Ziina timed its intent out — however long the
# shop had said to wait. That was fair enough when there was no way back in, but the
# tracking page and حسابي now hand out a fresh payment page, so an expired attempt is
# recoverable and releasing on it throws away an order the customer may still finish.
# The sweep lets PAYMENT_STALE_MINUTES decide that one instead.
#
# Anything else — pending, an instrument not yet chosen, a status this code has never
# seen — means "not resolved yet", and an unresolved payment never destroys an order:
# see cancel_payment.
REFUSED_STATUSES = {"failed", "cancelled", "canceled"}
EXPIRED_STATUSES = {"expired"}
# The two together: what the customer-facing endpoints act on, where somebody is
# waiting on an answer right now rather than a sweep deciding policy in the background.
FAILED_STATUSES = REFUSED_STATUSES | EXPIRED_STATUSES

# The two ways an order's stock moves, as exact inverses of each other. One statement
# per order rather than a read plus an update per line item, and grouping by product
# keeps the arithmetic right even if the same product somehow landed on two lines.
# Both are written to run on a caller's cursor, so a status change can move the stock
# inside the same transaction that changes the status — which is the only way the two
# can't come apart. Reserving may take a count negative: that is the honest reading
# (the shelf owes a unit) and a manager can see it, where leaving it high would sell
# the same jar to someone else.
_STOCK_MOVE = """update products p set stock = p.stock {op} s.qty
                 from (select product_id, sum(qty) as qty from order_items
                       where order_id = %s and product_id is not null
                       group by product_id) s
                 where p.id = s.product_id"""
_RESTORE_STOCK = _STOCK_MOVE.format(op="+")
_RESERVE_STOCK = _STOCK_MOVE.format(op="-")

# Statuses in which the order is holding stock that is still ours to give back. Once
# it is fulfilled the goods have physically left the shop, so cancelling the paperwork
# afterwards cannot put them back — a manager taking a real return restocks the
# product itself.
_HOLDS_STOCK = ("pending", "paid", "preparing")


def cancel_and_restore(order_id, *, why=None, request=None):
    """Restore reserved stock and mark an order cancelled (payment couldn't start/complete).

    Cancels once, whatever happens. Reloading /pay/return?…&cancel=1 on a genuinely
    failed intent lands here twice, as does a return page racing the reconcile sweep,
    and putting the same jars back twice invents stock the shelf does not have. So the
    cancel is claimed first — the row lock holds the second caller until it can see the
    first one's answer — and only the caller that won it restores anything.

    Never a paid order. Every caller decides to release on an answer read BEFORE it
    gets here — the sweep asks Ziina about each order and then acts, the return page
    asks and then acts — and the money can land in that window. The claim below is the
    only thing that sees the order as it is now, so it is where that has to be caught:
    without the payment_status guard the sweep releases an order the return page has
    just settled, and the customer is charged, sent their confirmation, and then has
    the order cancelled behind them with its stock put back for someone else to buy.
    Nothing would revisit it either — unresolved_orders stops looking at an order the
    moment it is paid. mark_paid guards the mirror image of this race; this is the
    other half. A manager cancelling a paid order is a different path (set_status),
    which moves the stock itself.

    `why` is what Ziina said, or what the shop concluded from its silence. It is the
    one thing the audit row cannot work out for itself.

    Returns whether this call was the one that cancelled it.
    """
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute(
            """update orders set status = 'cancelled'
               where id = %s and status is distinct from 'cancelled'
                 and payment_status is distinct from 'paid'
               returning user_id, total""",
            [order_id],
        )
        row = cur.fetchone()
        if not row:
            # Already cancelled (its stock is already back), or paid while this caller
            # was deciding — in which case the order is real and keeps what it holds.
            return False
        cur.execute(_RESTORE_STOCK, [order_id])
        cur.execute("insert into order_status_events (order_id, status) values (%s, 'cancelled')", [order_id])
    # Every release of an order and its stock leaves a row, wherever it was decided:
    # the failed hand-off at checkout, the return page, the cancel button, the sweep.
    # Recorded here rather than at those four call sites, so none of them can forget —
    # and only by the caller that won the cancel, so a reload doesn't claim two.
    _after_commit(order_id, "audit row", lambda: log_action(
        user_id=row["user_id"], action="payment_released",
        detail={"order_id": str(order_id), "total": row["total"], "why": why}, request=request))
    return True


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
    # What actually happened to the money, not how it was meant to arrive. Reading
    # this off payment_method alone told a guest their order was "مدفوع إلكترونياً"
    # while they were still looking at Ziina's payment page — and went on saying it
    # after an abandoned checkout had been cancelled and its stock put back.
    how = ("الدفع عند الاستلام" if order["payment_method"] == "cod"
           else "مدفوع إلكترونياً" if order.get("payment_status") == "paid"
           else "بانتظار الدفع")
    return (
        f"مرحباً {order['customer_name']},\n\n"
        f"استلمنا طلبك رقم {number} في دكّان كنعان.\n"
        f"الإجمالي: {order['total']} درهم\n"
        f"طريقة الدفع: {how}\n\n"
        f"تابع حالة طلبك من هنا:\n{track_url}\n\n"
        f"احفظ هذا الرابط — يفتح صفحة طلبك دون تسجيل دخول.\n"
        f"وإن فقدته، ابحث عن طلبك برقمه ({number}) ورقم هاتفك أو بريدك من صفحة تتبّع الطلب.\n\n"
        f"لأي استفسار راسلنا على واتساب: +971 52 298 1187\n"
        f"دكّان كنعان"
    )


def _track_url(order, request=None) -> str:
    """The link that opens an order with no account: its id plus its token."""
    base = os.getenv("APP_URL") or (request and request.headers.get("origin")) or ""
    return f"{base}/track/{order['id']}?t={order['track_token']}"


def _send_order_email(order, email, request):
    """Best-effort: a failed e-mail must never fail the order that triggered it."""
    if not email:
        return
    try:
        send_email(email, f"تأكيد طلبك {display_ref(order.get('ref'), order['id'])} — دكّان كنعان",
                   _order_email_body(order, _track_url(order, request)))
    except Exception as e:  # noqa: BLE001 — never break checkout over a mail failure
        print("[order-email]", e)


def _can_sign_in(user_id) -> bool:
    """Whether this order's customer can reach the in-app notifications at all.

    A shadow account from guest checkout has an empty password_hash and cannot be
    logged into until it is claimed through /register, so its owner sees nothing the
    bell or the push puts there. Treated as unreachable, and told on WhatsApp instead.
    On a lookup failure, say False: a message too many beats a customer told nothing.
    """
    if not user_id:
        return False
    try:
        row = fetch_one("select password_hash from users where id = %s", [user_id])
    except Exception as e:  # noqa: BLE001
        print("[order-whatsapp] account lookup failed:", e)
        return False
    return bool(row and (row.get("password_hash") or "").strip())


def _guest_email_for(order):
    """The address a guest left at checkout, or None for anybody else.

    A customer who can sign in has حسابي to find the order in and was never sent this
    mail; only the shadow account _guest_account opens gets one. That rule is
    unchanged — it is asked of the order now rather than of the request that created
    it, because a card order's mail is sent when the payment settles, long after that
    request has gone.
    """
    uid = order.get("user_id")
    if not uid or _can_sign_in(uid):
        return None
    try:
        row = fetch_one("select email from users where id = %s", [uid])
    except Exception as e:  # noqa: BLE001 — a missing e-mail must not fail a payment
        print("[order-email] account lookup failed:", e)
        return None
    return (row or {}).get("email")


def _send_order_whatsapp(order, request=None, *, status_label=None):
    """Tell the customer on WhatsApp. The phone is the one contact detail every order
    has, so this is the only channel that reaches a customer who can't sign in.

    Skipped only for someone who can actually read the in-app notification and the
    push — that is, someone who can log in. A guest who left an e-mail address has a
    user_id, but it points at the shadow account _guest_account opens for them, with
    an empty password_hash and no way to sign in: gating on user_id alone left them
    with a row in a bell they can't reach. WA_NOTIFY_ALL messages everyone.

    Sent on a thread, like the device push in push.py. Meta's endpoint is a
    twenty-second timeout away, and a manager marking an order shipped shouldn't wait
    on it — measured at 20.9s for one status change before this was moved off the
    request. Returns the thread so a test can wait for it; no request path does, and a
    script waits for every one of them at once through background.wait_all.
    """
    if not whatsapp.configured():
        return None
    if not whatsapp.notify_all() and _can_sign_in(order.get("user_id")):
        return None
    # read what the message needs before leaving the request — `request` is not ours
    # to touch once it has been answered
    try:
        args = {"phone": order["phone"],
                "number": display_ref(order.get("ref"), order["id"]),
                "track_url": _track_url(order, request)}
        args.update({"status_label": status_label} if status_label
                    else {"total": order["total"]})
    except Exception as e:  # noqa: BLE001 — a row missing fields is not worth a 500
        print("[order-whatsapp]", e)
        return None

    send = whatsapp.send_order_status if status_label else whatsapp.send_order_placed

    def _safe():
        try:
            send(**args)
        except Exception as e:  # noqa: BLE001 — never break an order over a message
            print("[order-whatsapp]", e)

    return background.spawn(_safe, name="order-whatsapp")


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
        # Optional. The phone is what the shop actually delivers and calls on, and the
        # order carries it, so an order can be found by number + phone with no account
        # at all (see /orders/lookup). An e-mail, when given, buys two extra things:
        # the tracking link by mail, and a row this order can hang off so the customer
        # keeps one history — so it's still asked for, just not insisted on.
        guest_email = (payload.get("email") or "").strip().lower()
        if guest_email and not is_email(guest_email):
            _checkout_failed(request, user, "bad_email")
            raise HTTPException(400, "That e-mail address doesn't look right")
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
        # failure later can't leave an account behind with no order. With no e-mail
        # there is nothing to key an account on and nothing to send to it, so the order
        # stands on its own — its phone is the way back to it.
        if user:
            user_id = user["id"]
        elif guest_email:
            user_id = _guest_account(run, guest_email, customer_name, phone_norm, request)["id"]
        else:
            user_id = None

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

        # coalesce, not price: an item on offer is charged at the offer price. Read
        # here rather than trusted from the basket, so a sale that started or ended
        # while the customer was shopping is still billed correctly.
        products = run("""select id, name, coalesce(sale_price, price) as price, stock
                          from products where id = any(%s::uuid[]) for update""",
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
            # No confirmation e-mail here. Nothing has been paid yet — the shopper is
            # about to be redirected to Ziina and may never arrive, in which case the
            # sweep cancels this order within the half hour. mark_paid sends it if and
            # when the money lands, which is also when it can honestly say so.
            return {"order": order, "redirect_url": intent.get("redirect_url")}
        except HTTPException:
            cancel_and_restore(oid, why="the payment could not be started", request=request)
            raise

    _alert_managers(order)  # COD: alert the manager now (Ziina alerts once paid)
    _notify_new_order_admins(order)  # in-app bell for managers
    # A guest has no order history to come back to, so the tracking link is their
    # only route to the order. Signed-in customers find it in حسابي. The e-mail is
    # sent when there is one; the WhatsApp goes to the phone, which there always is.
    _send_order_email(order, guest_email, request)
    _send_order_whatsapp(order, request)
    return {"order": order}


@router.get("")
def list_orders(request: Request, user=Depends(current_user)):
    """Orders for the caller. A manager gets the shop's; anyone else gets their own.

    `?mine=1` asks for the caller's own either way. حسابي and the manager area are
    two different pages built on this one endpoint, and without the flag a manager
    opening their own account page was shown every order in the shop — their
    customers' names, addresses and phone numbers, filed under طلباتي.
    """
    mine = request.query_params.get("mine") == "1"
    is_manager = user["role"] == "manager" and not mine
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
        # product_id is here for the basket, not the page: paying for an order from
        # حسابي takes exactly these lines back out of it (a product id is public
        # catalogue data either way — see track_order, which does the same).
        items = fetch_all(
            "select order_id, product_id, name, price, qty from order_items where order_id = any(%s::uuid[])",
            [ids])
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

    def _lookup_failed():
        # Someone holding an order number who still can't reach their order: a lost
        # e-mail, a typo, or the wrong phone on the order. No session here — this is
        # the page for people who have no account — so what they typed is the only
        # thing that identifies them, and it's what the shop needs to put it right.
        log_action(action="track_lookup_failed",
                   detail={"ref": ref[:20], "contact": contact[:60]}, request=request)

    if not order or not order["track_token"]:
        _lookup_failed()
        raise not_found
    # the contact may be the phone in any local format, or the e-mail on the account
    phone = normalize_uae_phone(contact)
    matches = (phone and phone == order["phone"]) or (contact == (order["email"] or "").lower())
    if not matches:
        _lookup_failed()
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
    # product_id is here for the basket, not the page: when a payment settles minutes
    # later, services/awaitingPayment.js takes exactly these lines back out and leaves
    # anything added since (a product id is public catalogue data either way).
    safe["items"] = fetch_all(
        "select product_id, name, price, qty from order_items where order_id = %s", [oid])
    safe["events"] = fetch_all(
        "select status, created_at from order_status_events where order_id = %s order by created_at", [oid])
    return {"order": safe}


def _after_commit(oid, what, do):
    """Do something that follows a committed change to an order — an alert, a
    customer's confirmation, an audit row — without letting it undo that change.

    The money is already decided by the time these run, and nothing revisits a
    resolved order (see mark_paid), so anything lost here is lost for good. Which is
    exactly why one of them failing must not cost the ones after it, and why none of
    them may turn a payment that went through into an error on the customer's screen.
    """
    try:
        do()
    except Exception as e:  # noqa: BLE001 — nothing here can unmake the change above
        print(f"[order {str(oid)[:8]}] {what} failed:", e)


def mark_paid(order, request=None, *, by="return"):
    """The moment an order becomes real: flip it to paid and raise every alarm a real
    order raises.

    `by` says who noticed the money — the return page, a cancel button that turned out
    to have been pressed after paying, or the cron sweep. The audit row cannot work
    that out for itself, and it is the difference between the return path doing its job
    and the sweep quietly doing it for them.

    Both return paths and the reconcile sweep land here, so a payment discovered ten
    minutes late by cron reaches the manager and the customer exactly like one seen
    at the return URL. Which is also why the flip has to be the thing that decides:
    the return page's polling and a cron run can arrive for the same order at the same
    moment, and each read payment_status earlier, separately, so both would pass a
    check made before the write. Everything below the flip happens once — one paid
    event, one manager alert, one billed WhatsApp template, one stock deduction.

    The flip, the stock and the timeline point go in together, because a settle that
    stops halfway can never be finished by anything: unresolved_orders in reconcile.py
    stops looking at an order the moment it is paid, so an order left paid without its
    stock taken off the shelf is invisible to the only thing that would come back.

    Returns the paid order, or None if it had already been settled and this call did
    nothing.
    """
    oid = str(order["id"])
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
        # `order` was read before a Ziina call that can take twenty seconds — and in
        # the sweep, before every other order's — so its status is not evidence of
        # anything by now. The locked row is: a manager who cancelled inside that
        # window has already put this stock back, and only this read can see that.
        cur.execute("select status from orders where id = %s for update", [oid])
        was = cur.fetchone()
        if not was:
            return None  # the order is gone
        cur.execute("""update orders set payment_status = 'paid', status = 'paid'
                       where id = %s and payment_status is distinct from 'paid'
                       returning *""", [oid])
        upd = cur.fetchone()
        if not upd:
            return None  # someone else settled it, and did everything below with it
        # An order cancelled while the money was still in flight had its stock put
        # back. The payment is real, so the order is real again, and the shelf has to
        # reflect it before that stock is sold to someone else.
        if was["status"] == "cancelled":
            cur.execute(_RESERVE_STOCK, [oid])
        cur.execute("insert into order_status_events (order_id, status) values (%s, 'paid')", [oid])
        cur.execute("select name, price, qty from order_items where order_id = %s", [oid])
        its = cur.fetchall()
    # Past the commit the order is paid for good and nothing passes this way again, so
    # one alarm failing must not cost the others: the managers still hear about a real
    # order if the customer's WhatsApp template is refused, and the other way round.
    _after_commit(oid, "manager alert", lambda: _alert_managers({**upd, "items": its}))
    _after_commit(oid, "manager bell", lambda: _notify_new_order_admins(upd))
    # the customer's own confirmation: here, not at the hand-off to Ziina, because
    # this is the point the order became real
    _after_commit(oid, "customer confirmation", lambda: _send_order_whatsapp(upd, request))
    # The guest's copy of the order, held back until now for the same reason: an
    # e-mail headed "تأكيد طلبك" belongs to an order that exists, not to one still
    # being paid for. A payment the sweep found ten minutes late is mailed exactly
    # like one the browser reported.
    _after_commit(oid, "customer e-mail", lambda: _send_order_email(upd, _guest_email_for(upd), request))
    # The shop's record that this money arrived. Here rather than at the three call
    # sites, so a payment the sweep found is recorded exactly like one the browser
    # reported, and only when this call was the one that settled it.
    _after_commit(oid, "audit row", lambda: log_action(
        user_id=upd["user_id"], action="payment_confirmed",
        detail={"order_id": oid, "total": upd["total"], "by": by}, request=request))
    return upd


def _is_paid(oid) -> bool:
    """Whether the money is in, asked of the row now rather than of a copy read
    earlier. The two endpoints below both hold an `order` they fetched before a Ziina
    call that can take twenty seconds, which is long enough for the answer to change.
    """
    row = fetch_one("select payment_status from orders where id = %s", [oid])
    return bool(row and row["payment_status"] == "paid")


@router.post("/{oid}/confirm-payment")
def confirm_payment(oid: str, request: Request, t: str = Query(""), user=Depends(optional_user)):
    if not user and not t:
        raise HTTPException(401, "Authentication required")
    order = _own_order_or_404(oid, user, token=t)
    if order["payment_status"] == "paid":
        return {"paid": True, "status": order["status"]}
    if order["payment_method"] != "ziina" or not order["ziina_payment_id"]:
        return {"paid": False, "status": order["status"]}
    status = get_payment_intent(order["ziina_payment_id"]).get("status")
    if status == "completed":
        mark_paid(order, request)  # which records the payment_confirmed row itself
        return {"paid": True, "status": "paid"}
    if status in FAILED_STATUSES:
        # A refused release means the order was already cancelled, or the money landed
        # while we were asking Ziina. Only the row can say which, and telling somebody
        # who has just paid that it failed puts a "try again" button in front of them —
        # the one mistake this whole path exists to avoid.
        if not cancel_and_restore(oid, why=status, request=request) and _is_paid(oid):
            return {"paid": True, "status": "paid"}
        return {"paid": False, "status": "failed"}
    return {"paid": False, "status": status}


@router.post("/{oid}/cancel-payment")
def cancel_payment(oid: str, request: Request, t: str = Query(""), user=Depends(optional_user)):
    if not user and not t:
        raise HTTPException(401, "Authentication required")
    order = _own_order_or_404(oid, user, token=t)
    if order["payment_status"] == "paid":
        return {"cancelled": False, "paid": True}
    if order["payment_method"] != "ziina" or not order["ziina_payment_id"]:
        cancel_and_restore(oid, why="cancelled by the customer", request=request)
        return {"cancelled": True}
    # Arriving here says which URL Ziina redirected to, not what happened to the money:
    # failure_url is the same URL, and a customer can pay and then press cancel or back.
    # So ask Ziina, and only act on an answer.
    try:
        status = get_payment_intent(order["ziina_payment_id"]).get("status")
    except HTTPException:
        # Couldn't ask. Cancelling now would restore the stock and bury an order that
        # may have been paid for, and nothing would ever revisit it — there is no
        # webhook, and the customer's browser is not coming back a second time. Leave
        # it pending for reconcile_payments, which asks again once Ziina answers.
        return {"cancelled": False, "paid": False, "pending": True}
    if status == "completed":
        # they pressed cancel, but the money had gone through
        mark_paid(order, request, by="cancel")
        return {"cancelled": False, "paid": True}
    if status in FAILED_STATUSES:
        # Same as confirm-payment: the release can be refused because the payment
        # landed in the seconds this request spent asking, and a customer who has paid
        # must not be shown the failure screen and invited to pay again.
        if not cancel_and_restore(oid, why=status, request=request) and _is_paid(oid):
            return {"cancelled": False, "paid": True}
        return {"cancelled": True}
    # Pressing cancel on Ziina's page does not itself fail the intent, so the usual
    # abandoned checkout lands here, unresolved — indistinguishable, right now, from a
    # card still being authorised. The order keeps its stock until reconcile_payments
    # can ask again with the answer settled. A shelf held for a few minutes is worth
    # more than an order cancelled out from under a payment that was on its way.
    return {"cancelled": False, "paid": False, "pending": True}


def _payment_urls(oid, tok, request):
    base = os.getenv("APP_URL") or (request and request.headers.get("origin")) or ""
    return (f"{base}/pay/return?order={oid}&t={tok}",
            f"{base}/pay/return?order={oid}&t={tok}&cancel=1")


# POST /api/orders/{oid}/pay — finish paying for an order that was never paid for.
#
# A card checkout that was abandoned leaves a real order sitting unpaid, and the only
# page its customer can reach is the tracking link. Until now that page showed them
# "الدفع الإلكتروني" and no way to act on it: their way back in was to build the whole
# basket again. This is the way back in — the same payment page they walked away from,
# or cash on delivery instead, which is often what they actually wanted.
@router.post("/{oid}/pay")
def resume_payment(oid: str, request: Request, t: str = Query(""),
                   user=Depends(optional_user), payload: dict = Body(default={})):
    if not user and not t:
        raise HTTPException(401, "Authentication required")
    rate_limit(request, bucket="resume_payment", limit=10, window=60)
    order = _own_order_or_404(oid, user, token=t)
    method = "cod" if (payload or {}).get("method") == "cod" else "ziina"

    if order["payment_status"] == "paid":
        return {"paid": True}   # nothing owing; the page will show it as paid
    if order["status"] == "cancelled":
        # The sweep released it and put its stock back on the shelf. Reviving it here
        # would take units this code cannot know are still there, so the page offers
        # the basket again instead — that path checks stock properly.
        raise HTTPException(409, "This order was released. Please order again.")

    if method == "cod":
        # Switching off ziina is what saves the order: unresolved_orders only looks at
        # payment_method = 'ziina', so from here the sweep leaves it alone and it stops
        # being half an hour from cancellation. It becomes exactly the order it would
        # have been had they chosen cash at checkout, and is announced the same way.
        row = fetch_one(
            """update orders set payment_method = 'cod'
               where id = %s and payment_status is distinct from 'paid'
                 and status is distinct from 'cancelled'
               returning *""", [oid])
        if not row:
            raise HTTPException(409, "This order can no longer be changed")
        row["items"] = fetch_all(
            "select product_id, name, price, qty from order_items where order_id = %s", [oid])
        _after_commit(oid, "manager alert", lambda: _alert_managers(row))
        _after_commit(oid, "manager bell", lambda: _notify_new_order_admins(row))
        _after_commit(oid, "customer confirmation", lambda: _send_order_whatsapp(row, request))
        _after_commit(oid, "customer e-mail",
                      lambda: _send_order_email(row, _guest_email_for(row), request))
        _after_commit(oid, "audit row", lambda: log_action(
            user_id=row["user_id"], action="payment_switched_to_cod",
            detail={"order_id": oid, "total": row["total"]}, request=request))
        return {"method": "cod"}

    # Card. Reuse the intent this order already has when Ziina still considers it
    # live: handing out a second payment page for the same order is how somebody ends
    # up paying twice, and only one of the two ids would be the one the sweep asks
    # about afterwards.
    success_url, cancel_url = _payment_urls(oid, order["track_token"], request)
    if order["ziina_payment_id"]:
        try:
            live = get_payment_intent(order["ziina_payment_id"])
            if live.get("status") == "completed":
                # they had paid after all, and nobody had noticed yet
                mark_paid(order, request, by="resume")
                return {"paid": True}
            if live.get("status") not in FAILED_STATUSES and live.get("redirect_url"):
                return {"redirect_url": live["redirect_url"]}
        except HTTPException:
            pass   # couldn't ask; fall through and start a fresh one

    intent = create_payment_intent(
        amount_fils=round(float(order["total"]) * 100),
        success_url=success_url, cancel_url=cancel_url,
        message=f"دكّان كنعان — طلب #{oid[:8]}",
    )
    execute("update orders set ziina_payment_id = %s, payment_method = 'ziina' where id = %s",
            [intent.get("id"), oid])
    log_action(user_id=order["user_id"], action="payment_resumed",
               detail={"order_id": oid, "total": order["total"]}, request=request)
    return {"redirect_url": intent.get("redirect_url")}


@router.patch("/{oid}/status")
def set_status(oid: str, request: Request, _m=Depends(require_manager), payload: dict = Body(default={})):
    status = payload.get("status")
    if status not in ("pending", "paid", "preparing", "fulfilled", "delivered", "cancelled"):
        raise HTTPException(400, "Invalid status")
    # One transaction, and the read that decides is locked. `was` is what says whether
    # the goods are on the shelf right now, so two managers on the same order — or one
    # double-tap — must not both read the old status and move the same stock twice.
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("select status from orders where id = %s for update", [oid])
        before = cur.fetchone()
        if not before:
            raise HTTPException(404, "Order not found")
        was = before["status"]
        cur.execute("update orders set status = %s where id = %s returning *", [status, oid])
        row = cur.fetchone()
        # add the point the customer's tracking timeline reads
        cur.execute("insert into order_status_events (order_id, status) values (%s, %s)", [oid, status])
        # A manager cancelling by hand is the shop deciding the order is dead, and the
        # shelf has been holding its units since checkout — nothing else gives them
        # back on this path. Reviving a cancelled order takes them off again, the same
        # way settling a cancelled payment does (see mark_paid).
        if status == "cancelled" and was in _HOLDS_STOCK:
            cur.execute(_RESTORE_STOCK, [oid])
        elif was == "cancelled" and status in _HOLDS_STOCK:
            cur.execute(_RESERVE_STOCK, [oid])
    # notify the customer their order status changed. An account holder gets the
    # in-app notification and the push; a guest has neither, and until this was wired
    # to WhatsApp was never told anything at all.
    #
    # Only on a real change: re-selecting the status an order already has, or a retried
    # request, would otherwise cost the customer a repeat message and the shop a repeat
    # bill. The event row above is still written, so the timeline keeps every touch.
    if was == status:
        return {"order": row}
    label = STATUS_LABELS.get(status, status)
    if row.get("user_id"):
        notify_users([row["user_id"]], type="order_status",
                     title="تحديث حالة طلبك",
                     body=f"طلب #{oid[:8]}: {label}", order_id=oid)
    _send_order_whatsapp(row, request, status_label=label)
    return {"order": row}


@router.delete("/{oid}")
def hide_order(oid: str, _m=Depends(require_manager)):
    """Soft-delete: hide the order from every list without erasing it (kept for
    records/accounting). It simply stops showing."""
    row = fetch_one("update orders set hidden = true where id = %s returning id", [oid])
    if not row:
        raise HTTPException(404, "Order not found")
    return {"hidden": True}
