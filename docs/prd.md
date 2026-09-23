# PRD — track17

## Problem

A program that needs to know "where is my package" cannot scrape carrier
websites: major carriers (e.g. FedEx, behind Akamai WAF) block plain HTTP
(403) and browser automation alike. Measured in September 2026: headless /
headed / stealth Playwright variants all failed on the tracking XHR
(`net::ERR_FAILED`), a 35+ minute cooldown retest also failed, while a real
interactive browser on the same machine and IP succeeded. The block keys on
per-instance browser-automation signals, not IP reputation, and no maintained
open-source scraper exists. Scraping is not a sustainable foundation.

## Solution

A thin CLI over the 17TRACK Tracking API v2.4: one integration covers 3,500+
carriers; 17TRACK keeps polling carriers upstream after a number is
registered; new API accounts (created after 2026-01-07) get a one-time
allocation of 200 tracking numbers, so a small project (a few dozen numbers)
can run entirely on the free tier.

## Users

- Scripts and cron jobs that need a status string for a tracking number.
- AI coding agents driving a subprocess: they need deterministic machine
  output (JSON envelope, stable exit codes) and a knowledge layer (quota
  semantics, error playbook), which `skills/track17.md` provides.

## Scope

In: `check`, `register`, `get`, `list`, `carriers` (offline code DB);
normalized summary + raw passthrough; envelope + exit-code contract;
MIT-licensed public repo.

Out (deliberate): MCP server, webhooks / push, email or chat notification
dispatch, batch/queue workers, multi-account support.

## Success criteria

1. `python -m pytest tests/` passes offline with no key configured.
2. `RUN_TRACK17_INTEGRATION=1` live tests pass against the real API.
3. A cold agent given only `README.md` + `skills/track17.md` can: validate a
   key, register a number (and recognize the idempotent no-op), fetch status,
   and report "no data yet" without looping.
4. No real keys, numbers, or personal data in the repo (privacy scan clean).
