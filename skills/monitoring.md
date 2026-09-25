# Package Monitoring — Agent Skill

## Metadata

- **Type**: Workflow / Recipe skill
- **Prerequisite**: The core tracking skill in this repository (`skills/track17.md`) — read it first.
- **Created**: 2026-09-25

## What This Covers

When a user says things like "keep an eye on this package", "monitor this tracking number", "check it every morning until it arrives", "每天早上查一下这个包裹、有更新就发邮件给我", "notify me when it ships", or any recurring-check request around a parcel, load this file.

One-shot questions ("where is my package right now?") do not need this file — use the core skill's `get` command and answer.

## The Idea, In One Paragraph

A monitoring request has three independent parts: a way to learn the current parcel state (this repo's CLI), a way to be woken up at the right times, and a way to tell the user what changed. Each user machine may already have different tools for parts two and three. Do not hard-code one stack. Treat this skill as instructions for how *you*, the agent, should behave when asked to set up a recurring check: figure out what the user's environment already offers, verify it actually works, and only then promise the user a working schedule. Like briefing a competent assistant: you describe the goal, the sources to check, and how to report back — you do not hand them a config file format to worship.

## How To Approach A Monitor Request

Work through these concerns in order. Each one ends with a verification step — an unverified setup must not be presented to the user as done.

### 1. Establish the facts of the watch

From the conversation, collect: tracking number, carrier (run `carriers search` if unsure), a short plain-language description of the parcel, the check cadence and end condition ("every morning for 5 days", "until it is delivered"), and the notification target (email address, and any CC convention). If anything is missing, ask — these are user-only facts you cannot infer.

If the number is not yet registered, run `register` with carrier and origin/destination/ship-date when known (this consumes 1 quota unit — mention it), then confirm with `get` that data flows. Note: `get --auto-register` is documented but was observed failing on 2026-09-25 (the API still returned `-18019902`); do an explicit `register` instead.

### 2. Inventory the user's runtime, then reuse it

You need three capabilities. Check what already exists on the user's machine before installing anything:

- **Scheduling**: any mechanism that can durably launch a command at a future time or on a daily schedule. Candidates in rough order of preference: an existing periodic-job manager the user already runs (for example, a local background job manager with declared periodic jobs), the OS scheduler (`launchd` on macOS, `cron`, `schtasks`), or an agent-harness scheduler the user already trusts. Prefer what is already configured and running — a new install the user did not ask for is a scope change, not a convenience.
- **Agent runtime**: the thing that turns a prompt file into actual reasoning each morning. If the user has an agentic CLI already set up (OpenCode, Claude Code, Codex, or similar), use it headlessly (`opencode run` or equivalent). Any agent harness with a non-interactive mode works; do not require a specific one.
- **Notification**: how the daily result reaches the user. Most commonly email via whatever sender tooling the user has (transactional email CLI, SMTP). Keep the recipient policy the user already has (for example, self-notification CC conventions).

If a capability is genuinely absent, say so plainly and propose the smallest installation — with the user's approval — of a recommended implementation rather than silently skipping the capability or silently installing.

### 3. Write the task prompt, not a program

The daily instruction to the agent should be a small Markdown prompt file in the agent's project directory — prose to a competent assistant, not a JSON schema for a dumb pipe. A good prompt file answers:

- What to check (number, carrier, the exact `get` command shape), and where the state file from previous runs lives.
- What "done for today" means: compare against the previous run's status; describe what changed, in plain language, including the boring case ("no movement for N days — still waiting on X").
- What to always do: send the report to the recipient even when nothing changed or the query failed (a failed check is itself information), keep a log of runs, and stop the whole schedule once the parcel reaches a terminal state (delivered, or returned/refused after the user has been told).
- What not to do: do not re-register, do not spend quota, do not send to anyone beyond the agreed recipient.

A reference template lives in `examples/monitor/` in this repository. Fill in the placeholders; do not commit real tracking numbers, real addresses, or real keys anywhere.

### 4. Verify the loop end-to-end before trusting it

Before telling the user it is set up:

1. Dry-run the agent invocation exactly as the scheduler will run it (same venv, same cwd, same prompt file) — confirm it exits 0 and produces the expected artifacts. Many harnesses support a cheap self-test mode; use it.
2. Dry-run or actually send the notification once with an obvious test marker.
3. For the scheduler: create a one-off trigger a few minutes out (or the tool's dry-run path) and confirm a real run fires, reads the prompt, and reaches the send step. If the scheduler has no dry-run, say so when reporting.
4. Tell the user how to stop it (which label/job to cancel), and where the run logs live.

### 5. Report in results, not mechanics

When you report back, state the promise in outcome terms: "every weekday at 09:00 Pacific for 5 days you'll get one email with the parcel's status and what changed; after delivery or day 5 it stops; here's the label to cancel early." The user does not need the JSON envelopes or file paths unless they ask.

## Acceptance Criteria

A monitor setup is complete when all of the following hold, and you can show evidence for each:

1. A `get` against the registered number returns a valid envelope (exit 0).
2. The scheduler shows the future runs (or fired run records) with the intended times and timezone.
3. One test email has been received by the target address (or the send tool's dry-run payload was verified).
4. One full agent invocation produced: a status comparison against the previous run, a log entry on disk, and a send action (real or verified dry-run).
5. The user was told the stop condition, the cancel mechanism, and the log location.

## Known Traps

All of these were observed in real setup runs (September 2026). Do not re-derive them the hard way.

| Trap | What Happened | What To Do |
|---|---|---|
| `get --auto-register` on an unregistered number | The API still rejected with `-18019902`; the flag did not rescue it | `register` explicitly first (with carrier/origin/destination/ship-date), then `get` |
| Carrier websites and their public tracking APIs | Every unauthenticated path failed: tracking pages are JS shells to plain HTTP fetches, unofficial endpoints 404 without a key, aggregator sites return shells or blocked pages | Do not burn turns scraping. The core skill's "Why One-Stop Tracking" section documents the wall; 17TRACK is the maintained path |
| Agent output without artifact | Headless agent prints JSON to stdout but leaves the result file empty | Verify the artifact on disk, fall back to stdout extraction per the agent CLI's contract, retry bounded |
| "No scans yet" treated as an error | A freshly registered number can legitimately show `InfoReceived` with zero events for days | Report as pending state, never as tool failure; do not poll aggressively |
| Scheduler created but never verified | A prompt file plus a hope is not a monitor; silent non-firing schedules are the most common silent failure | Always run the one-off verification trigger before telling the user it works |
| Notification failure treated as monitor failure | Track data was fine; the send step failed (credentials, recipient policy) | Log which stage failed; the daily "status" email and the send pipeline are separately verifiable |

## When NOT To Use This Skill

- One-time status checks — use the core skill's `get` directly.
- Programmatic webhooks / push — 17TRACK offers upstream webhooks, but that is a different product shape (a server to receive them), out of scope here by design.
- High-frequency polling — the pull model plus upstream polling makes sub-daily polling pointless and risks daily-limit errors (`-18019907`).