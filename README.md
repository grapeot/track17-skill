# track17

One-stop package tracking CLI for 3,500+ carriers, backed by the 17TRACK Tracking API.

## Why One-Stop Tracking

Scraping carrier websites directly is a dead end. In September 2026, systematic experiments against FedEx tracking demonstrated the barrier:

- Plain HTTP requests to tracking endpoints return HTTP 403 (Akamai WAF).
- Headless, headed, and stealth browser automation using Playwright variants fail on the tracking XHR request with `net::ERR_FAILED`. A cooldown retest after 35+ minutes fails identically.
- A real, interactive browser running on the same machine and IP address works without issue.

The block keys on per-instance browser-automation signals rather than IP reputation. Public scraping repositories hit this same wall, leaving no maintained, reliable open-source scrapers for major carriers. A software system needing to determine package status cannot depend on scraping carrier websites.

The 17TRACK Tracking API (v2.4) offers a reliable, unified alternative:

- **Single integration**: Covers 3,500+ parcel carriers, 190+ airlines, and 220+ countries.
- **Continuous polling**: 17TRACK polls carriers upstream once a tracking number is registered.
- **Predictable quota**: New accounts created after 2026-01-07 receive a one-time allocation of 200 free tracking numbers. Registering a number consumes 1 quota unit once; continuously tracking and re-querying registered numbers incurs no additional quota.

## What It Is

`track17` is a lightweight Python CLI providing machine-readable parcel tracking:

- **Zero runtime dependencies**: Standard library only (Python 3.9+).
- **Five subcommands**: `check`, `register`, `get`, `list`, and `carriers`.
- **Machine-first output**: Standardized JSON envelope with deterministic exit codes for shell scripts and AI agents.
- **Offline carrier database**: Bundles 3,523 carrier codes for instant lookups without network calls or API keys.
- **Stateless pull model**: Clean queries with no webhooks, SMS push, or background daemons.
- **Preserved raw payloads**: Normalizes status into a unified schema while preserving raw upstream responses without implicit retries.

## Installation

Requires Python 3.9+.

```bash
git clone https://github.com/grapeot/track17-skill
cd track17

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate
# Or with uv:
# uv venv && source .venv/bin/activate

pip install .
```

Verify the installation:

```bash
python -m track17_skill --help
```

## Setup

1. Create an account at [api.17track.net](https://api.17track.net).
2. Go to the dashboard, click **Settings** in the top-right corner, and copy your API key.
3. Configure the key via the `SEVENTEENTRACK_KEY` environment variable or place it in a `.env` file in your working directory:

```bash
export SEVENTEENTRACK_KEY="your_api_key_here"
```

Or in `.env`:

```env
SEVENTEENTRACK_KEY=your_api_key_here
```

**Free tier allocation**: New accounts created after 2026-01-07 receive a one-time grant of 200 tracking numbers. First-time registration consumes 1 quota unit per number. Re-registering an existing number is a free no-op. Re-querying registered numbers through `get` or `list` consumes no quota.

## Quick Start

A basic workflow using the placeholder tracking number `123456789012`:

```bash
# 1. Validate credentials and list current registrations
python -m track17_skill check

# 2. Register the tracking number (consumes 1 quota unit on first registration)
python -m track17_skill register 123456789012

# 3. Retrieve tracking information
python -m track17_skill get 123456789012
```

Example normalized JSON output:

```json
{
  "command": "get",
  "input": {
    "number": "123456789012"
  },
  "data": {
    "summary": {
      "number": "123456789012",
      "carrier": {
        "code": 100003,
        "name": "FedEx"
      },
      "status": "InTransit",
      "sub_status": "InTransit_PickedUp",
      "service_type": "FedEx 2Day",
      "weight_kg": 2.45,
      "route": {
        "origin": "Redmond, WA",
        "destination": "San Jose, CA"
      },
      "latest_event": {
        "time": "2026-09-23 14:15:00",
        "description": "Departed FedEx location",
        "location": "MEMPHIS, TN"
      },
      "days_since_last_update": 0,
      "provider_tips": null,
      "event_count": 4,
      "events": [
        {
          "time": "2026-09-23 14:15:00",
          "description": "Departed FedEx location",
          "location": "MEMPHIS, TN"
        }
      ]
    },
    "raw": {
      "code": 0,
      "data": {
        "accepted": [
          {
            "number": "123456789012",
            "carrier": 100003,
            "track_info": {
              "latest_status": { "status": "InTransit", "sub_status": "InTransit_PickedUp" },
              "tracking": { "providers": [ { "events": [ "..." ] } ] }
            }
          }
        ],
        "rejected": []
      }
    }
  },
  "error": null
}
```

The command terminates with exit code `0`.

## Commands

| Command | Purpose | Quota Cost |
|---|---|---|
| `check` | Validate API key and list registered tracking numbers | Free (does not consume quota) |
| `register NUMBER [--carrier CODE] [--origin-country CC] [--lang LANG] [--ship-date YYYY-MM-DD] [--destination-postal-code XX]` | Register a number. Without `--carrier`, 17TRACK auto-detects the carrier | First-time register: 1 quota unit. Re-registering an already-registered number is a no-op |
| `get NUMBER [--carrier CODE] [--lang LANG] [--auto-register]` | Fetch tracking status. `--auto-register` registers unregistered numbers (`-18019902`) automatically | Free for registered numbers |
| `list [--status STATUS] [--page N] [--number NUMBER]` | List registered numbers and statuses via `/gettracklist` | Free |
| `carriers search QUERY`<br>`carriers get CODE` | Look up carrier codes in bundled offline database (3,523 carriers) | Offline, no API key needed |

## Output Contract

Every command prints a consistent JSON envelope to standard output:

```json
{
  "command": "get",
  "input": {"number": "123456789012"},
  "data": {"summary": { ... }, "raw": { ... }},
  "error": null
}
```

- **Success**: `data` holds the normalized view plus `raw` (the unmodified 17TRACK payload) and `error` is `null`. The normalized shape depends on the command: `get` has `summary`, `check`/`list` have `count` and `items`, `register` has `accepted`/`rejected`.
- **Failure**: `data` is `null`; `error` contains `type`, `message`, and, for API failures, `http_status`, `api_code`, and `raw_body` (truncated to 2000 characters).

### Summary Fields

Normalized records (`get`, `list`) provide:

- `number`: Tracking number string.
- `carrier`: Object with `code` and `name`.
- `status`: Main tracking status (see vocabulary below).
- `sub_status`: Detailed sub-status string.
- `service_type`: Carrier-reported service tier.
- `weight_kg`: Package weight in kilograms.
- `route`: Object with `origin` and `destination` location strings (city, state).
- `latest_event`: Object with `time`, `description`, and `location`.
- `days_since_last_update`: Integer days since the last status event.
- `provider_tips`: Carrier advisory or delay notices.
- `event_count`: Total events tracked.
- `events`: Array of up to 15 recent events, ordered newest first.

### Status Vocabulary

17TRACK reports 9 main statuses:
`NotFound`, `InfoReceived`, `InTransit`, `Expired`, `AvailableForPickup`, `OutForDelivery`, `DeliveryFailure`, `Delivered`, `Exception`.

Each is refined by one of 30 sub-statuses (e.g., `InTransit_PickedUp`, `InTransit_CustomsProcessing`, `Exception_Returning`, `NotFound_InvalidCode`). Initial states like `InfoReceived` with no scans are legitimate tracking states for recently generated shipping labels.

### Exit Codes

| Exit Code | Meaning |
|---|---|
| `0` | Success or idempotent no-op (e.g., re-registering an existing number) |
| `2` | Usage error, invalid CLI arguments, or missing API key |
| `10` | Authentication failure (HTTP 401/403 or auth error codes) |
| `11` | Quota exhausted or rate limit exceeded (HTTP 429 or quota codes) |
| `12` | Request rejected or no data available (actionable per-number condition) |
| `13` | Network failure or 17TRACK server-side error |

### 17TRACK Error Codes

| Error Code | Meaning | Exit Code |
|---|---|---|
| `-18010001` | IP address not whitelisted (server-side whitelist mode) | `10` |
| `-18010002` | Invalid security key | `10` |
| `-18010003` | Internal service error — retry later | `13` |
| `-18010004` | Account disabled (verify email or check settings) | `10` |
| `-18010005` | Unauthorized access | `10` |
| `-18019901` | Already registered (idempotent no-op) | `0` |
| `-18019902` | Not registered yet — register first | `12` |
| `-18019903` | Carrier cannot be detected from number — pass `--carrier CODE` | `12` |
| `-18019907` | Daily tracking limit exceeded | `11` |
| `-18019908` | Quota exhausted — add numbers or upgrade | `11` |
| `-18019909` | No tracking info at the moment | `12` |
| `-18019910` | Carrier code is incorrect | `12` |

## Using It with AI Agents

`track17` is designed for autonomous tools and AI coding assistants. Structured JSON envelopes and deterministic exit codes allow agents to process parcel queries directly without prose scraping.

This repository includes an agent skill document at `skills/track17.md`. To install it into an agent environment:

1. Point your coding agent (Claude Code, Cursor, OpenCode, Codex, etc.) to this repository URL.
2. Direct the agent to install `skills/track17.md` into your workspace's skill directory.

The skill document equips the agent with knowledge of quota mechanics, error code recovery flows, and carrier disambiguation rules.

## Data Notes

Carrier lookups use an offline snapshot of 17TRACK's official carrier database containing 3,523 carriers (upstream source: `https://res.17track.net/asset/carrier/info/apicarrier.all.json`).

To refresh the bundled dataset:

```bash
python scripts/refresh_carriers.py
```

## Disclaimer

track17 is an independent open-source project and is not affiliated with, endorsed by, sponsored by, or officially associated with 17TRACK. It integrates the 17TRACK Tracking API as a third-party service, and 17TRACK is a trademark of its respective owner. Tracking data availability, status updates, quotas, and service terms are governed entirely by 17TRACK.

## License

MIT
