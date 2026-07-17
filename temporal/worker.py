"""The worker: hosts the workflow and activities against a Temporal server.

Run a local dev server first (`temporal server start-dev`), then `python -m temporal.worker`.
The pydantic data converter lets activities pass `Case` and `CoordinationPlan` models
directly.
"""

from __future__ import annotations

import asyncio

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from . import TASK_QUEUE
from .activities import commit_gated_surfaces, discover, escalate_stall
from .workflow import CoordinationWorkflow


async def main() -> None:
    client = await Client.connect("localhost:7233", data_converter=pydantic_data_converter)
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CoordinationWorkflow],
        activities=[discover, commit_gated_surfaces, escalate_stall],
    )
    print(f"Worker up on task queue '{TASK_QUEUE}'. Ctrl-C to stop.")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
