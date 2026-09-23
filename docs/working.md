# Working notes

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
