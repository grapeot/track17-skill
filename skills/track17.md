# track17 Skill

## Goal

Give agents a reliable, quota-aware data channel for parcel tracking across 3,500+ carriers via the 17TRACK v2.4 API, with deterministic machine-readable output.

## When to Use

Trigger words: `tracking number`, `parcel status`, `package where`, `carrier code`, `17track`.

Use whenever an automated workflow or user inquiry requires verifying package delivery status, identifying courier information, or registering shipments for tracking.

## Prerequisites

- `SEVENTEENTRACK_KEY` set in the environment or defined in a local `.env` file.
- Package installed (`pip install .` in repo root).
- Command invocation: `python -m track17_skill <subcommand>`.

## CLI Reference

### Commands

| Subcommand | Arguments & Options | Behavior & Quota Impact |
|---|---|---|
| `check` | None | Validates API credentials and lists registered tracking numbers. Free (consumes no quota). |
| `register` | `NUMBER [--carrier CODE] [--origin-country CC] [--lang LANG] [--ship-date YYYY-MM-DD] [--destination-postal-code XX]` | Registers package for continuous tracking. Auto-detects carrier if `--carrier` omitted. Consumes 1 quota unit on initial registration; re-registering is a free no-op. |
| `get` | `NUMBER [--carrier CODE] [--lang LANG] [--auto-register]` | Retrieves current tracking details. Free for registered numbers. With `--auto-register`, automatically registers first if unregistered (`-18019902`). |
| `list` | `[--status STATUS] [--page N] [--number NUMBER]` | Queries registered tracking numbers via `/gettracklist`. Free. |
| `carriers search` | `QUERY` | Searches the bundled 3,523 carrier database offline. No key or network required. |
| `carriers get` | `CODE` | Retrieves carrier metadata by numeric code from the offline database. Free and offline. |

### Output Envelope

All subcommands emit a JSON object with fixed top-level keys to standard output:

```json
{
  "command": "get",
  "input": {"number": "123456789012"},
  "data": {
    "summary": { ... },
    "raw": { ... }
  },
  "error": null
}
```

- **Success**: `data.summary` provides the normalized payload (carrier, main status, sub-status, timestamps, and up to 15 recent events); `data.raw` preserves the untouched upstream 17TRACK response; `error` is `null`.
- **Success**: `data` holds the normalized view plus `raw` (the unmodified 17TRACK payload). Shape varies by command: `get` → `summary`, `check`/`list` → `count` + `items`, `register` → `accepted`/`rejected`.
- **Failure**: `data` is `null`; `error` contains `type` and `message`, plus `http_status`, `api_code`, and `raw_body` (truncated to 2000 chars) for API failures.

### Exit Codes

| Exit Code | Classification | Meaning & Agent Handling |
|---|---|---|
| `0` | Success | Command completed successfully, including idempotent no-ops. |
| `2` | Client Error | CLI argument error or missing `SEVENTEENTRACK_KEY`. |
| `10` | Auth Failure | Invalid API key, IP whitelist restriction, or disabled account. Prompt user. |
| `11` | Quota / Rate | HTTP 429 or quota exhaustion. Halt polling; notify user. |
| `12` | Request Rejected | Actionable rejection (unregistered number, invalid carrier, no data yet). |
| `13` | Server / Network | Network connectivity failure (including read timeouts) or 17TRACK internal service error (`-18010003`). Retry later. |

## Knowledge

### Quota Semantics

- **One-time allocation**: New accounts created after 2026-01-07 receive a one-time grant of 200 tracking numbers.
- **Registration cost**: Calling `register` on a new tracking number consumes 1 quota unit. Re-registering an already-registered number returns API code `-18019901` and consumes zero quota (handled as exit code `0`).
- **Free operations**: `get`, `list`, and `check` consume zero quota for registered tracking numbers.
- **Preflight check**: Use `check` to verify credentials and inspect account registration status before initiating registrations.
- **API limits**: 3 requests per second; maximum 40 tracking numbers per batch request; pagination limit of 40 items on list calls.
- **Scan presence**: A tracking number with zero scan records is a normal operational state, not an error.

### Error Playbook

When commands exit with non-zero codes, consult `error.api_code` and follow these recovery actions:

| API Code | Exit Code | Upstream Condition | Agent Action |
|---|---|---|---|
| `-18010001` | `10` | IP address not whitelisted | Ask user to add IP address to whitelist or disable IP restrictions in 17TRACK console. |
| `-18010002` | `10` | Invalid security key | Prompt user to check that `SEVENTEENTRACK_KEY` is correctly set and active. |
| `-18010003` | `13` | Internal service error | Transient 17TRACK backend failure. Back off and retry request later. |
| `-18010004` | `10` | Account disabled | Ask user to verify account email and active status at api.17track.net. |
| `-18010005` | `10` | Unauthorized access | Ask user to check API key permissions in the dashboard. |
| `-18019901` | `0` | Already registered | Idempotent no-op. Treat as success; proceed immediately to `get`. |
| `-18019902` | `12` | Not registered yet | Number is not tracked. Run `register <number>` or re-run `get <number> --auto-register`. |
| `-18019903` | `12` | Carrier detection failed | Run `carriers search <carrier-name>` offline to find code, then pass `--carrier CODE`. If carrier unknown, ask user. |
| `-18019907` | `11` | Daily tracking limit hit | Account exceeded daily tracking frequency. Halt automated queries; alert user. |
| `-18019908` | `11` | Quota exhausted | Tracking number allowance depleted. Stop calls immediately and inform user to add quota. |
| `-18019909` | `12` | No tracking info yet | Carrier has not provided tracking events. Report status as pending; do not loop or poll aggressively. |
| `-18019910` | `12` | Incorrect carrier code | Provided carrier code is invalid. Search offline database via `carriers search` to obtain valid code. |

### Carrier Codes

- **Offline database**: Bundles 3,523 carriers. Always run `python -m track17_skill carriers search <query>` before asking the user for carrier codes.
- **Upstream source**: Full list available at `https://res.17track.net/asset/carrier/info/apicarrier.all.json`.
- **Disambiguation**: Queries matching multiple carriers (e.g., regional affiliates or separate express vs freight divisions) should be resolved by matching against the shipment context or asking the user to confirm the carrier brand.

### API v2.4 Response Gotchas

The normalized `data.summary` structure shields agents from several upstream quirks in 17TRACK v2.4:

- **Nested status**: The primary shipment state lives under `accepted[].track_info.latest_status` (`status`, `sub_status`, `sub_status_descr`), not at the payload root.
- **Events in a separate branch**: Scan events live under `track_info.tracking.providers[0].events`, not next to `latest_status`.
- **Non-uniform timestamps**: `time_raw` may appear as a structured object (`{"date": "...", "time": "...", "timezone": "..."}`) or as a plain string.
- **Nested provider metadata**: Courier details reside inside `track_info.tracking.providers[0].provider` dictionaries containing `key`, `name`, `alias`, `tel`, `homepage`, and `country`.
- **Vocabulary hierarchy**: 9 main statuses (`NotFound`, `InfoReceived`, `InTransit`, `Expired`, `AvailableForPickup`, `OutForDelivery`, `DeliveryFailure`, `Delivered`, `Exception`) refined by 30 sub-statuses (e.g., `InTransit_PickedUp`, `InTransit_CustomsProcessing`, `Exception_Returning`, `NotFound_InvalidCode`). Always inspect `sub_status` when detailed milestone tracking is required.

### No Data Is Not an Error

Shipping labels created recently often show `status: "InfoReceived"` with empty event lists for several days. This indicates the carrier has received electronic manifest data but has not scanned the physical package into a transit facility. Report this as an informative operational status rather than a retrieval failure or system error.

## Boundaries

- **Subprocess CLI**: Invoked via standard subprocess execution returning JSON to stdout. Not an MCP server.
- **Pull model only**: Implements client-initiated polling. No webhook endpoints or SMS push handlers. Users needing push callbacks should be directed to 17TRACK's native webhook configuration.
- **No external notifications**: Does not send emails, chat messages, or operating system alerts.
- **No persistent daemon**: Operates statelessly per command; does not manage background scheduling or queues.
- **Independent third-party integration**: track17 is not affiliated with, endorsed by, or sponsored by 17TRACK; the 17TRACK Tracking API is used as a third-party service under 17TRACK's own terms.

## Note on Private Overlays

When consumed within a private workspace or agent harness, the host workspace maintains its own routing rules pointing to this skill (e.g., credential retrieval from secure stores, local alias conventions). This file serves exclusively as the public, technical interface definition and must remain free of secrets, credentials, or private file paths.
