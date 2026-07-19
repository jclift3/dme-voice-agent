"""The durable coordination workflow.

The shape is the trust boundary made durable. First the discovery activity runs the
reads. Then the workflow blocks on the care-advocate gate, which arrives as a signal, and
holds that state for as long as it takes (days, a restart, a redeploy). A supplier that
says yes then goes silent, or an order that sits in a queue, is the stall the brief cares
about: an SLA timer fires an escalation instead of the case quietly losing a week. Only
after approval do the gated surfaces commit.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    # Preload pydantic so the data converter does not import it mid-workflow (sandbox warns).
    import pydantic_core  # noqa: F401

    from app.models import Case, CoordinationPlan, GateStatus

    from .activities import commit_gated_surfaces, discover, escalate_stall

# How long the gated surfaces may wait on the care advocate before we escalate the stall.
GATE_SLA = timedelta(days=2)

_RETRY = RetryPolicy(maximum_attempts=4, initial_interval=timedelta(seconds=2))


@workflow.defn
class CoordinationWorkflow:
    def __init__(self) -> None:
        self._approved = False
        self._rejected = False
        self._reject_reason = ""
        self._phase = "starting"

    @workflow.run
    async def run(self, case: Case) -> CoordinationPlan:
        self._phase = "discovering"
        plan = await workflow.execute_activity(
            discover, case, start_to_close_timeout=timedelta(minutes=5), retry_policy=_RETRY
        )

        # Trust boundary: the reads are done; nothing commits until a care advocate signals.
        self._phase = "awaiting_care_advocate"
        try:
            await workflow.wait_condition(
                lambda: self._approved or self._rejected, timeout=GATE_SLA
            )
        except TimeoutError:
            self._phase = "escalated"
            await workflow.execute_activity(
                escalate_stall, plan, start_to_close_timeout=timedelta(minutes=1)
            )
            # Keep the case open and keep waiting; the escalation is not a resolution.
            await workflow.wait_condition(lambda: self._approved or self._rejected)

        if self._rejected:
            self._phase = "rejected"
            plan.gate = GateStatus.REJECTED
            if self._reject_reason:
                plan.escalations.insert(0, f"Advocate rejected the plan: {self._reject_reason}")
            return plan

        self._phase = "committing"
        plan = await workflow.execute_activity(
            commit_gated_surfaces,
            plan,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=_RETRY,
        )
        self._phase = "done"
        return plan

    @workflow.signal
    def approve(self) -> None:
        self._approved = True

    @workflow.signal
    def reject(self, reason: str = "") -> None:
        self._rejected = True
        self._reject_reason = reason

    @workflow.query
    def phase(self) -> str:
        return self._phase
