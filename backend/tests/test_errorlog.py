"""The reporter that carries a server-side failure to the manager's errors page.

Everything it is called from is an except block whose whole purpose is not failing —
a customer's WhatsApp, a push, an audit row, one order in the nightly sweep. So the
properties worth pinning down are not about what it records but about what it must
never do: raise, recurse, or bury one subsystem's failures under another's noise.
"""
import threading

import pytest

import errorlog


@pytest.fixture(autouse=True)
def fresh():
    """The throttle is module state and would otherwise leak between tests."""
    errorlog._last.clear()
    errorlog._busy.on = False
    yield
    errorlog._last.clear()


@pytest.fixture
def written(monkeypatch):
    rows = []
    monkeypatch.setattr(errorlog, "execute", lambda sql, params=None: rows.append(params))
    return rows


# --- it must never raise -----------------------------------------------------
def test_a_failing_insert_is_swallowed(monkeypatch):
    """The database being down is exactly when this is called and exactly when it
    cannot work. Raising here turns a missed WhatsApp into a 500 on a paid order."""
    monkeypatch.setattr(errorlog, "execute",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no database")))
    assert errorlog.report_error("t", ValueError("boom")) is False


def test_nothing_thrown_by_a_broken_argument(written):
    class Awkward(Exception):
        def __str__(self): raise RuntimeError("even my message is broken")

    assert errorlog.report_error("t", Awkward()) is False
    assert errorlog.report_error("t2", None) is True, "a non-exception is still worth a row"


def test_the_guard_is_released_after_a_failed_insert(monkeypatch, written):
    """_busy is set around the write. Left stuck on, it would silence this thread's
    reporting for the life of the process — the failure mode nobody would notice."""
    monkeypatch.setattr(errorlog, "execute",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no database")))
    errorlog.report_error("t", ValueError("boom"))
    assert getattr(errorlog._busy, "on", False) is False
    monkeypatch.setattr(errorlog, "execute", lambda sql, params=None: written.append(params))
    errorlog._last.clear()
    assert errorlog.report_error("t", ValueError("again")) is True


# --- it must never recurse ---------------------------------------------------
def test_a_report_raised_while_reporting_does_not_loop():
    """The insert can fail for the reason the caller failed, and whatever handles
    that failure may itself report. One level in, this has to answer no."""
    depth = {"n": 0}

    def reentrant(sql, params=None):
        depth["n"] += 1
        if depth["n"] > 3:
            raise AssertionError("report_error recursed")
        errorlog.report_error("inner", RuntimeError("from inside the insert"))
        raise RuntimeError("and then the insert failed")

    errorlog.execute, original = reentrant, errorlog.execute
    try:
        assert errorlog.report_error("outer", ValueError("boom")) is False
        assert depth["n"] == 1, "the nested call must not reach the database at all"
    finally:
        errorlog.execute = original


# --- the throttle ------------------------------------------------------------
def test_a_burst_of_one_failure_writes_one_row(written):
    """An expired WhatsApp token fails for every order in the shop. A page with a
    thousand identical rows on it is not more information than one."""
    for _ in range(50):
        errorlog.report_error("whatsapp", RuntimeError("token expired"))
    assert len(written) == 1


def test_one_noisy_subsystem_does_not_hide_another(written):
    """Where this differs from the storefront reporter's single clock, and why: the
    rare failure is the one the page exists for."""
    for _ in range(20):
        errorlog.report_error("whatsapp", RuntimeError("token expired"))
    assert errorlog.report_error("order-after-commit", RuntimeError("a payment")) is True
    assert len(written) == 2


def test_the_throttle_lets_the_next_one_through(written, monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(errorlog.time, "monotonic", lambda: clock["t"])
    assert errorlog.report_error("t", RuntimeError("one")) is True
    assert errorlog.report_error("t", RuntimeError("two")) is False
    clock["t"] += errorlog._MIN_GAP_SECONDS + 0.01
    assert errorlog.report_error("t", RuntimeError("three")) is True


def test_a_failed_write_still_costs_its_turn(monkeypatch):
    """A database refusing connections refuses them slowly. A hundred callers each
    queueing to discover that is its own outage, so the clock is stamped before the
    write, not after it."""
    monkeypatch.setattr(errorlog, "execute",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no database")))
    assert errorlog.report_error("t", ValueError("boom")) is False
    assert errorlog._last.get("t"), "the attempt must still hold the tag's slot"


def test_two_threads_racing_one_tag_write_once(written, monkeypatch):
    monkeypatch.setattr(errorlog.time, "monotonic", lambda: 500.0)
    threads = [threading.Thread(target=errorlog.report_error,
                                args=("shared", RuntimeError("x"))) for _ in range(12)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert len(written) == 1, "the check and the stamp have to be one step"


# --- what lands on the page --------------------------------------------------
def test_the_row_names_the_call_site_and_the_failure(written):
    errorlog.report_error("order-email", ValueError("no such mailbox"))
    name, message, detail = written[0]
    assert name == errorlog._SERVER, "not a customer report — the page says so"
    assert message == "[order-email] ValueError: no such mailbox"
    assert "ValueError" in detail, "the traceback is the part worth having"


def test_a_note_carries_what_the_tag_cannot(written):
    """Which order, which customer — the varying part, kept out of the tag so the
    throttle stays keyed on a fixed set."""
    errorlog.report_error("order-after-commit", RuntimeError("Meta said no"),
                          note="order 4f2a1b9c — customer confirmation")
    assert written[0][1] == ("[order-after-commit] order 4f2a1b9c — customer confirmation "
                             "— RuntimeError: Meta said no")


def test_the_columns_are_not_overrun(written):
    errorlog.report_error("t", RuntimeError("x" * 5000), detail="y" * 9000)
    _name, message, detail = written[0]
    assert len(message) <= 1000 and len(detail) <= 4000


def test_a_deep_stack_keeps_the_end_that_matters(written):
    """The tail, not the head: the frames nearest the failure are the ones that say
    what broke, and a truncated traceback that stops before them says nothing."""
    errorlog.report_error("t", RuntimeError("boom"), detail="head" + "." * 9000 + "TAIL")
    assert written[0][2].endswith("TAIL")


# --- and the call sites are wired --------------------------------------------
def test_every_swallowed_handler_reports(monkeypatch):
    """Each of these printed into stdout and nowhere else. The point of the change is
    that none of them is silent any more."""
    import ast
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    missing = []
    for f in sorted(root.glob("*.py")) + sorted((root / "routers").glob("*.py")):
        if f.name in ("errorlog.py", "conftest.py"):
            continue
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ExceptHandler):
                continue
            body = ast.dump(ast.Module(body=node.body, type_ignores=[]))
            if "Raise(" in body or "'print'" not in body:
                continue   # re-raised, or an intentional quiet fallback (tier 3)
            if "'report_error'" not in body:
                missing.append(f"{f.relative_to(root)}:{node.lineno}")
    assert missing == ["notify.py:24"], (
        "a handler that only prints is invisible outside the container logs. The one "
        "exception is the timezone fallback at import time: a note about the machine "
        "the shop is running on, not a failure — and it fires before there is a pool "
        f"to write it with. Unreported: {missing}"
    )
