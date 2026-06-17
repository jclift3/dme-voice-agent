"""Local end-to-end demo, no telephony required.

This drives the same backend the Vapi webhook drives, but feeds it a scripted
intake (what the voice agent would have captured). It proves the whole thread:
intake -> coverage steps -> AI vendor match -> coordination plan -> trust
boundary -> nurse approval -> callback. Also runs two failure paths.

Run:  python -m sim.run_demo
With a real key:  ANTHROPIC_API_KEY=... python -m sim.run_demo  (uses Claude)
Without:          deterministic fallback (still fully runnable).
"""

from __future__ import annotations

from app import store
from app.models import IntakeRequest

LINE = "=" * 72


def show_plan(plan) -> None:
    print(f"\nPLAN {plan.plan_id}   gate={plan.gate.value}")
    print("-" * 72)
    print("COVERAGE (deterministic, steps needed, NOT a coverage decision):")
    print(f"  {plan.coverage.headline}")
    for r in plan.coverage.requirements:
        mark = {True: "[x]", False: "[ ]", None: "[?]"}[r.met]
        print(f"   {mark} {r.detail}")

    print(
        f"\nVENDOR MATCH ({'AI / Claude' if plan.vendors.used_ai else 'deterministic fallback'}):"
    )
    print(f"  {plan.vendors.summary}")
    for v in plan.vendors.shortlist:
        stock = "in stock" if v.in_stock else "backordered"
        print(f"   #{v.rank} {v.name}  ({stock}), {v.rationale}")
    for x in plan.vendors.excluded:
        print(f"   ✗  {x.name}, {x.reason}")

    print("\nLEGS (gated = needs nurse approval before any external action):")
    for leg in plan.legs:
        gate = "GATED" if leg.gated else "auto "
        print(f"   [{gate}] {leg.name}: {leg.status}, {leg.detail}")

    if plan.escalated_to_human:
        print(f"\n  ⚠ ESCALATED TO HUMAN: {plan.escalation_reason}")


def scenario_happy_path() -> None:
    print(LINE)
    print("SCENARIO 1, wheelchair, recent PCP visit, no order, PCP office closed")
    print(LINE)
    intake = IntakeRequest(
        equipment="standard_wheelchair",
        plan_id="HUM-MA-PPO",
        plan_name="Humana Medicare Advantage PPO",
        zip="78704",
        pcp_name="Dr. Alvarez",
        recent_visit=True,
        has_order=False,
        urgency="soon",
        patient_callback_number="+15125550142",
        confidence=0.95,
        notes="First-time DME user; anxious about cost.",
    )
    plan = store.build_plan(intake)
    show_plan(plan)

    print("\n>>> Nurse reviews and APPROVES the plan...")
    store.approve_plan(plan.plan_id)
    from app.callback import send_callback

    send_callback(intake.patient_callback_number, plan.callback_script)
    print("Callback script (note: states next steps, never 'you are covered'):")
    print(f'  "{plan.callback_script}"')


def scenario_no_in_network() -> None:
    print("\n" + LINE)
    print("SCENARIO 2, failure path: plan with no in-network supplier")
    print(LINE)
    intake = IntakeRequest(
        equipment="standard_wheelchair",
        plan_id="CIGNA-MA-HMO",  # not in any supplier's network
        zip="78704",
        recent_visit=True,
        has_order=False,
        confidence=0.9,
    )
    plan = store.build_plan(intake)
    show_plan(plan)


def scenario_low_confidence() -> None:
    print("\n" + LINE)
    print("SCENARIO 3, failure path: low-confidence extraction routes to human")
    print(LINE)
    intake = IntakeRequest(
        equipment="standard_wheelchair",
        plan_id="HUM-MA-PPO",
        zip="78704",
        recent_visit=None,
        has_order=None,
        confidence=0.35,
        notes="Caller hard to hear; plan and order status unclear.",
    )
    plan = store.build_plan(intake)
    show_plan(plan)


if __name__ == "__main__":
    scenario_happy_path()
    scenario_no_in_network()
    scenario_low_confidence()
    print("\n" + LINE)
    print("Done. Every external action above was gated behind nurse approval.")
    print(LINE)
