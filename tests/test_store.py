"""Unit tests for the orchestration + nurse approval gate (the trust boundary)."""

from app.models import GateStatus, IntakeRequest
from app.store import approve_plan, build_plan, reject_plan

HAPPY = IntakeRequest(
    equipment="standard_wheelchair",
    plan_id="HUM-MA-PPO",
    zip="78704",
    recent_visit=True,
    has_order=False,
    confidence=0.95,
    patient_callback_number="+15125550142",
)


def _legs(plan):
    return {leg.name: leg for leg in plan.legs}


def test_build_plan_starts_pending_with_no_callback_script():
    plan = build_plan(HAPPY)
    assert plan.gate is GateStatus.PENDING
    assert plan.callback_script is None
    assert not plan.escalated_to_human


def test_reads_are_auto_and_writes_are_gated():
    legs = _legs(build_plan(HAPPY))
    assert legs["vendor_research"].gated is False
    assert legs["pcp_order_nudge"].gated is True
    assert legs["patient_callback"].gated is True


def test_low_confidence_escalates_to_human():
    plan = build_plan(HAPPY.model_copy(update={"confidence": 0.3}))
    assert plan.escalated_to_human
    assert "confidence" in plan.escalation_reason.lower()


def test_no_in_network_vendor_escalates():
    plan = build_plan(HAPPY.model_copy(update={"plan_id": "CIGNA-MA-HMO"}))
    assert plan.escalated_to_human
    assert "supplier" in plan.escalation_reason.lower()


def test_pcp_nudge_skipped_when_order_exists():
    legs = _legs(build_plan(HAPPY.model_copy(update={"has_order": True})))
    assert legs["pcp_order_nudge"].status == "not_needed"


def test_approve_opens_gate_and_writes_callback_script():
    plan = build_plan(HAPPY)
    approved = approve_plan(plan.plan_id)
    assert approved.gate is GateStatus.APPROVED
    assert approved.callback_script


def test_callback_script_states_next_steps_never_coverage():
    plan = build_plan(HAPPY)
    script = approve_plan(plan.plan_id).callback_script.lower()
    assert "you're covered" not in script and "you are covered" not in script
    assert "approved" not in script and "denied" not in script


def test_reject_sets_rejected_gate():
    plan = build_plan(HAPPY)
    assert reject_plan(plan.plan_id, "not eligible").gate is GateStatus.REJECTED


def test_approve_unknown_plan_returns_none():
    assert approve_plan("plan_does_not_exist") is None
