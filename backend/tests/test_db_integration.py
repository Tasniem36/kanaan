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

import pytest

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
    with live_db.connection() as conn:
        # cascades clear order_items, events, wishlists, stock_alerts, notifications
        conn.execute("truncate table users, products, orders, audit_logs cascade")
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


def test_cancel_restores_stock_in_one_statement(live_db):
    import routers.orders as o
    from db import fetch_one

    before = fetch_one("select stock from products where id = %s", [P_OIL])["stock"]
    o.cancel_and_restore(O_PREP)   # this order holds 1 unit of the oil
    after = fetch_one("select stock from products where id = %s", [P_OIL])["stock"]
    assert after == before + 1
    assert fetch_one("select status from orders where id = %s", [O_PREP])["status"] == "cancelled"
    assert fetch_one(
        "select 1 as x from order_status_events where order_id = %s and status = 'cancelled'", [O_PREP]
    ), "cancelling should land on the timeline too"


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
    w.add_to_wishlist(P_CUP, user={"id": U_CUST})
    w.add_to_wishlist(P_CUP, user={"id": U_CUST})   # idempotent
    ids = set(w.list_wishlist_ids(user={"id": U_CUST})["ids"])
    assert ids == {P_OIL, P_CUP}

    w.remove_from_wishlist(P_CUP, response=type("R", (), {"status_code": None})(), user={"id": U_CUST})
    assert set(w.list_wishlist_ids(user={"id": U_CUST})["ids"]) == {P_OIL}


def test_wishlist_is_scoped_per_customer(live_db):
    import routers.wishlist as w
    assert w.list_wishlist_ids(user={"id": U_MGR})["ids"] == [], "must not see another account's saves"


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
