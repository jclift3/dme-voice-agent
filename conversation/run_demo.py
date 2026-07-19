"""Play a scripted patient through the conversation graph, keyless.

Run it and watch the context stay bounded: `window` never grows past WINDOW turns even as
`turn` climbs, the rolling summary picks up the older turns, and the slots fill in as the
durable memory. That is the whole lesson made visible.

    python -m conversation.run_demo
"""

from __future__ import annotations

from .graph import WINDOW, build_graph, handle_turn, initial_state
from .state import REQUIRED_SLOTS

# A patient who genuinely needs a power wheelchair, answering in the order the agent asks.
PATIENT = "Margaret Ellison"
SCRIPT = [
    "I can maybe walk to my mailbox and back, but I get short of breath and my knees give out.",
    "I have COPD and bad osteoarthritis in both knees, and some heart trouble.",
    "I have a walker, but I can't push myself far and I've fallen twice using it this month.",
    "It's a one-floor apartment, wide doorways, no steps inside, hardwood floors throughout.",
    "Yes, my hands are steady and I already drive, so a joystick would be no problem.",
    "Yes, I saw Dr. Patel about three weeks ago specifically about my mobility.",
    "Dr. Anjali Patel at Lakeview Internal Medicine is prescribing it.",
]


def _status(state) -> str:
    filled = len(state["slots"].filled()) - 1  # minus patient_name
    return (
        f"turn={state['turn_count']:>2}  window={len(state['recent_turns'])}/{WINDOW}  "
        f"summary={len(state['running_summary']):>3} chars  "
        f"slots={filled}/{len(REQUIRED_SLOTS)} required"
    )


def main() -> None:
    graph = build_graph()
    state = initial_state(PATIENT)

    state = handle_turn(graph, state, "")  # greeting + first question
    print(f"\nAGENT: {state['agent_reply']}")
    print(f"       [{_status(state)}]")

    for line in SCRIPT:
        if state["done"]:
            break
        print(f"\nPATIENT: {line}")
        state = handle_turn(graph, state, line)
        print(f"AGENT: {state['agent_reply']}")
        print(f"       [{_status(state)}]")

    outcome = state["outcome"]
    print("\n" + "=" * 78)
    print("HANDOFF OUTCOME (what a Temporal activity would return):")
    print(f"  ready_for_prior_auth: {outcome.ready_for_prior_auth}")
    print(f"  handoff_note: {outcome.handoff_note}")
    print("  captured facts:")
    for f, v in outcome.slots.filled().items():
        print(f"    - {f}: {v}")
    print(f"\n  rolling summary held instead of the transcript:\n    {state['running_summary']}")


if __name__ == "__main__":
    main()
