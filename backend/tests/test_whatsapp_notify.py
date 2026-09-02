"""Telling the customer what happened to their order, on WhatsApp.

The point of this channel is the guest who left no e-mail address: they have no
account, so no in-app notification and no push, and before this they were told
nothing at all from the moment they ordered.

What's worth pinning down:
  * an unconfigured shop must not try to send, and must not break anything;
  * a guest order (no user_id) gets the message;
  * an account holder does not — they already have two channels, and each template
    message is billed — unless WA_NOTIFY_ALL says otherwise;
  * a send that fails must never take the status change or the order down with it;
  * the phone goes out in the digits-only form the Cloud API wants.
"""
import threading

import pytest

import whatsapp
import routers.orders as orders


GUEST_ORDER = {"id": "0f1d4e0e-1111-4000-8000-000000000000", "user_id": None,
               "phone": "+971501234567", "ref": "L4MNFBU", "total": 63,
               "track_token": "tok-abc"}
ACCOUNT_ORDER = {**GUEST_ORDER, "user_id": "some-user-id"}


@pytest.fixture
def sent(monkeypatch):
    """Capture what would have gone to Meta, with the client configured."""
    monkeypatch.setenv("WA_CLOUD_TOKEN", "test-token")
    monkeypatch.setenv("WA_CLOUD_PHONE_ID", "1234567890")
    monkeypatch.delenv("WA_NOTIFY_ALL", raising=False)
    calls = []

    class FakeRes:
        ok = True
        content = b"{}"

        @staticmethod
        def json():
            return {"messages": [{"id": "wamid.TEST"}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "body": json})
        return FakeRes()

    monkeypatch.setattr(whatsapp.requests, "post", fake_post)
    return calls


def _wait(thread):
    """The send is dispatched off the request (see routers/orders.py), so a test has
    to wait for it rather than assume it already happened."""
    if thread is not None:
        thread.join(10)
        assert not thread.is_alive(), "the WhatsApp send did not finish"
    return thread


# ---- the client -------------------------------------------------------------

def test_unconfigured_shop_sends_nothing(monkeypatch):
    monkeypatch.delenv("WA_CLOUD_TOKEN", raising=False)
    monkeypatch.delenv("WA_CLOUD_PHONE_ID", raising=False)

    def explode(*a, **k):  # pragma: no cover - must never be reached
        raise AssertionError("tried to send with no credentials")

    monkeypatch.setattr(whatsapp.requests, "post", explode)
    assert whatsapp.configured() is False
    res = whatsapp.send_order_status(phone="+971501234567", number="DK-L4MNFBU",
                                     status_label="قيد التجهيز", track_url="http://x/track/1")
    assert res["configured"] is False and res["ok"] is False


def test_half_configured_is_not_configured(monkeypatch):
    monkeypatch.setenv("WA_CLOUD_TOKEN", "only-the-token")
    monkeypatch.delenv("WA_CLOUD_PHONE_ID", raising=False)
    assert whatsapp.configured() is False


def test_phone_is_sent_as_digits_only(sent):
    whatsapp.send_order_status(phone="+971 50 123 4567", number="DK-L4MNFBU",
                               status_label="تمّ الشحن", track_url="http://x/track/1")
    assert sent[0]["body"]["to"] == "971501234567"


def test_template_carries_number_status_and_link(sent):
    whatsapp.send_order_status(phone="+971501234567", number="DK-L4MNFBU",
                               status_label="تمّ التوصيل", track_url="http://x/track/1?t=tok")
    body = sent[0]["body"]
    assert body["type"] == "template"
    assert body["template"]["name"] == "order_status"
    params = [p["text"] for p in body["template"]["components"][0]["parameters"]]
    assert params == ["DK-L4MNFBU", "تمّ التوصيل", "http://x/track/1?t=tok"]


def test_template_names_and_language_are_configurable(sent, monkeypatch):
    monkeypatch.setenv("WA_TEMPLATE_STATUS", "my_status_tpl")
    monkeypatch.setenv("WA_TEMPLATE_LANG", "en")
    whatsapp.send_order_status(phone="+971501234567", number="DK-1", status_label="Shipped",
                               track_url="http://x")
    assert sent[0]["body"]["template"]["name"] == "my_status_tpl"
    assert sent[0]["body"]["template"]["language"]["code"] == "en"


def test_a_rejected_send_is_reported_not_raised(sent, monkeypatch):
    class Rejected:
        ok = False
        status_code = 400
        content = b"{}"

        @staticmethod
        def json():
            return {"error": {"message": "Template name does not exist"}}

    monkeypatch.setattr(whatsapp.requests, "post", lambda *a, **k: Rejected())
    res = whatsapp.send_order_status(phone="+971501234567", number="DK-1",
                                     status_label="x", track_url="http://x")
    assert res["ok"] is False and "Template name" in res["error"]


def test_a_network_error_is_reported_not_raised(sent, monkeypatch):
    def boom(*a, **k):
        raise whatsapp.requests.RequestException("connection reset")

    monkeypatch.setattr(whatsapp.requests, "post", boom)
    res = whatsapp.send_order_placed(phone="+971501234567", number="DK-1", total=63,
                                     track_url="http://x")
    assert res["ok"] is False and "connection reset" in res["error"]


def test_no_phone_on_the_order_is_not_sent(sent):
    res = whatsapp.send_order_status(phone="", number="DK-1", status_label="x", track_url="http://x")
    assert res["ok"] is False and not sent


# ---- who gets messaged ------------------------------------------------------

def test_guest_order_with_no_account_is_messaged(sent):
    """user_id is None, so no account lookup is even needed."""
    _wait(orders._send_order_whatsapp(GUEST_ORDER, None, status_label="قيد التجهيز"))
    assert len(sent) == 1
    params = [p["text"] for p in sent[0]["body"]["template"]["components"][0]["parameters"]]
    assert params[0] == "DK-L4MNFBU"


@pytest.fixture
def account(monkeypatch):
    """Control whether the order's user can actually sign in."""
    def use(password_hash):
        monkeypatch.setattr(orders, "fetch_one",
                            lambda *a, **k: {"password_hash": password_hash})
    return use


def test_real_account_holder_is_left_to_their_own_channels(sent, account):
    account("$2b$12$a-real-bcrypt-hash")
    _wait(orders._send_order_whatsapp(ACCOUNT_ORDER, None, status_label="قيد التجهيز"))
    assert sent == []


def test_guest_who_left_an_email_is_still_messaged(sent, account):
    """The commonest guest. _guest_account gives them a user_id, but the row has an
    empty password_hash and cannot be logged into — so the in-app bell and the push
    both land somewhere they can never look. Gating on user_id alone told them
    nothing at all."""
    account("")
    _wait(orders._send_order_whatsapp(ACCOUNT_ORDER, None, status_label="قيد التجهيز"))
    assert len(sent) == 1


def test_an_unreadable_account_row_errs_towards_telling_them(sent, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(orders, "fetch_one", boom)
    _wait(orders._send_order_whatsapp(ACCOUNT_ORDER, None, status_label="قيد التجهيز"))
    assert len(sent) == 1, "a message too many beats a customer told nothing"


def test_notify_all_reaches_account_holders_too(sent, monkeypatch, account):
    account("$2b$12$a-real-bcrypt-hash")
    monkeypatch.setenv("WA_NOTIFY_ALL", "true")
    _wait(orders._send_order_whatsapp(ACCOUNT_ORDER, None, status_label="قيد التجهيز"))
    assert len(sent) == 1


def test_placed_message_carries_number_total_and_link(sent, monkeypatch):
    monkeypatch.setenv("APP_URL", "https://dukkan-kanaan.com")
    _wait(orders._send_order_whatsapp(GUEST_ORDER, None))
    body = sent[0]["body"]
    assert body["template"]["name"] == "order_placed"
    params = [p["text"] for p in body["template"]["components"][0]["parameters"]]
    assert params == ["DK-L4MNFBU", "63",
                      "https://dukkan-kanaan.com/track/0f1d4e0e-1111-4000-8000-000000000000?t=tok-abc"]


def test_the_link_is_absolute_so_it_is_tappable(sent, monkeypatch):
    """APP_URL is set from DOMAIN in docker-compose.prod.yml. Without it the link
    would be a bare path, which is no use inside a message — worth pinning, since
    this is the one channel where the link IS the message."""
    monkeypatch.setenv("APP_URL", "https://dukkan-kanaan.com")
    _wait(orders._send_order_whatsapp(GUEST_ORDER, None, status_label="تمّ الشحن"))
    link = [p["text"] for p in sent[0]["body"]["template"]["components"][0]["parameters"]][2]
    assert link.startswith("https://")


def test_an_order_without_a_ref_falls_back_to_its_id(sent):
    _wait(orders._send_order_whatsapp({**GUEST_ORDER, "ref": None}, None, status_label="x"))
    params = [p["text"] for p in sent[0]["body"]["template"]["components"][0]["parameters"]]
    assert params[0] == "#0f1d4e0e"


def test_the_send_does_not_hold_up_the_request(sent, monkeypatch):
    """Meta is a twenty-second timeout away. Sending inline cost a measured 20.9s on
    one status change, which a manager marking an order shipped would have waited for."""
    import time
    started = threading.Event()

    def slow_post(*a, **k):
        started.set()
        time.sleep(5)
        raise AssertionError("should never be waited on")

    monkeypatch.setattr(whatsapp.requests, "post", slow_post)
    t0 = time.monotonic()
    thread = orders._send_order_whatsapp(GUEST_ORDER, None, status_label="قيد التجهيز")
    elapsed = time.monotonic() - t0
    assert started.wait(5), "the send never started"
    assert elapsed < 1, f"the caller waited {elapsed:.2f}s on the send"
    assert thread is not None and thread.daemon, "must not keep the process alive"


def test_a_broken_order_row_does_not_raise(sent):
    # a row missing the fields the message needs must not take the caller down
    _wait(orders._send_order_whatsapp({"user_id": None}, None, status_label="x"))
    assert sent == []
