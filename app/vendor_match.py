"""In-network vendor research/matching — the AI-judgment centerpiece.

This is the exact task nurses say is painful: given a patient's plan, ZIP, and
equipment, figure out which suppliers are actually in-network, in stock, and
responsive — and rank them with a defensible rationale.

Two layers, on purpose:
  * AI (Claude, claude-opus-4-8): synthesizes messy supplier data into a ranked
    shortlist *with reasoning*. Latency doesn't matter here (it's async), so we
    use a strong model at high effort — the opposite tradeoff from the live call.
  * Deterministic fallback: if no API key is configured (or the call fails),
    a transparent scoring function produces the same shape. The demo always
    runs, and we can show the AI and the rules side by side.

The mocked directory has deliberate traps (out-of-network-but-responsive,
in-network-by-id-but-doesn't-accept-assignment) so a correct ranking proves
judgment, not a lookup.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .models import ExcludedVendor, IntakeRequest, RankedVendor, VendorMatch

_SUPPLIERS_PATH = Path(__file__).resolve().parent.parent / "mock_suppliers.json"
_MODEL = "claude-opus-4-8"


def _load_suppliers() -> list[dict]:
    data = json.loads(_SUPPLIERS_PATH.read_text())
    return data["suppliers"]


def match_vendors(intake: IntakeRequest) -> VendorMatch:
    """Return a ranked, reasoned shortlist. Prefers Claude; falls back to rules."""
    suppliers = _load_suppliers()
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _match_with_claude(intake, suppliers)
        except Exception as exc:  # never let the demo die on the AI leg
            print(f"[vendor_match] AI path failed ({exc!r}); using deterministic fallback")
    return _match_deterministic(intake, suppliers)


# ---------------------------------------------------------------------------
# AI path — Claude with structured output
# ---------------------------------------------------------------------------


def _match_with_claude(intake: IntakeRequest, suppliers: list[dict]) -> VendorMatch:
    import anthropic

    client = anthropic.Anthropic()
    prompt = (
        "You are coordinating durable medical equipment for a Medicare patient. "
        "From the supplier directory, produce a ranked shortlist of suppliers the "
        "patient should actually use, and a list of ones to exclude with reasons.\n\n"
        "Hard rules:\n"
        "  - A supplier is only usable if it is in-network for the patient's plan_id "
        "(check in_network_plan_ids). Out-of-network suppliers are EXCLUDED no matter "
        "how responsive or well-stocked.\n"
        "  - Prefer suppliers that accept Medicare assignment, have the item in stock, "
        "are responsive (higher responsiveness_score, lower avg_callback_hours), close, "
        "and have few complaints.\n"
        "  - A supplier that is in-network but does NOT accept assignment, is far, or has "
        "high complaints should be ranked low or excluded with a clear reason.\n"
        "  - Backordered-but-in-network suppliers can be offered only as a "
        "wait-if-needed option.\n\n"
        "Give each shortlisted vendor a one-sentence rationale a nurse can verify. "
        "Do not invent suppliers or fields.\n\n"
        f"PATIENT:\n{intake.model_dump_json(indent=2)}\n\n"
        f"SUPPLIER DIRECTORY:\n{json.dumps(suppliers, indent=2)}"
    )

    # Strong model + adaptive thinking: quality matters here, latency doesn't
    # (this runs async, after the call). Effort defaults to high on opus-4-8.
    msg = client.messages.parse(
        model=_MODEL,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
        output_format=VendorMatch,
    )
    result = msg.parsed_output
    if result is None:
        raise RuntimeError("structured output did not parse")
    result.used_ai = True
    return result


# ---------------------------------------------------------------------------
# Deterministic fallback — transparent scoring (also our oracle for tests)
# ---------------------------------------------------------------------------


def _match_deterministic(intake: IntakeRequest, suppliers: list[dict]) -> VendorMatch:
    plan = intake.plan_id
    eq = intake.equipment

    shortlist: list[tuple[float, dict]] = []
    excluded: list[ExcludedVendor] = []

    for s in suppliers:
        if plan and plan not in s["in_network_plan_ids"]:
            excluded.append(
                ExcludedVendor(id=s["id"], name=s["name"], reason=f"Not in-network for {plan}.")
            )
            continue
        if eq not in s.get("stocks", []):
            excluded.append(
                ExcludedVendor(id=s["id"], name=s["name"], reason=f"Does not carry {eq}.")
            )
            continue
        if not s.get("accepts_medicare_assignment", True):
            excluded.append(
                ExcludedVendor(
                    id=s["id"],
                    name=s["name"],
                    reason="Does not accept Medicare assignment (higher patient cost).",
                )
            )
            continue

        in_stock = bool(s.get("in_stock_now", {}).get(eq, False))
        score = (
            (2.0 if in_stock else 0.0)
            + s.get("responsiveness_score", 0.0)
            - s.get("distance_mi", 0.0) / 50.0
            - s.get("complaints_last_90d", 0) * 0.1
        )
        shortlist.append((score, {**s, "_in_stock": in_stock}))

    shortlist.sort(key=lambda t: t[0], reverse=True)
    ranked = []
    for i, (_, s) in enumerate(shortlist, start=1):
        stock_txt = "in stock" if s["_in_stock"] else "backordered"
        ranked.append(
            RankedVendor(
                id=s["id"],
                name=s["name"],
                rank=i,
                in_network=True,
                in_stock=s["_in_stock"],
                distance_mi=s.get("distance_mi", 0.0),
                rationale=(
                    f"In-network, {stock_txt}, {s.get('avg_callback_hours', '?')}h avg callback, "
                    f"{s.get('distance_mi', '?')} mi away."
                ),
            )
        )

    summary = (
        f"{len(ranked)} in-network option(s) for {eq}; "
        f"{len(excluded)} excluded. Top pick: {ranked[0].name}."
        if ranked
        else f"No in-network supplier found for {eq} — escalate to a nurse."
    )
    return VendorMatch(shortlist=ranked, excluded=excluded, summary=summary, used_ai=False)
