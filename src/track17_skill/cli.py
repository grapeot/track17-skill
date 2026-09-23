"""track17 CLI logic (kept separate from __main__ for testability).

Stable contract:
- Every subcommand prints exactly one JSON envelope to stdout:
    {"command": ..., "input": ..., "data": ..., "error": null | {...}}
- On HTTP success, data.raw always carries the full 17TRACK response.
- On failure, error always carries raw detail (http_status, api_code,
  message, raw_body) - never a generic "something went wrong".
- Exit codes:
    0  ok (including an idempotent register no-op)
    2  usage error or missing API key
    10 auth failure (bad key, IP whitelist, disabled account)
    11 quota or rate limit (HTTP 429, -18019907, -18019908)
    12 rejected / no data (agent-actionable: fix input, register first,
       or wait for the carrier to produce data)
    13 network or server error
"""
from __future__ import annotations

import argparse
import json

from . import __version__
from .carriers import by_code, count, search
from .client import (
    CODE_ALREADY_REGISTERED,
    CODE_NOT_REGISTERED,
    CODES_AUTH,
    CODES_QUOTA,
    CODES_SERVER,
    ApiError,
    KeyMissingError,
    NetworkError,
    api_call,
    load_key,
)
from .normalize import summarize_gettrackinfo, summarize_gettracklist, summarize_register

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_AUTH = 10
EXIT_QUOTA = 11
EXIT_NO_DATA = 12
EXIT_SERVER = 13


def _envelope(command, input_, data, error):
    return {"command": command, "input": input_, "data": data, "error": error}


def _rejected_codes(rejected):
    codes = set()
    for r in rejected or []:
        err = r.get("error") or {}
        if isinstance(err, dict) and err.get("code") is not None:
            codes.add(err["code"])
    return codes


def classify_rejected(command, rejected) -> int:
    """Map rejected items to an exit code.

    register + everything already registered (-18019901) is a successful
    no-op, not an error.
    """
    codes = _rejected_codes(rejected)
    if not codes:
        return EXIT_NO_DATA
    if command == "register" and codes <= {CODE_ALREADY_REGISTERED}:
        return EXIT_OK
    if codes & CODES_AUTH:
        return EXIT_AUTH
    if codes & CODES_QUOTA:
        return EXIT_QUOTA
    return EXIT_NO_DATA


def classify_exception(exc) -> tuple:
    """Map an exception to (exit_code, error_dict) with raw detail."""
    if isinstance(exc, KeyMissingError):
        return EXIT_USAGE, {"type": "missing_key", "message": str(exc)}
    if isinstance(exc, NetworkError):
        return EXIT_SERVER, {"type": "network", "message": str(exc)}
    if isinstance(exc, ApiError):
        err = {
            "http_status": exc.http_status,
            "api_code": exc.api_code,
            "message": exc.message,
            "raw_body": exc.raw_body[:2000],
        }
        if exc.http_status in (401, 403) or exc.api_code in CODES_AUTH:
            return EXIT_AUTH, {**err, "type": "auth"}
        if exc.http_status == 429 or exc.api_code in CODES_QUOTA:
            return EXIT_QUOTA, {**err, "type": "quota"}
        return EXIT_SERVER, {**err, "type": "server"}
    return EXIT_SERVER, {"type": "internal", "message": f"unexpected error: {exc!r}"}


def run_api(command, input_, endpoint, payload, key, timeout=60.0, transform=None) -> tuple:
    """One API round-trip. Returns (exit_code, envelope)."""
    try:
        status, body = api_call(endpoint, payload, key, timeout=timeout)
    except (KeyMissingError, NetworkError, ApiError) as exc:
        code, err = classify_exception(exc)
        return code, _envelope(command, input_, None, err)

    if isinstance(body, dict):
        top_code = body.get("code")
        if top_code is not None and top_code != 0:
            if top_code in CODES_AUTH:
                code, etype = EXIT_AUTH, "auth"
            elif top_code in CODES_QUOTA:
                code, etype = EXIT_QUOTA, "quota"
            elif top_code in CODES_SERVER:
                code, etype = EXIT_SERVER, "server"
            else:
                code, etype = EXIT_NO_DATA, "no_data"
            err = {
                "type": etype,
                "http_status": status,
                "api_code": top_code,
                "message": body.get("message") or "",
                "raw_body": json.dumps(body)[:2000],
            }
            return code, _envelope(command, input_, None, err)

    data = transform(body) if transform else body
    if isinstance(data, dict):
        data["raw"] = body
    rejected = (body.get("data") or {}).get("rejected") if isinstance(body, dict) else None
    if rejected:
        code = classify_rejected(command, rejected)
        if code == EXIT_OK:
            data["note"] = "already registered; nothing consumed"
        elif command == "get" and CODE_NOT_REGISTERED in _rejected_codes(rejected):
            data["hint"] = (
                "number not registered yet; run register first or retry with --auto-register"
            )
        return code, _envelope(command, input_, data, None)
    return EXIT_OK, _envelope(command, input_, data, None)


def cmd_check(args, key):
    return run_api("check", {}, "gettracklist", {}, key, transform=summarize_gettracklist)


def cmd_register(args, key):
    input_ = {"number": args.number}
    payload = {"number": args.number}
    for flag, field in (
        ("carrier", "carrier"),
        ("origin_country", "origin_country"),
        ("lang", "lang"),
        ("ship_date", "ship_date"),
        ("destination_postal_code", "destination_postal_code"),
    ):
        value = getattr(args, flag, None)
        if value is not None:
            input_[field] = value
            payload[field] = value
    return run_api("register", input_, "register", [payload], key, transform=summarize_register)


def cmd_get(args, key):
    input_ = {"number": args.number, "auto_register": args.auto_register}
    payload = {"number": args.number}
    if args.carrier is not None:
        input_["carrier"] = args.carrier
        payload["carrier"] = args.carrier
    if args.lang:
        input_["lang"] = args.lang
        payload["lang"] = args.lang
    code, env = run_api("get", input_, "gettrackinfo", [payload], key, transform=summarize_gettrackinfo)
    if code == EXIT_NO_DATA and args.auto_register:
        data = env.get("data") or {}
        if CODE_NOT_REGISTERED in _rejected_codes(data.get("rejected")):
            reg_code, _reg_env = run_api(
                "register", input_, "register", [payload], key, transform=summarize_register
            )
            if reg_code == EXIT_OK:
                code, env = run_api(
                    "get", input_, "gettrackinfo", [payload], key, transform=summarize_gettrackinfo
                )
                data = env.get("data")
                if isinstance(data, dict) and data.get("summary") is not None:
                    data["auto_registered"] = True
    return code, env


def cmd_list(args, key):
    input_ = {"page": args.page}
    payload = {"page_no": args.page}
    if args.status:
        input_["status"] = args.status
        payload["package_status"] = args.status
    if args.number:
        input_["number"] = args.number
        payload["number"] = args.number
    return run_api("list", input_, "gettracklist", payload, key, transform=summarize_gettracklist)


def cmd_carriers(args):
    if args.carriers_action == "search":
        data = {
            "query": args.query,
            "results": search(args.query, limit=args.limit),
            "total_carriers": count(),
        }
        return EXIT_OK, _envelope("carriers", {"action": "search", "query": args.query}, data, None)
    carrier = by_code(args.code)
    code = EXIT_OK if carrier else EXIT_NO_DATA
    data = {"code": args.code, "carrier": carrier}
    return code, _envelope("carriers", {"action": "get", "code": args.code}, data, None)


class _Parser(argparse.ArgumentParser):
    """argparse that honors the envelope contract on usage errors too."""

    def error(self, message):
        print(
            json.dumps(
                _envelope("usage", None, None, {"type": "usage", "message": message}),
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(EXIT_USAGE)


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(
        prog="track17",
        description="One-stop package tracking via the 17TRACK Tracking API (v2.4).",
    )
    p.add_argument("--version", action="version", version=f"track17 {__version__}")

    env_file_help = (
        "path to a .env file defining SEVENTEENTRACK_KEY "
        "(explicit file beats ./.env; the env var beats both)"
    )
    p.add_argument("--env-file", default=None, help=env_file_help)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--env-file", default=None, help=env_file_help)

    sub = p.add_subparsers(dest="command", required=True, parser_class=_Parser)

    sub.add_parser(
        "check",
        help="validate the API key and list registered numbers (free)",
        parents=[common],
    )

    reg = sub.add_parser(
        "register", help="register a tracking number (consumes 1 quota the first time only)",
        parents=[common],
    )
    reg.add_argument("number", help="tracking number, 5-50 letters/digits/hyphens")
    reg.add_argument("--carrier", type=int, default=None, help="carrier code, e.g. 100003 (FedEx)")
    reg.add_argument("--origin-country", dest="origin_country", default=None, help="Alpha-2 code, e.g. US")
    reg.add_argument("--lang", default=None, help="translation language code, e.g. en / zh-cn")
    reg.add_argument("--ship-date", dest="ship_date", default=None, help="ship date, YYYY-MM-DD")
    reg.add_argument(
        "--destination-postal-code", dest="destination_postal_code", default=None, help="destination postal code"
    )

    get = sub.add_parser(
        "get", help="get tracking details for a registered number (free)", parents=[common]
    )
    get.add_argument("number")
    get.add_argument("--carrier", type=int, default=None, help="carrier code if auto-detection fails")
    get.add_argument("--lang", default=None, help="translation language code")
    get.add_argument(
        "--auto-register",
        action="store_true",
        help="if the number is not registered yet, register it (consumes 1 quota) and fetch again",
    )

    lst = sub.add_parser(
        "list", help="list registered numbers with current status (free)", parents=[common]
    )
    lst.add_argument("--status", default=None, help="filter by package status, e.g. InTransit / Delivered")
    lst.add_argument("--page", type=int, default=1, help="page number (40 items per page max)")
    lst.add_argument("--number", default=None, help="filter by tracking number(s), comma separated, 200 max")

    car = sub.add_parser(
        "carriers", help="offline carrier-code lookup (no API call, free)", parents=[common]
    )
    car_sub = car.add_subparsers(dest="carriers_action", required=True)
    car_search = car_sub.add_parser("search", help="case-insensitive name search")
    car_search.add_argument("query")
    car_search.add_argument("--limit", type=int, default=10)
    car_get = car_sub.add_parser("get", help="look up a carrier by code")
    car_get.add_argument("code", type=int)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "carriers":
        code, env = cmd_carriers(args)
    else:
        try:
            key = load_key(args.env_file)
        except KeyMissingError as exc:
            code, env = EXIT_USAGE, _envelope(
                args.command, vars(args), None, {"type": "missing_key", "message": str(exc)}
            )
        else:
            handler = {
                "check": cmd_check,
                "register": cmd_register,
                "get": cmd_get,
                "list": cmd_list,
            }[args.command]
            code, env = handler(args, key)
    print(json.dumps(env, ensure_ascii=False, indent=2))
    return code
