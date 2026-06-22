# CLAUDE.md

## What this is
DME back-end coordination. Intake is already done; starting from a documented case
(Eleanor, K0001, Original Medicare Part B), the system works the coordination across
four surfaces: supplier outreach, PCP order, coverage, and the patient update.
**Thesis: the system owns coordination, not clinical or coverage judgment.** Calling
to discover runs on its own; anything that commits on the patient's behalf is gated
behind a care-advocate approval and is reversible. It says "here's what's needed and
what you'll owe," never "you're covered." This is a take-home and learning artifact, so
clarity and a single coherent story matter more than feature count.

## How I want code written here
- The best code is the code I don't write. Before adding anything, check: does it need
  to exist? Can stdlib or an already-installed dep do it? Can it be one line?
- No premature abstraction, no speculative config, no defensive scaffolding for cases
  that can't happen here. Match the surrounding code's density.
- Keep deliverables aligned to one story. Code, README, DESIGN, WRITEUP, and evals
  should tell the same story; if a change makes one drift, fix the others or flag it.
- Don't touch the trust boundary lightly: anything that gates, escalates, or could
  fabricate a coverage decision is safety-critical. Call it out, don't silently change it.
- Plain prose in docs and comments. No em-dashes.

## Conventions
- Python >= 3.11. Style enforced by ruff (line-length 100; select `E,F,W,I,B,UP,C4,SIM`).
  Run `make gate` (ruff, format check, pytest, evals, demo).
- Runnable app, not a packaged library: modules run via `python -m ...`
  (`sim.run_demo`, `evals.run_evals`, `evals.conversation_evals`, `cekura.provision`).
- Tests in `tests/` (unit + functional via FastAPI `TestClient`); `python -m pytest`.
- Model split is intentional: a fast model for the live calls (latency is UX), a strong
  model (`claude-opus-4-8`) for async supplier synthesis (quality matters, latency
  doesn't). Keep it that way unless asked.
- Deterministic fallbacks exist on purpose (supplier outreach, coverage rules) so the
  demo runs with no API key. Don't remove them.

## Map
- `app/` FastAPI backend: `cases` (the documented case), `orchestrator` (four surfaces +
  the care-advocate gate), `supplier_outreach` (discovery-based, AI + fallback),
  `coverage` (deterministic rules), `callback` (outbound calls), `main` (HTTP + console)
- `data/` sparse supplier directory CSV + mocked call outcomes
- `sim/` keyless demo driver  ·  `evals/` policy + conversation evals
- `cekura/` voice-eval layer (supplier-persona calls, production monitoring; MCP in `.mcp.json`)
- `vapi/` outbound assistant config + system prompts (supplier outreach, patient update)
- `DESIGN.md` decisions  ·  `WRITEUP.md` deliverable  ·  `README.md` entry point
