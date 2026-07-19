# Conversation layer (LangGraph)

This is the other half of the orchestration story. Where `temporal/` orchestrates the
*case* across days, this orchestrates the *reasoning inside one call*, turn by turn. It is
the concrete answer to "how do you keep a 30-minute call from drifting or blowing up the
context window."

The worked example is a **prior-authorization intake for a power wheelchair (K0856)**.
Unlike Eleanor's K0001, a power wheelchair needs prior auth and a lot of clinical
justification, so it is a genuinely long, multi-topic conversation. The agent gathers the
facts and hands them off; it never decides coverage or medical necessity.

## The graph

Three nodes run per turn (`conversation/graph.py`):

1. **extract** records what the patient just said into structured **slots**.
2. **plan_reply** picks the next question, one at a time, or closes the call.
3. **compress** appends the exchange to a bounded window and folds anything older into a
   **rolling summary**.

The context stays bounded because of node 3: the verbatim window never grows past `WINDOW`
turns, and the durable memory lives in the slots and the summary, not in an ever-growing
transcript. That is the lesson in one place: **you do not keep the transcript, you keep the
extracted facts.**

## Run it (keyless)

```bash
pip install -r requirements.txt -r conversation/requirements.txt
python -m conversation.run_demo
```

Watch the status line: `window` pins at `4/4` while `turn` climbs past it, the slots fill
in, and the call closes with a handoff outcome that never claims coverage. With no key it
uses the deterministic paths (slot-filling extraction, a facts-based summary); with
`ANTHROPIC_API_KEY` set it uses a fast model for freeform extraction and a condensed prose
summary. Reply phrasing is a fixed question bank on purpose: control over the turn is a
feature, and it guarantees one question at a time.

## The context-bounding patterns, and where each lives

| Pattern | Where |
|---|---|
| Rolling summary (older turns folded, window trimmed) | `_compress` in `graph.py`, `summarize` in `intake.py` |
| Structured slot-filling (the durable memory) | `IntakeSlots` in `state.py`, `apply_answer` in `intake.py` |
| Tight scope to prevent drift (one question at a time, never adjudicate) | `plan_next` and the closing in `intake.py` |
| Turn budget so a long call still ends | `MAX_TURNS` in `graph.py` |

## How it composes with Temporal

They sit on different layers and do not compete. In production the voice platform drives
one patient turn per webhook and calls `handle_turn`; Temporal owns the surrounding
workflow (schedule the call, retry, wait, react to the result). A **whole call is one
activity** to Temporal, and the `IntakeOutcome` this graph produces is exactly what that
activity returns. `run_scripted` drives a full transcript end to end, which is the shape a
Temporal activity would call to run or replay a call.

Temporal never sees the individual turns. It is not in the audio loop. The full reasoning
is in [../docs/orchestration.md](../docs/orchestration.md).
