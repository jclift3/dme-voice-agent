"""Deterministic Medicare DME coverage *requirements*.

This module is intentionally NOT AI. It returns the checklist of what Medicare
requires for a piece of equipment, the steps that must happen, and never a
yes/no coverage decision. That line is the heart of the design: the agent can
tell a patient "here's what's needed," but a coverage determination is a
clinical/billing judgment that stays with the PCP and the nurse.

Rules are a small hand-authored table. In production this is where a rules
engine (or a CMS policy feed) would live; the point is that it's deterministic
and auditable, not improvised by a model.
"""

from __future__ import annotations

from .models import CoverageChecklist, CoverageRequirement, IntakeRequest

CMS_WHEELCHAIR = "https://www.medicare.gov/coverage/wheelchairs-scooters"

# Equipment -> the requirement template. `met` is resolved from intake below.
_RULES: dict[str, dict] = {
    "standard_wheelchair": {
        "headline": "A standard wheelchair is covered under Part B as DME when these are in place:",
        "cms_reference": CMS_WHEELCHAIR,
        "requirements": [
            (
                "face_to_face",
                "Recent face-to-face exam with the treating provider "
                "documenting the mobility need.",
            ),
            ("written_order", "A written order (prescription) from the PCP sent to the supplier."),
            (
                "in_network_supplier",
                "A Medicare-enrolled supplier that accepts assignment (lowest out-of-pocket).",
            ),
            (
                "home_mobility_need",
                "The need is for mobility within the home that a cane or walker can't resolve.",
            ),
        ],
    },
    # Other equipment reuses a generic template; extend as needed.
    "_default": {
        "headline": "This equipment is covered under Part B as DME when these are in place:",
        "cms_reference": None,
        "requirements": [
            ("face_to_face", "Recent face-to-face exam documenting medical necessity."),
            ("written_order", "A written order from the PCP sent to the supplier."),
            ("in_network_supplier", "A Medicare-enrolled supplier that accepts assignment."),
        ],
    },
}


def coverage_requirements(intake: IntakeRequest) -> CoverageChecklist:
    spec = _RULES.get(intake.equipment, _RULES["_default"])

    # Resolve what we already know from intake. Unknown stays None (not False)
    # so the nurse/PCP can fill the gap, we never assert a requirement is unmet.
    known = {
        "face_to_face": intake.recent_visit,
        "written_order": intake.has_order,
        "in_network_supplier": None,  # decided by the vendor-matching leg
        "home_mobility_need": None,  # clinical, PCP, not us
    }

    reqs = [
        CoverageRequirement(label=label, detail=detail, met=known.get(label))
        for (label, detail) in spec["requirements"]
    ]
    return CoverageChecklist(
        equipment=intake.equipment,
        headline=spec["headline"],
        requirements=reqs,
        cms_reference=spec["cms_reference"],
    )
