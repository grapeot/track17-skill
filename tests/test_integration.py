"""L2 integration tests against the live 17TRACK API.

Opt-in only. Requires:
    RUN_TRACK17_INTEGRATION=1
    SEVENTEENTRACK_KEY=<your key>
    TRACK17_TEST_NUMBER=<a number already registered with your key>
"""
import json
import os

import pytest

from track17_skill import cli

KEY = os.environ.get("SEVENTEENTRACK_KEY", "")
NUMBER = os.environ.get("TRACK17_TEST_NUMBER", "")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not (KEY and NUMBER), reason="set SEVENTEENTRACK_KEY and TRACK17_TEST_NUMBER"),
]


def _env(code, capsys):
    return json.loads(capsys.readouterr().out)


def test_check_key_valid(capsys):
    code = cli.main(["check"])
    env = _env(code, capsys)
    assert code == 0
    assert env["error"] is None
    assert env["data"]["count"] >= 1


def test_get_registered_number(capsys):
    code = cli.main(["get", NUMBER])
    env = _env(code, capsys)
    assert code == 0
    s = env["data"]["summary"]
    assert s is not None
    assert s["number"] == NUMBER
    assert s["status"]


def test_register_idempotent_noop(capsys):
    code = cli.main(["register", NUMBER])
    env = _env(code, capsys)
    # Already registered from a previous session -> exit 0 no-op. If the
    # number was somehow unregistered, register succeeds -> also exit 0.
    assert code == 0
    assert env["error"] is None


def test_get_unregistered_number_is_no_data(capsys):
    code = cli.main(["get", "000000000000"])
    env = _env(code, capsys)
    assert code == cli.EXIT_NO_DATA
    assert env["error"] is None  # rejection is data, not an HTTP error
    assert env["data"]["summary"] is None
    assert env["data"]["rejected"]


def test_bad_key_is_auth_error(capsys, monkeypatch):
    monkeypatch.setenv("SEVENTEENTRACK_KEY", "00000000000000000000000000000000")
    code = cli.main(["check"])
    env = _env(code, capsys)
    assert code == cli.EXIT_AUTH
    assert env["error"]["http_status"] in (401, 403)
    assert env["error"]["raw_body"]
