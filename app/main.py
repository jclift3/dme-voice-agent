"""FastAPI backend for the DME voice agent.

Two surfaces:
  1. /vapi/webhook , Vapi calls this during and after the phone call.
       * tool-calls: the agent captures the request / asks for coverage steps.
       * end-of-call-report: we kick off the async coordination + build a plan.
  2. Nurse console, list plans, inspect the trust boundary, approve/reject.
       Approval is what lets the gated legs (PCP nudge, patient callback) fire.

Run: uvicorn app.main:app --reload  (then expose with a tunnel for Vapi).
The sim harness (sim/run_demo.py) exercises all of this without telephony.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from . import store
from .callback import send_callback
from .coverage import coverage_requirements
from .models import IntakeRequest

app = FastAPI(title="DME Voice Agent")

_CONSOLE = Path(__file__).resolve().parent.parent / "static" / "console.html"


@app.get("/")
def console() -> FileResponse:
    """The nurse console, the trust boundary, made clickable."""
    return FileResponse(_CONSOLE)


# Per-call intake buffers, keyed by Vapi call id. The agent may fill the request
# across several tool calls during one conversation.
_CALL_BUFFERS: dict[str, dict[str, Any]] = {}


@app.get("/health")
def health() -> dict:
    return {"ok": True}


# ---------------------------------------------------------------------------
# Vapi webhook
# ---------------------------------------------------------------------------


@app.post("/vapi/webhook")
async def vapi_webhook(payload: dict) -> JSONResponse:
    message = payload.get("message", payload)
    mtype = message.get("type")

    if mtype == "tool-calls":
        return JSONResponse(_handle_tool_calls(message))

    if mtype == "end-of-call-report":
        return JSONResponse(_handle_end_of_call(message))

    # status-update, transcript, etc., ack and ignore.
    return JSONResponse({"ok": True})


def _call_id(message: dict) -> str:
    return (message.get("call") or {}).get("id") or "demo-call"


def _handle_tool_calls(message: dict) -> dict:
    call_id = _call_id(message)
    tool_calls = message.get("toolCallList") or message.get("toolCalls") or []
    results = []
    for tc in tool_calls:
        fn = tc.get("function", {})
        name = fn.get("name")
        args = fn.get("arguments") or {}
        if isinstance(args, str):
            import json

            args = json.loads(args or "{}")

        if name == "capture_request":
            buf = _CALL_BUFFERS.setdefault(call_id, {})
            buf.update({k: v for k, v in args.items() if v is not None})
            results.append(
                {
                    "toolCallId": tc.get("id"),
                    "result": "Captured. Continue gathering anything still missing.",
                }
            )

        elif name == "coverage_requirements":
            equip = args.get("equipment") or _CALL_BUFFERS.get(call_id, {}).get("equipment", "")
            checklist = coverage_requirements(IntakeRequest(equipment=equip))
            steps = "; ".join(r.detail for r in checklist.requirements)
            # NOTE: phrased as steps, never as a coverage decision.
            results.append({"toolCallId": tc.get("id"), "result": f"{checklist.headline} {steps}"})
        else:
            results.append({"toolCallId": tc.get("id"), "result": f"Unknown tool {name}"})
    return {"results": results}


def _handle_end_of_call(message: dict) -> dict:
    call_id = _call_id(message)
    buf = _CALL_BUFFERS.pop(call_id, {})
    if not buf.get("equipment"):
        return {"ok": True, "note": "no equipment captured; nothing to coordinate"}
    intake = IntakeRequest(**buf)
    plan = store.build_plan(intake)  # async coordination happens here
    return {"ok": True, "plan_id": plan.plan_id, "escalated": plan.escalated_to_human}


# ---------------------------------------------------------------------------
# Nurse console
# ---------------------------------------------------------------------------


@app.get("/plans")
def list_plans() -> list[dict]:
    return [p.model_dump() for p in store.all_plans()]


@app.get("/plans/{plan_id}")
def get_plan(plan_id: str) -> JSONResponse:
    plan = store.get_plan(plan_id)
    if plan is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(plan.model_dump())


@app.post("/plans/{plan_id}/approve")
def approve(plan_id: str) -> JSONResponse:
    plan = store.approve_plan(plan_id)
    if plan is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    # Approval fires the one external write that talks to the patient.
    callback = send_callback(plan.intake.patient_callback_number, plan.callback_script or "")
    return JSONResponse({"plan": plan.model_dump(), "callback": callback})


@app.post("/plans/{plan_id}/reject")
def reject(plan_id: str, reason: str = "") -> JSONResponse:
    plan = store.reject_plan(plan_id, reason)
    if plan is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(plan.model_dump())


# ---------------------------------------------------------------------------
# Demo seeding, lets the console run a full inbound-call scenario in one click,
# so the live demo never depends on telephony. Mirrors sim/run_demo.py.
# ---------------------------------------------------------------------------

_SCENARIOS = {
    "happy": {
        "equipment": "standard_wheelchair",
        "plan_id": "HUM-MA-PPO",
        "plan_name": "Humana Medicare Advantage PPO",
        "zip": "78704",
        "pcp_name": "Dr. Alvarez",
        "recent_visit": True,
        "has_order": False,
        "urgency": "soon",
        "patient_callback_number": "+15125550142",
        "confidence": 0.95,
        "notes": "First-time DME user; anxious about cost.",
    },
    "no_vendor": {
        "equipment": "standard_wheelchair",
        "plan_id": "CIGNA-MA-HMO",
        "zip": "78704",
        "recent_visit": True,
        "has_order": False,
        "confidence": 0.9,
    },
    "low_conf": {
        "equipment": "standard_wheelchair",
        "plan_id": "HUM-MA-PPO",
        "zip": "78704",
        "confidence": 0.35,
        "notes": "Caller hard to hear; plan and order status unclear.",
    },
}


@app.post("/demo/seed")
def demo_seed(scenario: str = "happy") -> JSONResponse:
    intake = IntakeRequest(**_SCENARIOS.get(scenario, _SCENARIOS["happy"]))
    plan = store.build_plan(intake)
    return JSONResponse({"plan_id": plan.plan_id})
