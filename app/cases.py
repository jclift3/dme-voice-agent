"""The case the brief hands us. Intake is complete; this is the starting state."""

from __future__ import annotations

from .models import Case

ELEANOR = Case(
    patient_name="Eleanor Martinez",
    age=72,
    medicare_type="Original Medicare (Part B)",
    has_supplemental=False,
    equipment="standard_manual_wheelchair",
    hcpcs="K0001",
    pcp_name="Dr. Sarah Chen",
    pcp_practice="Sunrise Family Medicine, Chicago IL",
    pcp_phone="(312) 555-0198",
    pcp_visit_done=True,
    verbal_order=True,
    written_order_submitted=False,
)


def _case(name, age, pcp, practice, phone, order_signed):
    return Case(
        patient_name=name,
        age=age,
        medicare_type="Original Medicare (Part B)",
        has_supplemental=False,
        equipment="standard_manual_wheelchair",
        hcpcs="K0001",
        pcp_name=pcp,
        pcp_practice=practice,
        pcp_phone=phone,
        pcp_visit_done=True,
        verbal_order=True,
        written_order_submitted=order_signed,
    )


# A small illustrative caseload to show how one advocate triages several cases at once
# (the brief notes one advocate carries multiple). Only Eleanor is from the prompt; the
# others are illustrative variations that differ in order status so the queue and its
# filters are meaningful.
CASELOAD = [
    ELEANOR,  # order not signed -> waiting on order (high)
    _case(
        "Robert Hayes",
        68,
        "Dr. Aisha Karim",
        "Northshore Primary Care, Chicago IL",
        "(312) 555-0210",
        order_signed=True,
    ),  # ready to confirm (medium)
    _case(
        "Marie Dubois",
        79,
        "Dr. Leon Park",
        "Lakeview Family Medicine, Chicago IL",
        "(312) 555-0233",
        order_signed=False,
    ),  # waiting on order (high)
    _case(
        "James Okafor",
        71,
        "Dr. Nina Alvarez",
        "West Loop Medical, Chicago IL",
        "(312) 555-0244",
        order_signed=True,
    ),  # will be approved -> complete (low)
]
