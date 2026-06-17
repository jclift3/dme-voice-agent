# Cekura: voice-agent simulation testing and monitoring

Verified live (runs 648061 and 648929, project 7236). Persona callers placed real calls
to the deployed agent. `never_claims_coverage` held under an adversarial coverage-pressure
caller, and the suite caught two real bugs: runaway call duration (fixed decisively, 9:58
down to 2:11, the agent now ends the call itself) and question-stacking (substantially
improved). Found, fixed, re-verified. Scorecard: [docs/cekura_results.md](../docs/cekura_results.md).

This is the third of three eval layers. The local `evals/` cover the first two, backend
policy and live conversation. Cekura is the deployed-voice layer.

| Layer | What it tests | Speed and cost | When |
|---|---|---|---|
| `evals/` (local) | backend policy plus a few live conversation turns | fast, near-free, no telephony | every commit, CI |
| `cekura/` (this) | the deployed Vapi agent end to end: telephony, speech, latency, interruptions, persona behavior | slower, places real calls | pre-deploy gate, prod monitoring |

Local evals cannot catch what actually breaks voice agents: a caller who interrupts, bad
audio, a model that drifts on coverage out loud under pressure, or latency that makes the
call feel broken. Cekura drives LLM persona callers into the live number and grades the
transcripts.

## The substance: trust boundary becomes the test suite

The mapping is the point. The product's risk model becomes the metrics
([provision.py](provision.py) has the rubrics):

- `never_claims_coverage` (critical): the core thesis, checked on real audio.
- `no_medical_advice` (critical): defers necessity to the PCP.
- `captures_required_fields`: equipment, plan, ZIP, callback number.
- `one_question_at_a_time`: added because the real test call surfaced this exact bug. The
  agent front-loaded questions and the caller pushed back. Now it is a metric.
- `sets_next_step_expectations`: closes the call honestly.

Scenarios pair these with personas: the grounding wheelchair case, a coverage-pressure
caller, and a confused or hard-of-hearing caller.

## Run it

```bash
python -m cekura.provision          # dry run: prints every API payload, sends nothing
# with a key:
CEKURA_API_KEY=... CEKURA_PROJECT_ID=... VAPI_ASSISTANT_ID=... \
  python -m cekura.provision --run  # creates agent, metrics, scenarios; triggers calls
```

The API is verified against Cekura's OpenAPI spec (`https://docs.cekura.ai/openapi.json`):
base `https://api.cekura.ai`, header `X-CEKURA-API-KEY`. Account-specific fields (the
project id, persona ids, and the metric type and eval_type) come from env or your Cekura
workspace. The script defaults are marked and may need a one-line tweak to match your
account.

## Production monitoring (the other half)

Beyond pre-deploy simulation, Cekura ingests live calls for observability via
`POST /observability/v1/vapi/observe/`, so the same `never_claims_coverage` metric that
gates a deploy also alerts on real traffic. That is the "keep it working with many moving
parts" story: one rubric, both simulation and production.

## Cekura MCP server (trigger runs from Claude Code)

Cekura exposes an HTTP MCP server so Claude Code can register agents, trigger runs, and
review pass or fail without leaving the editor. It is a natural fit for a CI gate or an
"re-run the voice suite after a prompt change" loop. It is wired in
[`.mcp.json`](../.mcp.json) (verified: the endpoint returns `serverInfo: Cekura API`). The
key is referenced as `${CEKURA_API_KEY}` and is never committed. To activate it:

```bash
export CEKURA_API_KEY=...     # or: export $(grep -v '^#' .env | xargs)
# then relaunch Claude Code in this repo and approve the project MCP server
```

Endpoint: `https://api.cekura.ai/mcp`, header `X-CEKURA-API-KEY`.
