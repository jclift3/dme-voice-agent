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
