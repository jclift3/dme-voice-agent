# Cekura — voice-agent simulation testing + monitoring

> **Verified live** (run 648061, project 7236): three persona callers placed real
> calls to the deployed agent. `never_claims_coverage` passed under an adversarial
> coverage-pressure caller; the suite caught a real `one_question_at_a_time` regression
> (now fixed). Scorecard: [docs/cekura_results.md](../docs/cekura_results.md).

Our two eval layers, and why both exist:

| Layer | What it tests | Speed / cost | When |
|---|---|---|---|
| `evals/` (local) | Backend **policy** + a few live conversation turns (Anthropic API) | fast, ~free, no telephony | every commit / CI |
| `cekura/` (this) | The **deployed Vapi agent** end-to-end: telephony, ASR/TTS, latency, interruptions, persona behavior | slower, places real calls | pre-deploy gate + prod monitoring |

The local evals can't catch what actually breaks voice agents: a caller who
interrupts, bad audio, a model that drifts on coverage *out loud* under pressure,
or latency that makes the call feel broken. Cekura drives **LLM persona callers**
into the live number and grades the transcripts.

## The substance: our trust boundary → Cekura metrics

The mapping is the point — the product's risk model becomes the test suite
([provision.py](provision.py) has the rubrics):

- **never_claims_coverage** (critical) — the core thesis, checked on real audio.
- **no_medical_advice** (critical) — defers necessity to the PCP.
- **captures_required_fields** — equipment, plan, ZIP, callback number.
- **one_question_at_a_time** — added *because the real test call surfaced this exact
  bug* (the agent front-loaded questions; the caller pushed back). Now it's a metric.
- **sets_next_step_expectations** — closes the call honestly.

Scenarios pair these with personas: the grounding wheelchair case, a
coverage-pressure caller, and a confused/hard-of-hearing caller.

## Run it

```bash
python -m cekura.provision          # dry-run: prints every API payload, sends nothing
# with a key:
CEKURA_API_KEY=... CEKURA_PROJECT_ID=... VAPI_ASSISTANT_ID=... \
  python -m cekura.provision --run  # creates agent + metrics + scenarios, triggers calls
```

API verified against Cekura's OpenAPI spec (`https://docs.cekura.ai/openapi.json`):
base `https://api.cekura.ai`, header `X-CEKURA-API-KEY`. Account-specific fields
(`project_id`, persona ids, and the metric `type`/`eval_type` enum) come from env or
your Cekura workspace; the script defaults are marked and may need a one-line tweak
to match your account's current enum.

## Production monitoring (the other half)

Beyond pre-deploy simulation, Cekura ingests live calls for observability via
`POST /observability/v1/vapi/observe/` — so the same `never_claims_coverage` metric
that gates a deploy also alerts on real traffic. That's the "keep it working with
many moving parts" story: same rubric, simulation *and* production.

## Cekura MCP server (trigger runs from Claude Code)

Cekura exposes an HTTP MCP server so Claude Code can register agents, trigger runs,
and review pass/fail without leaving the editor — a natural fit for a CI gate or an
autonomous "re-run the voice suite after a prompt change" loop.

Wired up in [`.mcp.json`](../.mcp.json) (verified: the endpoint returns
`serverInfo: Cekura API`). The key is referenced as `${CEKURA_API_KEY}` — never
committed. To activate:

```bash
export CEKURA_API_KEY=...     # or: export $(grep -v '^#' .env | xargs)
# then relaunch Claude Code in this repo and approve the project MCP server
```

Endpoint: `https://api.cekura.ai/mcp`, header `X-CEKURA-API-KEY`.
