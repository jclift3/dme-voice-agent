"""Data shapes for DME back-end coordination.

Intake is already done (per the brief). A `Case` starts from a documented patient
and is worked across four coordination surfaces: supplier outreach, PCP order,
coverage, and the patient update. These models keep the trust boundary legible:
what the system discovers and drafts on its own, versus what a care advocate must
approve before it commits.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# The case (documented intake is the starting state, not something we build)
# ---------------------------------------------------------------------------


class Case(BaseModel):
    patient_name: str
    age: int
    medicare_type: str  # e.g. "Original Medicare (Part B)"
    has_supplemental: bool
    equipment: str  # "standard_manual_wheelchair"
    hcpcs: str  # "K0001"
    pcp_name: str
    pcp_practice: str
    pcp_phone: str
    pcp_visit_done: bool
    verbal_order: bool
    written_order_submitted: bool


# ---------------------------------------------------------------------------
# Supplier outreach. The directory is sparse (name/phone/address). Everything
# that matters is DISCOVERED by calling, then assessed.
# ---------------------------------------------------------------------------


class Supplier(BaseModel):
    name: str
    phone: str
    address: str


class Reached(StrEnum):
    ANSWERED = "answered"
    VOICEMAIL = "voicemail"
    NO_ANSWER = "no_answer"


class SupplierStatus(StrEnum):
    CANDIDATE = "candidate"  # reachable, taking patients, in stock, usable
    WAIT_ONLY = "wait_only"  # in network of options but backordered
    FLAGGED = "flagged"  # usable but a catch (e.g. no assignment)
    EXCLUDED = "excluded"  # not taking patients / cannot serve
    NEEDS_RECALL = "needs_recall"  # no answer or voicemail, try again
    NEEDS_RECONTACT = "needs_recontact"  # said yes then went silent


class SupplierAssessment(BaseModel):
    name: str
    reached: Reached
    taking_new_medicare_patients: bool | None = None
    stocks_k0001: bool | None = None
    accepts_assignment: bool | None = None
    delivery_eta_days: int | None = None
    approx_miles: float | None = None
    status: SupplierStatus
    reason: str  # the one-line a care advocate can verify


class SupplierOutreach(BaseModel):
    shortlist: list[SupplierAssessment]  # ranked, usable now
    other: list[SupplierAssessment]  # excluded / wait-only / flagged
    followups: list[SupplierAssessment]  # need a callback or re-contact
    summary: str
    used_ai: bool = True


# ---------------------------------------------------------------------------
# PCP order tracking. The interesting decision is when to nudge, not the fax.
# ---------------------------------------------------------------------------


class OrderStatus(StrEnum):
    NOT_STARTED = "not_started"
    REQUESTED = "requested"
    IN_PROGRESS = "in_progress"
    SIGNED = "signed"
    STALLED = "stalled"


class PcpOrder(BaseModel):
    status: OrderStatus
    attempts: int
    detail: str
    nudge_after_days: int | None = None  # when to chase again if still unsigned


# ---------------------------------------------------------------------------
# Coverage. DETERMINISTIC. Returns what is needed and what she will owe, never
# a coverage verdict.
# ---------------------------------------------------------------------------


class CoverageRequirement(BaseModel):
    label: str
    met: bool | None = None  # None = unknown from the case so far
    detail: str


class CoverageCheck(BaseModel):
    equipment: str
    hcpcs: str
    headline: str
    requirements: list[CoverageRequirement]
    prior_auth_required: bool
    estimated_patient_responsibility: str  # plain-language, e.g. "about 20% coinsurance"
    cms_reference: str | None = None


# ---------------------------------------------------------------------------
# Coordination plan + the care-advocate approval gate (human in the loop)
# ---------------------------------------------------------------------------


class GateStatus(StrEnum):
    PENDING = "pending_advocate_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class AuditEvent(BaseModel):
    """One recorded interaction or decision. The append-only trail is the record of
    what the system did (which suppliers it called, what it learned, what a care
    advocate approved) and the substrate for improving the agents over time."""

    seq: int
    when: str
    actor: str  # "system" | "care_advocate"
    action: str  # supplier_call | coverage_check | order_request | patient_call | approval
    target: str
    detail: str
    outcome: str | None = None


class Surface(BaseModel):
    """One coordination surface and whether acting on it commits liability."""

    name: str
    status: str
    gated: bool
    detail: str


class CoordinationPlan(BaseModel):
    plan_id: str
    case: Case
    coverage: CoverageCheck
    suppliers: SupplierOutreach
    order: PcpOrder
    surfaces: list[Surface]
    next_action: str  # what a care advocate should do next
    gate: GateStatus = GateStatus.PENDING
    patient_update_script: str | None = None  # filled after approval
    escalations: list[str] = Field(default_factory=list)
    audit: list[AuditEvent] = Field(default_factory=list)
