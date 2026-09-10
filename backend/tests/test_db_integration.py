"""SQL that must genuinely execute — run against a real PostgreSQL.

The rest of the suite patches the database out, which is fast but can't catch a
malformed window function, a broken CTE, or revenue arithmetic that's off. These
tests apply the real db/schema.sql to a scratch database and exercise the queries
end to end.

SKIPPED unless a server is pointed at, so `pytest` stays offline by default:

    TEST_PG_DSN=postgresql://postgres@127.0.0.1:5432/postgres pytest

The scratch database (dukkan_pytest) is dropped and recreated per run, so never
aim this at anything you care about.
"""
import datetime
import os
import pathlib
import threading

import pytest
from fastapi import Response

DSN = os.getenv("TEST_PG_DSN")
SCRATCH = "dukkan_pytest"

pytestmark = pytest.mark.skipif(
    not DSN, reason="set TEST_PG_DSN to run the database integration tests"
)

SCHEMA = pathlib.Path(__file__).resolve().parent.parent / "db" / "schema.sql"

U_CUST = "11111111-1111-1111-1111-111111111111"
U_MGR = "22222222-2222-2222-2222-222222222222"
P_OIL = "aaaaaaaa-0000-0000-0000-000000000001"
P_ZAATAR = "aaaaaaaa-0000-0000-0000-000000000002"
P_PLATE = "aaaaaaaa-0000-0000-0000-000000000003"
P_CUP = "aaaaaaaa-0000-0000-0000-000000000004"
O_DONE = "bbbbbbbb-0000-0000-0000-000000000001"
O_PREP = "bbbbbbbb-0000-0000-0000-000000000002"
O_ABANDONED = "bbbbbbbb-0000-0000-0000-000000000003"
O_CANCELLED = "bbbbbbbb-0000-0000-0000-000000000004"
# a manager opens any order, so these tests need no tracking token
_MGR_USER = {"id": U_MGR, "role": "manager"}

SEED = f"""
insert into users (id, email, password_hash, full_name, role) values
  ('{U_CUST}', 'c@x.com', 'h', 'Cust', 'customer'),
  ('{U_MGR}',  'm@x.com', 'h', 'Mgr',  'manager');

insert into products (id, name, name_en, description, description_en, price, unit,
                      category, type, stock, sort) values
  ('{P_OIL}',    'زيت زيتون', 'Olive Oil', 'عصرة أولى', 'First press', 55.00, 'لتر', 'pantry', 'oil',    10, 0),
  ('{P_ZAATAR}', 'زعتر',      null,        'بلدي',      null,          20.00, 'كغ',  'pantry', 'herbs',   3, 1),
  ('{P_PLATE}',  'صحن فخار',  'Clay Plate', null,       null,          75.00, 'حبة', 'pottery','plates',  0, 2),
  ('{P_CUP}',    'كوب فخار',  'Clay Cup',  null,        null,          30.00, 'حبة', 'pottery','cups',    7, 3);

-- two real orders (130 + 55), one abandoned online payment, one cancelled
insert into orders (id, user_id, customer_name, phone, city, street, house,
                    status, total, payment_method, payment_status) values
  ('{O_DONE}',      '{U_CUST}', 'Cust', '0501234567', 'دبي', 's', '1', 'delivered', 130.00, 'cod',   'unpaid'),
  ('{O_PREP}',      '{U_CUST}', 'Cust', '0501234567', 'دبي', 's', '1', 'preparing',  55.00, 'ziina', 'paid'),
  ('{O_ABANDONED}', '{U_CUST}', 'Cust', '0501234567', 'دبي', 's', '1', 'pending',    99.00, 'ziina', 'unpaid'),
  ('{O_CANCELLED}', '{U_CUST}', 'Cust', '0501234567', 'دبي', 's', '1', 'cancelled', 500.00, 'cod',   'unpaid');

insert into order_items (order_id, product_id, name, price, qty) values
  ('{O_DONE}', '{P_OIL}',    'زيت زيتون', 55.00, 2),
  ('{O_DONE}', '{P_ZAATAR}', 'زعتر',      20.00, 1),
  ('{O_PREP}', '{P_OIL}',    'زيت زيتون', 55.00, 1);

insert into order_status_events (order_id, status) values
  ('{O_DONE}', 'pending'), ('{O_DONE}', 'preparing'), ('{O_DONE}', 'delivered');

insert into wishlists (user_id, product_id) values ('{U_CUST}', '{P_OIL}');
insert into stock_alerts (user_id, product_id) values ('{U_CUST}', '{P_PLATE}');
"""


@pytest.fixture(scope="module")
def live_db():
    """Build the scratch database and point db.pool at it for the whole module."""
    import psycopg
    from psycopg.rows import dict_row
    from conftest import REAL_CONNECTION_POOL

    with psycopg.connect(DSN, autocommit=True) as admin:
        admin.execute(f"drop database if exists {SCRATCH}")
        admin.execute(f"create database {SCRATCH}")

    scratch_dsn = DSN.rsplit("/", 1)[0] + "/" + SCRATCH
    with psycopg.connect(scratch_dsn, autocommit=True) as conn:
        conn.execute(SCHEMA.read_text(encoding="utf-8"))

    import db
    import routers.orders
    pool = REAL_CONNECTION_POOL(scratch_dsn, min_size=1, max_size=3, open=True,
                                kwargs={"row_factory": dict_row})

    # db.fetch_all/execute read db.pool at call time, but modules that did
    # `from db import pool` hold their own reference — swap those too, or they
    # keep talking to conftest's stub.
    holders = [db, routers.orders]
    originals = [(m, m.pool) for m in holders if hasattr(m, "pool")]
    for module in holders:
        if hasattr(module, "pool"):
            module.pool = pool

    yield pool

    for module, original in originals:
        module.pool = original
    pool.close()
    with psycopg.connect(DSN, autocommit=True) as admin:
        admin.execute(f"drop database if exists {SCRATCH}")


@pytest.fixture(autouse=True)
def fresh_data(live_db):
    """Reset the rows before every test.

    The schema is built once, but several tests here restock, cancel, or save
    products — without this each would inherit the previous one's mutations and
    start failing in whatever order pytest happened to pick.
    """
    # Settling and releasing write their audit row on a background thread. One still
    # in flight when the truncate below reaches for its lock deadlocks against it —
    # which surfaces as a random earlier test erroring, nowhere near the cause.
    import background
    background.wait_all(5)
    with live_db.connection() as conn:
        # cascades clear order_items, events, wishlists, stock_alerts, notifications.
        # discount_codes hangs off nothing (an order keeps the code as text), so it has
        # to be named here or a code created by one test is still there for the next.
        conn.execute("truncate table users, products, orders, audit_logs, discount_codes cascade")
        conn.execute(SEED)
        conn.commit()
    yield


class Req:
    """Minimal stand-in for a Starlette Request."""
    def __init__(self, **params):
        self.query_params = params
        self.headers = {"host": "dukkan-kanaan.com", "x-forwarded-proto": "https"}
        self.url = type("U", (), {"scheme": "https", "netloc": "dukkan-kanaan.com"})()


# --- schema -----------------------------------------------------------------
def test_schema_is_idempotent(live_db):
    """Deploys re-run schema.sql every time; a non-idempotent statement would
    break the next release rather than the one that introduced it."""
    with live_db.connection() as conn:
        conn.execute(SCHEMA.read_text(encoding="utf-8"))
        conn.execute(SCHEMA.read_text(encoding="utf-8"))


# --- product listing --------------------------------------------------------
def _list(**kw):
    import routers.products as p
    return p.list_products(Req(active="1", **kw))


def test_window_count_returns_the_full_total_while_paging(live_db):
    page = _list(limit="2", offset="0")
    assert len(page["products"]) == 2
    assert page["total"] == 4, "total must be all matches, not the page size"


def test_price_filter_and_sort_execute(live_db):
    rows = _list(min_price="25", max_price="60")["products"]
    assert sorted(float(r["price"]) for r in rows) == [30.0, 55.0]


def test_sold_out_products_sort_last_on_the_storefront(live_db):
    rows = _list(sort="price_desc")["products"]
    prices = [float(r["price"]) for r in rows]
    assert prices == [55.0, 30.0, 20.0, 75.0], (
        "in-stock descending, then the sold-out 75 — got " + str(prices)
    )


def test_search_matches_either_language(live_db):
    assert _list(q="Olive")["total"] == 1
    assert _list(q="زيت")["total"] == 1
    assert _list(q="First press")["total"] == 1, "English description should match"
    assert _list(q="بلدي")["total"] == 1, "Arabic description should match"


def test_related_products_query_runs_and_ranks_by_type(live_db):
    import routers.products as p
    rows = p.related_products(P_CUP)["products"]
    assert rows, "should suggest something"
    assert all(r["category"] == "pottery" for r in rows)
    assert all(r["id"] != P_CUP for r in rows)


def test_related_products_on_an_unknown_id_is_empty(live_db):
    import routers.products as p
    assert p.related_products("aaaaaaaa-0000-0000-0000-0000000000ff")["products"] == []


# --- stock alerts + the update CTE -----------------------------------------
def test_restock_notifies_waiters_exactly_once(live_db):
    import routers.products as p
    from db import fetch_all

    p.restock(P_PLATE, payload={"qty": 5})
    fired = fetch_all("select 1 from notifications where user_id = %s and type = 'back_in_stock'", [U_CUST])
    assert len(fired) == 1, "the waiting customer should be told"
    assert fetch_all("select 1 from stock_alerts where product_id = %s", [P_PLATE]) == []

    p.restock(P_PLATE, payload={"qty": 5})
    fired = fetch_all("select 1 from notifications where user_id = %s and type = 'back_in_stock'", [U_CUST])
    assert len(fired) == 1, "a later restock must not re-notify"


def test_update_products_cte_returns_the_pre_edit_stock(live_db):
    """The 0 → N detection rides on a CTE in the same statement; if it broke, a
    manual restock via the edit form would silently skip the waiting list."""
    import routers.products as p
    from db import fetch_one

    p.update_product(P_CUP, payload={"stock": 0})
    row = p.update_product(P_CUP, payload={"stock": 4})["product"]
    assert row["stock"] == 4
    assert "prev_stock" not in row, "internal column must not reach the client"
    assert fetch_one("select updated_at from products where id = %s", [P_CUP])["updated_at"] is not None


def test_translations_round_trip_and_blank_becomes_null(live_db):
    import routers.products as p
    from db import fetch_one

    p.update_product(P_ZAATAR, payload={"name_en": "  Wild Za'atar  "})
    assert fetch_one("select name_en from products where id = %s", [P_ZAATAR])["name_en"] == "Wild Za'atar"
    p.update_product(P_ZAATAR, payload={"name_en": "   "})
    assert fetch_one("select name_en from products where id = %s", [P_ZAATAR])["name_en"] is None, (
        "a cleared translation must be NULL so the Arabic fallback applies"
    )


# --- orders -----------------------------------------------------------------
def test_order_list_attaches_items_and_timeline_events(live_db):
    import routers.orders as o
    orders = o.list_orders(user={"id": U_CUST, "role": "customer"})["orders"]
    done = next(x for x in orders if str(x["id"]) == O_DONE)
    assert len(done["items"]) == 2
    assert [e["status"] for e in done["events"]] == ["pending", "preparing", "delivered"], (
        "events must come back in chronological order for the stepper"
    )


@pytest.fixture
def unpaid_order(live_db):
    """O_ABANDONED with one litre of oil on it. cancel_and_restore is the payment
    path, and the only order it is ever right to release is one nobody has paid for —
    so a paid fixture cannot stand in for one here."""
    from db import execute
    execute("""insert into order_items (order_id, product_id, name, price, qty)
               values (%s, %s, 'زيت زيتون', 55.00, 1)""", [O_ABANDONED, P_OIL])
    return O_ABANDONED


def test_a_paid_order_is_never_released_by_the_payment_path(live_db):
    """The mirror image of the settle race. The sweep reads an order as unresolved,
    the customer's browser settles it a second later, and the stale snapshot comes
    back to release it — putting stock back for an order that was paid for and
    burying it as cancelled. Only the locked row knows, so the claim asks it."""
    import routers.orders as o
    from db import fetch_one

    before = _stock(P_OIL)
    assert o.cancel_and_restore(O_PREP, why="expired") is False
    assert _stock(P_OIL) == before, "its stock stays where a paid order needs it"
    assert fetch_one("select status from orders where id = %s", [O_PREP])["status"] == "preparing"


def test_cancel_restores_stock_in_one_statement(live_db, unpaid_order):
    import routers.orders as o
    from db import fetch_one

    before = fetch_one("select stock from products where id = %s", [P_OIL])["stock"]
    o.cancel_and_restore(unpaid_order)   # this order holds 1 unit of the oil
    after = fetch_one("select stock from products where id = %s", [P_OIL])["stock"]
    assert after == before + 1
    assert fetch_one("select status from orders where id = %s", [unpaid_order])["status"] == "cancelled"
    assert fetch_one(
        "select 1 as x from order_status_events where order_id = %s and status = 'cancelled'", [unpaid_order]
    ), "cancelling should land on the timeline too"


def test_cancelling_twice_restores_the_stock_once(live_db, unpaid_order):
    """A reloaded /pay/return?…&cancel=1 calls this twice, as does a return page racing
    the reconcile sweep. Putting the same litre back a second time invents stock the
    shelf hasn't got, and the shop oversells it."""
    import routers.orders as o
    from db import fetch_one

    before = fetch_one("select stock from products where id = %s", [P_OIL])["stock"]
    assert o.cancel_and_restore(unpaid_order) is True
    assert o.cancel_and_restore(unpaid_order) is False, "the second call has nothing to cancel"
    after = fetch_one("select stock from products where id = %s", [P_OIL])["stock"]
    assert after == before + 1
    assert fetch_one(
        """select count(*) as n from order_status_events
           where order_id = %s and status = 'cancelled'""", [unpaid_order])["n"] == 1


def test_settling_the_same_order_twice_pays_it_once(live_db, monkeypatch):
    """The return page's polling and the cron sweep can both reach mark_paid for one
    order, each having read payment_status earlier. Only the write can decide."""
    import routers.orders as o
    from db import execute, fetch_all, fetch_one

    for quiet in ("notify_new_order", "_notify_new_order_admins", "_send_order_whatsapp"):
        monkeypatch.setattr(o, quiet, lambda *a, **k: None)
    # the abandoned order was cancelled while its payment was still in flight, so its
    # two bags of za'atar went back on the shelf: settling it takes them off again
    execute("""insert into order_items (order_id, product_id, name, price, qty)
               values (%s, %s, 'زعتر', 20.00, 2)""", [O_ABANDONED, P_ZAATAR])
    execute("update orders set status = 'cancelled' where id = %s", [O_ABANDONED])
    order = fetch_one("select * from orders where id = %s", [O_ABANDONED])
    before = fetch_one("select stock from products where id = %s", [P_ZAATAR])["stock"]

    assert o.mark_paid(order)["payment_status"] == "paid"
    assert o.mark_paid(order) is None, "the second settle finds nothing left to do"

    after = fetch_one("select stock from products where id = %s", [P_ZAATAR])["stock"]
    assert after == before - 2, "one deduction, not two"
    events = fetch_all("select status from order_status_events where order_id = %s", [O_ABANDONED])
    assert [e["status"] for e in events] == ["paid"]


# --- two callers arriving at the same moment ---------------------------------
def test_two_settles_at_once_pay_the_order_once(live_db, monkeypatch):
    """The return page's polling and the cron sweep, arriving together on one order.

    The scripted-cursor tests can show that mark_paid asks the right question; only
    this can show that the answer holds when two callers ask it at the same instant.
    Everything below the claim has to happen exactly once — one deduction, one paid
    event, one row in the shop's record — and the caller that lost has to be told it
    did nothing, so it doesn't go on to bill the customer for a second WhatsApp.
    """
    import background
    import routers.orders as o
    from db import execute, fetch_one

    for quiet in ("notify_new_order", "_notify_new_order_admins", "_send_order_whatsapp"):
        monkeypatch.setattr(o, quiet, lambda *a, **k: None)   # log_action stays real
    # cancelled while the money was in flight, so settling has to take stock off too:
    # the branch with the most to get wrong
    execute("""insert into order_items (order_id, product_id, name, price, qty)
               values (%s, %s, 'زعتر', 20.00, 2)""", [O_ABANDONED, P_ZAATAR])
    execute("update orders set status = 'cancelled' where id = %s", [O_ABANDONED])
    order = fetch_one("select * from orders where id = %s", [O_ABANDONED])
    before = _stock(P_ZAATAR)

    settled, ready = [], threading.Barrier(2)

    def settle():
        ready.wait(5)          # both callers past the gate before either writes
        settled.append(o.mark_paid(order))

    threads = [threading.Thread(target=settle) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(15)
    assert not any(t.is_alive() for t in threads), "a settle never finished — a deadlock?"
    background.wait_all(5)     # the audit rows go out on their own threads

    assert sum(r is not None for r in settled) == 1, "one caller settled it, one was told it didn't"
    assert _stock(P_ZAATAR) == before - 2, "one deduction, not two"
    assert fetch_one("""select count(*) as n from order_status_events
                        where order_id = %s and status = 'paid'""", [O_ABANDONED])["n"] == 1
    assert fetch_one("""select count(*) as n from audit_logs
                        where action = 'payment_confirmed'""")["n"] == 1


def test_two_cancels_at_once_release_the_order_once(live_db, unpaid_order):
    """The same race on the other path: a reloaded /pay/return?…&cancel=1 against the
    sweep. Putting the same litre back twice invents stock the shelf hasn't got."""
    import background
    import routers.orders as o
    from db import fetch_one

    before = _stock(P_OIL)
    released, ready = [], threading.Barrier(2)

    def release():
        ready.wait(5)
        released.append(o.cancel_and_restore(unpaid_order, why="expired"))

    threads = [threading.Thread(target=release) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(15)
    assert not any(t.is_alive() for t in threads), "a cancel never finished — a deadlock?"
    background.wait_all(5)

    assert sorted(released) == [False, True], "one of them cancelled it, the other did not"
    assert _stock(P_OIL) == before + 1, "one litre back, not two"
    assert fetch_one("""select count(*) as n from audit_logs
                        where action = 'payment_released'""")["n"] == 1


def test_the_sweep_does_not_release_a_payment_that_landed_while_it_asked(live_db, monkeypatch):
    """The same race end to end, through reconcile() itself rather than the helper.

    This is how it actually reaches the shop: the sweep asks Ziina about a stale order
    and is told it is still undecided, the customer's browser settles the payment while
    that answer is on the wire, and the sweep then acts on what it was told. Its
    decision is a snapshot; only the claim inside cancel_and_restore sees the order as
    it is by then.

    Left unguarded this is the worst outcome the shop can produce — charged, confirmed
    on WhatsApp, then cancelled behind the customer with the goods they paid for back
    on the shelf, and no second chance: unresolved_orders stops looking at a paid order.
    """
    import background
    import reconcile as rec
    import routers.orders as o
    from db import execute, fetch_all, fetch_one

    for quiet in ("notify_new_order", "_notify_new_order_admins",
                  "_send_order_whatsapp", "_send_order_email"):
        monkeypatch.setattr(o, quiet, lambda *a, **k: None)   # log_action stays real
    # an abandoned ziina checkout, old enough that the sweep reads it as given up on,
    # still holding the two bags of za'atar it reserved
    execute("""insert into order_items (order_id, product_id, name, price, qty)
               values (%s, %s, 'زعتر', 20.00, 2)""", [O_ABANDONED, P_ZAATAR])
    execute("""update orders set created_at = now() - interval '45 minutes',
                                 ziina_payment_id = 'pi_race' where id = %s""", [O_ABANDONED])
    before = _stock(P_ZAATAR)

    def ziina_still_deciding(pid):
        # the return page gets its answer first, while this one is still in flight
        o.mark_paid(fetch_one("select * from orders where id = %s", [O_ABANDONED]))
        return {"status": "pending"}

    monkeypatch.setattr(rec, "get_payment_intent", ziina_still_deciding)
    counts = rec.reconcile(apply=True)
    background.wait_all(5)

    row = fetch_one("select status, payment_status from orders where id = %s", [O_ABANDONED])
    assert row["payment_status"] == "paid"
    assert row["status"] != "cancelled", "the sweep buried an order that had just been paid for"
    assert _stock(P_ZAATAR) == before, "stock the customer paid for went back on the shelf"
    assert (counts["cancelled"], counts["already"]) == (0, 1), \
        "the sweep should report it found nothing left to release, not a release"
    assert [r["action"] for r in fetch_all("select action from audit_logs")] == ["payment_confirmed"]


# --- the shop's record reaches the table, not just the call ------------------
def test_a_swept_payment_leaves_a_row_a_manager_can_read(live_db, monkeypatch):
    """The sweep is the only settler with no other witness — before this its work
    existed solely as a line of stdout in a cron log."""
    import background
    import routers.orders as o
    from db import fetch_one

    for quiet in ("notify_new_order", "_notify_new_order_admins", "_send_order_whatsapp"):
        monkeypatch.setattr(o, quiet, lambda *a, **k: None)
    order = fetch_one("select * from orders where id = %s", [O_ABANDONED])
    assert o.mark_paid(order, by="sweep")
    background.wait_all(5)

    row = fetch_one("select * from audit_logs where action = 'payment_confirmed'")
    assert row["detail"]["by"] == "sweep"
    assert row["detail"]["order_id"] == O_ABANDONED
    assert str(row["user_id"]) == U_CUST


# --- a manager's status change moves the stock with it ----------------------
@pytest.fixture
def quiet_orders(monkeypatch):
    """No WhatsApp, no bell — these tests are about the shelf."""
    import routers.orders as o
    monkeypatch.setattr(o, "_send_order_whatsapp", lambda *a, **k: None)
    monkeypatch.setattr(o, "notify_users", lambda *a, **k: None)
    return o


def _stock(pid):
    from db import fetch_one
    return fetch_one("select stock from products where id = %s", [pid])["stock"]


def test_a_manager_cancelling_an_order_puts_its_stock_back(live_db, quiet_orders):
    """Nothing else does it on this path: the shelf has held that litre since checkout
    and the order is now dead. Cancelling twice must not put it back twice."""
    before = _stock(P_OIL)
    quiet_orders.set_status(O_PREP, request=None, _m=None, payload={"status": "cancelled"})
    assert _stock(P_OIL) == before + 1
    quiet_orders.set_status(O_PREP, request=None, _m=None, payload={"status": "cancelled"})
    assert _stock(P_OIL) == before + 1, "a second cancel is not a second litre"


def test_reviving_a_cancelled_order_takes_its_stock_off_again(live_db, quiet_orders):
    before = _stock(P_OIL)
    quiet_orders.set_status(O_PREP, request=None, _m=None, payload={"status": "cancelled"})
    quiet_orders.set_status(O_PREP, request=None, _m=None, payload={"status": "preparing"})
    assert _stock(P_OIL) == before, "the order holds its stock again, or the shop oversells it"


def test_cancelling_a_delivered_order_does_not_invent_stock(live_db, quiet_orders):
    """The goods physically left the shop. Cancelling the paperwork afterwards cannot
    put them back on the shelf — a real return is a manager restocking the product."""
    oil, zaatar = _stock(P_OIL), _stock(P_ZAATAR)
    quiet_orders.set_status(O_DONE, request=None, _m=None, payload={"status": "cancelled"})
    assert (_stock(P_OIL), _stock(P_ZAATAR)) == (oil, zaatar)


# --- dashboard arithmetic ---------------------------------------------------
def test_revenue_counts_only_real_orders(live_db):
    """130 (delivered COD) + 55 (paid Ziina). The abandoned Ziina order and the
    cancelled one must not inflate the figures."""
    import routers.stats as s
    money = s.overview(_m=None)["money"]
    assert float(money["revenue_all"]) == 185.0
    assert money["orders_all"] == 2
    assert round(float(money["aov_30d"]), 2) == 92.5


def test_status_breakdown_covers_every_status(live_db):
    import routers.stats as s
    rows = s.overview(_m=None)["by_status"]
    assert {r["status"] for r in rows} == {
        "pending", "paid", "preparing", "fulfilled", "delivered", "cancelled"
    }, "a status with no orders must still appear, as a zero"


def test_customer_count_excludes_managers(live_db):
    import routers.stats as s
    assert s.overview(_m=None)["customers"]["total"] == 1


def test_top_products_aggregates_across_orders(live_db):
    import routers.stats as s
    top = s.overview(_m=None)["top_products"]
    best = top[0]
    assert best["name"] == "زيت زيتون"
    assert best["qty"] == 3, "2 from one order + 1 from another"
    assert float(best["revenue"]) == 165.0


def test_daily_series_is_gap_filled_to_14_days(live_db):
    """generate_series keeps quiet days as zeros so the chart has no holes."""
    import routers.stats as s
    daily = s.overview(_m=None)["daily"]
    assert len(daily) == 14
    days = [d["day"] for d in daily]
    assert days == sorted(days)
    assert days[-1] == datetime.date.today()


def test_low_stock_list_finds_what_needs_restocking(live_db):
    import routers.stats as s
    low = {r["name"]: r["stock"] for r in s.overview(_m=None)["low_stock"]}
    assert "زعتر" in low and low["زعتر"] == 3


# --- wishlist ---------------------------------------------------------------
def test_wishlist_round_trip(live_db):
    import routers.wishlist as w

    assert [str(p["id"]) for p in w.list_wishlist(user={"id": U_CUST})["products"]] == [P_OIL]
    w.add_to_wishlist(P_CUP, Req(), user={"id": U_CUST})
    w.add_to_wishlist(P_CUP, Req(), user={"id": U_CUST})   # idempotent
    ids = set(w.list_wishlist_ids(user={"id": U_CUST})["ids"])
    assert ids == {P_OIL, P_CUP}

    w.remove_from_wishlist(P_CUP, response=type("R", (), {"status_code": None})(), user={"id": U_CUST})
    assert set(w.list_wishlist_ids(user={"id": U_CUST})["ids"]) == {P_OIL}


def test_wishlist_is_scoped_per_customer(live_db):
    import routers.wishlist as w
    assert w.list_wishlist_ids(user={"id": U_MGR})["ids"] == [], "must not see another account's saves"


# --- discount codes ---------------------------------------------------------
def test_both_kinds_of_discount_code_round_trip(live_db):
    """Percentage and fixed-amount codes both store and evaluate against real SQL."""
    import routers.discounts as d
    from db import fetch_all

    d.create_code(Response(), payload={"code": "TEN", "percent": 10, "first_order_only": False})
    d.create_code(Response(), payload={"code": "OFF30", "amount": 30, "first_order_only": False})

    run = lambda sql, params=None: fetch_all(sql, params)
    assert d.evaluate_code(run, "TEN", U_CUST, 200)["discount"] == 20.0
    assert d.evaluate_code(run, "OFF30", U_CUST, 200)["discount"] == 30.0
    too_small = d.evaluate_code(run, "OFF30", U_CUST, 20)
    assert too_small["reason"] == "min_basket" and too_small["short"] == 10.0


def test_the_database_refuses_a_code_carrying_two_discounts_or_none(live_db):
    """The API validates this, but the constraint is what makes it true of the data."""
    import psycopg
    with live_db.connection() as conn:
        for percent, amount in ((10, 30), (None, None)):
            with pytest.raises(psycopg.errors.CheckViolation):
                conn.execute("insert into discount_codes (code, percent, amount) values (%s, %s, %s)",
                             [f"BAD{percent}{amount}", percent, amount])
            conn.rollback()


def test_a_fixed_amount_discount_survives_a_real_checkout(live_db, auth_mod):
    """The order records the dirhams taken off and the total charged reflects them."""
    import routers.discounts as d
    import routers.orders as o

    d.create_code(Response(), payload={"code": "OFF30", "amount": 30, "first_order_only": False})
    order = o.create_order(Req(), user={"id": U_CUST, "role": "customer"}, payload={
        "customer_name": "ندى", "phone": "0501234567", "city": "دبي", "street": "ش", "house": "1",
        "items": [{"product_id": P_OIL, "qty": 2}], "code": "OFF30"})["order"]

    assert float(order["discount_amount"]) == 30.0
    # 2 × 55 = 110, less 30, plus whatever delivery costs for that city
    assert float(order["total"]) == 110.0 - 30.0 + float(order["delivery_fee"])


# --- forgotten password -----------------------------------------------------
@pytest.fixture
def auth_mod(monkeypatch):
    """routers.auth with the audit trail silenced.

    log_action writes from a background thread, which would still be in flight when
    the next test's `truncate ... cascade` asks for its lock — a deadlock, and one
    that surfaces in whichever test came next rather than this one. The trail itself
    is covered in test_audit_signals.py.
    """
    import routers.auth as auth
    monkeypatch.setattr(auth, "log_action", lambda **k: None)
    return auth


def test_a_forgotten_password_round_trip(live_db, auth_mod):
    """Every statement in the flow against real SQL: the code is written with a live
    expiry, found again, spent, and the password on the account genuinely changes."""
    auth = auth_mod
    from db import fetch_all, fetch_one

    code = auth.password_forgot(Req(), payload={"email": "c@x.com"})["dev_code"]
    row = fetch_one("select * from password_resets where lower(email) = 'c@x.com'")
    assert row["expires_at"] > datetime.datetime.now(datetime.timezone.utc)

    out = auth.password_reset(Req(), payload={"email": "c@x.com", "code": code, "password": "NewPass12"})
    assert out["user"]["email"] == "c@x.com" and out["token"]
    stored = fetch_one("select password_hash from users where email = 'c@x.com'")["password_hash"]
    assert auth.verify_password("NewPass12", stored), "the new password must actually work"
    assert fetch_all("select 1 from password_resets") == [], "and the code is spent"


def test_an_address_with_no_account_leaves_no_trace(live_db, auth_mod):
    auth = auth_mod
    from db import fetch_all

    assert auth.password_forgot(Req(), payload={"email": "nobody@x.com"}) == {"sent": True}
    assert fetch_all("select 1 from password_resets") == []


def test_only_the_newest_reset_code_survives(live_db, auth_mod):
    """Asking twice leaves one row, holding the code from the second e-mail."""
    auth = auth_mod
    from db import fetch_all, fetch_one

    auth.password_forgot(Req(), payload={"email": "c@x.com"})
    fresh = auth.password_forgot(Req(), payload={"email": "c@x.com"})["dev_code"]

    assert len(fetch_all("select 1 from password_resets")) == 1
    row = fetch_one("select code_hash from password_resets where lower(email) = 'c@x.com'")
    assert auth.verify_password(fresh, row["code_hash"])
    auth.password_reset(Req(), payload={"email": "c@x.com", "code": fresh, "password": "NewPass12"})


class Bearer:
    """A request carrying nothing but a token, for the dependencies to resolve."""
    def __init__(self, token):
        self.headers = {"authorization": f"Bearer {token}"}


def test_a_reset_retires_the_sessions_on_the_other_devices(live_db, auth_mod, monkeypatch):
    """The whole guarantee against real SQL: the token from before a reset stops being
    accepted, and the one the reset handed back goes on working."""
    import security
    import db as db_module

    # conftest answers this read with "every account is current" so the rest of the
    # suite needn't know about it; here the real column is the point.
    monkeypatch.setattr(security, "fetch_one", db_module.fetch_one)

    code = auth_mod.password_forgot(Req(), payload={"email": "c@x.com"})["dev_code"]
    first = auth_mod.password_reset(
        Req(), payload={"email": "c@x.com", "code": code, "password": "NewPass12"})["token"]
    assert security.current_user(Bearer(first))["id"] == U_CUST

    code = auth_mod.password_forgot(Req(), payload={"email": "c@x.com"})["dev_code"]
    second = auth_mod.password_reset(
        Req(), payload={"email": "c@x.com", "code": code, "password": "OtherPass34"})["token"]

    with pytest.raises(security.HTTPException):
        security.current_user(Bearer(first))
    assert security.optional_user(Bearer(first)) is None, "nor as a guest-facing caller"
    assert security.current_user(Bearer(second))["id"] == U_CUST


# --- sitemap ----------------------------------------------------------------
def test_sitemap_renders_from_the_live_catalogue(live_db):
    import routers.seo as seo
    xml = seo.sitemap(Req()).body.decode()
    assert xml.count("<loc>") == 4 + len(seo.STATIC_PATHS)
    assert f"/product/{P_OIL}" in xml


# --- the follow-up panel, against real SQL ----------------------------------
def test_an_abandoned_basket_is_reported_with_what_was_left_in_it(live_db):
    """The panel showed a column of identical "زائر" rows: a guest has no name, no
    e-mail and no phone, and last_at came only from the failures CTE, so a person who
    merely abandoned a basket had no time against their name either. Everything worth
    chasing them for — when, how much, how many — was already in the table.
    """
    from db import execute
    from routers.audit import struggling

    execute("""insert into audit_logs (action, detail, ip, visitor, page, created_at)
               values ('checkout_opened', '{"items": 3, "total": 285}'::jsonb,
                       '2.3.4.5', 'vis-abc', '/', now() - interval '10 minutes')""")

    rows = struggling(Req(hours="24"), _m=None)["customers"]
    row = next(r for r in rows if r["who"] == "v:vis-abc")
    assert (row["abandoned"], row["failures"]) == (1, 0)
    assert (row["basket_items"], row["basket_total"]) == (3, "285"), "the money at stake"
    assert row["last_at"] is not None, "an abandoned basket needs a time too"
    assert row["ip"] == "2.3.4.5", "so one anonymous visitor can be told from the next"
    assert row["events"] == 1


def test_a_basket_that_was_paid_for_is_not_chased(live_db):
    """An order placed after the checkout opened settles it."""
    from db import execute
    from routers.audit import struggling

    execute("""insert into audit_logs (action, detail, visitor, created_at) values
               ('checkout_opened', '{"items": 1}'::jsonb, 'vis-ok', now() - interval '9 minutes'),
               ('order_placed', '{}'::jsonb, 'vis-ok', now() - interval '8 minutes')""")
    assert not [r for r in struggling(Req(hours="24"), _m=None)["customers"]
                if r["who"] == "v:vis-ok"]


def test_repeated_failures_are_reported_with_the_reason(live_db):
    """"محاولة دخولٍ فاشلة" twice says nothing a manager can act on. Whether the
    e-mail has no account or the password is wrong is two different conversations."""
    from db import execute
    from routers.audit import struggling

    execute("""insert into audit_logs (action, detail, visitor, created_at) values
               ('login_failed', '{"reason": "no_account"}'::jsonb, 'vis-f', now() - interval '5 minutes'),
               ('verify_failed', '{"reason": "too_many"}'::jsonb, 'vis-f', now() - interval '4 minutes')""")

    row = next(r for r in struggling(Req(hours="24"), _m=None)["customers"] if r["who"] == "v:vis-f")
    assert row["failures"] == 2
    assert sorted(row["kinds"]) == ["login_failed", "verify_failed"]
    assert sorted(row["reasons"]) == ["no_account", "too_many"]


def test_a_basket_size_the_panel_cannot_read_costs_only_that_number(live_db):
    """/audit/event coerces this now, but rows written before it did are still in the
    table — and the panel casts the value with ::int. One unreadable basket size used
    to fail the whole query, so a single visitor could 500 the follow-up panel for
    every manager until the row aged out of a week-long window.

    The row still has to appear: what it was worth is lost, who was stuck is not.
    """
    from db import execute
    from routers.audit import struggling

    execute("""insert into audit_logs (action, detail, ip, visitor, page, created_at)
               values ('checkout_opened', '{"items": "abc", "total": 285}'::jsonb,
                       '2.3.4.5', 'vis-bad', '/', now() - interval '10 minutes')""")

    row = next(r for r in struggling(Req(hours="24"), _m=None)["customers"]
               if r["who"] == "v:vis-bad")
    assert row["basket_items"] is None, "unreadable, so not reported"
    assert row["basket_total"] == "285", "the rest of the row still stands"
    assert row["abandoned"] == 1


# --- the money landing mid-request --------------------------------------------
@pytest.fixture
def settling_race(live_db, monkeypatch):
    """An unresolved ziina order, and a Ziina that settles it while answering.

    Both endpoints read the order, then spend up to twenty seconds asking Ziina about
    it. This is what happens when the payment completes inside that window and Ziina's
    answer is a failed one: the release is refused, and the endpoint has to notice.
    """
    import routers.orders as o
    from db import execute, fetch_one

    for quiet in ("notify_new_order", "_notify_new_order_admins",
                  "_send_order_whatsapp", "_send_order_email"):
        monkeypatch.setattr(o, quiet, lambda *a, **k: None)
    execute("""insert into order_items (order_id, product_id, name, price, qty)
               values (%s, %s, 'زعتر', 20.00, 2)""", [O_ABANDONED, P_ZAATAR])
    # the seed leaves this null, and without it both endpoints answer "no intent to
    # ask about" long before the race they are here to exercise
    execute("update orders set ziina_payment_id = 'pi_race' where id = %s", [O_ABANDONED])

    def settles_then_denies(pid):
        o.mark_paid(fetch_one("select * from orders where id = %s", [O_ABANDONED]))
        return {"status": "expired"}
    monkeypatch.setattr(o, "get_payment_intent", settles_then_denies)
    return o


def test_confirming_does_not_report_a_failure_for_money_that_landed(settling_race):
    """"Payment failed — you can try again" put in front of somebody who has just
    paid is how a shop takes the same money twice. The order survives the race (see
    cancel_and_restore); the answer has to survive it too."""
    before = _stock(P_ZAATAR)
    res = settling_race.confirm_payment(O_ABANDONED, Req(), t="", user=_MGR_USER)
    assert res == {"paid": True, "status": "paid"}
    assert _stock(P_ZAATAR) == before, "a paid order keeps the stock it reserved"


def test_cancelling_does_not_report_a_failure_for_money_that_landed(settling_race):
    """Same race on the cancel button, which is the likelier one: they pressed cancel
    on Ziina's page having already paid."""
    before = _stock(P_ZAATAR)
    res = settling_race.cancel_payment(O_ABANDONED, Req(), t="", user=_MGR_USER)
    assert res == {"cancelled": False, "paid": True}
    assert _stock(P_ZAATAR) == before


def test_one_request_for_help_is_enough_to_reach_the_follow_up_list(live_db):
    """Two failures, or one abandoned basket, is the bar for the rest of this panel —
    a single mistyped password is noise. Being shown the help panel is not: it is a
    dead end the shop put in front of somebody, and they may already have messaged
    about it. One is enough, and the pill has to say which dead end it was.
    """
    from db import execute
    from routers.audit import struggling

    execute("""insert into audit_logs (action, detail, ip, visitor, page, created_at)
               values ('help_needed', '{"reason": "pay_unresolved"}'::jsonb,
                       '2.3.4.5', 'vis-help', '/pay/return', now() - interval '3 minutes')""")

    row = next(r for r in struggling(Req(hours="24"), _m=None)["customers"]
               if r["who"] == "v:vis-help")
    assert row["failures"] == 1, "one on its own, where the rest of the panel needs two"
    assert row["kinds"] == ["help_needed"]
    assert row["reasons"] == ["pay_unresolved"], "or the manager never learns which screen"


# --- finishing a payment that was walked away from ---------------------------
@pytest.fixture
def unpaid_ziina(live_db, monkeypatch):
    """The order an abandoned card checkout leaves behind: real, unpaid, holding
    its stock, and reachable only through its tracking link."""
    import routers.orders as o
    from db import execute, fetch_one

    for quiet in ("notify_new_order", "_notify_new_order_admins", "_alert_managers",
                  "_send_order_whatsapp", "_send_order_email"):
        monkeypatch.setattr(o, quiet, lambda *a, **k: None)
    execute("""insert into order_items (order_id, product_id, name, price, qty)
               values (%s, %s, 'زعتر', 20.00, 2)""", [O_ABANDONED, P_ZAATAR])
    execute("""update orders set ziina_payment_id = 'pi_old', track_token = 'tok'
               where id = %s""", [O_ABANDONED])
    return o, fetch_one("select * from orders where id = %s", [O_ABANDONED])


def test_switching_to_cash_takes_the_order_out_of_the_sweep(unpaid_ziina, live_db):
    """The rescue. unresolved_orders only looks at payment_method = 'ziina', so this
    is what stops the order being cancelled half an hour after it was placed — and it
    becomes exactly the order it would have been had they chosen cash at checkout."""
    import reconcile as rec
    from db import execute, fetch_one
    o, _ = unpaid_ziina
    before = _stock(P_ZAATAR)

    assert o.resume_payment(O_ABANDONED, Req(), t="tok", user=None,
                            payload={"method": "cod"}) == {"method": "cod"}

    row = fetch_one("select payment_method, payment_status, status from orders where id = %s",
                    [O_ABANDONED])
    assert row["payment_method"] == "cod"
    assert row["payment_status"] == "unpaid", "cash is unpaid until it is handed over"
    assert _stock(P_ZAATAR) == before, "the goods were always reserved; nothing moves"

    # and the sweep now leaves it alone, however old it gets
    execute("update orders set created_at = now() - interval '2 hours' where id = %s",
            [O_ABANDONED])
    assert not [r for r in rec.unresolved_orders() if str(r["id"]) == O_ABANDONED]


def test_resuming_a_card_payment_reuses_the_page_it_already_has(unpaid_ziina, monkeypatch):
    """Handing out a second payment page for one order is how somebody pays twice —
    and only one of the two ids would be the one the sweep asks about afterwards."""
    import routers.orders as o
    _, _order = unpaid_ziina
    monkeypatch.setattr(o, "get_payment_intent",
                        lambda pid: {"status": "pending", "redirect_url": "https://pay.ziina/old"})
    monkeypatch.setattr(o, "create_payment_intent",
                        lambda **k: pytest.fail("a live intent must not be replaced"))

    assert o.resume_payment(O_ABANDONED, Req(), t="tok", user=None,
                            payload={})["redirect_url"] == "https://pay.ziina/old"


def test_resuming_settles_an_order_that_turns_out_to_have_been_paid(unpaid_ziina, monkeypatch):
    """Asking Ziina to resume is also the last chance to notice the money arrived."""
    import routers.orders as o
    import background
    from db import fetch_one
    _, _order = unpaid_ziina
    monkeypatch.setattr(o, "get_payment_intent", lambda pid: {"status": "completed"})

    assert o.resume_payment(O_ABANDONED, Req(), t="tok", user=None, payload={}) == {"paid": True}
    background.wait_all(5)
    assert fetch_one("select payment_status from orders where id = %s",
                     [O_ABANDONED])["payment_status"] == "paid"


def test_a_released_order_cannot_be_paid_for_from_the_tracking_page(unpaid_ziina):
    """Its stock went back on the shelf when the sweep let it go. Taking it off again
    here would sell units this code cannot know are still there — the page sends them
    back to the basket, which checks stock properly."""
    from fastapi import HTTPException
    o, _ = unpaid_ziina
    o.cancel_and_restore(O_ABANDONED, why="unresolved for over 30m")

    for method in ({"method": "cod"}, {}):
        with pytest.raises(HTTPException) as e:
            o.resume_payment(O_ABANDONED, Req(), t="tok", user=None, payload=method)
        assert e.value.status_code == 409


def test_paying_for_an_order_that_is_not_yours_is_a_404(unpaid_ziina):
    from fastapi import HTTPException
    o, _ = unpaid_ziina
    with pytest.raises(HTTPException) as e:
        o.resume_payment(O_ABANDONED, Req(), t="wrong-token", user=None, payload={})
    assert e.value.status_code == 404
