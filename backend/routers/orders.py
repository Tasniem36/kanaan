import os
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from db import pool, fetch_all, fetch_one, execute
from security import current_user, require_manager
from validate import normalize_uae_phone
from audit import log_action
from ziina import create_payment_intent, get_payment_intent
from notify import notify_new_order
from notifications import notify_managers, notify_users
from delivery import compute_fee as compute_delivery_fee
from routers.discounts import evaluate_code

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


@router.post("")
def create_order(request: Request, user=Depends(current_user), payload: dict = Body(default={})):
    customer_name = payload.get("customer_name")
    city, street, house = payload.get("city"), payload.get("street"), payload.get("house")
    payment_method = "ziina" if payload.get("payment_method") == "ziina" else "cod"
    if not customer_name or not payload.get("phone") or not city or not street or not house:
        raise HTTPException(400, "Please complete the required fields")
    phone_norm = normalize_uae_phone(payload.get("phone"))
    if not phone_norm:
        raise HTTPException(400, "Invalid UAE phone number")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise HTTPException(400, "Your cart is empty")

    with pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
        def run(sql, params=None):
            cur.execute(sql, params or [])
            return cur.fetchall() if cur.description else []

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
                raise HTTPException(409, f"Not enough stock for “{p['name']}”")
            total += float(p["price"]) * qty
            lines.append({"product_id": str(p["id"]), "name": p["name"], "price": float(p["price"]), "qty": qty})

        discount, discount_code = 0, None
        if payload.get("code"):
            r = evaluate_code(run, payload["code"], user["id"], total)
            if r.get("error"):
                raise HTTPException(400, r["error"])
            discount, discount_code = r["discount"], r["dc"]["code"]
        # delivery fee (recomputed server-side from the delivery city + subtotal)
        delivery_fee = compute_delivery_fee(city, total)
        final_total = max(0, round((total - discount + delivery_fee) * 100) / 100)

        order = run(
            """insert into orders (user_id, customer_name, phone, city, street, house, notes, total,
                                   payment_method, discount_code, discount_amount, delivery_fee)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning *""",
            [user["id"], customer_name, phone_norm, city, street, house, payload.get("notes"),
             final_total, payment_method, discount_code, discount, delivery_fee],
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

    log_action(user_id=user["id"], action="order_placed",
               detail={"order_id": str(order["id"]), "total": order["total"],
                       "payment_method": payment_method, "discount_code": discount_code}, request=request)

    if payment_method == "ziina":
        app_url = os.getenv("APP_URL") or request.headers.get("origin") or ""
        oid = str(order["id"])
        try:
            intent = create_payment_intent(
                amount_fils=round(final_total * 100),
                success_url=f"{app_url}/pay/return?order={oid}",
                cancel_url=f"{app_url}/pay/return?order={oid}&cancel=1",
                message=f"دكّان كنعان — طلب #{oid[:8]}",
            )
            execute("update orders set ziina_payment_id = %s where id = %s", [intent.get("id"), oid])
            return {"order": order, "redirect_url": intent.get("redirect_url")}
        except HTTPException:
            cancel_and_restore(oid)
            raise

    notify_new_order(order)  # COD: alert the manager now (Ziina alerts once paid)
    _notify_new_order_admins(order)  # in-app bell for managers
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


def _own_order_or_404(oid, user):
    """Fetch an order the caller is allowed to act on. 404 (not 403) for orders
    that aren't theirs, so order ids can't be probed for existence."""
    order = fetch_one("select * from orders where id = %s", [oid])
    if not order or (user["role"] != "manager" and str(order["user_id"]) != str(user["id"])):
        raise HTTPException(404, "Order not found")
    return order


@router.post("/{oid}/confirm-payment")
def confirm_payment(oid: str, request: Request, user=Depends(current_user)):
    order = _own_order_or_404(oid, user)
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
def cancel_payment(oid: str, user=Depends(current_user)):
    order = _own_order_or_404(oid, user)
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
