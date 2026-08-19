"""Housekeeping for the tables that grow forever.

Every rule here deletes rows, so the tests are about blast radius: the window must be
bounded, a mistyped setting must never widen it to everything, and each statement must
touch only its own table.
"""
import maintenance


def _capture(monkeypatch, returned=3):
    calls = []

    def fake_fetch_one(sql, params=None):
        calls.append((" ".join(sql.split()), list(params or [])))
        return {"n": returned}

    monkeypatch.setattr(maintenance, "fetch_one", fake_fetch_one)
    return calls


def test_activity_older_than_the_window_goes(monkeypatch):
    calls = _capture(monkeypatch)
    assert maintenance.prune_audit_logs(90) == 3
    sql, params = calls[-1]
    assert "delete from audit_logs" in sql
    assert "created_at < now() - (%s || ' days')::interval" in sql
    assert params == [90]


def test_the_window_is_configurable(monkeypatch):
    calls = _capture(monkeypatch)
    monkeypatch.setenv("AUDIT_RETENTION_DAYS", "30")
    maintenance.prune_audit_logs()
    assert calls[-1][1] == [30]


def test_a_mistyped_window_cannot_empty_the_table(monkeypatch):
    """0, a negative, or nonsense must not turn into "delete everything"."""
    calls = _capture(monkeypatch)
    for value, expected in [("0", maintenance.MIN_DAYS), ("-5", maintenance.MIN_DAYS),
                            ("banana", maintenance.AUDIT_DAYS), ("", maintenance.AUDIT_DAYS)]:
        monkeypatch.setenv("AUDIT_RETENTION_DAYS", value)
        maintenance.prune_audit_logs()
        assert calls[-1][1] == [expected], f"{value!r} became {calls[-1][1]}"


def test_abandoned_signups_are_removed(monkeypatch):
    """Each row holds the password hash the person typed, and an expired verification
    can never be completed — so it is only risk."""
    calls = _capture(monkeypatch)
    assert maintenance.prune_dead_signups() == 3
    sql, _ = calls[-1]
    assert "delete from signup_verifications" in sql
    assert "expires_at < now() - interval '1 day'" in sql, "a grace period past expiry"


def test_pruning_touches_nothing_else(monkeypatch):
    """Orders, reviews, messages and the rest are business records — never pruned."""
    calls = _capture(monkeypatch)
    maintenance.prune()
    touched = {sql.split("delete from ")[1].split()[0] for sql, _ in calls}
    assert touched == {"audit_logs", "signup_verifications"}


def test_prune_reports_what_it_removed(monkeypatch):
    _capture(monkeypatch, returned=7)
    assert maintenance.prune() == {"audit_logs": 7, "signup_verifications": 7}
