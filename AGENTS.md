# AGENTS.md — agent operating rules for this repository

## Exact commands

```bash
# setup (Python 3.9+; 3.12 recommended)
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# run the CLI
python -m track17_skill <subcommand>
python -m track17_skill --help

# offline unit tests (no network, no API key needed)
python -m pytest tests/ -v

# live integration tests (opt-in; consumes no quota for registered numbers)
SEVENTEENTRACK_KEY=<your key> TRACK17_TEST_NUMBER=<registered number> \
  RUN_TRACK17_INTEGRATION=1 python -m pytest tests/test_integration.py -v
```

## Invariants

- Standard library only in `src/` — no third-party runtime dependencies. Tests may use pytest.
- Every command prints exactly one JSON envelope to stdout: `{command, input, data, error}`.
  On success `data.raw` always contains the unmodified upstream response.
- Exit codes are a contract: 0 ok / 2 usage / 10 auth / 11 quota-rate / 12 rejected-no-data / 13 network-server. Do not add new exit codes without updating the README, `skills/track17.md`, and the unit tests together.
- No implicit retries. Transient failures are the caller's decision.
- `carriers.json` is a snapshot of the official 17TRACK carrier list; regenerate with `python scripts/refresh_carriers.py`, do not edit by hand.
- Never commit a real API key, a real tracking number, or personal data. Examples use the fake number `123456789012`.
- This repository's default branch is `master`.

## Layout

- `src/track17_skill/` — package (`client.py` transport, `normalize.py` v2.4 flattening, `carriers.py` offline lookup, `cli.py` subcommands)
- `tests/` — `test_unit.py` (offline), `test_integration.py` (live, opt-in)
- `fixtures/` — anonymized real v2.4 responses
- `skills/track17.md` — public agent skill document
- `docs/` — prd / rfc / test / working notes
