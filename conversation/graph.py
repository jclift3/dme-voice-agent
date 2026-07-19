"""The LangGraph conversation graph.

Three nodes run per turn: `extract` records what the patient just said into slots,
`plan_reply` chooses the next question (or closes), and `compress` appends the exchange to
a bounded window and folds anything older into the rolling summary. That last node is where
the context stays bounded: the window never grows past WINDOW turns, and the facts live in
slots and the summary, not in an ever-growing transcript.

In production the voice platform drives one turn per webhook and calls `handle_turn`.
`run_scripted` plays a full transcript through the same graph for the demo and for a
Temporal activity that needs to replay or drive a call end to end.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from .intake import apply_answer, plan_next, summarize
from .state import ConversationState, IntakeOutcome, IntakeSlots

WINDOW = 4  # turns kept verbatim; older ones fold into the rolling summary
MAX_TURNS = 25  # a hard budget so a long call still ends


def _extract(state: ConversationState) -> dict:
    slots = apply_answer(state["slots"], state["pending_slot"], state["latest_user"])
    return {"slots": slots}


def _plan_reply(state: ConversationState) -> dict:
    name = state["slots"].patient_name or "there"
    reply, target, done, outcome = plan_next(state["slots"], state["turn_count"], name, MAX_TURNS)
    return {"agent_reply": reply, "pending_slot": target, "done": done, "outcome": outcome}


def _compress(state: ConversationState) -> dict:
    turns = list(state["recent_turns"])
    if state["latest_user"]:
        turns.append({"role": "patient", "text": state["latest_user"]})
    turns.append({"role": "agent", "text": state["agent_reply"]})

    summary = state["running_summary"]
    if len(turns) > WINDOW:
        overflow = turns[:-WINDOW]
        turns = turns[-WINDOW:]
        summary = summarize(state["slots"], overflow, summary)

    return {
        "recent_turns": turns,
        "running_summary": summary,
        "turn_count": state["turn_count"] + 1,
    }


def build_graph():
    g = StateGraph(ConversationState)
    g.add_node("extract", _extract)
    g.add_node("plan_reply", _plan_reply)
    g.add_node("compress", _compress)
    g.set_entry_point("extract")
    g.add_edge("extract", "plan_reply")
    g.add_edge("plan_reply", "compress")
    g.add_edge("compress", END)
    return g.compile()


def initial_state(patient_name: str) -> ConversationState:
    return {
        "recent_turns": [],
        "running_summary": "",
        "slots": IntakeSlots(patient_name=patient_name),
        "latest_user": "",
        "pending_slot": None,
        "turn_count": 0,
        "agent_reply": "",
        "done": False,
        "outcome": None,
    }


def handle_turn(graph, state: ConversationState, user_text: str) -> ConversationState:
    """One patient turn in, one agent turn out. This is the per-webhook entry point."""
    state = dict(state)
    state["latest_user"] = user_text
    return graph.invoke(state)


def run_scripted(
    patient_name: str, utterances: list[str]
) -> tuple[ConversationState, IntakeOutcome]:
    """Play a full transcript through the graph and return the final state and outcome.

    The first turn has no patient input (the agent greets and asks). This is what a Temporal
    activity would call to drive or replay a whole call and get back the extracted outcome."""
    graph = build_graph()
    state = initial_state(patient_name)

    state = handle_turn(graph, state, "")  # greeting + first question
    for text in utterances:
        if state["done"]:
            break
        state = handle_turn(graph, state, text)

    if not state["done"]:  # ran out of scripted input; close on what we have
        from .intake import finalize

        state["outcome"] = finalize(state["slots"])
        state["done"] = True

    return state, state["outcome"]
