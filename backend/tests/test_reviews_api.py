"""Shop reviews: what the public may read, what a customer may write, and who
may moderate.

The risks worth pinning down are (a) an unapproved review leaking onto the
storefront, (b) one customer editing or deleting another's, and (c) moderation
being reachable without a manager token.
"""
import pytest

import routers.reviews as rv


@pytest.fixture
def spy(monkeypatch):
    """Capture the SQL/params each endpoint issues, and return a plausible row."""
    calls = []
    row = {
        "id": "r1", "rating": 5, "body": "طعمٌ أصلي", "city": "دبي",
        "status": "pending", "created_at": "2026-08-01T10:00:00Z", "user_id": "me",
    }

    def _fetch_all(sql, params=None):
        calls.append((" ".join(sql.split()), list(params or [])))
        # no list query selects user_id, so the fake list row doesn't carry one either
        return [{**{k: v for k, v in row.items() if k != "user_id"},
                 "author": "أحمد", "total_count": 1, "avg_rating": 4.5}]

    def _fetch_one(sql, params=None):
        calls.append((" ".join(sql.split()), list(params or [])))
        return {**row}

    monkeypatch.setattr(rv, "fetch_all", _fetch_all)
    monkeypatch.setattr(rv, "fetch_one", _fetch_one)
    monkeypatch.setattr(rv, "log_action", lambda **k: None)
    monkeypatch.setattr(rv, "notify_managers", lambda **k: None)
    monkeypatch.setattr(rv, "notify_users", lambda *a, **k: None)
    return calls


# --- the public list ---------------------------------------------------------
def test_public_list_returns_only_approved_reviews(client, spy):
    assert client.get("/api/reviews").status_code == 200
    sql, _ = spy[-1]
    assert "r.status = 'approved'" in sql, "pending/rejected reviews must never be public"


def test_public_list_never_exposes_the_reviewer_identity(client, spy):
    body = client.get("/api/reviews").json()
    sql, _ = spy[-1]
    selected = sql.split(" from ")[0]  # the select list, without the join's u.id = r.user_id
    assert "user_id" not in selected and "email" not in selected, "the card carries no identity column"
    card = body["reviews"][0]
    assert "user_id" not in card and "author_email" not in card
    assert body["total"] == 1 and body["average"] == 4.5
    # the window-function columns are an implementation detail, not part of the card
    assert "total_count" not in card and "avg_rating" not in card


def test_public_list_leads_with_the_best_rated(client, spy):
    """The storefront shows three cards by default — they should be the best ones,
    and every page must share that order or offset paging would repeat rows."""
    client.get("/api/reviews")
    sql, params = spy[-1]
    assert "order by r.rating desc, r.created_at desc" in sql
    assert params == [3, 0], "three by default"


def test_public_list_paginates_within_bounds(client, spy):
    client.get("/api/reviews?limit=3&offset=6")
    _, params = spy[-1]
    assert params == [3, 6]
    # over the cap: FastAPI rejects it, and main.py turns validation errors into 400
    assert client.get("/api/reviews?limit=999").status_code == 400


def test_public_list_needs_no_session(client, spy):
    assert client.get("/api/reviews").status_code == 200


# --- writing ----------------------------------------------------------------
@pytest.mark.parametrize("method,path", [
    ("get", "/api/reviews/mine"),
    ("delete", "/api/reviews/6f1d4e0e-0000-4000-8000-000000000000"),
])
def test_reading_or_removing_your_own_still_needs_a_session(client, method, path):
    """Writing is open to guests, but "my review" and deleting it identify a person."""
    assert getattr(client, method)(path).status_code == 401


def test_submitting_stores_the_callers_own_id_and_starts_pending(client, as_user, spy):
    as_user({"id": "me", "role": "customer"})
    res = client.post("/api/reviews", json={"rating": 5, "body": "ممتاز جدًا", "city": "دبي"})
    assert res.status_code == 201
    sql, params = spy[-1]
    assert params[0] == "me", "the author is the token's user, never a client-supplied id"
    assert "status = 'pending'" in sql, "an edited review must go back through moderation"
    assert "on conflict (user_id)" in sql, "one review per customer — the second edits the first"


@pytest.mark.parametrize("payload", [
    {"rating": 0, "body": "نصٌّ كافٍ"},
    {"rating": 6, "body": "نصٌّ كافٍ"},
    {"rating": "five", "body": "نصٌّ كافٍ"},
    {"body": "نصٌّ كافٍ"},
    {"rating": 4},
    {"rating": 4, "body": "  "},
    {"rating": 4, "body": "x" * 601},
])
def test_bad_submissions_are_rejected(client, as_user, spy, payload):
    as_user({"id": "me", "role": "customer"})
    assert client.post("/api/reviews", json=payload).status_code == 400


def test_a_customer_can_only_delete_their_own(client, as_user, spy):
    as_user({"id": "me", "role": "customer"})
    rid = "6f1d4e0e-0000-4000-8000-000000000000"
    assert client.delete(f"/api/reviews/{rid}").status_code == 204
    sql, params = spy[-1]
    assert "user_id = %s" in sql and params == [rid, "me"]


def test_a_manager_can_delete_any_review(client, as_user, spy):
    as_user({"id": "boss", "role": "manager"})
    rid = "6f1d4e0e-0000-4000-8000-000000000000"
    assert client.delete(f"/api/reviews/{rid}").status_code == 204
    sql, _ = spy[-1]
    assert "user_id" not in sql


def test_a_malformed_id_is_a_404_not_a_500(client, as_user, spy):
    as_user({"id": "me", "role": "customer"})
    assert client.delete("/api/reviews/not-a-uuid").status_code == 404


# --- moderation -------------------------------------------------------------
@pytest.mark.parametrize("method,path", [
    ("get", "/api/reviews/all"),
    ("get", "/api/reviews/pending-count"),
    ("patch", "/api/reviews/6f1d4e0e-0000-4000-8000-000000000000"),
])
def test_moderation_is_manager_only(client, method, path, spy):
    from conftest import token_for
    assert getattr(client, method)(path).status_code == 401
    shopper = {"Authorization": f"Bearer {token_for('me', 'customer')}"}
    assert getattr(client, method)(path, headers=shopper).status_code == 403


def test_approving_publishes_and_tells_the_author(client, spy, monkeypatch):
    from conftest import token_for
    sent = []
    monkeypatch.setattr(rv, "notify_users", lambda ids, **k: sent.append((ids, k)))
    headers = {"Authorization": f"Bearer {token_for('boss', 'manager')}"}
    rid = "6f1d4e0e-0000-4000-8000-000000000000"
    res = client.patch(f"/api/reviews/{rid}", json={"status": "approved"}, headers=headers)
    assert res.status_code == 200
    assert "user_id" not in res.json()["review"], "don't hand the author's id back to the client"
    assert sent and sent[0][0] == ["me"]


def test_rejecting_stays_silent(client, spy, monkeypatch):
    from conftest import token_for
    sent = []
    monkeypatch.setattr(rv, "notify_users", lambda ids, **k: sent.append(ids))
    headers = {"Authorization": f"Bearer {token_for('boss', 'manager')}"}
    rid = "6f1d4e0e-0000-4000-8000-000000000000"
    client.patch(f"/api/reviews/{rid}", json={"status": "rejected"}, headers=headers)
    assert sent == [], "no 'your review was turned down' notification"


def test_unknown_status_is_rejected(client, spy):
    from conftest import token_for
    headers = {"Authorization": f"Bearer {token_for('boss', 'manager')}"}
    rid = "6f1d4e0e-0000-4000-8000-000000000000"
    assert client.patch(f"/api/reviews/{rid}", json={"status": "published"}, headers=headers).status_code == 400


def test_the_queue_can_be_filtered_by_status_only(client, spy):
    from conftest import token_for
    headers = {"Authorization": f"Bearer {token_for('boss', 'manager')}"}
    client.get("/api/reviews/all?status=pending", headers=headers)
    _, params = spy[-1]
    assert params[0] == "pending"
    # an unknown status falls back to "everything" rather than injecting the value
    client.get("/api/reviews/all?status=' or 1=1--", headers=headers)
    _, params = spy[-1]
    assert params == [50, 0]

# --- writing without an account ----------------------------------------------
GUEST_REVIEW = {"rating": 5, "body": "زيت الزيتون أصليّ", "name": "أم خالد", "city": "دبي"}


def test_a_guest_can_write_a_review(client, spy):
    res = client.post("/api/reviews", json=GUEST_REVIEW)
    assert res.status_code == 201, res.text
    sql, params = spy[-1]
    assert "author_name" in sql, "a guest review carries the name they typed"
    assert "on conflict" not in sql, "no account to upsert on — each guest row is its own"
    assert params[0] == "أم خالد"


def test_a_guest_review_starts_pending_like_any_other(client, spy):
    client.post("/api/reviews", json=GUEST_REVIEW)
    sql, _ = spy[-1]
    # the column default is 'pending'; the insert must not set a status of its own
    assert "status" not in sql.split("returning")[0], "a guest can't publish straight to the storefront"


@pytest.mark.parametrize("name", ["", "  ", "x", None])
def test_a_guest_must_give_a_name(client, spy, name):
    """The card has nothing else to show above the city."""
    assert client.post("/api/reviews", json={**GUEST_REVIEW, "name": name}).status_code == 400


def test_a_guest_name_is_trimmed_and_capped(client, spy):
    client.post("/api/reviews", json={**GUEST_REVIEW, "name": "  أم   خالد  "})
    assert spy[-1][1][0] == "أم خالد", "runs of whitespace collapse"
    client.post("/api/reviews", json={**GUEST_REVIEW, "name": "خ" * 200})
    assert len(spy[-1][1][0]) == rv.NAME_MAX


def test_guest_reviews_are_rate_limited_harder_than_signed_in_ones(client, spy):
    """No signup stands between a bot and the moderation queue."""
    codes = [client.post("/api/reviews", json=GUEST_REVIEW).status_code for _ in range(6)]
    assert 429 in codes
    assert codes.count(201) <= 3


def test_a_signed_in_review_still_upserts_on_the_account(client, as_user, spy):
    as_user({"id": "me", "role": "customer"})
    client.post("/api/reviews", json={"rating": 4, "body": "ممتاز جدًا"})
    sql, params = spy[-1]
    assert "on conflict (user_id)" in sql
    assert params[0] == "me"
    assert "author_name" not in sql, "the account's own name is used, not a typed one"


# --- the optional photo -------------------------------------------------------
DATA_URL = "data:image/webp;base64,UklGRg=="


@pytest.fixture
def stored_image(monkeypatch):
    monkeypatch.setattr(rv, "save_image", lambda src, subdir=None: "/media/reviews/abc.webp")
    monkeypatch.setattr(rv, "make_thumb", lambda src: "/media/reviews/abc-thumb.webp")


def test_a_photo_is_stored_as_files_not_base64(client, spy, stored_image):
    res = client.post("/api/reviews", json={**GUEST_REVIEW, "image": DATA_URL})
    assert res.status_code == 201
    _sql, params = spy[-1]
    assert "/media/reviews/abc.webp" in params and "/media/reviews/abc-thumb.webp" in params
    assert not any(str(p).startswith("data:") for p in params), "no data-URL may reach the row"


def test_a_remote_url_is_refused(client, spy, stored_image):
    """A review must not point at an image the shop can't vouch for or keep alive."""
    for src in ["https://example.com/cat.jpg", "/media/products/x.webp", "javascript:alert(1)"]:
        assert client.post("/api/reviews", json={**GUEST_REVIEW, "image": src}).status_code == 400


def test_an_oversized_upload_is_refused(client, spy, stored_image):
    huge = "data:image/png;base64," + "A" * (rv.IMAGE_MAX_CHARS + 1)
    assert client.post("/api/reviews", json={**GUEST_REVIEW, "image": huge}).status_code == 400


def test_an_undecodable_upload_is_refused(client, spy, monkeypatch):
    """media.py returns its input when it can't decode — that must be a 400, not a row."""
    monkeypatch.setattr(rv, "save_image", lambda src, subdir=None: src)
    assert client.post("/api/reviews", json={**GUEST_REVIEW, "image": DATA_URL}).status_code == 400


def test_no_photo_is_the_normal_case(client, spy):
    assert client.post("/api/reviews", json=GUEST_REVIEW).status_code == 201
    _sql, params = spy[-1]
    assert params[-2:] == [None, None], "image and thumb are null when nothing was attached"


def test_the_public_card_carries_the_photo(client, spy):
    client.get("/api/reviews")
    selected = spy[-1][0].split(" from ")[0]
    assert "r.thumb_url" in selected and "r.image_url" in selected


def test_the_card_falls_back_to_a_guest_name(client, spy):
    """`author` comes from the account when there is one, else the typed name."""
    client.get("/api/reviews")
    selected = spy[-1][0].split(" from ")[0]
    assert "coalesce(nullif(btrim(u.full_name), \'\'), nullif(btrim(r.author_name), \'\')) as author" in selected
    assert "left join users" in spy[-1][0], "a guest review has no user row to join to"
