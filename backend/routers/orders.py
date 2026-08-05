import os

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from db import pool, fetch_all, fetch_one, execute
from security import current_user, require_manager
from validate import normalize_uae_phone
from audit import log_action
from ziina import create_payment_intent, get_payment_intent
from notify import notify_new_order, send_test_notification
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
        cur.execute("select product_id, qty from order_items where order_id = %s", [order_id])
        for it in cur.fetchall():
            if it["product_id"]:
                cur.execute("update products set stock = stock + %s where id = %s", [it["qty"], it["product_id"]])
        cur.execute("update orders set status = 'cancelled' where id = %s", [order_id])


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

        ids = [i.get("product_id") for i in items]
        products = run("select id, name, price, stock from products where id = any(%s::uuid[]) for update", [ids])
        by_id = {str(p["id"]): p for p in products}

        total = 0.0
        lines = []
        for item in items:
            p = by_id.get(item.get("product_id"))
            try:
                qty = int(item.get("qty"))
            except (TypeError, ValueError):
                qty = 0
            if not p:
                raise HTTPException(400, "Product not found")
            if qty <= 0:
                raise HTTPException(400, "Invalid quantity")
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
        for line in lines:
            run("insert into order_items (order_id, product_id, name, price, qty) values (%s, %s, %s, %s, %s)",
                [order["id"], line["product_id"], line["name"], line["price"], line["qty"]])
            run("update products set stock = stock - %s where id = %s", [line["qty"], line["product_id"]])
        if discount_code:
            run("update discount_codes set used_count = used_count + 1 where code = %s", [discount_code])
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


@router.post("/notify-test")
def notify_test(_m=Depends(require_manager)):
    return send_test_notification()


@router.get("")
def list_orders(user=Depends(current_user)):
    is_manager = user["role"] == "manager"
    if is_manager:
        orders = fetch_all("select * from orders where not hidden order by created_at desc")
    else:
        orders = fetch_all("select * from orders where user_id = %s and not hidden order by created_at desc", [user["id"]])
    if orders:
        ids = [o["id"] for o in orders]
        items = fetch_all("select order_id, name, price, qty from order_items where order_id = any(%s::uuid[])", [ids])
        by = {}
        for it in items:
            by.setdefault(str(it["order_id"]), []).append(it)
        for o in orders:
            o["items"] = by.get(str(o["id"]), [])
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
