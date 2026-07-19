"""The state the conversation carries. Slots are the durable memory.

The key idea: we do not keep the transcript, we keep the extracted facts. `IntakeSlots` is
that memory. It stays small and bounded no matter how long the call runs, so when older raw
turns fall out of the window nothing important is lost, because it was already extracted.
"""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel

# The facts a power-mobility prior-auth request needs. Required ones gate completion; the
# agent works through the missing ones, one question at a time.
REQUIRED_SLOTS = [
    "mobility_limitation",
    "conditions",
    "current_equipment",
    "home_can_accommodate",
    "can_operate_safely",
    "face_to_face_exam",
    "prescribing_physician",
]


class IntakeSlots(BaseModel):
    patient_name: str | None = None
    mobility_limitation: str | None = None
    conditions: str | None = None
    current_equipment: str | None = None
    home_can_accommodate: str | None = None
    can_operate_safely: str | None = None
    face_to_face_exam: str | None = None
    prescribing_physician: str | None = None
    caregiver_support: str | None = None  # helpful context, not required

    def missing_required(self) -> list[str]:
        return [f for f in REQUIRED_SLOTS if not getattr(self, f)]

    def is_complete(self) -> bool:
        return not self.missing_required()

    def filled(self) -> dict[str, str]:
        return {f: v for f, v in self.model_dump().items() if v}


class IntakeOutcome(BaseModel):
    """What the call hands off. This is what a Temporal activity would return."""

    slots: IntakeSlots
    summary: str
    ready_for_prior_auth: bool
    handoff_note: str


class ConversationState(TypedDict):
    recent_turns: list[dict]  # bounded window of {"role", "text"}
    running_summary: str  # the rolling summary of everything older than the window
    slots: IntakeSlots  # the durable extracted memory
    latest_user: str  # the turn coming in
    pending_slot: str | None  # the slot the last question asked about
    turn_count: int
    agent_reply: str
    done: bool
    outcome: IntakeOutcome | None
