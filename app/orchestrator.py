"""Coordination orchestrator: works a case across the four surfaces and decides
the next action.

This is where the brief's four coordination surfaces come together: supplier
outreach, PCP order, coverage, and the patient update. It assembles a plan, marks
which surfaces commit liability (and so are gated behind a care advocate), surfaces
the blockers and failure modes, and says what to do next. Reads (calling to discover,
checking coverage rules) run on their own; commits (sending the order request,
calling the patient) wait for approval.

No persistent DB on purpose (per the brief). Plans live in memory.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from .coverage import coverage_check
from .models import (
    AuditEvent,
    Case,
    CoordinationPlan,
    GateStatus,
    OrderStatus,
    PcpOrder,
    SupplierStatus,
    Surface,
)
from .supplier_outreach import load_directory, work_suppliers


def _now() -> str:
    return datetime.now(UTC).strftime("%H:%M:%S")


_PLANS: dict[str, CoordinationPlan] = {}


def all_plans() -> list[CoordinationPlan]:
    return list(_PLANS.values())


def clear_plans() -> None:
    _PLANS.clear()


def get_plan(plan_id: str) -> CoordinationPlan | None:
    return _PLANS.get(plan_id)


def _assess_order(case: Case) -> PcpOrder:
    """The interesting decision is when to nudge, not how the fax is sent."""
    if case.written_order_submitted:
        return PcpOrder(status=OrderStatus.SIGNED, attempts=1, detail="Written order is on file.")
    detail = (
        f"Verbal order is in {case.patient_name.split()[0]}'s chart, but the written order "
        f"is not submitted. Request it from {case.pcp_name}'s office ({case.pcp_practice}) "
        "and nudge again if it is not signed."
    )
    return PcpOrder(status=OrderStatus.REQUESTED, attempts=1, detail=detail, nudge_after_days=2)


def assemble_plan(case: Case) -> CoordinationPlan:
    """Work all four surfaces and assemble a plan, without storing it.

    This is the pure discovery pass: it calls to discover, checks coverage, and drafts
    the order request, leaving the gated surfaces pending. `build_plan` wraps this for
    the in-memory console; the Temporal workflow calls it as the discovery activity."""
    plan_id = f"case_{uuid.uuid4().hex[:8]}"
    coverage = coverage_check(case)
    suppliers = work_suppliers(case)
    order = _assess_order(case)

    surfaces = [
        Surface(
            name="supplier_outreach",
            status="done",
            gated=False,  # calling to discover is a read
            detail=suppliers.summary,
        ),
        Surface(
            name="pcp_order",
            status=order.status.value,
            gated=True,  # sending a request to the PCP commits on the patient's behalf
            detail=order.detail,
        ),
        Surface(
            name="coverage",
            status="checked",
            gated=False,  # reading the rules is a read
            detail=f"{coverage.headline} {coverage.estimated_patient_responsibility}",
        ),
        Surface(
            name="patient_update",
            status="pending_approval",
            gated=True,  # a patient-facing commitment
            detail="Status call with the plan, timeline, and expected cost, sent after approval.",
        ),
    ]

    escalations = _escalations(case, suppliers, order)
    plan = CoordinationPlan(
        plan_id=plan_id,
        case=case,
        coverage=coverage,
        suppliers=suppliers,
        order=order,
        surfaces=surfaces,
        next_action=_next_action(suppliers, order),
        escalations=escalations,
        audit=_build_audit(case, suppliers, order),
    )
    return plan


def build_plan(case: Case) -> CoordinationPlan:
    """Assemble a plan and store it for the in-memory console."""
    plan = assemble_plan(case)
    _PLANS[plan.plan_id] = plan
    return plan


def _build_audit(case, suppliers, order) -> list[AuditEvent]:
    """The record of what the system did: every supplier call it placed, then the
    coverage check and the drafted order request. Recorded in the order calls were made."""
    events: list[AuditEvent] = []
    by_name = {a.name: a for a in (suppliers.shortlist + suppliers.followups + suppliers.other)}
    seq = 0
    for s in load_directory():
        a = by_name.get(s.name)
        if a is None:
            continue
        seq += 1
        events.append(
            AuditEvent(
                seq=seq,
                when=_now(),
                actor="system",
                action="supplier_call",
                target=a.name,
                detail=f"Called {s.phone}. Asked: taking new Medicare patients, K0001 in stock, "
                f"accepts assignment, delivery ETA. Reached: {a.reached.value}.",
                outcome=a.status.value,
            )
        )
    seq += 1
    events.append(
        AuditEvent(
            seq=seq,
            when=_now(),
            actor="system",
            action="coverage_check",
            target=case.hcpcs,
            detail="Checked Medicare Part B coverage rules for K0001.",
            outcome="checked",
        )
    )
    seq += 1
    events.append(
        AuditEvent(
            seq=seq,
            when=_now(),
            actor="system",
            action="order_request",
            target=case.pcp_name,
            detail=order.detail,
            outcome=order.status.value,
        )
    )
    return events


def _escalations(case, suppliers, order) -> list[str]:
    out = []
    if order.status != OrderStatus.SIGNED:
        out.append(
            "Written order is not signed yet. Nothing delivers or bills until it is, so this is "
            "the critical-path blocker, not the supplier."
        )
    if not suppliers.shortlist:
        out.append("No supplier can serve her now. Work the callbacks or widen the directory.")
    for a in suppliers.followups:
        if a.status == SupplierStatus.NEEDS_RECONTACT:
            out.append(f"{a.name} agreed then went silent. Re-contact before relying on them.")
    return out


def _next_action(suppliers, order) -> str:
    if not suppliers.shortlist:
        return "No ready supplier. Chase the callbacks before promising the patient anything."
    top = suppliers.shortlist[0].name
    if order.status != OrderStatus.SIGNED:
        return (
            f"Approve the written-order request to the PCP and hold {top} as the lead supplier. "
            "The order is the blocker; do not confirm delivery until it is signed."
        )
    return f"Confirm {top} and schedule delivery, then update the patient."


def apply_approval(plan: CoordinationPlan) -> CoordinationPlan:
    """Fire the gated surfaces and record the approval on a plan object.

    The care-advocate gate. Only here do the gated surfaces commit. Shared by the
    in-memory `approve_plan` and the Temporal commit activity so there is one source
    of truth for what happens across the trust boundary."""
    plan.gate = GateStatus.APPROVED
    for s in plan.surfaces:
        if s.gated:
            s.status = "sent" if s.name == "patient_update" else "approved_to_send"
    plan.patient_update_script = _patient_update_script(plan)

    seq = len(plan.audit)
    plan.audit.append(
        AuditEvent(
            seq=seq + 1,
            when=_now(),
            actor="care_advocate",
            action="approval",
            target=plan.case.patient_name,
            detail="Approved the gated surfaces.",
            outcome="approved",
        )
    )
    plan.audit.append(
        AuditEvent(
            seq=seq + 2,
            when=_now(),
            actor="system",
            action="order_request",
            target=plan.case.pcp_name,
            detail="Sent the written-order request to the PCP office.",
            outcome="sent",
        )
    )
    plan.audit.append(
        AuditEvent(
            seq=seq + 3,
            when=_now(),
            actor="system",
            action="patient_call",
            target=plan.case.patient_name,
            detail="Placed the patient status call.",
            outcome="sent",
        )
    )
    return plan


def approve_plan(plan_id: str) -> CoordinationPlan | None:
    """The care-advocate gate for the in-memory console."""
    plan = _PLANS.get(plan_id)
    if plan is None:
        return None
    return apply_approval(plan)


def reject_plan(plan_id: str, reason: str = "") -> CoordinationPlan | None:
    plan = _PLANS.get(plan_id)
    if plan is None:
        return None
    plan.gate = GateStatus.REJECTED
    if reason:
        plan.escalations.insert(0, f"Advocate rejected the plan: {reason}")
    return plan


def _patient_update_script(plan: CoordinationPlan) -> str:
    """What the patient hears. It states next steps and the likely cost share, and
    never says she is covered."""
    first = plan.case.patient_name.split()[0]
    top = plan.suppliers.shortlist[0].name if plan.suppliers.shortlist else None
    if top is None:
        return (
            f"Hi {first}, this is your care team with an update on your wheelchair. We are "
            "still lining up a supplier who can deliver to you, and a care advocate is "
            "working on it personally. We will call you as soon as we have a date. You do "
            "not need to do anything yet."
        )
    order_line = (
        " Your doctor still needs to sign the written order, and we are on it."
        if plan.order.status != OrderStatus.SIGNED
        else ""
    )
    return (
        f"Hi {first}, this is your care team with an update on your wheelchair. We found a "
        f"supplier who can deliver, {top}.{order_line} On cost: after your Part B deductible, "
        "Medicare covers most of it and you would owe about 20%. We will call you when "
        "delivery is scheduled. For now, there is nothing you need to do."
    )
