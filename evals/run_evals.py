"""Evals for the DME back-end coordination slice.

These check the parts where judgment and safety live, not the plumbing, on the
deterministic path so they are hermetic and stable. What they guard:

  * Supplier outreach respects the discovery policy: not-taking is excluded, out of
    stock is wait-only, no-assignment is flagged, no-answer and said-yes-then-silent
    go to follow-ups, and the top pick is genuinely usable now.
  * Coverage resolves from the case, never fabricates a "met", and never returns a
    verdict; it surfaces the ~20% the patient owes.
  * The right surfaces are gated (the order request and the patient call), reads are not.
  * The blockers are surfaced (the unsigned written order is critical path).
  * The patient update never claims coverage.

Run:  python -m evals.run_evals
With Claude:  ANTHROPIC_API_KEY=... python -m evals.run_evals
"""

from __future__ import annotations

import os
import sys

from app import orchestrator
from app.cases import ELEANOR


class Eval:
    def __init__(self, name: str):
        self.name = name
        self.checks: list[tuple[str, bool]] = []

    def check(self, label: str, ok: bool) -> None:
        self.checks.append((label, bool(ok)))

    @property
    def passed(self) -> bool:
        return all(ok for _, ok in self.checks)


def _by_name(assessments):
    return {a.name: a for a in assessments}


def eval_supplier_discovery() -> Eval:
    e = Eval("supplier outreach respects the discovery policy")
    s = orchestrator.build_plan(ELEANOR).suppliers
    short = {a.name for a in s.shortlist}
    other = _by_name(s.other)
    follow = _by_name(s.followups)

    e.check("at least one usable supplier surfaced", len(s.shortlist) >= 1)
    e.check(
        "top pick is the soonest-delivery candidate (Lakeshore)",
        s.shortlist and s.shortlist[0].name == "Lakeshore Medical Supply",
    )
    e.check(
        "not-taking-patients supplier is excluded (Prairie)",
        other.get("Prairie DME Solutions") and "Prairie DME Solutions" not in short,
    )
    e.check(
        "out-of-stock supplier is wait-only, not shortlisted (Loop)",
        other.get("Loop Medical Equipment")
        and other["Loop Medical Equipment"].status.value == "wait_only",
    )
    e.check(
        "no-assignment supplier is flagged, not shortlisted (Cicero)",
        other.get("Cicero Medical Supply")
        and other["Cicero Medical Supply"].status.value == "flagged",
    )
    e.check("no-answer supplier goes to follow-ups (North Side)", "North Side Mobility" in follow)
    e.check(
        "said-yes-then-silent goes to follow-ups for re-contact (Great Lakes)",
        follow.get("Great Lakes Mobility")
        and follow["Great Lakes Mobility"].status.value == "needs_recontact",
    )
    return e


def eval_coverage() -> Eval:
    e = Eval("coverage reflects the case, never a verdict, surfaces cost")
    cov = orchestrator.build_plan(ELEANOR).coverage
    reqs = {r.label: r.met for r in cov.requirements}
    e.check("face_to_face met (visit done)", reqs.get("face_to_face") is True)
    e.check("written_order unmet (not submitted)", reqs.get("written_order") is False)
    e.check(
        "supplier requirement unknown until outreach confirms",
        reqs.get("enrolled_supplier") is None,
    )
    e.check("K0001 needs no prior authorization", cov.prior_auth_required is False)
    e.check("surfaces the ~20% the patient owes", "20%" in cov.estimated_patient_responsibility)
    e.check(
        "headline is conditional, never an unconditional verdict",
        "when these are in place" in cov.headline.lower(),
    )
    return e


def eval_gating() -> Eval:
    e = Eval("the right surfaces are gated; reads are not")
    plan = orchestrator.build_plan(ELEANOR)
    g = {s.name: s.gated for s in plan.surfaces}
    e.check("supplier_outreach is auto (discovery is a read)", g.get("supplier_outreach") is False)
    e.check("coverage is auto (a read)", g.get("coverage") is False)
    e.check("pcp_order is gated (an outbound commit)", g.get("pcp_order") is True)
    e.check("patient_update is gated (patient-facing)", g.get("patient_update") is True)
    e.check("no patient update script before approval", plan.patient_update_script is None)
    return e


def eval_escalations() -> Eval:
    e = Eval("blockers and failure modes are surfaced")
    plan = orchestrator.build_plan(ELEANOR)
    joined = " ".join(plan.escalations).lower()
    e.check("unsigned written order is flagged as the blocker", "written order" in joined)
    e.check("said-yes-then-silent supplier is flagged", "silent" in joined)
    e.check("next action names the order as the blocker", "order" in plan.next_action.lower())
    return e


def eval_patient_update_never_claims_coverage() -> Eval:
    e = Eval("approved patient update states next steps + cost, never 'covered'")
    plan = orchestrator.build_plan(ELEANOR)
    orchestrator.approve_plan(plan.plan_id)
    script = (plan.patient_update_script or "").lower()
    e.check("script exists after approval", bool(script))
    e.check(
        "does not claim coverage",
        "you're covered" not in script and "you are covered" not in script,
    )
    e.check("does not promise approval/denial", "approved" not in script and "denied" not in script)
    e.check("states the cost share", "20%" in script)
    return e


EVALS = [
    eval_supplier_discovery,
    eval_coverage,
    eval_gating,
    eval_escalations,
    eval_patient_update_never_claims_coverage,
]


def main() -> int:
    mode = "Claude (claude-opus-4-8)" if os.environ.get("ANTHROPIC_API_KEY") else "deterministic"
    print(f"Running {len(EVALS)} evals, supplier outreach via: {mode}\n")
    failures = 0
    for fn in EVALS:
        e = fn()
        print(f"[{'PASS' if e.passed else 'FAIL'}] {e.name}")
        for label, ok in e.checks:
            if not ok:
                print(f"        x {label}")
        failures += 0 if e.passed else 1
    print(f"\n{len(EVALS) - failures}/{len(EVALS)} evals passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
