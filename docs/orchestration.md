# Orchestration: why Temporal, and where LangGraph fits

This is the reasoning behind the orchestration choice, written to be retained and defended
in a review. The one idea to hold onto: orchestration here is two layers, not one, and the
answer is different on each.

## The two layers

**Workflow orchestration** coordinates the *case* over hours and days: start a supplier
call, record the outcome, retry a flaky one, wait two days, chase the supplier that went
silent, block on the care-advocate gate. This is long-lived, stateful, and human-gated.

**Conversation orchestration** coordinates the *reasoning inside one call*, turn by turn:
what to ask next, what to remember, when to stop. This is real-time and short-lived.

These sit on top of each other. They are not competitors. A whole 30-minute phone call is
a *single step* in the workflow layer. Conflating them is the mistake to avoid.

## Why Temporal for the workflow layer

The hard problem this project was handed is durable, multi-day, stall-prone, human-gated
coordination. That is exactly what durable execution is for:

- **Durability**: workflow state survives restarts and redeploys, so a case in flight is
  never lost. A dict in memory (what `app/orchestrator.py` uses today, correctly, for the
  no-DB take-home) cannot do this.
- **Timers**: `sleep(2 days)` then re-contact is a first-class primitive. The stall (a
  supplier says yes then goes quiet, or an order sits in a queue) becomes an SLA timer that
  escalates instead of the case quietly losing a week. That is the failure mode `DESIGN.md`
  names as the thing to worry about shipping.
- **Retries**: flaky supplier calls get backoff for free.
- **Human-in-the-loop**: the care-advocate gate maps cleanly to a **signal** the workflow
  blocks on, which is exactly what the console's Approve button sends.

Our whole "what's next" list (SLA alerting, a re-contact scheduler, per-case durable state)
is nearly a description of what Temporal gives for free.

## Why not LangGraph for the workflow layer

LangGraph orchestrates LLM-agent graphs: a state machine where an LLM decides the next
step. That is the wrong fit for the *workflow* layer here because:

- Our coordination is mostly **deterministic policy** plus a couple of AI calls. The LLM is
  one node (supplier synthesis), not the control flow. LangGraph shines when the control
  flow itself is LLM-driven; ours is not.
- Its checkpointing is **weaker than Temporal** for multi-day timers, retries, and
  surviving restarts, which is precisely our hard part.

So for the workflow, Temporal wins. But that does not banish LangGraph from the project.

## Where LangGraph *does* fit: the conversation layer

LangGraph is a strong tool for the *conversation* layer, the turn-by-turn reasoning inside
a long call. It makes conversation state explicit (a graph of nodes with a state object you
control), so the context-management patterns below become clean, deterministic steps rather
than prompt spaghetti, and it gives you `interrupt` for mid-call human handoff.

Crucially, **this composes with Temporal, it does not conflict.** Temporal fires the call
as one activity. Inside that activity, the agent manages its own bounded context (LangGraph,
or today just Vapi plus a tight prompt plus the record-outcome tool). Temporal never sees
the turns, only the final recorded outcome. Choosing Temporal for the workflow does not lock
LangGraph out of the conversation.

## The 30-minute call: keeping context bounded without losing the thread

A long call risks the context window blowing up and the agent drifting. This is a
**context-engineering** problem at the voice + LLM layer, not something the workflow engine
solves. The key move: **you do not keep the transcript, you keep the extracted facts.**

1. **Rolling summary.** Keep the last few turns verbatim plus a short running summary of
   everything before. The window stays bounded no matter how long the call runs.
2. **Structured state / slot-filling.** As the call goes, extract the facts that matter into
   a small structured object (does the supplier stock K0001? accept assignment? delivery
   ETA?). *That* is the memory; the meandering minutes can fall out of the window. This is
   exactly what our `record_supplier_outcome` tool already does.
3. **Tight scope prevents drift.** A narrow task and hard guardrails ("one question at a
   time, never discuss coverage") keep it on rails. Drift is prevented by narrow scope plus
   the eval rubrics, not by feeding it more context. Our Cekura metrics grade this.
4. **Retrieval on demand.** Pull reference facts when needed rather than stuffing them all
   into the prompt up front.
5. **A turn or time budget.** For a bounded task, cap it. Our Vapi assistant sets
   `maxDurationSeconds: 300`.

Worth noting: our *supplier* calls are transactional (four questions, record, hang up), so
they do not really have the 30-minute problem. The long, meandering call is more the
patient-facing empathetic conversation, and that is where the rolling-summary plus
slot-filling pattern earns its keep.

## The decision on the code, and why

We built the durable **Temporal** path (on the `temporal-orchestration` branch) because the
workflow layer is the orchestration question we were actually asked. We did **not** add
LangGraph to the code, on purpose:

- The conversation layer is handled today by the voice platform plus a tight prompt plus the
  record-outcome tool, and the transactional supplier calls do not need more.
- Adding a custom LangGraph conversation runtime now would duplicate what the voice platform
  does and add a heavy dependency for no current value.
- Knowing exactly where LangGraph would go, and why it is not needed yet, is a cleaner
  position than an unused import. If the patient-facing empathetic call grows long enough to
  need explicit turn-state control, that is the deliberate moment to add it, inside a
  Temporal activity.

## The soundbites

1. Two layers: Temporal orchestrates the case across days; LangGraph would orchestrate the
   reasoning within a call. It is not either/or.
2. A 30-minute call is one activity to Temporal. Temporal is never in the audio loop.
3. You do not keep the transcript, you keep the extracted facts: a rolling summary plus
   structured slot-filling. That is what bounds the context, and it is what our
   record-outcome tool already does.

## Vocabulary, so you are precise

- **LangChain**: the broad toolkit (chains, integrations, glue).
- **LangGraph**: the stateful graph/state-machine for agents, the part relevant to long,
  cyclic, human-in-the-loop conversations. When people say "LangChain for orchestration"
  they now usually mean LangGraph.
- **Temporal**: a durable-execution engine for long-running workflows (timers, retries,
  signals, state that survives restarts).
