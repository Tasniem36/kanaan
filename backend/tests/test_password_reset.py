"""Forgotten-password flow: what it discloses, what it costs to guess, and the
one thing that must be true at the end (the password is actually changed).

No database: fetch_one/execute are patched, as everywhere else in these tests.
"""
from datetime import datetime, timedelta, timezone

import pytest

import routers.auth as auth
from security import hash_password


@pytest.fixture
def db(monkeypatch):
    """Collects the SQL the handler runs, and answers its reads from `rows`.

    `rows` maps a fragment of the statement to what fetch_one should return, so a
    test says what exists rather than replaying query text.
    """
    class DB:
        def __init__(self):
            self.rows = {}
            self.ran = []

        def fetch_one(self, sql, params=None):
            self.ran.append((" ".join(sql.split()), params))
            for needle, value in self.rows.items():
                if needle in sql:
                    return value
            return None

        def execute(self, sql, params=None):
            self.ran.append((" ".join(sql.split()), params))

        def sql(self):
            return [s for s, _ in self.ran]

    d = DB()
    monkeypatch.setattr(auth, "fetch_one", d.fetch_one)
    monkeypatch.setattr(auth, "execute", d.execute)
    monkeypatch.setattr(auth, "log_action", lambda **k: None)
    monkeypatch.setattr(auth, "send_email", lambda *a, **k: True)
    return d


def live_reset(code="123456", attempts=0, minutes=5):
    return {"id": "r1", "email": "her@example.com", "code_hash": hash_password(code),
            "attempts": attempts,
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=minutes)}


# --- step 1: asking for a code -------------------------------------------------
def test_an_unknown_address_gets_the_same_answer_as_a_real_one(client, db):
    """Whether an e-mail has an account here is not a stranger's question to ask."""
    db.rows = {}   # no such user
    unknown = client.post("/api/auth/password/forgot", json={"email": "nobody@example.com"})
    db.rows = {"from users": {"id": "u1"}}
    known = client.post("/api/auth/password/forgot", json={"email": "her@example.com"})

    assert unknown.status_code == known.status_code == 200
    assert unknown.json()["sent"] == known.json()["sent"] is True


def test_nothing_is_written_or_sent_for_an_address_with_no_account(client, db, monkeypatch):
    sent = []
    monkeypatch.setattr(auth, "send_email", lambda *a, **k: sent.append(a) or True)
    db.rows = {}
    client.post("/api/auth/password/forgot", json={"email": "nobody@example.com"})
    assert not sent
    assert not any("insert into password_resets" in s for s in db.sql())


def test_the_code_is_stored_hashed_never_in_the_clear(client, db):
    db.rows = {"from users": {"id": "u1"}}
    res = client.post("/api/auth/password/forgot", json={"email": "her@example.com"})
    code = res.json()["dev_code"]   # non-prod echo, so the test can see what was sent

    insert = next(p for s, p in db.ran if "insert into password_resets" in s)
    assert code not in str(insert), "a leaked table would hand out live reset codes"
    assert auth.verify_password(code, insert[1])


def test_only_the_newest_code_stays_live(client, db):
    """Older rows for the address can only confuse — and clearing them is what keeps
    the table from growing."""
    db.rows = {"from users": {"id": "u1"}}
    client.post("/api/auth/password/forgot", json={"email": "her@example.com"})
    verbs = [s.split()[0] for s in db.sql() if "password_resets" in s]
    assert verbs == ["delete", "insert"], "the old rows go before the new one lands"


def test_a_malformed_address_is_refused(client, db):
    assert client.post("/api/auth/password/forgot", json={"email": "not-an-email"}).status_code == 400


def test_production_says_so_when_there_is_no_way_to_send_mail(client, db, monkeypatch):
    """Promising a code that can never arrive leaves the customer waiting for it."""
    monkeypatch.setattr(auth, "_IS_PROD", True)
    monkeypatch.setattr(auth, "email_configured", lambda: False)
    res = client.post("/api/auth/password/forgot", json={"email": "her@example.com"})
    assert res.status_code == 503


def test_a_real_reset_code_never_reaches_the_production_logs(client, db, monkeypatch, capsys):
    monkeypatch.setattr(auth, "_IS_PROD", True)
    monkeypatch.setattr(auth, "email_configured", lambda: True)
    monkeypatch.setattr(auth, "send_email", lambda *a, **k: False)   # send failed
    db.rows = {"from users": {"id": "u1"}}
    res = client.post("/api/auth/password/forgot", json={"email": "her@example.com"})
    assert "dev_code" not in res.json()
    assert "[reset]" not in capsys.readouterr().out


# --- step 2: spending the code -------------------------------------------------
def _reset(client, **over):
    body = {"email": "her@example.com", "code": "123456", "password": "NewPass12"}
    return client.post("/api/auth/password/reset", json={**body, **over})


def test_the_right_code_sets_the_new_password_and_signs_them_in(client, db):
    db.rows = {"from password_resets": live_reset(),
               "update users": {"id": "u1", "email": "her@example.com", "full_name": "ن",
                                "phone": "+971500000000", "role": "customer"}}
    res = _reset(client)
    assert res.status_code == 200
    assert res.json()["token"] and res.json()["user"]["email"] == "her@example.com"

    update = next(p for s, p in db.ran if "update users set password_hash" in s)
    assert auth.verify_password("NewPass12", update[0]), "the new password must actually work"


def test_the_reset_signs_the_other_devices_out(client, db):
    """The session the customer is resetting *because of* is the one that must die —
    on a device they can't reach. The device doing the resetting stays signed in."""
    import jwt
    import security

    db.rows = {"from password_resets": live_reset(),
               "update users": {"id": "u1", "email": "her@example.com", "full_name": None,
                                "phone": None, "role": "customer", "token_version": 7}}
    token = _reset(client).json()["token"]

    update = next(s for s in db.sql() if "update users set password_hash" in s)
    assert "token_version = token_version + 1" in update
    assert jwt.decode(token, security.SECRET, algorithms=["HS256"])["v"] == 7


def test_a_spent_code_cannot_be_used_twice(client, db):
    db.rows = {"from password_resets": live_reset(),
               "update users": {"id": "u1", "email": "her@example.com", "full_name": None,
                                "phone": None, "role": "customer"}}
    _reset(client)
    assert ("delete from password_resets where id = %s", ["r1"]) in db.ran


def test_a_wrong_code_is_refused_and_counted(client, db):
    db.rows = {"from password_resets": live_reset(code="111111")}
    assert _reset(client, code="999999").status_code == 400
    assert ("update password_resets set attempts = attempts + 1 where id = %s", ["r1"]) in db.ran
    assert not any("update users" in s for s in db.sql())


def test_guessing_runs_out_of_attempts(client, db):
    db.rows = {"from password_resets": live_reset(attempts=8)}
    res = _reset(client, code="999999")
    assert res.status_code == 429
    assert ("delete from password_resets where id = %s", ["r1"]) in db.ran, "and the code is dead"


def test_a_stuck_customer_shows_up_in_the_activity_trail(client, db, monkeypatch):
    logged = []
    monkeypatch.setattr(auth, "log_action", lambda **k: logged.append(k))
    db.rows = {"from password_resets": live_reset(code="111111")}
    _reset(client, code="999999")
    assert logged[0]["action"] == "password_reset_failed"
    assert logged[0]["detail"]["email"] == "her@example.com"


def test_a_weak_password_is_refused_without_spending_an_attempt(client, db):
    db.rows = {"from password_resets": live_reset()}
    assert _reset(client, password="short").status_code == 400
    assert not any("password_resets" in s for s in db.sql()), "the code was never even read"


def test_an_over_long_password_is_refused(client, db):
    """bcrypt silently truncates at 72 bytes, and hashing is deliberately slow."""
    assert _reset(client, password="Aa1" + "x" * 300).status_code == 400


def test_an_expired_or_missing_request_asks_them_to_start_again(client, db):
    db.rows = {}   # the query already filters on expires_at > now()
    res = _reset(client)
    assert res.status_code == 400
    assert "start again" in res.json()["error"]


def test_the_expiry_is_enforced_in_the_lookup(client, db):
    db.rows = {"from password_resets": live_reset()}
    _reset(client)
    select = next(s for s in db.sql() if "from password_resets" in s and s.startswith("select"))
    assert "expires_at > now()" in select


def test_an_account_that_vanished_mid_reset_does_not_500(client, db):
    db.rows = {"from password_resets": live_reset()}   # 'update users' returns nothing
    assert _reset(client).status_code == 400


def test_resetting_is_rate_limited(client, db):
    db.rows = {}
    codes = [_reset(client).status_code for _ in range(11)]
    assert codes[:10] == [400] * 10
    assert codes[10] == 429


def test_asking_for_codes_is_rate_limited(client, db):
    db.rows = {}
    codes = [client.post("/api/auth/password/forgot", json={"email": "a@b.com"}).status_code
             for _ in range(6)]
    assert codes[:5] == [200] * 5
    assert codes[5] == 429
