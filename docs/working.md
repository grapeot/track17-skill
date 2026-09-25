# Working notes

## 2026-09-25 — monitoring skill + reference implementation

- Added `skills/monitoring.md`: agent-facing recipe for recurring package
  monitors ("check daily and email me"). Key stance: the skill instructs the
  agent how to behave (inventory the user's existing scheduler / agent
  runtime / email tooling, verify each layer, report in outcomes) instead of
  hard-coding one stack or a JSON task schema.
- Added `examples/monitor/` reference implementation: a placeholder prompt
  template (`monitor_prompt.md`), `state.example.json`, and a README naming
  one verified stack (track17 + OpenCode headless + process-launcher
  periodic jobs + an email CLI) while stating all four are substitutable.
- Trigger context that produced this: setting up a real monitor for a
  FedEx parcel surfaced the gaps below; the monitoring skill encodes them so
  the next agent does not re-derive them.
- Real findings folded into the skill's Known Traps:
  - `get --auto-register` did not register an unregistered number in a live
    run (API returned `-18019902`); explicit `register` worked. Docs for
    `get` now caveat this in the skill (README table not reworded yet).
  - Re-confirmed the "no scraping" wall: carrier web pages are JS shells to
    plain HTTP, unofficial API endpoints 404 without keys, aggregators block.
  - Scheduler verification before user sign-off added as an explicit
    acceptance criterion — unverified schedules were the main silent
    failure mode observed.

## 2026-09-23 — v0.1.0

- First public release of the CLI, docs, and skill file.
- L1: 28 unit tests passing. L2: 5 live tests passing against a real key.
- Carrier snapshot: 3,523 entries from the official list URL.
- Known facts confirmed during build:
  - v2.4 nests `latest_status` under `track_info` and events under
    `track_info.tracking.providers[0].events`.
  - Re-registering a registered number returns -18019901 and consumes no
    quota (treated as exit 0).
  - `gettracklist` is quota-free; use it as the key preflight.
  - Free tier: accounts created after 2026-01-07, one-time 200 numbers.
- Open questions (deliberately deferred):
  - `changeinfo` / `getRealTimeTrackInfo` endpoints: not exposed; revisit if
    users need mid-flight parameter fixes.
  - Push model: 17TRACK webhooks exist but are out of scope by design (D1).
