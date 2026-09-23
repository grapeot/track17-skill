# Testing

## Layers

### L1 — offline unit tests (`tests/test_unit.py`)

No network, no API key. Covers:

- envelope shape and exit-code classification for every error family
  (auth 401/403, quota 429, network, missing key, top-level api error codes,
  per-number rejections)
- idempotent register no-op → exit 0
- normalization against a real (anonymized) v2.4 response fixture:
  status, sub_status, carrier, service_type, route, latest_event,
  days_since_last_update, event cap (15) and newest-first ordering
- key loading precedence: `SEVENTEENTRACK_KEY` env var > `.env` in cwd >
  explicit `--env-file` > error
- `run_api` with the transport monkeypatched (success envelope carries
  `data.raw`; failures carry `error.raw_body`)
- offline carrier lookup (search / by_code / count / no-match)
- CLI end-to-end for the key-free subcommands and `--version`

Run: `python -m pytest tests/ -v`

### L2 — live integration tests (`tests/test_integration.py`)

Opt-in via `RUN_TRACK17_INTEGRATION=1` plus a real key and a number already
registered under that key. Skipped (not failed) otherwise. Covers the live
contract: `check` validates, `get` on a registered number returns a summary,
register is idempotent, `get` on an unregistered number exits 12 with
`error=null`, a garbage key exits 10 with the raw body preserved.

Registered-number queries cost no quota, so these are cheap to run.

## Fixture policy

`fixtures/` contains real 17TRACK responses with all identifying fields
replaced (fake tracking number, generic cities). New fixtures must be
anonymized before committing: no real numbers, names, addresses, phone
digits, or keys.
