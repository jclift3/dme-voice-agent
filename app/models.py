"""Shared data shapes for the DME coordination backend.

These are the contracts between the voice layer (Vapi), the deterministic
rules, the AI vendor-matching, and the nurse approval gate. Keeping them in
one place makes the trust boundary legible: what the agent *captures* vs. what
the rules *decide* vs. what a human *approves*.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Intake, what the voice agent captures on the call (REAL, via Vapi tools)
# ---------------------------------------------------------------------------


class IntakeRequest(BaseModel):
    """Structured request extracted from the inbound call.

    The agent fills this from natural conversation. `confidence` is the agent's
    own read of how sure it is, below threshold we route to a human rather
    than guess (see app/main.py).
    """

    equipment: str = Field(
        description="e.g. standard_wheelchair, cpap, walker, hospital_bed, oxygen_concentrator"
    )
    plan_id: str | None = Field(
        default=None, description="Medicare plan id if the patient knows it"
    )
    plan_name: str | None = Field(
        default=None, description="Plan name as spoken, even if id unknown"
    )
    zip: str | None = Field(default=None, description="Patient ZIP for in-area matching")
    pcp_name: str | None = Field(default=None, description="Primary care provider name")
    recent_visit: bool | None = Field(
        default=None, description="Had a recent face-to-face PCP visit?"
    )
    has_order: bool | None = Field(default=None, description="Does a written order already exist?")
    urgency: str = Field(default="routine", description="routine | soon | urgent")
    patient_callback_number: str | None = Field(default=None)
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Agent's confidence in this capture"
    )
    notes: str | None = Field(default=None, description="Anything else worth a nurse seeing")


# ---------------------------------------------------------------------------
# Coverage requirements, DETERMINISTIC. Never a coverage *determination*.
# ---------------------------------------------------------------------------


class CoverageRequirement(BaseModel):
    label: str
    met: bool | None = None  # None = unknown from intake
    detail: str


class CoverageChecklist(BaseModel):
    equipment: str
    headline: str  # what's needed, phrased as steps, NOT "you are covered"
    requirements: list[CoverageRequirement]
    cms_reference: str | None = None


# ---------------------------------------------------------------------------
# Vendor matching, AI judgment (Claude) over a mocked supplier directory
# ---------------------------------------------------------------------------


class RankedVendor(BaseModel):
    id: str
    name: str
    rank: int
    in_network: bool
    in_stock: bool
    distance_mi: float
    rationale: str = Field(
        description="Why this vendor placed here, the reasoning a nurse would want to see"
    )


class ExcludedVendor(BaseModel):
    id: str
    name: str
    reason: str


class VendorMatch(BaseModel):
    shortlist: list[RankedVendor]
    excluded: list[ExcludedVendor]
    summary: str = Field(description="One or two sentences a nurse can read at a glance")
    used_ai: bool = True  # False when the deterministic fallback produced this


# ---------------------------------------------------------------------------
# Coordination plan + the nurse approval gate (human-in-the-loop)
# ---------------------------------------------------------------------------


class GateStatus(StrEnum):
    PENDING = "pending_nurse_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class PlanLeg(BaseModel):
    """One unit of coordination work. `gated` legs touch liability and require
    nurse approval before any external write or patient-facing commitment."""

    name: str
    status: str
    gated: bool
    detail: str


class CoordinationPlan(BaseModel):
    plan_id: str
    intake: IntakeRequest
    coverage: CoverageChecklist
    vendors: VendorMatch
    legs: list[PlanLeg]
    gate: GateStatus = GateStatus.PENDING
    callback_script: str | None = None  # filled after approval
    escalated_to_human: bool = False
    escalation_reason: str | None = None
