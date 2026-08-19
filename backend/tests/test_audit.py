"""What lands in the customer activity log, and what deliberately doesn't.

The log is a trail of what customers DID. Two things keep it readable: every row
names the API call that produced it, and actions a visitor repeats just by browsing
are collapsed instead of filling the table.
"""
import audit


def test_a_row_records_the_endpoint_not_just_the_page(monkeypatch):
    written = {}
    monkeypatch.setattr(audit, "execute", lambda sql, params=None: written.update(
        {"sql": " ".join(sql.split()), "params": list(params or [])}))
    monkeypatch.setattr(audit.threading, "Thread",
                        lambda target, daemon=None: type("T", (), {"start": staticmethod(target)})())

    class Req:
        method = "POST"
        url = type("U", (), {"path": "/api/orders"})()
        headers = {"referer": "https://shop.example/checkout?x=1"}
        client = type("C", (), {"host": "1.2.3.4"})()

    audit.log_action(user_id="u1", action="order_placed", detail={"total": 90}, request=Req())
    assert "api" in written["sql"]
    assert "POST /api/orders" in written["params"], "the action the customer took"
    assert "/checkout?x=1" in written["params"], "the page is kept as context"


def test_browsing_does_not_bury_the_log(monkeypatch):
    """One shopper reloading the storefront must not write a row every time."""
    rows = []
    monkeypatch.setattr(audit, "execute", lambda sql, params=None: rows.append(params))
    monkeypatch.setattr(audit.threading, "Thread",
                        lambda target, daemon=None: type("T", (), {"start": staticmethod(target)})())
    audit._recent.clear()
    for _ in range(12):
        audit.log_action(user_id="u1", action="visit", request=None)
    assert len(rows) == 1, f"expected the repeats to collapse, wrote {len(rows)}"


def test_the_collapse_is_per_visitor_and_per_action(monkeypatch):
    rows = []
    monkeypatch.setattr(audit, "execute", lambda sql, params=None: rows.append(params))
    monkeypatch.setattr(audit.threading, "Thread",
                        lambda target, daemon=None: type("T", (), {"start": staticmethod(target)})())
    audit._recent.clear()
    audit.log_action(user_id="u1", action="visit")
    audit.log_action(user_id="u2", action="visit")        # a different shopper
    audit.log_action(user_id="u1", action="order_placed")  # a different action
    assert len(rows) == 3, "collapsing must not swallow other visitors or other actions"


def test_actions_worth_keeping_are_never_collapsed(monkeypatch):
    rows = []
    monkeypatch.setattr(audit, "execute", lambda sql, params=None: rows.append(params))
    monkeypatch.setattr(audit.threading, "Thread",
                        lambda target, daemon=None: type("T", (), {"start": staticmethod(target)})())
    audit._recent.clear()
    for action in ["login", "order_placed", "review_submitted", "product_view"]:
        for _ in range(3):
            audit.log_action(user_id="u1", action=action)
    assert len(rows) == 12, "only the actions named in _COLLAPSE may be suppressed"


def test_the_shops_own_actions_are_never_recorded(monkeypatch):
    """A manager moderating or browsing isn't customer activity, and their rows would
    crowd out the ones the log exists for."""
    rows = []
    monkeypatch.setattr(audit, "execute", lambda sql, params=None: rows.append(params))
    monkeypatch.setattr(audit.threading, "Thread",
                        lambda target, daemon=None: type("T", (), {"start": staticmethod(target)})())
    monkeypatch.setattr(audit, "fetch_one",
                        lambda sql, params=None: {"role": "manager" if params[0] == "boss" else "customer"})
    audit._recent.clear()
    audit._roles.clear()
    audit.log_action(user_id="boss", action="review_approved")
    audit.log_action(user_id="shopper", action="review_submitted")
    assert len(rows) == 1 and rows[0][0] == "shopper"


def test_the_role_lookup_is_cached_per_user(monkeypatch):
    """It runs on the audit thread, but shouldn't hit the database on every row."""
    looked_up = []
    monkeypatch.setattr(audit, "execute", lambda sql, params=None: None)
    monkeypatch.setattr(audit.threading, "Thread",
                        lambda target, daemon=None: type("T", (), {"start": staticmethod(target)})())
    monkeypatch.setattr(audit, "fetch_one",
                        lambda sql, params=None: looked_up.append(params[0]) or {"role": "customer"})
    audit._recent.clear()
    audit._roles.clear()
    for _ in range(5):
        audit.log_action(user_id="shopper", action="product_view")
    assert looked_up == ["shopper"], f"expected one lookup, made {len(looked_up)}"


def test_a_db_hiccup_keeps_the_row(monkeypatch):
    """Losing customer activity is worse than an occasional staff row slipping in."""
    rows = []
    monkeypatch.setattr(audit, "execute", lambda sql, params=None: rows.append(params))
    monkeypatch.setattr(audit.threading, "Thread",
                        lambda target, daemon=None: type("T", (), {"start": staticmethod(target)})())
    monkeypatch.setattr(audit, "fetch_one",
                        lambda sql, params=None: (_ for _ in ()).throw(RuntimeError("db down")))
    audit._recent.clear()
    audit._roles.clear()
    audit.log_action(user_id="shopper", action="login")
    assert len(rows) == 1


# --- ad parameters ------------------------------------------------------------
IG_AD = ("/?utm_medium=paid&utm_source=ig&utm_campaign=120251759493910659"
         "&utm_content=120251759495550659&fbclid=PAdGRzdgTxKDRwZG9mAmV4dG4DYWVtATAAYWRpZAGrOFaQ")


def _req(referer):
    return type("R", (), {
        "method": "GET",
        "url": type("U", (), {"path": "/api/products"})(),
        "headers": {"referer": f"https://dukkan-kanaan.com{referer}"},
        "client": type("C", (), {"host": "1.2.3.4"})(),
    })()


def test_the_stored_page_drops_the_ad_parameters():
    """A click from an Instagram campaign arrives with a dozen of them, which made
    the column an unreadable wall and said nothing about what the customer did."""
    assert audit._page(_req(IG_AD)) == "/"
    assert audit._page(_req("/search?q=زعتر&utm_source=ig&fbclid=xyz")) == "/search?q=%D8%B2%D8%B9%D8%AA%D8%B1"
    assert audit._page(_req("/product/abc")) == "/product/abc"


def test_the_campaign_itself_is_kept():
    """Which ad brought them in is the one useful thing in that URL."""
    assert audit.traffic_source(_req(IG_AD)) == {
        "source": "ig", "medium": "paid", "campaign": "120251759493910659"}


def test_a_bare_click_id_still_names_the_network():
    assert audit.traffic_source(_req("/?fbclid=abc123")) == {"source": "facebook"}


def test_a_direct_visit_has_no_source():
    assert audit.traffic_source(_req("/")) is None
    assert audit.traffic_source(None) is None
