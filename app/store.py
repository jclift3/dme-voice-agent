"""In-memory store for coordination plans + the orchestration that builds them.

No persistent DB on purpose (per the brief — mock freely). This is where the
async coordination work happens after the call ends: build coverage checklist
(deterministic), match vendors (AI), assemble legs, and decide what's gated.
"""

from __future__ import annotations

import uuid

from . import coverage as coverage_mod
from .models import (
    CoordinationPlan,
    GateStatus,
    IntakeRequest,
    PlanLeg,
)
from .vendor_match import match_vendors

# Below this, extraction is too uncertain to act on — route to a human.
CONFIDENCE_THRESHOLD = 0.6

_PLANS: dict[str, CoordinationPlan] = {}


def all_plans() -> list[CoordinationPlan]:
    return list(_PLANS.values())


def get_plan(plan_id: str) -> CoordinationPlan | None:
    return _PLANS.get(plan_id)


def build_plan(intake: IntakeRequest) -> CoordinationPlan:
    """The async coordination step. Runs after the call ends."""
    plan_id = f"plan_{uuid.uuid4().hex[:8]}"
    checklist = coverage_mod.coverage_requirements(intake)
    vendors = match_vendors(intake)

    # PCP leg is MOCKED (office closed in the scenario). We model *when* to nudge,
    # which is the interesting decision; the fax/EHR write itself is plumbing.
    pcp_needed = not intake.has_order
    legs = [
        PlanLeg(
            name="vendor_research",
            status="done",
            gated=False,  # research is a read — safe to automate
            detail=vendors.summary,
        ),
        PlanLeg(
            name="pcp_order_nudge",
            status="drafted" if pcp_needed else "not_needed",
            gated=True,  # sending anything to the PCP is a write — gate it
            detail=(
                "Draft order-nudge queued for nurse to send to PCP "
                f"({intake.pcp_name or 'PCP on file'})."
                if pcp_needed
                else "Order already exists; no nudge needed."
            ),
        ),
        PlanLeg(
            name="patient_callback",
            status="pending_approval",
            gated=True,  # a patient-facing commitment — gate it
            detail="Callback with plan + timeline, sent only after nurse approves.",
        ),
    ]

    plan = CoordinationPlan(
        plan_id=plan_id,
        intake=intake,
        coverage=checklist,
        vendors=vendors,
        legs=legs,
    )

    # Guardrails: escalate (don't auto-proceed) when we can't act safely.
    if intake.confidence < CONFIDENCE_THRESHOLD:
        plan.escalated_to_human = True
        plan.escalation_reason = (
            f"Low extraction confidence ({intake.confidence:.2f}) — nurse should "
            "review the captured request before anything proceeds."
        )
    elif not vendors.shortlist:
        plan.escalated_to_human = True
        plan.escalation_reason = (
            "No in-network supplier found — nurse should research manually and "
            "set honest expectations with the patient."
        )

    _PLANS[plan_id] = plan
    return plan


def approve_plan(plan_id: str) -> CoordinationPlan | None:
    """The nurse approval gate. Only here do liability-bearing legs proceed."""
    plan = _PLANS.get(plan_id)
    if plan is None:
        return None
    plan.gate = GateStatus.APPROVED
    for leg in plan.legs:
        if leg.gated and leg.status in ("pending_approval", "drafted"):
            leg.status = "sent" if leg.name == "patient_callback" else "approved_to_send"
    plan.callback_script = _build_callback_script(plan)
    return plan


def reject_plan(plan_id: str, reason: str = "") -> CoordinationPlan | None:
    plan = _PLANS.get(plan_id)
    if plan is None:
        return None
    plan.gate = GateStatus.REJECTED
    plan.escalation_reason = reason or "Nurse rejected the plan."
    return plan


def _build_callback_script(plan: CoordinationPlan) -> str:
    """What the patient hears on the callback. Note what it never says:
    it states what's needed and the next step — never 'you are covered'."""
    top = plan.vendors.shortlist[0] if plan.vendors.shortlist else None
    eq = plan.intake.equipment.replace("_", " ")
    if top is None:
        return (
            f"Hi, this is your care team following up about your {eq}. We weren't "
            "able to confirm an in-network supplier yet, so a nurse is looking into "
            "it personally and will call you back. You don't need to do anything yet."
        )
    pcp_line = (
        " Your provider still needs to sign the order, and we've queued a request to their office."
        if not plan.intake.has_order
        else ""
    )
    return (
        f"Hi, this is your care team following up about your {eq}. We found "
        f"{len(plan.vendors.shortlist)} in-network supplier(s) for your plan — the best "
        f"fit is {top.name}, which has it in stock.{pcp_line} "
        "We'll coordinate the next steps and keep you updated. Here's what's needed from "
        "you: nothing right now — we'll reach out if we need anything."
    )
