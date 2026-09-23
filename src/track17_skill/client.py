"""Minimal 17TRACK v2.4 HTTP client. Standard library only."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

API_BASE = "https://api.17track.net/track/v2.4"
ENV_KEY_NAME = "SEVENTEENTRACK_KEY"
# Official full carrier-code list, referenced by API error -18019903.
CARRIER_CODE_URL = "https://res.17track.net/asset/carrier/info/apicarrier.all.json"

# Error codes from the official v2.4 docs ("Error Codes" section).
CODE_SUCCESS = 0
# IP not whitelisted / invalid key / account disabled / unauthorized access.
CODES_AUTH = {-18010001, -18010002, -18010004, -18010005}
# Daily tracking limit exceeded / quotas exhausted.
CODES_QUOTA = {-18019907, -18019908}
# Internal service error.
CODES_SERVER = {-18010003}
# Tracking number already registered (idempotent no-op on /register).
CODE_ALREADY_REGISTERED = -18019901
# Tracking number not registered yet.
CODE_NOT_REGISTERED = -18019902


class KeyMissingError(Exception):
    """No API key found in the environment or .env file."""


class NetworkError(Exception):
    """Connection-level failure (timeout, DNS, refused) or undecodable response."""


class ApiError(Exception):
    """HTTP-level failure. The raw body is preserved for debugging."""

    def __init__(self, http_status: int, api_code, message: str, raw_body: str):
        self.http_status = http_status
        self.api_code = api_code
        self.message = message
        self.raw_body = raw_body
        super().__init__(f"HTTP {http_status} api_code={api_code}: {message}")


def load_key(env_file=None) -> str:
    """Resolve the API key: SEVENTEENTRACK_KEY env var first, then .env files.

    .env lookup order: explicit --env-file path, then ./.env in the cwd.
    """
    key = os.environ.get(ENV_KEY_NAME, "").strip()
    if key:
        return key
    candidates = []
    if env_file:
        candidates.append(Path(env_file))
    candidates.append(Path.cwd() / ".env")
    for path in candidates:
        try:
            if path.is_file():
                for line in path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith(ENV_KEY_NAME + "="):
                        value = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if value:
                            return value
        except OSError:
            continue
    raise KeyMissingError(
        f"no {ENV_KEY_NAME} found: set the environment variable or put it in .env "
        f"(current dir) or pass --env-file"
    )


def api_call(endpoint: str, payload, key: str, timeout: float = 60):
    """POST to the 17TRACK v2.4 API. Returns (http_status, parsed_json).

    Raises ApiError on non-2xx responses (raw body preserved) and
    NetworkError on connection-level failures.
    """
    body = json.dumps(payload).encode("utf-8") if isinstance(payload, (dict, list)) else payload
    req = urllib.request.Request(
        f"{API_BASE}/{endpoint}",
        data=body,
        headers={"17token": key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw)
            except ValueError:
                raise NetworkError(
                    f"invalid JSON in HTTP {resp.status} response: {raw[:200]}"
                ) from None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = None
        api_code = parsed.get("code") if isinstance(parsed, dict) else None
        message = (
            parsed.get("message")
            if isinstance(parsed, dict) and parsed.get("message")
            else raw[:500]
        )
        raise ApiError(exc.code, api_code, str(message), raw) from None
    except urllib.error.URLError as exc:
        raise NetworkError(str(exc.reason)) from None
