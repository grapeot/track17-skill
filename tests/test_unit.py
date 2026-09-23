"""L1 offline tests: no network, no API key.

Run: .venv/bin/python -m pytest tests/ -v
"""
import json
from pathlib import Path

import pytest

from track17_skill import carriers, cli, normalize
from track17_skill.client import ApiError, KeyMissingError, NetworkError, load_key

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


# ---------- envelope / exit-code contract ----------

def assert_envelope_shape(env):
    assert set(env.keys()) == {"command", "input", "data", "error"}
    assert env["command"]


def test_classify_error_auth_http401():
    code, err = cli.classify_exception(ApiError(401, -18010002, "Invalid security key.", '{"code": -18010002}'))
    assert code == cli.EXIT_AUTH
    assert err["type"] == "auth"
    assert err["http_status"] == 401
    assert err["api_code"] == -18010002
    assert err["raw_body"]


def test_classify_error_quota_http429():
    code, err = cli.classify_exception(ApiError(429, None, "rate limited", "slow down"))
    assert code == cli.EXIT_QUOTA
    assert err["raw_body"] == "slow down"


def test_classify_error_network():
    code, err = cli.classify_exception(NetworkError("timed out"))
    assert code == cli.EXIT_SERVER
    assert err["type"] == "network"
    assert "timed out" in err["message"]


def test_classify_error_key_missing():
    code, err = cli.classify_exception(KeyMissingError("no key"))
    assert code == cli.EXIT_USAGE


def test_classify_rejected_register_idempotent_is_success():
    rejected = [{"number": "123", "error": {"code": -18019901, "message": "already registered"}}]
    assert cli.classify_rejected("register", rejected) == cli.EXIT_OK


def test_classify_rejected_register_quota_is_11():
    rejected = [{"number": "123", "error": {"code": -18019908, "message": "quotas ran out"}}]
    assert cli.classify_rejected("register", rejected) == cli.EXIT_QUOTA


def test_classify_rejected_get_not_registered_is_12():
    rejected = [{"number": "123", "error": {"code": -18019902, "message": "not registered yet"}}]
    assert cli.classify_rejected("get", rejected) == cli.EXIT_NO_DATA


def test_classify_rejected_auth_code_is_10():
    rejected = [{"number": "123", "error": {"code": -18010001, "message": "IP not whitelisted"}}]
    assert cli.classify_rejected("get", rejected) == cli.EXIT_AUTH


# ---------- normalization (real v2.4 response fixture) ----------

def _load_fixture():
    return json.loads((FIXTURES / "gettrackinfo_info_received.json").read_text())


def test_normalize_gettrackinfo_real_fixture():
    out = normalize.summarize_gettrackinfo(_load_fixture())
    s = out["summary"]
    assert s["number"] == "123456789012"
    assert s["carrier"] == {"code": 100003, "name": "FedEx"}
    assert s["status"] == "InfoReceived"
    assert s["sub_status"] == "InfoReceived"
    assert s["service_type"] == "FedEx 2Day"
    assert s["route"]["origin"] == "Redmond, WA"
    assert s["route"]["destination"] == "San Jose, CA"
    assert s["weight_kg"] == 0.45
    assert isinstance(s["weight_kg"], float)
    assert s["days_since_last_update"] == 7
    assert s["provider_tips"].startswith("Label created")
    assert s["event_count"] == 1
    assert s["latest_event"]["description"] == "Shipment information sent to FedEx"
    assert s["latest_event"]["time"] == "2026-09-17 11:40:22"
    assert out["rejected"] == []


def test_normalize_rejected_only_yields_null_summary():
    resp = {"code": 0, "data": {"accepted": [], "rejected": [
        {"number": "123", "error": {"code": -18019909, "message": "No tracking info at the moment."}}]}}
    out = normalize.summarize_gettrackinfo(resp)
    assert out["summary"] is None
    assert out["rejected"][0]["error"]["code"] == -18019909


def test_normalize_survives_none_items():
    resp = {"code": 0, "data": {"accepted": [None], "rejected": []}}
    assert normalize.summarize_gettrackinfo(resp)["summary"] is None
    resp = {"code": 0, "data": {"accepted": [{
        "number": "1", "carrier": 1,
        "track_info": {"tracking": {"providers": [None, {"events": [None]}]}}}
    ]}}
    s = normalize.summarize_gettrackinfo(resp)["summary"]
    assert s["event_count"] == 0
    resp = {"code": 0, "data": {"accepted": [None, {"number": "9"}]}}
    assert normalize.summarize_gettracklist(resp)["items"] == [
        {"number": "9", "carrier_code": None, "status": None, "sub_status": None, "sync_status": None}
    ]


def test_normalize_events_capped_and_newest_first():
    events = [{"time_raw": f"2026-01-{i:02d} 00:00:00", "description": f"e{i}"} for i in range(1, 20)]
    resp = {"code": 0, "data": {"accepted": [{
        "number": "1", "carrier": 1,
        "track_info": {"tracking": {"providers": [{"events": events}]}}}]}}
    s = normalize.summarize_gettrackinfo(resp)["summary"]
    assert s["event_count"] == 19
    assert len(s["events"]) == normalize.MAX_EVENTS
    assert s["events"][0]["description"] == "e19"  # newest first


# ---------- key loading ----------

def test_load_key_env_wins(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("SEVENTEENTRACK_KEY=from-file\n")
    monkeypatch.setenv("SEVENTEENTRACK_KEY", "from-env")
    assert load_key() == "from-env"


def test_load_key_env_file_fallback(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SEVENTEENTRACK_KEY", raising=False)
    (tmp_path / ".env").write_text('SEVENTEENTRACK_KEY="from-file"\n')
    assert load_key() == "from-file"


def test_load_key_explicit_env_file_beats_cwd(monkeypatch, tmp_path):
    # Explicit --env-file wins over ./.env (env var still wins over both).
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SEVENTEENTRACK_KEY", raising=False)
    (tmp_path / ".env").write_text("SEVENTEENTRACK_KEY=from-cwd\n")
    other = tmp_path / "elsewhere.env"
    other.write_text("SEVENTEENTRACK_KEY=explicit\n")
    assert load_key(str(other)) == "explicit"
    assert load_key() == "from-cwd"


def test_load_key_env_file_parsing_variants(monkeypatch, tmp_path):
    monkeypatch.delenv("SEVENTEENTRACK_KEY", raising=False)
    for line in (
        "export SEVENTEENTRACK_KEY=with-export",
        'SEVENTEENTRACK_KEY="quoted-value"',
        "SEVENTEENTRACK_KEY=with-comment # trailing note",
    ):
        env = tmp_path / "k.env"
        env.write_text(line + "\n")
        assert load_key(str(env)) in ("with-export", "quoted-value", "with-comment"), line


def test_load_key_missing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SEVENTEENTRACK_KEY", raising=False)
    with pytest.raises(KeyMissingError):
        load_key()


# ---------- run_api with the transport injected ----------

def _patch_call(monkeypatch, result=None, exc=None):
    def fake(endpoint, payload, key, timeout=60):
        if exc is not None:
            raise exc
        return result
    monkeypatch.setattr(cli, "api_call", fake)


def test_run_api_success_envelope(monkeypatch):
    _patch_call(monkeypatch, result=(200, _load_fixture()))
    code, env = cli.run_api("get", {"number": "123456789012"}, "gettrackinfo",
                            [{"number": "123456789012"}], "k", transform=normalize.summarize_gettrackinfo)
    assert code == cli.EXIT_OK
    assert_envelope_shape(env)
    assert env["error"] is None
    assert env["data"]["summary"]["status"] == "InfoReceived"
    assert env["data"]["raw"]["code"] == 0  # raw always attached on success


def test_run_api_http_error_preserves_raw(monkeypatch):
    _patch_call(monkeypatch, exc=ApiError(401, -18010002, "Invalid security key.", '{"code": -18010002, "message": "x"}'))
    code, env = cli.run_api("check", {}, "gettracklist", {}, "bad-key", transform=normalize.summarize_gettracklist)
    assert code == cli.EXIT_AUTH
    assert_envelope_shape(env)
    assert env["data"] is None
    assert env["error"]["http_status"] == 401
    assert env["error"]["raw_body"]


def test_run_api_top_level_error_code(monkeypatch):
    _patch_call(monkeypatch, result=(200, {"code": -18019908, "message": "Your quotas have ran out."}))
    code, env = cli.run_api("register", {"number": "1"}, "register", [{"number": "1"}], "k",
                            transform=normalize.summarize_register)
    assert code == cli.EXIT_QUOTA
    assert env["error"]["type"] == "quota"
    assert env["error"]["api_code"] == -18019908
    assert env["error"]["message"]


def test_run_api_top_level_server_error_is_13(monkeypatch):
    # -18010003 arrives with HTTP 200 and must map to 13, not 12.
    _patch_call(monkeypatch, result=(200, {"code": -18010003, "message": "Internal service error."}))
    code, env = cli.run_api("check", {}, "gettracklist", {}, "k",
                            transform=normalize.summarize_gettracklist)
    assert code == cli.EXIT_SERVER
    assert env["error"]["type"] == "server"
    assert env["error"]["api_code"] == -18010003


def test_read_timeout_becomes_network_error_envelope(monkeypatch):
    # A socket read timeout escapes urllib's URLError wrapper; the client
    # must convert it to NetworkError so main() still emits an envelope.
    import track17_skill.client as client_mod

    def fake_urlopen(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(client_mod.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(NetworkError):
        client_mod.api_call("gettrackinfo", [{}], "k", timeout=0.5)
    code, err = cli.classify_exception(NetworkError("timed out"))
    assert code == cli.EXIT_SERVER
    assert err["type"] == "network"


def test_run_api_register_idempotent_noop(monkeypatch):
    body = {"code": 0, "data": {"accepted": [], "rejected": [
        {"number": "123", "error": {"code": -18019901, "message": "already registered"}}]}}
    _patch_call(monkeypatch, result=(200, body))
    code, env = cli.run_api("register", {"number": "123"}, "register", [{"number": "123"}], "k",
                            transform=normalize.summarize_register)
    assert code == cli.EXIT_OK
    assert env["data"]["note"] == "already registered; nothing consumed"
    assert env["error"] is None


def test_run_api_get_not_registered_hint(monkeypatch):
    body = {"code": 0, "data": {"accepted": [], "rejected": [
        {"number": "999", "error": {"code": -18019902, "message": "not registered yet"}}]}}
    _patch_call(monkeypatch, result=(200, body))
    code, env = cli.run_api("get", {"number": "999"}, "gettrackinfo", [{"number": "999"}], "k",
                            transform=normalize.summarize_gettrackinfo)
    assert code == cli.EXIT_NO_DATA
    assert env["data"]["summary"] is None
    assert "register" in env["data"]["hint"]


# ---------- carriers (offline) ----------

def test_carriers_search_fedex():
    results = carriers.search("fedex")
    codes = [c["code"] for c in results]
    assert 100003 in codes


def test_carriers_by_code():
    c = carriers.by_code(100003)
    assert c and c["name"] == "FedEx" and c["country"] == "US"


def test_carriers_count():
    assert carriers.count() >= 3000


def test_carriers_search_no_match():
    assert carriers.search("zzz-nonexistent-zzz") == []


# ---------- CLI end-to-end (offline subcommands) ----------

def test_cli_carriers_search_subcommand(capsys, monkeypatch):
    monkeypatch.delenv("SEVENTEENTRACK_KEY", raising=False)
    code = cli.main(["carriers", "search", "fedex", "--limit", "3"])
    assert code == 0
    env = json.loads(capsys.readouterr().out)
    assert_envelope_shape(env)
    assert env["command"] == "carriers"
    assert len(env["data"]["results"]) <= 3


def test_cli_carriers_unknown_code(capsys):
    code = cli.main(["carriers", "get", "999999999"])
    assert code == cli.EXIT_NO_DATA


def test_cli_missing_key_is_usage_error(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SEVENTEENTRACK_KEY", raising=False)
    code = cli.main(["check"])
    assert code == cli.EXIT_USAGE
    env = json.loads(capsys.readouterr().out)
    assert env["error"]["message"]
    assert "SEVENTEENTRACK_KEY" in env["error"]["message"]


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert "track17" in capsys.readouterr().out


def test_cli_usage_error_emits_envelope(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc:
        cli.main(["get"])  # missing the required number
    assert exc.value.code == cli.EXIT_USAGE
    env = json.loads(capsys.readouterr().out)
    assert_envelope_shape(env)
    assert env["error"]["type"] == "usage"


def test_cli_carriers_get_known_code(capsys):
    code = cli.main(["carriers", "get", "100003"])
    assert code == cli.EXIT_OK
    env = json.loads(capsys.readouterr().out)
    assert env["data"]["carrier"]["name"] == "FedEx"


GET_FIXTURE_BODY = _load_fixture()
REJECTED_NOT_REGISTERED = {
    "code": 0,
    "data": {"accepted": [], "rejected": [
        {"number": "999", "error": {"code": -18019902, "message": "not registered yet"}}]},
}
REJECTED_NO_DATA_YET = {
    "code": 0,
    "data": {"accepted": [], "rejected": [
        {"number": "999", "error": {"code": -18019909, "message": "No tracking info at the moment."}}]},
}
REGISTER_OK = {"code": 0, "data": {"accepted": [{"number": "999", "carrier": 100003}], "rejected": []}}


def _seq_call(monkeypatch, responses):
    """Serve a sequence of (status, body) responses, one per api_call."""
    it = iter(responses)
    def fake(endpoint, payload, key, timeout=60):
        return next(it)
    monkeypatch.setattr(cli, "api_call", fake)


def _args_get_auto_register():
    return type("A", (), {"number": "999", "auto_register": True, "carrier": None, "lang": None})()


def test_get_auto_register_success(monkeypatch, capsys):
    _seq_call(monkeypatch, [(200, REJECTED_NOT_REGISTERED), (200, REGISTER_OK), (200, GET_FIXTURE_BODY)])
    code, env = cli.cmd_get(_args_get_auto_register(), "k")
    assert code == cli.EXIT_OK
    assert env["data"]["summary"]["status"] == "InfoReceived"
    assert env["data"]["auto_registered"] is True


def test_get_auto_register_still_no_data(monkeypatch, capsys):
    _seq_call(monkeypatch, [(200, REJECTED_NOT_REGISTERED), (200, REGISTER_OK), (200, REJECTED_NO_DATA_YET)])
    code, env = cli.cmd_get(_args_get_auto_register(), "k")
    assert code == cli.EXIT_NO_DATA
    assert env["data"]["summary"] is None
    assert "auto_registered" not in (env["data"] or {})


def test_get_auto_register_quota_failure_stops(monkeypatch, capsys):
    _seq_call(monkeypatch, [
        (200, REJECTED_NOT_REGISTERED),
        (200, {"code": -18019908, "message": "quotas ran out"}),
    ])
    code, env = cli.cmd_get(_args_get_auto_register(), "k")
    # The original get result stands: not registered, exit 12.
    assert code == cli.EXIT_NO_DATA
    assert env["data"]["summary"] is None
