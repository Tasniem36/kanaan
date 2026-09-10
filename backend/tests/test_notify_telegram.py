"""Telegram order alerts, and specifically their recipients.

TELEGRAM_CHAT_ID holds one id or several, comma-separated, so the shop can alert a
second phone (or a phone and a channel) without a code change. What matters here is
that every id gets its own message and that one bad id can't silence the others —
a lost new-order alert is a lost order. No network: requests.post is captured.
"""
import pytest

import notify


class FakeResponse:
    def __init__(self, ok=True, status_code=200, text=""):
        self.ok, self.status_code, self.text = ok, status_code, text


class Posts(list):
    """The Telegram calls that were made. Append to `replies` to script the
    responses, in order; anything unscripted succeeds."""
    replies = None

    @property
    def chat_ids(self):
        return [p["chat_id"] for p in self]


@pytest.fixture
def posts(monkeypatch):
    sent = Posts()
    sent.replies = []

    def fake_post(url, json=None, timeout=None):
        sent.append({"url": url, "chat_id": json["chat_id"], "text": json["text"]})
        return sent.replies.pop(0) if sent.replies else FakeResponse()

    monkeypatch.setattr(notify.requests, "post", fake_post)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:secret")
    monkeypatch.delenv("WHATSAPP_PHONE", raising=False)   # keep _send to one channel
    monkeypatch.delenv("WHATSAPP_APIKEY", raising=False)
    return sent


def test_one_id_still_sends_exactly_one_message(posts, monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "812345678")

    res = notify._send_telegram("طلب جديد")

    assert res["ok"] is True
    assert posts.chat_ids == ["812345678"]
    assert posts[0]["url"] == "https://api.telegram.org/bot123:secret/sendMessage"


def test_every_id_in_the_list_is_messaged(posts, monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "812345678,-1001234567890")

    res = notify._send_telegram("طلب جديد")

    assert res["ok"] is True
    assert posts.chat_ids == ["812345678", "-1001234567890"]
    assert all(p["text"] == "طلب جديد" for p in posts)


def test_spacing_and_repeats_in_the_env_var_are_tolerated(posts, monkeypatch):
    """A hand-edited .env picks up spaces, a trailing comma, or the same id twice."""
    monkeypatch.setenv("TELEGRAM_CHAT_ID", " 812345678 , -100123 , 812345678, ")

    notify._send_telegram("طلب جديد")

    assert posts.chat_ids == ["812345678", "-100123"]


def test_a_dead_recipient_does_not_stop_the_rest(posts, monkeypatch):
    """403 is what Telegram returns for someone who never pressed Start, or a bot
    kicked from the channel. The other manager still has to get the order."""
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "dead,alive")
    posts.replies.extend([FakeResponse(ok=False, status_code=403, text="bot was blocked"), FakeResponse()])

    res = notify._send_telegram("طلب جديد")

    assert posts.chat_ids == ["dead", "alive"]
    assert res["ok"] is True                       # one landed, so the alert landed
    assert res["recipients"]["dead"]["ok"] is False
    assert res["recipients"]["alive"]["ok"] is True
    assert "dead: HTTP 403" in res["error"]        # ...but the broken id is named


def test_an_exception_on_one_recipient_is_contained(posts, monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "boom,alive")
    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append(json["chat_id"])
        if json["chat_id"] == "boom":
            raise RuntimeError("connection reset")
        return FakeResponse()

    monkeypatch.setattr(notify.requests, "post", fake_post)

    res = notify._send_telegram("طلب جديد")

    assert calls == ["boom", "alive"]
    assert res["ok"] is True
    assert res["recipients"]["boom"]["error"] == "connection reset"


def test_all_recipients_failing_is_not_ok(posts, monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "a,b")
    posts.replies.extend([FakeResponse(ok=False, status_code=400, text="bad request"),
                          FakeResponse(ok=False, status_code=400, text="bad request")])

    res = notify._send_telegram("طلب جديد")

    assert res["configured"] is True
    assert res["ok"] is False


@pytest.mark.parametrize("chat_id", ["", "   ", ",", " , "])
def test_no_usable_id_reads_as_not_configured(posts, monkeypatch, chat_id):
    """Not configured is different from failing: an unset channel is normal, and
    _send must not report the shop as alerted when nobody was."""
    monkeypatch.setenv("TELEGRAM_CHAT_ID", chat_id)

    res = notify._send_telegram("طلب جديد")

    assert res == {"configured": False, "ok": False,
                   "error": "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set"}
    assert posts == []


def test_a_new_order_reaches_both_managers(posts, monkeypatch):
    """End to end through the public entry point, with the order text intact."""
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "812345678,-1001234567890")

    res = notify.notify_new_order({
        "id": "abcdef12-3456-7890-abcd-ef1234567890",
        "customer_name": "سارة", "phone": "971500000000",
        "city": "دبي", "street": "شارع 1", "house": "12",
        "items": [{"name": "زعتر", "qty": 2}],
        "total": 45, "payment_method": "cod", "payment_status": "pending",
    })

    assert res["ok"] is True
    assert len(posts) == 2
    for p in posts:
        assert "سارة" in p["text"] and "زعتر ×2" in p["text"] and "#abcdef12" in p["text"]
