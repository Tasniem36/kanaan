"""security.py must refuse to start with a missing / default / weak signing key.
Run in a subprocess so a failed import can't corrupt the in-process module."""
import os
import subprocess
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _import_security(env_over):
    env = {**os.environ, **env_over}
    return subprocess.run(
        [sys.executable, "-c", "import security"],
        cwd=BACKEND, env=env, capture_output=True, text=True,
    )


def test_empty_secret_refuses_to_start():
    r = _import_security({"JWT_SECRET": ""})
    assert r.returncode != 0
    assert "JWT_SECRET" in r.stderr


def test_default_secret_refuses_to_start():
    r = _import_security({"JWT_SECRET": "dev-secret-change-me"})
    assert r.returncode != 0
    assert "JWT_SECRET" in r.stderr


def test_short_secret_refuses_in_production():
    r = _import_security({"JWT_SECRET": "short", "ENV": "production"})
    assert r.returncode != 0
    assert "too short" in r.stderr.lower()


def test_good_secret_starts():
    r = _import_security({"JWT_SECRET": "x" * 64, "ENV": "production"})
    assert r.returncode == 0, r.stderr
