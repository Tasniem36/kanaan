"""Discount codes: a code takes either a percentage off or a fixed number of
dirhams off, and whichever it is, the checkout only ever sees dirhams.

The arithmetic is the part worth pinning down — a fixed amount can be larger than
the basket it's used on, which a percentage never can be.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

import routers.discounts as disc


def code_row(**over):
    row = {"id": "d1", "code": "RAMADAN", "percent": 10, "amount": None, "active": True,
           "first_order_only": False, "max_uses": None, "used_count": 0, "expires_at": None}
    row.update(over)
    return row


def evaluate(row, subtotal, orders_placed=0):
    """evaluate_code against a single stubbed row. `run` answers both the code lookup
    and the first-order count, told apart by the statement."""
    def run(sql, params=None):
        if "from orders" in sql:
            return [{"n": orders_placed}]
        return [row] if row else []
    return disc.evaluate_code(run, "RAMADAN", "u1", subtotal)


# --- what the checkout is charged -------------------------------------------
def test_a_percentage_takes_a_share_of_the_basket():
    assert evaluate(code_row(percent=25), 200)["discount"] == 50.0


def test_a_fixed_amount_takes_exactly_that_many_dirhams():
    r = evaluate(code_row(percent=None, amount=30), 200)
    assert r["discount"] == 30.0
    assert r["percent"] is None, "the checkout needs to know it isn't a percentage"
    assert r["amount"] == 30


def test_a_code_worth_more_than_the_basket_asks_for_more_items():
    """Shrinking it to fit would quietly hand over the difference. Saying so turns the
    code into a reason to add something — and the numbers come back so the storefront
    can ask in Arabic."""
    r = evaluate(code_row(percent=None, amount=30), 20)
    assert r["reason"] == "min_basket"
    assert (r["amount"], r["short"]) == (30.0, 10.0)
    assert "add 10 more" in r["error"], "the English fallback says it too"
    assert "discount" not in r, "nothing is taken off"


def test_a_fixed_amount_equal_to_the_basket_takes_all_of_it():
    """Equal is not more, so it applies: the goods come free, delivery is still paid."""
    assert evaluate(code_row(percent=None, amount=20), 20)["discount"] == 20.0


def test_only_the_askable_errors_carry_numbers():
    """Every other rejection is just a sentence, exactly as before."""
    expired = {"error": "This discount code has expired"}
    assert disc.error_body(expired) == expired["error"]
    body = disc.error_body(evaluate(code_row(percent=None, amount=30), 20))
    assert body["reason"] == "min_basket" and body["short"] == 10.0


def test_fractional_dirhams_survive_the_round_trip():
    assert evaluate(code_row(percent=None, amount=15.5), 100)["discount"] == 15.5


def test_no_code_is_no_discount():
    assert disc.evaluate_code(lambda *a: [], "", "u1", 100) == {"discount": 0}


# --- the guards apply to both kinds ------------------------------------------
@pytest.mark.parametrize("kind", [{"percent": 10}, {"percent": None, "amount": 30}])
def test_an_inactive_code_is_refused_whichever_kind_it_is(kind):
    assert "error" in evaluate(code_row(active=False, **kind), 200)


@pytest.mark.parametrize("kind", [{"percent": 10}, {"percent": None, "amount": 30}])
def test_an_expired_code_is_refused_whichever_kind_it_is(kind):
    expired = code_row(expires_at=datetime.now(timezone.utc) - timedelta(days=1), **kind)
    assert "expired" in evaluate(expired, 200)["error"]


@pytest.mark.parametrize("kind", [{"percent": 10}, {"percent": None, "amount": 30}])
def test_a_used_up_code_is_refused_whichever_kind_it_is(kind):
    assert "usage limit" in evaluate(code_row(max_uses=5, used_count=5, **kind), 200)["error"]


def test_a_first_order_code_is_refused_to_a_returning_customer():
    r = evaluate(code_row(first_order_only=True, percent=None, amount=30), 200, orders_placed=2)
    assert "first order" in r["error"]


def test_the_rejection_reaches_the_page_with_its_numbers(client, as_user, monkeypatch):
    """A dict error has to survive the exception handler, or the storefront can't ask
    for the difference in Arabic and falls back to the English sentence."""
    monkeypatch.setattr(disc, "fetch_all", lambda sql, params=None: [code_row(percent=None, amount=30)])
    monkeypatch.setattr(disc, "log_action", lambda **k: None)
    as_user({"id": "me", "role": "customer"})

    res = client.post("/api/discounts/validate", json={"code": "OFF30", "subtotal": 20})
    body = res.json()
    assert res.status_code == 400
    assert (body["reason"], body["amount"], body["short"]) == ("min_basket", 30.0, 10.0)
    assert body["error"], "still a sentence, for anything that only reads that"


def test_an_ordinary_rejection_is_still_just_a_sentence(client, as_user, monkeypatch):
    monkeypatch.setattr(disc, "fetch_all", lambda sql, params=None: [code_row(active=False)])
    monkeypatch.setattr(disc, "log_action", lambda **k: None)
    as_user({"id": "me", "role": "customer"})

    res = client.post("/api/discounts/validate", json={"code": "NOPE", "subtotal": 200})
    assert res.status_code == 400
    assert res.json() == {"error": "Invalid discount code"}


# --- what the admin is allowed to create -------------------------------------
def test_one_kind_or_the_other_but_not_both():
    with pytest.raises(HTTPException) as e:
        disc._kind({"percent": 10, "amount": 30})
    assert e.value.status_code == 400
    with pytest.raises(HTTPException):
        disc._kind({})   # nor neither


def test_a_percentage_must_be_between_1_and_100():
    assert disc._kind({"percent": 100}) == (100, None)
    for bad in (0, -5, 101):
        with pytest.raises(HTTPException):
            disc._kind({"percent": bad})


def test_an_amount_must_be_a_positive_number_of_dirhams():
    assert disc._kind({"amount": "15.5"}) == (None, 15.5)
    for bad in (0, -1, "abc"):
        with pytest.raises(HTTPException):
            disc._kind({"amount": bad})


def test_a_blank_field_counts_as_absent():
    """The admin form sends "" for the box it isn't using."""
    assert disc._kind({"percent": "", "amount": 30}) == (None, 30.0)
    assert disc._kind({"percent": 20, "amount": ""}) == (20, None)


def test_creating_a_code_needs_a_code(client, monkeypatch):
    from conftest import token_for
    monkeypatch.setattr(disc, "fetch_one", lambda *a, **k: None)
    headers = {"Authorization": f"Bearer {token_for('boss', 'manager')}"}
    res = client.post("/api/discounts", json={"amount": 30}, headers=headers)
    assert res.status_code == 400


def test_creating_a_fixed_amount_code_stores_the_amount(client, monkeypatch):
    from conftest import token_for
    seen = []
    monkeypatch.setattr(disc, "fetch_one",
                        lambda sql, params=None: seen.append((sql, params)) or code_row())
    headers = {"Authorization": f"Bearer {token_for('boss', 'manager')}"}
    res = client.post("/api/discounts", json={"code": "eid30", "amount": 30}, headers=headers)

    assert res.status_code == 201
    sql, params = seen[0]
    assert "amount" in sql
    assert params[0] == "EID30", "codes are stored uppercased"
    assert params[1] is None and params[2] == 30.0, "a percentage-free row"


def test_switching_a_code_to_an_amount_clears_its_percentage(client, monkeypatch):
    """Both columns are written together — a row left holding two discounts, or none,
    has no single meaning at the checkout (and the schema refuses it)."""
    from conftest import token_for
    seen = []
    monkeypatch.setattr(disc, "fetch_one",
                        lambda sql, params=None: seen.append((sql, params)) or code_row())
    headers = {"Authorization": f"Bearer {token_for('boss', 'manager')}"}
    res = client.patch("/api/discounts/d1", json={"amount": 15}, headers=headers)

    assert res.status_code == 200
    sql, params = seen[0]
    assert "percent = %s" in sql and "amount = %s" in sql
    assert None in params and 15.0 in params


def test_only_a_manager_can_create_a_code(client):
    from conftest import token_for
    assert client.post("/api/discounts", json={"code": "X", "amount": 30}).status_code == 401
    shopper = {"Authorization": f"Bearer {token_for('me', 'customer')}"}
    res = client.post("/api/discounts", json={"code": "X", "amount": 30}, headers=shopper)
    assert res.status_code == 403
