# Daily parcel monitor — PLACEHOLDER EDITION

You are running the scheduled daily check for a parcel. This prompt is the
entire task. Work through it in order; the run either produces one email and
an updated state file, or a failure email explaining which stage broke.

## Facts

- Tracking number: `TRACKING_NUMBER`
- Carrier: FedEx (code `100003`)
- Parcel description (for the email subject): `A SHORT DESCRIPTION`
- Check command (run from the track17_skill project directory):
  `python -m track17_skill get TRACKING_NUMBER --carrier 100003`
- Recipient: `RECIPIENT@example.com` (add `CC_ADDRESS` only if that is the
  standing convention for self-notifications on this machine)
- End condition: stop the whole schedule once the parcel is delivered, or
  returned/refused (after reporting it), or after `END_DATE` — whichever
  comes first.

## Steps

1. Run the check command above. If it exits non-zero, read the envelope's
   `error` field: an auth/quota problem (exit 10/11) needs a louder failure
   email than a transient server error (exit 13, note and stop quietly).
2. Read `state.json` next to this prompt (create it from
   `state.example.json` if missing). Compare: what changed since the last
   run? New events, status change, days since last update?
3. Update `state.json` with today's result and append to `runs`.
4. Compose the email in plain language for the parcel's owner:
   - Subject: `[Parcel Monitor] DESCRIPTION — STATUS (change or no-change)`
   - Body: current status in one line, what changed since yesterday (or
     explicitly "no movement for N days"), the last 3 events with times and
     locations, and — only when something material happened (customs hold,
     delivery failure, return, delivery) — one short paragraph of what it
     means and whether any action seems needed. Keep the judgment brief;
     this is a report, not an essay.
5. Send via the local email tooling. A failed or empty tracking result is
   still an email (say which stage failed). Send failure is the only
   condition under which today's run counts as failed in the log.
6. If the parcel reached a terminal state (delivered / returned), mark
   `terminal: true` in `state.json` and note in the email that the monitor
   will stop; leave cancelling the schedule to the scheduler's end date or
   the user.

## Boundaries

- Do not register anything, do not spend quota, do not retry unboundedly.
- Do not send to any address other than the recipient above.
- If `state.json` is unreadable, say so in the email and recreate it from
  today's data — never silently skip the send because bookkeeping broke.
- Do not interpret statuses beyond what the events support; when unsure,
  quote the event text and say "worth a look" rather than guessing.

Scheduling note (for the human or agent setting this up): this file is meant
to be launched daily by a scheduler — a periodic job in a local background
job manager, or a cron line invoking the same agent command. Verify one real
firing before trusting the schedule (see skills/monitoring.md §4).