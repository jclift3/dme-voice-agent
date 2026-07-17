"""Drive Eleanor's case through the durable workflow.

Start it, read the phase (it parks at `awaiting_care_advocate`), then send the approval
signal the way the console's Approve button would. Run the worker first, then this:

    python -m temporal.worker      # in one terminal
    python -m temporal.starter     # in another
"""

from __future__ import annotations

import asyncio
import uuid

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from app.cases import ELEANOR

from . import TASK_QUEUE
from .workflow import CoordinationWorkflow


async def main() -> None:
    client = await Client.connect("localhost:7233", data_converter=pydantic_data_converter)

    handle = await client.start_workflow(
        CoordinationWorkflow.run,
        ELEANOR,
        id=f"dme-{uuid.uuid4().hex[:8]}",
        task_queue=TASK_QUEUE,
    )
    print(f"Started {handle.id}")

    # Let discovery run, then confirm we are parked at the trust boundary.
    await asyncio.sleep(2)
    print("Phase:", await handle.query(CoordinationWorkflow.phase))

    # The care advocate approves. In the console this is the Approve button.
    await handle.signal(CoordinationWorkflow.approve)
    plan = await handle.result()

    print("Gate:", plan.gate.value)
    print("Next action:", plan.next_action)
    print("Patient update:", plan.patient_update_script)


if __name__ == "__main__":
    asyncio.run(main())
