"""The intake domain: the question bank, extraction, and summarization.

Same two-layer shape as the rest of the project. Extraction and summarization use a fast
model when a key is present and fall back to deterministic logic so the demo runs keyless.
Reply phrasing is a fixed question bank on purpose: it guarantees one question at a time
and keeps the agent from drifting, which is the whole point on a long call.
"""

from __future__ import annotations

import os

from .state import IntakeOutcome, IntakeSlots

# A fast model, because this is the live-call layer where latency is the experience.
_MODEL = "claude-haiku-4-5-20251001"

# Answers that do not actually fill a slot; the agent re-asks instead of recording noise.
_VAGUE = {"", "i don't know", "idk", "not sure", "no idea", "um", "i'm not sure"}

QUESTIONS = {
    "mobility_limitation": (
        "To start, how far are you able to walk on your own right now, and what makes it hard?"
    ),
    "conditions": "What health conditions affect your ability to get around?",
    "current_equipment": (
        "What are you using to get around today, like a cane, walker, or manual wheelchair, "
        "and how is that working for you?"
    ),
    "home_can_accommodate": (
        "Tell me a little about your home. Are the doorways and floors clear enough for a "
        "power wheelchair to move through?"
    ),
    "can_operate_safely": (
        "Would you be able to safely steer and control a power wheelchair with a joystick yourself?"
    ),
    "face_to_face_exam": (
        "Have you had an in-person visit with your doctor about your mobility, and about when "
        "was that?"
    ),
    "prescribing_physician": "And which doctor is prescribing the wheelchair for you?",
}

GREETING = (
    "Hi {name}, this is your care team calling to gather what your doctor needs for the "
    "power wheelchair request. It should only take a few minutes, and there are no wrong "
    "answers."
)


def apply_answer(slots: IntakeSlots, pending_slot: str | None, latest_user: str) -> IntakeSlots:
    """Record what the patient just said into the slot the agent asked about.

    Uses the model for freeform extraction when a key is present; otherwise assigns the
    answer to the pending slot, skipping vague non-answers so we re-ask instead."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _extract_llm(slots, latest_user)
        except Exception as exc:  # never let the call die on the AI leg
            print(f"[intake] extraction AI path failed ({exc!r}); using fallback")
    text = latest_user.strip()
    if pending_slot and text and text.lower() not in _VAGUE:
        setattr(slots, pending_slot, text)
    return slots


def summarize(slots: IntakeSlots, overflow: list[dict], prior: str) -> str:
    """Fold turns that are leaving the window into the rolling summary.

    The deterministic version derives the summary from the extracted facts, which is the
    lesson in miniature: once a turn's content is in a slot, the raw turn is safe to drop."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _summarize_llm(slots, overflow, prior)
        except Exception as exc:
            print(f"[intake] summary AI path failed ({exc!r}); using fallback")
    facts = "; ".join(f"{f}: {v}" for f, v in slots.filled().items())
    return f"Facts captured so far: {facts}." if facts else prior


def plan_next(
    slots: IntakeSlots, turn_count: int, name: str, max_turns: int
) -> tuple[str, str | None, bool, IntakeOutcome | None]:
    """Decide the next question, or close the call. Always deterministic: control over the
    turn is a feature, not something to hand to the model."""
    missing = slots.missing_required()
    if not missing or turn_count >= max_turns:
        outcome = finalize(slots)
        return _closing(slots), None, True, outcome

    target = missing[0]
    question = QUESTIONS[target]
    if turn_count == 0:
        question = f"{GREETING.format(name=name)} {question}"
    return question, target, False, None


def finalize(slots: IntakeSlots) -> IntakeOutcome:
    ready = slots.is_complete()
    facts = "; ".join(f"{f}: {v}" for f, v in slots.filled().items())
    summary = f"Prior-auth intake for a power wheelchair (K0856). {facts}."
    note = (
        "Complete: hand to the care team to assemble the prior-auth packet for the "
        "prescribing physician to sign."
        if ready
        else (
            f"Incomplete: still missing {', '.join(slots.missing_required())}. Schedule a callback."
        )
    )
    return IntakeOutcome(
        slots=slots, summary=summary, ready_for_prior_auth=ready, handoff_note=note
    )


def _closing(slots: IntakeSlots) -> str:
    name = slots.patient_name or "there"
    if slots.is_complete():
        return (
            f"Thank you, {name}. I have everything your care team needs to put the request "
            "together for your doctor to review. To be clear, I do not decide what Medicare "
            "covers; your care team and doctor handle that. We will follow up with next steps."
        )
    return (
        f"Thank you, {name}. I have most of what we need. A care advocate will call you back "
        "to finish the last couple of details. We do not decide coverage here; your doctor "
        "and care team handle that."
    )


# ---------------------------------------------------------------------------
# AI paths (used only when a key is present)
# ---------------------------------------------------------------------------


def _extract_llm(slots: IntakeSlots, latest_user: str) -> IntakeSlots:
    import anthropic

    prompt = (
        "You are recording a patient's answers during a power-wheelchair intake call. "
        "Here is what has been captured so far, then the patient's latest reply. Return the "
        "slots updated with anything new the reply provides. Do not invent facts; leave a "
        "slot null if the reply does not address it.\n\n"
        f"CAPTURED SO FAR:\n{slots.model_dump_json(indent=2)}\n\n"
        f"PATIENT JUST SAID:\n{latest_user}"
    )
    client = anthropic.Anthropic()
    msg = client.messages.parse(
        model=_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
        output_format=IntakeSlots,
    )
    return msg.parsed_output or slots


def _summarize_llm(slots: IntakeSlots, overflow: list[dict], prior: str) -> str:
    import anthropic

    turns = "\n".join(f"{t['role']}: {t['text']}" for t in overflow)
    prompt = (
        "Update the running summary of a patient intake call. Keep it short (a few "
        "sentences), factual, and focused on anything a care team would need. Fold in the "
        "older turns below.\n\n"
        f"CURRENT SUMMARY:\n{prior or '(none yet)'}\n\n"
        f"OLDER TURNS LEAVING THE WINDOW:\n{turns}"
    )
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()
