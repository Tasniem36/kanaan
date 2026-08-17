"""Stock accounting at checkout.

Regression cover for an oversell bug: duplicate line items for the same product
were each validated against stock independently, so a basket carrying the same
product on two lines could pass the check and drive stock negative-in-effect.
Quantities are now merged per product *before* validation.

The DB is faked at the cursor level so the whole transaction body runs.
"""
import contextlib

import pytest
from fastapi import HTTPException

import routers.orders as orders_mod

PID_A = "aaaaaaaa-0000-0000-0000-000000000001"
PID_B = "aaaaaaaa-0000-0000-0000-000000000002"


class FakeCursor:
    """Answers the handful of queries create_order runs, and records the writes."""

    def __init__(self, stock):
        self.stock = stock          # {product_id: units available}
        self.statements = []        # [(normalised sql, params)]
        self._rows = []
        self.description = True

    def execute(self, sql, params=None):
        flat = " ".join(sql.split()).lower()
        self.statements.append((flat, list(params or [])))
        if flat.startswith("select id, name, price, stock from products"):
            wanted = params[0]
            self._rows = [
                {"id": p, "name": f"product-{p[-1]}", "price": 10, "stock": self.stock[p]}
                for p in wanted if p in self.stock
            ]
        elif flat.startswith("insert into orders"):
            self._rows = [{"id": "order-1", "status": "pending", "total": params[7]}]
        else:
            self._rows = []
        return self

    def fetchall(self):
        return self._rows


class FakePool:
    def __init__(self, cursor):
        self.cursor = cursor

    @contextlib.contextmanager
    def connection(self):
        pool_cursor = self.cursor

        class Conn:
            @contextlib.contextmanager
            def transaction(self):
                yield

            @contextlib.contextmanager
            def cursor(self):
                yield pool_cursor

        yield Conn()


@pytest.fixture
def checkout(monkeypatch):
    """Run create_order against fake stock; returns (result_or_error, cursor)."""
    def _run(items, stock):
        cur = FakeCursor(stock)
        monkeypatch.setattr(orders_mod, "pool", FakePool(cur))
        monkeypatch.setattr(orders_mod, "log_action", lambda **k: None)
        monkeypatch.setattr(orders_mod, "notify_new_order", lambda o: None)
        monkeypatch.setattr(orders_mod, "_notify_new_order_admins", lambda o: None)
        monkeypatch.setattr(orders_mod, "compute_delivery_fee", lambda city, total: 0)

        payload = {
            "customer_name": "Cust", "phone": "0501234567",
            "city": "دبي", "street": "st", "house": "1", "items": items,
        }
        try:
            return orders_mod.create_order(
                request=type("R", (), {"headers": {}})(),
                user={"id": "u1", "role": "shopper"},
                payload=payload,
            ), cur
        except HTTPException as e:
            return e, cur
    return _run


def _stock_update(cur):
    """The single batched stock decrement, as (product_ids, quantities)."""
    for sql, params in cur.statements:
        if sql.startswith("update products p set stock = p.stock - u.qty"):
            return params[0], params[1]
    return None, None


# --- the oversell regression ------------------------------------------------
def test_duplicate_lines_for_one_product_are_summed_before_the_stock_check():
    """Two lines of qty 1 on a product with 1 left must be rejected, not accepted
    as "1 <= 1" twice."""
    cur = FakeCursor({PID_A: 1})
    import routers.orders as m
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(m, "pool", FakePool(cur))
        mp.setattr(m, "log_action", lambda **k: None)
        with pytest.raises(HTTPException) as e:
            m.create_order(
                request=type("R", (), {"headers": {}})(),
                user={"id": "u1", "role": "shopper"},
                payload={
                    "customer_name": "C", "phone": "0501234567", "city": "دبي",
                    "street": "s", "house": "1",
                    "items": [{"product_id": PID_A, "qty": 1}, {"product_id": PID_A, "qty": 1}],
                },
            )
    assert e.value.status_code == 409, "should refuse: 2 wanted, 1 in stock"


def test_duplicate_lines_within_stock_are_merged_into_one_decrement(checkout):
    result, cur = checkout(
        [{"product_id": PID_A, "qty": 1}, {"product_id": PID_A, "qty": 2}],
        {PID_A: 5},
    )
    assert not isinstance(result, HTTPException), getattr(result, "detail", result)
    pids, qtys = _stock_update(cur)
    assert pids == [PID_A], "the product should appear once"
    assert qtys == [3], "quantities should be summed"


def test_stock_is_decremented_once_per_product_in_one_statement(checkout):
    result, cur = checkout(
        [{"product_id": PID_A, "qty": 2}, {"product_id": PID_B, "qty": 1}],
        {PID_A: 5, PID_B: 5},
    )
    assert not isinstance(result, HTTPException)
    decrements = [s for s, _ in cur.statements if s.startswith("update products p set stock")]
    assert len(decrements) == 1, "the whole basket should be one UPDATE, not one per line"
    pids, qtys = _stock_update(cur)
    assert dict(zip(pids, qtys)) == {PID_A: 2, PID_B: 1}


def test_order_items_are_inserted_in_one_statement(checkout):
    result, cur = checkout(
        [{"product_id": PID_A, "qty": 1}, {"product_id": PID_B, "qty": 1}],
        {PID_A: 5, PID_B: 5},
    )
    assert not isinstance(result, HTTPException)
    inserts = [s for s, _ in cur.statements if s.startswith("insert into order_items")]
    assert len(inserts) == 1


# --- validation -------------------------------------------------------------
def test_more_than_available_is_refused(checkout):
    result, _ = checkout([{"product_id": PID_A, "qty": 6}], {PID_A: 5})
    assert isinstance(result, HTTPException) and result.status_code == 409


def test_exactly_available_is_allowed(checkout):
    result, _ = checkout([{"product_id": PID_A, "qty": 5}], {PID_A: 5})
    assert not isinstance(result, HTTPException)


def test_unknown_product_is_refused(checkout):
    result, _ = checkout([{"product_id": PID_A, "qty": 1}], {PID_B: 5})
    assert isinstance(result, HTTPException) and result.status_code == 400


@pytest.mark.parametrize("qty", [0, -3, "abc", None])
def test_non_positive_quantities_are_refused(checkout, qty):
    result, _ = checkout([{"product_id": PID_A, "qty": qty}], {PID_A: 5})
    assert isinstance(result, HTTPException) and result.status_code == 400


@pytest.mark.parametrize("pid", ["not-a-uuid", "", None, 123, "'; drop table products; --"])
def test_a_malformed_product_id_is_a_400_not_a_500(checkout, pid):
    """It reaches a ::uuid[] cast, which would otherwise blow up as a server error."""
    result, _ = checkout([{"product_id": pid, "qty": 1}], {PID_A: 5})
    assert isinstance(result, HTTPException), f"{pid!r} should have been rejected"
    assert result.status_code == 400


def test_empty_basket_is_refused(checkout):
    result, _ = checkout([], {PID_A: 5})
    assert isinstance(result, HTTPException) and result.status_code == 400


# --- the tracking timeline gets its first event -----------------------------
def test_placing_an_order_records_its_first_status_event(checkout):
    """The customer's timeline reads from order_status_events, so a missing first
    row would show a blank tracker on a brand-new order."""
    result, cur = checkout([{"product_id": PID_A, "qty": 1}], {PID_A: 5})
    assert not isinstance(result, HTTPException)
    events = [(s, p) for s, p in cur.statements if s.startswith("insert into order_status_events")]
    assert len(events) == 1
    assert events[0][1] == ["order-1", "pending"]
