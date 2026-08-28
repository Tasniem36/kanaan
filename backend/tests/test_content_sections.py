"""Editable section headings (the reviews section's eyebrow/title/description).

They live in the settings table under 'section:<key>'. The things worth pinning
down: only a manager may write them, only known sections exist, and the reader is
public so the storefront can render them.
"""
import pytest

import routers.content as content


@pytest.fixture
def spy(monkeypatch):
    calls = []

    def _fetch_all(sql, params=None):
        calls.append((" ".join(sql.split()), list(params or [])))
        return [{"key": "section:reviews", "value": {"title_ar": "ماذا يقول عملاؤنا"}}]

    monkeypatch.setattr(content, "fetch_all", _fetch_all)
    monkeypatch.setattr(content, "fetch_one", lambda sql, params=None: (
        calls.append((" ".join(sql.split()), list(params or []))) or {"key": "section:reviews"}
    ))
    return calls


def test_reading_sections_is_public_and_keyed_by_section(client, spy):
    body = client.get("/api/content/sections").json()
    assert body == {"sections": {"reviews": {"title_ar": "ماذا يقول عملاؤنا"}}}, \
        "the 'section:' prefix is storage detail, not part of the response"


def test_editing_a_section_requires_a_manager(client):
    from conftest import token_for
    assert client.patch("/api/content/sections/reviews", json={}).status_code == 401
    shopper = {"Authorization": f"Bearer {token_for('me', 'customer')}"}
    assert client.patch("/api/content/sections/reviews", json={}, headers=shopper).status_code == 403


def test_only_known_sections_can_be_written(client, spy):
    from conftest import token_for
    headers = {"Authorization": f"Bearer {token_for('boss', 'manager')}"}
    assert client.patch("/api/content/sections/reviews", json={"title_ar": "x"}, headers=headers).status_code == 200
    # an arbitrary key must not become a settings row
    assert client.patch("/api/content/sections/../delivery", json={"title_ar": "x"}, headers=headers).status_code == 404
    assert client.patch("/api/content/sections/pantry", json={"title_ar": "x"}, headers=headers).status_code == 404


def test_a_save_writes_every_field_and_caps_the_length(client, spy):
    from conftest import token_for
    headers = {"Authorization": f"Bearer {token_for('boss', 'manager')}"}
    res = client.patch("/api/content/sections/reviews",
                       json={"desc_ar": "  آراءٌ   حقيقيّة  ", "desc_en": "x" * 900, "nope": "ignored"},
                       headers=headers)
    saved = res.json()["section"]
    assert set(saved) == set(content._SECTION_FIELDS) | {"hidden"}, \
        "a save is a full replace, so blanks can clear a field"
    assert saved["hidden"] is False, "the section shows unless the manager hides it"
    assert saved["desc_ar"] == "آراءٌ حقيقيّة", "runs of whitespace are collapsed"
    assert len(saved["desc_en"]) == content._SECTION_FIELDS["desc_en"]
    assert "nope" not in saved
    assert saved["title_ar"] == "", "an omitted field is stored blank → falls back to the bundled text"


# --- the auth pages' panel --------------------------------------------------
def test_the_auth_panels_are_sections_too(client, monkeypatch):
    """Sign-in, sign-up and reset are editable the same way a homepage heading is —
    one mechanism, not a parallel one."""
    import routers.content as c
    assert set(c._SECTION_KEYS) == {"reviews", "login", "register", "reset"}


def test_an_auth_panel_saves_its_photograph(client, monkeypatch):
    from conftest import token_for
    import routers.content as c
    saved = {}
    monkeypatch.setattr(c, "fetch_one", lambda sql, params=None: saved.update(key=params[0], value=params[1]) or {"key": params[0]})
    res = client.patch("/api/content/sections/login",
                       json={"title_ar": "س", "image": "/images/olives.jpg"},
                       headers={"Authorization": f"Bearer {token_for('boss', 'manager')}"})
    assert res.status_code == 200
    assert res.json()["section"]["image"] == "/images/olives.jpg"
    assert saved["key"] == "section:login"


def test_a_section_without_a_photograph_never_grows_one(client, monkeypatch):
    """`reviews` is a heading, not a panel — an image sent to it is ignored."""
    from conftest import token_for
    import routers.content as c
    monkeypatch.setattr(c, "fetch_one", lambda sql, params=None: {"key": "section:reviews"})
    res = client.patch("/api/content/sections/reviews",
                       json={"title_ar": "س", "image": "/images/olives.jpg"},
                       headers={"Authorization": f"Bearer {token_for('boss', 'manager')}"})
    assert "image" not in res.json()["section"]


def test_an_uploaded_photograph_becomes_a_file(client, monkeypatch):
    """A data-URL left in the row would be re-read out of the database on every
    visit to the sign-in page."""
    from conftest import token_for
    import routers.content as c
    seen = []
    monkeypatch.setattr(c, "save_image", lambda src, subdir=None: seen.append((src, subdir)) or "/media/content/a.webp")
    monkeypatch.setattr(c, "fetch_one", lambda sql, params=None: {"key": "section:register"})
    res = client.patch("/api/content/sections/register",
                       json={"image": "data:image/png;base64,AAAA"},
                       headers={"Authorization": f"Bearer {token_for('boss', 'manager')}"})
    assert res.json()["section"]["image"] == "/media/content/a.webp"
    assert seen[0][1] == "content", "kept out of the products folder"


def test_an_unknown_section_is_still_refused(client):
    from conftest import token_for
    res = client.patch("/api/content/sections/nonsense", json={},
                       headers={"Authorization": f"Bearer {token_for('boss', 'manager')}"})
    assert res.status_code == 404
