# Temporal orchestration (review branch)

This branch makes the coordination workflow durable. It is the answer to "what runs the
long-lived, stall-prone, human-gated coordination in production," and it maps one to one
onto the trust boundary the rest of the system is built around.

Today the in-memory `app/orchestrator.py` works a case in a single request: it is correct
for the take-home's no-DB constraint, but a dict in memory cannot survive a restart or
wake itself in three days to chase a silent supplier. Temporal is the durable version of
the same logic. It reuses the exact domain code; nothing about the coordination behavior
changes.

## The mapping

| Coordination concept | Temporal primitive | Where |
|---|---|---|
| The reads (call suppliers, check coverage, draft the order) | one `discover` activity | `activities.py` |
| The care-advocate gate | a `wait_condition` on an `approve` / `reject` **signal** | `workflow.py` |
| The stall (yes-then-silent, order stuck in a queue) | an **SLA timer** that fires `escalate_stall` | `workflow.py` |
| The commits (order request, patient call) | `commit_gated_surfaces` activity, only after approval | `activities.py` |
| Durability across restarts and multi-day waits | workflow state, not a module dict | Temporal server |

The workflow parks at `awaiting_care_advocate` and holds there indefinitely. Approval is a
signal, exactly what the console's Approve button sends. If the gate is not worked within
`GATE_SLA` (2 days here), the timer escalates instead of the case quietly losing a week,
which is the failure mode `DESIGN.md` calls out as the thing to worry about shipping.

## One source of truth

The activities are thin wrappers over `app.orchestrator.assemble_plan` (the reads) and
`app.orchestrator.apply_approval` (the commits). Those two functions also back the
in-memory console, so the durable path and the demo path cannot drift.

## Run it

```bash
pip install -r requirements.txt -r temporal/requirements.txt
temporal server start-dev          # Temporal dev server + UI on localhost:8233
python -m temporal.worker          # hosts the workflow + activities
python -m temporal.starter         # drives Eleanor's case, then signals approve
```

The starter starts the workflow, queries the phase (it is parked at the gate), sends the
approval signal, and prints the committed plan. Open the Temporal UI to see the workflow
history, the pending timer, and the signal.

## Why this and not the alternatives

Durable execution fits because the domain *is* long-lived, timer-driven, and human-gated.
LangGraph orchestrates LLM-agent graphs, which is a different problem: here the LLM is one
node, not the control flow. Inngest is the lighter durable-timer option if standing up
Temporal is too much. CrewAI is multi-agent collaboration, which this is not. See the
orchestration discussion in the PR description.
