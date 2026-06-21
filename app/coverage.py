"""Deterministic Medicare coverage rules for a standard manual wheelchair (K0001).

Not AI. It returns the checklist of what Medicare Part B requires and a plain-language
estimate of what the patient will owe. It never returns a coverage verdict: whether a
claim is actually paid depends on the signed order, supplier enrollment, and billing
codes lining up, which is a care advocate and provider judgment, not the system's.
"""

from __future__ import annotations

from .models import Case, CoverageCheck, CoverageRequirement

CMS_WHEELCHAIR = "https://www.medicare.gov/coverage/wheelchairs-scooters"


def coverage_check(case: Case) -> CoverageCheck:
    reqs = [
        CoverageRequirement(
            label="face_to_face",
            met=case.pcp_visit_done,
            detail="A face-to-face exam with the treating provider documenting the mobility need.",
        ),
        CoverageRequirement(
            label="written_order",
            met=case.written_order_submitted,
            detail="A written order signed by the PCP and on file with the supplier (a verbal "
            "order in the chart is not enough).",
        ),
        CoverageRequirement(
            label="enrolled_supplier",
            met=None,  # resolved by supplier outreach, not knowable from the case alone
            detail="A Medicare-enrolled supplier that accepts assignment, so the patient "
            "owes the least.",
        ),
        CoverageRequirement(
            label="medical_necessity",
            met=None,  # the PCP's clinical call; a verbal order is noted but not formalized
            detail="The chair is medically necessary for mobility within the home "
            "(the provider's call).",
        ),
    ]
    return CoverageCheck(
        equipment=case.equipment,
        hcpcs=case.hcpcs,
        headline="A standard manual wheelchair (K0001) is covered under Medicare Part B as DME "
        "when these are in place:",
        requirements=reqs,
        # K0001 (standard manual wheelchair) is not on Medicare's prior-authorization list;
        # that requirement applies to certain power mobility devices, not this chair.
        prior_auth_required=False,
        estimated_patient_responsibility=(
            "After the Part B deductible, about 20% coinsurance of the Medicare-approved "
            f"amount. {case.patient_name.split()[0]} has no supplemental plan, so she pays "
            "that share herself."
        ),
        cms_reference=CMS_WHEELCHAIR,
    )
