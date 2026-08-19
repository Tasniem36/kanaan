"""Housekeeping for the customer activity log.

The tests are about blast radius: the activity log is the only table that may be
deleted from, nothing deletes unless explicitly asked to, the window is bounded, and
a mistyped setting can shorten it but never widen it to everything.
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
    assert maintenance.prune_audit_logs(90, apply=True) == 3
    sql, params = calls[-1]
    assert "delete from audit_logs" in sql
    assert "created_at < now() - (%s || ' days')::interval" in sql
    assert params == [90]


def test_the_window_is_configurable(monkeypatch):
    calls = _capture(monkeypatch)
    monkeypatch.setenv("AUDIT_RETENTION_DAYS", "30")
    maintenance.prune_audit_logs(apply=True)
    assert calls[-1][1] == [30]


def test_a_mistyped_window_cannot_empty_the_table(monkeypatch):
    """0, a negative, or nonsense must not turn into "delete everything"."""
    calls = _capture(monkeypatch)
    for value, expected in [("0", maintenance.MIN_DAYS), ("-5", maintenance.MIN_DAYS),
                            ("banana", maintenance.AUDIT_DAYS), ("", maintenance.AUDIT_DAYS)]:
        monkeypatch.setenv("AUDIT_RETENTION_DAYS", value)
        maintenance.prune_audit_logs(apply=True)
        assert calls[-1][1] == [expected], f"{value!r} became {calls[-1][1]}"


def test_the_activity_log_is_the_only_table_it_may_delete_from(monkeypatch):
    """Orders, reviews, messages, users and pending signups are all off limits — this
    file does not get to decide that someone's data has stopped being useful."""
    calls = _capture(monkeypatch)
    maintenance.prune(apply=True)
    touched = {sql.split("delete from ")[1].split()[0] for sql, _ in calls if "delete from " in sql}
    assert touched == {"audit_logs"}


def test_prune_reports_what_it_removed(monkeypatch):
    _capture(monkeypatch, returned=7)
    assert maintenance.prune(apply=True) == {"audit_logs": 7}


# --- nothing goes without being asked ----------------------------------------
def test_by_default_it_only_counts(monkeypatch):
    """Running the module to see what it does must not remove anything."""
    calls = _capture(monkeypatch)
    maintenance.prune()
    assert calls, "it should still have looked"
    assert not any("delete" in sql for sql, _ in calls), \
        "a report must not contain a single DELETE"
    assert all(sql.startswith("select count(*)") for sql, _ in calls)


def test_the_report_and_the_deletion_select_the_same_rows(monkeypatch):
    """A dry run is only useful if it counts exactly what --apply would remove."""
    calls = _capture(monkeypatch)
    maintenance.prune_audit_logs(45)
    maintenance.prune_audit_logs(45, apply=True)
    counted, deleted = calls[0][0], calls[1][0]
    condition = "created_at < now() - (%s || ' days')::interval"
    assert condition in counted and condition in deleted
    assert calls[0][1] == calls[1][1] == [45]
