# CLAUDE.md

## What this is
DME voice agent — a Medicare patient calls in for durable medical equipment;
the agent captures the request, researches in-network vendors async, and calls
back. **Thesis: the agent owns *coordination*, not clinical or coverage
judgment.** Reads are automated; liability-bearing writes are gated behind a
nurse approval step and reversible. The agent says "here's what's needed,"
never "you're covered." This is a take-home / learning artifact — clarity and a
single coherent story matter more than feature count.

## How I want code written here
- **The best code is the code I don't write.** Before adding anything, check:
  does it need to exist? Can stdlib / an already-installed dep do it? Can it be
  one line? Only then write it.
- **No premature abstraction, no speculative config, no defensive scaffolding**
  for cases that can't happen here. Match the surrounding code's density.
- **Keep deliverables aligned to one story.** Code, README, DESIGN, WRITEUP, and
  evals should tell the same story; if a change makes one drift, fix the others
  or flag it. Don't add a doc/section that isn't pulling its weight.
- Don't touch the trust boundary lightly: anything that gates, escalates, or
  could fabricate a coverage decision is safety-critical — call it out, don't
  silently change it.

## Conventions
- Python ≥3.11. Style enforced by **ruff** (line-length 100; select
  `E,F,W,I,B,UP,C4,SIM`) — run `ruff check . && ruff format --check .`.
- Runnable app, not a packaged library: modules run via `python -m ...`
  (`sim.run_demo`, `evals.run_evals`, `evals.conversation_evals`).
- Tests in `tests/` (unit + functional via FastAPI `TestClient`); `python -m pytest`.
- **Model split is intentional:** `claude-haiku-4-5` for the live conversation
  (latency is UX), `claude-opus-4-8` for async vendor research (quality matters,
  latency doesn't). Keep it that way unless asked.
- Deterministic fallbacks exist on purpose (vendor match, coverage rules) so the
  demo runs with no API key — don't remove them.

## Map
- `app/` — FastAPI backend, webhook, store, coverage rules, callback, nurse console
- `sim/` — keyless demo driver  · `evals/` — policy + conversation evals
- `cekura/` — voice-eval layer (persona calls, production monitoring; MCP in `.mcp.json`)
- `vapi/` — assistant config + system prompt
- `DESIGN.md` decisions · `WRITEUP.md` 1-page deliverable · `README.md` entry point
