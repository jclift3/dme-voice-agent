"""Unit tests for the coordination orchestrator and the care-advocate gate."""

from app.cases import ELEANOR
from app.models import GateStatus, OrderStatus
from app.orchestrator import approve_plan, build_plan, reject_plan


def _surfaces(plan):
    return {s.name: s for s in plan.surfaces}


def test_build_plan_starts_pending_with_no_patient_script():
    plan = build_plan(ELEANOR)
    assert plan.gate is GateStatus.PENDING
    assert plan.patient_update_script is None


def test_reads_are_auto_and_commits_are_gated():
    s = _surfaces(build_plan(ELEANOR))
    assert s["supplier_outreach"].gated is False
    assert s["coverage"].gated is False
    assert s["pcp_order"].gated is True
    assert s["patient_update"].gated is True


def test_order_is_requested_and_nudge_scheduled_when_unsigned():
    order = build_plan(ELEANOR).order
    assert order.status is OrderStatus.REQUESTED
    assert order.nudge_after_days is not None


def test_order_is_signed_when_written_order_on_file():
    plan = build_plan(ELEANOR.model_copy(update={"written_order_submitted": True}))
    assert plan.order.status is OrderStatus.SIGNED


def test_unsigned_order_is_the_surfaced_blocker():
    plan = build_plan(ELEANOR)
    assert any("written order" in e.lower() for e in plan.escalations)
    assert "order" in plan.next_action.lower()


def test_approve_opens_gate_and_writes_patient_script():
    plan = build_plan(ELEANOR)
    approved = approve_plan(plan.plan_id)
    assert approved.gate is GateStatus.APPROVED
    assert approved.patient_update_script


def test_patient_script_states_cost_never_coverage():
    plan = build_plan(ELEANOR)
    script = approve_plan(plan.plan_id).patient_update_script.lower()
    assert "20%" in script
    assert "you're covered" not in script and "you are covered" not in script


def test_reject_sets_rejected_gate():
    plan = build_plan(ELEANOR)
    assert reject_plan(plan.plan_id, "needs review").gate is GateStatus.REJECTED


def test_approve_unknown_plan_returns_none():
    assert approve_plan("case_missing") is None
