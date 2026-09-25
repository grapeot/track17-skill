# Monitor Reference Implementation

A worked example of the package-monitoring recipe described in
[`skills/monitoring.md`](../../skills/monitoring.md). Everything here uses
placeholders — fill in your own numbers, recipients, and paths. Never commit
real tracking numbers, addresses, or API keys.

## Layout

```
examples/monitor/
├── README.md              <- this file
├── monitor_prompt.md      <- the daily task prompt given to the agent
└── state.example.json     <- what the per-run state file looks like
```

The reference stack used here (and known to work together):

- **Tracking data**: this repository's CLI (`track17_skill`).
- **Agent runtime**: OpenCode in headless mode (`opencode run`), via the
  [`opencode_skill`](https://github.com/grapeot/opencode_skill) submission
  helper. Any agent harness with a non-interactive mode works; swap in
  whichever your user already runs.
- **Scheduler**: [process-launcher](https://github.com/grapeot/process-launcher)
  periodic jobs (declarative YAML, daily schedule). A plain cron line works
  too — see the prompt's scheduling note.
- **Notification**: any email CLI. The example was exercised with the
  author's `resend_email_skill`; any transactional email or SMTP tool with a
  non-interactive send mode is equivalent.

None of these four are hard dependencies of the *idea*; they are one verified
combination. Substitute freely, then re-verify (the skill's acceptance
criteria tell you how).

## The Prompt File

See `monitor_prompt.md`. It is written as instructions to a competent
assistant, not as a config format. Fill in the `PLACEHOLDER` fields before
first use.

## Quick Start

```bash
# 1. Facts + registration (consumes 1 quota unit on first registration)
python -m track17_skill register TRACKING_NUMBER --carrier 100003 \
  --origin-country NL --destination-postal-code 98027 --ship-date 2026-09-17

# 2. Sanity: does data flow?
python -m track17_skill get TRACKING_NUMBER --carrier 100003

# 3. Dry-run the agent invocation exactly as the scheduler will run it
#    (shape shown for OpenCode via the opencode_skill helper)
python -m opencode_skill submit --prompt-file monitor_prompt.md --title "Parcel monitor dry-run" --dry-run --json

# 4. Schedule it (process-launcher periodic job, or a cron line running
#    the same command daily) — then verify one real firing before
#    telling the user it works.
```

## State File

Each run appends/updates `state.json` next to the prompt. Shape (example,
placeholders only):

```json
{
  "tracking_number": "TRACKING_NUMBER",
  "last_checked_utc": "2026-09-25T16:00:00Z",
  "last_status": {"status": "Exception", "sub_status": "Exception_Delayed"},
  "last_event_summary": "Clearance delay - Import, OAKLAND CA, 2026-09-19 13:15 -07:00",
  "runs": [
    {"date": "2026-09-25", "status": "Exception/Exception_Delayed", "changed": false, "emailed": true}
  ],
  "terminal": false,
  "stop_reason": null
}
```

The agent reads this file, compares, updates it, and writes its judgment in
the email — the file is the memory between runs, not a config format.