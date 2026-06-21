"""Local end-to-end demo, no telephony required.

Drives the documented Eleanor case through the orchestrator: supplier outreach,
PCP order, coverage, and the patient update, then the care-advocate approval. The
mocked supplier call outcomes include every failure mode the brief names (no answer,
voicemail, said-yes-then-silent, not taking patients, out of stock, no assignment),
so the coordination judgment is visible, not assumed.

Run:  python -m sim.run_demo
With Claude:  ANTHROPIC_API_KEY=... python -m sim.run_demo  (AI supplier synthesis)
"""

from __future__ import annotations

from app import orchestrator
from app.cases import ELEANOR

LINE = "=" * 74


def show(plan) -> None:
    c = plan.case
    print(f"\nCASE {plan.plan_id}   gate={plan.gate.value}")
    print(f"  {c.patient_name}, {c.age} | {c.medicare_type} | {c.equipment} ({c.hcpcs})")
    print(
        f"  PCP {c.pcp_name}, {c.pcp_practice} | visit done={c.pcp_visit_done} "
        f"written order={c.written_order_submitted}"
    )

    print("\nCOVERAGE (deterministic, steps needed and cost, NOT a coverage verdict):")
    print(f"  {plan.coverage.headline}")
    for r in plan.coverage.requirements:
        mark = {True: "[x]", False: "[ ]", None: "[?]"}[r.met]
        print(f"   {mark} {r.detail}")
    print(f"  prior authorization required: {plan.coverage.prior_auth_required}")
    print(f"  patient owes: {plan.coverage.estimated_patient_responsibility}")

    print(f"\nSUPPLIER OUTREACH ({'AI / Claude' if plan.suppliers.used_ai else 'deterministic'}):")
    print(f"  {plan.suppliers.summary}")
    for a in plan.suppliers.shortlist:
        print(
            f"   #{plan.suppliers.shortlist.index(a) + 1} {a.name} ({a.delivery_eta_days}d, "
            f"{a.approx_miles}mi) - {a.reason}"
        )
    for a in plan.suppliers.followups:
        print(f"   ... {a.name} [{a.status.value}] - {a.reason}")
    for a in plan.suppliers.other:
        print(f"   x   {a.name} [{a.status.value}] - {a.reason}")

    print("\nSURFACES (gated = needs care-advocate approval before it commits):")
    for s in plan.surfaces:
        gate = "GATED" if s.gated else "auto "
        print(f"   [{gate}] {s.name}: {s.status} - {s.detail}")

    if plan.escalations:
        print("\nBLOCKERS / ESCALATIONS:")
        for e in plan.escalations:
            print(f"   ! {e}")

    print(f"\nNEXT ACTION: {plan.next_action}")


def main() -> None:
    print(LINE)
    print("CASE: Eleanor Martinez, standard manual wheelchair (K0001), Original Medicare Part B")
    print(LINE)
    plan = orchestrator.build_plan(ELEANOR)
    show(plan)

    print("\n>>> Care advocate reviews and APPROVES...")
    orchestrator.approve_plan(plan.plan_id)
    from app.callback import send_outbound

    send_outbound(None, plan.patient_update_script)
    print("Patient update (note: states next steps and ~20% cost, never 'you are covered'):")
    print(f'  "{plan.patient_update_script}"')

    print("\n" + LINE)
    print("Done. Calling to discover was automatic; the order request and the patient call")
    print("were gated behind care-advocate approval.")
    print(LINE)


if __name__ == "__main__":
    main()
