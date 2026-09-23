# RFC — design decisions

## D1: subprocess CLI, not a library import or MCP server

Agents in this workspace drive tools via subprocess and parse stdout. A single
JSON envelope per invocation is the whole interface: no import surface to
maintain, no server process, trivially sandboxable. MCP is explicitly out of
scope (see `skills/track17.md` boundaries).

## D2: standard library only

The CLI does three things: POST JSON, parse JSON, print JSON. `urllib` covers
this without pulling in requests/httpx. Consequence: timeouts and retries are
hand-rolled in `client.py`; we do not retry at all (D5).

## D3: envelope = {command, input, data, error}

Fixed top-level keys so an agent never needs per-command parsing. On success
`data.raw` is the unmodified upstream response — normalization is a convenience
layer, never a lossy one. On failure `error.raw_body` preserves the upstream
body, because 17TRACK error bodies are the ground truth for diagnosis.

## D4: two-level error model (exit codes + api codes)

Exit codes classify (auth / quota / rejected / server) so a shell script can
branch cheaply; `error.api_code` (17TRACK's `-1801...` codes) discriminates
within a class so an agent can follow the exact playbook entry. Per-number
rejections inside an otherwise-200 response (e.g. -18019902 not registered)
map to exit 12 with `data.summary = null` plus a `hint` — they are data, not
transport errors. Re-registering an already-registered number
(-18019901) is exit 0: idempotency is a feature.

## D5: no implicit retries

Retrying a failed register can double-consume quota in the failure mode where
the request landed but the response did not. The caller (script or agent)
decides after seeing the envelope.

## D6: offline carrier database

`/register` without `--carrier` auto-detects, but when 17TRACK cannot detect
(-18019903) the agent must resolve a code. Bundling the official list
(3,523 entries, from the URL 17TRACK itself references in that error) makes the
recovery path offline, instant, and key-free. Refresh is a script, not a build
step, because the list changes slowly.

## D7: normalize defensively against v2.4 drift

Observed v2.4 quirks (real responses): `latest_status` nested under
`track_info`; events under `track_info.tracking.providers[0].events`;
`time_raw` as object `{date,time,timezone}` or string; `provider` as a nested
object. `normalize.py` flattens all of these and falls back where the shape
changes, so a 17TRACK schema drift degrades to missing fields in the summary
while `data.raw` stays intact for debugging.

## D8: master branch, public repo, 0-reviewer protection

Solo-maintained: `master` with branch protection configured to require zero
approved reviews but enforce the rule on admins (no bypass), so every change
still lands through a PR.
