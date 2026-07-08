"""FastAPI backend for DME back-end coordination.

Intake is already done, so there is no inbound capture here. The surfaces are:
  * build a coordination plan for a documented case (the orchestrator works the four
    surfaces: supplier outreach, PCP order, coverage, patient update),
  * a care-advocate console to review it and approve or reject the gated surfaces,
  * a Vapi webhook where outbound calls (supplier outreach, patient update) post
    their results in production.

Run: uvicorn app.main:app --port 8000
The sim harness (sim/run_demo.py) exercises the orchestrator with no telephony.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import orchestrator
from .callback import send_outbound
from .cases import CASELOAD, ELEANOR

app = FastAPI(title="DME Back-End Coordination")

_STATIC = Path(__file__).resolve().parent.parent / "static"
_CONSOLE = _STATIC / "console.html"
app.mount("/static", StaticFiles(directory=_STATIC), name="static")


@app.get("/")
def console() -> FileResponse:
    # no-store so a reviewer always gets the current console, never a stale cache
    return FileResponse(_CONSOLE, headers={"Cache-Control": "no-store"})


_REPLAY = Path(__file__).resolve().parent.parent / "static" / "replay.html"


@app.get("/replay")
def replay() -> FileResponse:
    """A self-playing walkthrough of the whole flow (no backend calls). Present it
    live or screen-record it as a demo backup."""
    return FileResponse(_REPLAY, headers={"Cache-Control": "no-store"})


@app.get("/health")
def health() -> dict:
    return {"ok": True}


# ---------------------------------------------------------------------------
# Coordination
# ---------------------------------------------------------------------------


@app.post("/case/build")
def build_case() -> JSONResponse:
    """Work Eleanor's case across the four surfaces. Idempotent: one case at a time,
    so clicking build twice reuses the existing plan rather than duplicating it."""
    existing = orchestrator.all_plans()
    plan = existing[0] if existing else orchestrator.build_plan(ELEANOR)
    return JSONResponse({"plan_id": plan.plan_id})


@app.post("/case/reset")
def reset_case() -> JSONResponse:
    """Clear the case so the demo can be run again from a clean slate."""
    orchestrator.clear_plans()
    return JSONResponse({"ok": True})


@app.post("/caseload/build")
def build_caseload() -> JSONResponse:
    """Work a small caseload so the queue and its filters are meaningful (this is how
    one advocate triages several cases at once). One case is approved to show a
    completed one."""
    orchestrator.clear_plans()
    plans = [orchestrator.build_plan(c) for c in CASELOAD]
    orchestrator.approve_plan(plans[-1].plan_id)  # James: order signed -> mark complete
    return JSONResponse({"count": len(plans)})


@app.get("/plans")
def list_plans() -> list[dict]:
    return [p.model_dump() for p in orchestrator.all_plans()]


@app.get("/plans/{plan_id}")
def get_plan(plan_id: str) -> JSONResponse:
    plan = orchestrator.get_plan(plan_id)
    if plan is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(plan.model_dump())


@app.post("/plans/{plan_id}/approve")
def approve(plan_id: str) -> JSONResponse:
    plan = orchestrator.approve_plan(plan_id)
    if plan is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    # Approval fires the one patient-facing outbound call.
    update = send_outbound(None, plan.patient_update_script or "")
    return JSONResponse({"plan": plan.model_dump(), "patient_update": update})


@app.post("/plans/{plan_id}/reject")
def reject(plan_id: str, reason: str = "") -> JSONResponse:
    plan = orchestrator.reject_plan(plan_id, reason)
    if plan is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(plan.model_dump())


# ---------------------------------------------------------------------------
# Vapi webhook: in production the outbound supplier and patient calls post their
# results here. The demo drives discovery from mocked call outcomes instead.
# ---------------------------------------------------------------------------


@app.post("/vapi/webhook")
async def vapi_webhook(payload: dict) -> JSONResponse:
    message = payload.get("message", payload)
    return JSONResponse({"ok": True, "received": message.get("type")})
