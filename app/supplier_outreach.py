"""Supplier outreach: the AI-and-judgment core of the coordination work.

The directory is sparse (name, phone, address). Everything that decides whether a
supplier can actually serve the patient is DISCOVERED by calling, one at a time:
are they taking new Medicare patients, do they stock K0001, do they accept
assignment, how soon can they deliver, and did they even pick up. This module works
the list, assesses each outcome, handles the failure modes the brief calls out
(no answer, said-yes-then-silent, out of stock, not taking patients), and ranks the
suppliers that can serve her now.

Two layers, same as the rest of the system: Claude synthesizes the discovered
outcomes into a ranked plan with reasons (latency does not matter here, it is async),
and a deterministic fallback applies transparent rules so the demo always runs and the
evals have a stable oracle. The calls themselves are mocked in data/ (or, in
production, placed by the voice agent and graded by Cekura supplier personas).
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

from .models import Case, Reached, Supplier, SupplierAssessment, SupplierOutreach, SupplierStatus

_DATA = Path(__file__).resolve().parent.parent / "data"
_DIRECTORY = _DATA / "sample-supplier-directory.csv"
_RESPONSES = _DATA / "mock_supplier_responses.json"
_MODEL = "claude-opus-4-8"


def load_directory() -> list[Supplier]:
    with _DIRECTORY.open() as f:
        return [Supplier(**row) for row in csv.DictReader(f)]


def _call_outcome(name: str) -> dict:
    """Mocked external system: what we learn by phoning this supplier."""
    data = json.loads(_RESPONSES.read_text())["responses"]
    return data.get(name, {"reached": "no_answer"})


def work_suppliers(case: Case) -> SupplierOutreach:
    """Call every supplier in the directory, assess, bucket, and rank."""
    discovered = []
    for s in load_directory():
        o = _call_outcome(s.name)
        discovered.append((s, o))

    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _work_with_claude(case, discovered)
        except Exception as exc:  # never let the demo die on the AI leg
            print(f"[supplier_outreach] AI path failed ({exc!r}); using deterministic fallback")
    return _work_deterministic(discovered)


# ---------------------------------------------------------------------------
# Deterministic assessment (the policy, and the evals' oracle)
# ---------------------------------------------------------------------------


def _assess(s: Supplier, o: dict) -> SupplierAssessment:
    reached = Reached(o.get("reached", "no_answer"))
    common = {
        "name": s.name,
        "reached": reached,
        "taking_new_medicare_patients": o.get("taking_new_medicare_patients"),
        "stocks_k0001": o.get("stocks_k0001"),
        "accepts_assignment": o.get("accepts_assignment"),
        "delivery_eta_days": o.get("delivery_eta_days"),
        "approx_miles": o.get("approx_miles"),
    }

    if reached in (Reached.NO_ANSWER, Reached.VOICEMAIL):
        msg = "No answer, no voicemail." if reached == Reached.NO_ANSWER else "Left a voicemail."
        return SupplierAssessment(
            **common,
            status=SupplierStatus.NEEDS_RECALL,
            reason=f"{msg} Call back before ruling them out.",
        )

    if o.get("taking_new_medicare_patients") is False:
        return SupplierAssessment(
            **common,
            status=SupplierStatus.EXCLUDED,
            reason="Not taking new Medicare patients right now.",
        )
    if o.get("stocks_k0001") is False:
        eta = o.get("delivery_eta_days")
        return SupplierAssessment(
            **common,
            status=SupplierStatus.WAIT_ONLY,
            reason=f"K0001 backordered (~{eta} days). Only if she can wait.",
        )
    if o.get("awaiting_confirmation"):
        return SupplierAssessment(
            **common,
            status=SupplierStatus.NEEDS_RECONTACT,
            reason="Agreed on the call but never sent confirmation. Chase before relying on them.",
        )
    if o.get("accepts_assignment") is False:
        return SupplierAssessment(
            **common,
            status=SupplierStatus.FLAGGED,
            reason="Does not accept assignment, so she would pay more. Use only if needed.",
        )
    return SupplierAssessment(
        **common,
        status=SupplierStatus.CANDIDATE,
        reason=f"Taking patients, K0001 in stock, accepts assignment, "
        f"~{o.get('delivery_eta_days')} day delivery.",
    )


def _rank_key(a: SupplierAssessment):
    return (a.delivery_eta_days or 999, a.approx_miles or 999)


def _work_deterministic(discovered: list[tuple[Supplier, dict]]) -> SupplierOutreach:
    assessed = [_assess(s, o) for s, o in discovered]
    shortlist = sorted([a for a in assessed if a.status == SupplierStatus.CANDIDATE], key=_rank_key)
    followups = [
        a
        for a in assessed
        if a.status in (SupplierStatus.NEEDS_RECALL, SupplierStatus.NEEDS_RECONTACT)
    ]
    other = [
        a
        for a in assessed
        if a.status in (SupplierStatus.EXCLUDED, SupplierStatus.WAIT_ONLY, SupplierStatus.FLAGGED)
    ]
    top = shortlist[0].name if shortlist else "none yet"
    summary = (
        f"Worked {len(assessed)} suppliers: {len(shortlist)} can serve her now "
        f"(top pick {top}), {len(followups)} need a callback, {len(other)} can't serve now."
    )
    return SupplierOutreach(
        shortlist=shortlist, other=other, followups=followups, summary=summary, used_ai=False
    )


# ---------------------------------------------------------------------------
# AI path: Claude synthesizes the discovered outcomes into a ranked plan
# ---------------------------------------------------------------------------


def _work_with_claude(case: Case, discovered: list[tuple[Supplier, dict]]) -> SupplierOutreach:
    import anthropic

    rows = [{"name": s.name, "address": s.address, "call_outcome": o} for s, o in discovered]
    prompt = (
        "You are a care advocate working a Medicare DME case. You have ALREADY called each "
        "supplier below; `call_outcome` is what you learned (the directory itself only had "
        "name, phone, address). Sort them for the patient (a standard manual wheelchair, K0001, "
        "Original Medicare Part B).\n\n"
        "Rules:\n"
        "  - shortlist: reachable, taking new Medicare patients, stocks K0001, accepts assignment, "
        "not awaiting confirmation. Rank by soonest delivery then nearest.\n"
        "  - followups: no answer, voicemail, or said-yes-then-silent (awaiting_confirmation). "
        "These need a callback before you rule them in or out.\n"
        "  - other: not taking patients (exclude), out of stock (wait-only), or does not accept "
        "assignment (flag, costs her more).\n"
        "Give each a one-line reason a care advocate can verify. Do not invent facts beyond the "
        "call outcomes.\n\n"
        f"SUPPLIERS:\n{json.dumps(rows, indent=2)}"
    )
    client = anthropic.Anthropic()
    msg = client.messages.parse(
        model=_MODEL,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
        output_format=SupplierOutreach,
    )
    result = msg.parsed_output
    if result is None:
        raise RuntimeError("structured output did not parse")
    result.used_ai = True
    return result
