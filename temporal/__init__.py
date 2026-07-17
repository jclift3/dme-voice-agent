"""Temporal orchestration for the DME coordination workflow.

A durable-execution version of the same coordination the in-memory `app/orchestrator.py`
runs today. The four surfaces become activities, the care-advocate gate becomes a signal
the workflow blocks on, and the stall (a supplier says yes then goes silent, or the order
sits in a queue) becomes an SLA timer that escalates instead of losing a week.

This lives on a branch for review. The in-memory path stays the demo default.
"""

TASK_QUEUE = "dme-coordination"
