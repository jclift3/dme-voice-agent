"""Activities: the side-effecting work the durable workflow drives.

Everything non-deterministic lives here, not in the workflow: the discovery calls, the
timestamps and ids inside plan assembly, and the commit across the trust boundary. Each
activity is a thin wrapper over the same `app` domain logic the console uses, so there is
one source of truth for coordination behavior.
"""

from __future__ import annotations

from temporalio import activity

from app.models import Case, CoordinationPlan
from app.orchestrator import apply_approval, assemble_plan


@activity.defn
async def discover(case: Case) -> CoordinationPlan:
    """The reads: call suppliers to discover, check coverage, draft the order request.

    Runs on its own because it is reversible. Leaves the gated surfaces pending."""
    return assemble_plan(case)


@activity.defn
async def commit_gated_surfaces(plan: CoordinationPlan) -> CoordinationPlan:
    """The commits: fire the gated surfaces after the care advocate approves.

    Sends the written-order request to the PCP and places the patient status call."""
    return apply_approval(plan)


@activity.defn
async def escalate_stall(plan: CoordinationPlan) -> None:
    """The SLA breach: the gate has not been worked in time, or a supplier went silent.

    In production this pages the on-call advocate and re-queues the case. Here it records
    the escalation so the stall is visible instead of invisible."""
    who = plan.case.patient_name
    activity.logger.warning("SLA breach on %s: gated surfaces still awaiting a care advocate", who)
