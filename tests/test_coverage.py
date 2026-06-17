"""Unit tests for the deterministic coverage-requirements rules."""

from app.coverage import coverage_requirements
from app.models import IntakeRequest


def _reqs(intake):
    return {r.label: r for r in coverage_requirements(intake).requirements}


def test_wheelchair_has_four_requirements_and_cms_link():
    cl = coverage_requirements(IntakeRequest(equipment="standard_wheelchair"))
    assert len(cl.requirements) == 4
    assert cl.cms_reference and "medicare.gov" in cl.cms_reference


def test_headline_never_asserts_an_unconditional_verdict():
    cl = coverage_requirements(IntakeRequest(equipment="standard_wheelchair"))
    # It may say "covered ... when X is in place" but never an unconditional yes.
    assert "when these are in place" in cl.headline.lower()
    assert "you're covered" not in cl.headline.lower()


def test_met_resolves_from_intake():
    reqs = _reqs(IntakeRequest(equipment="standard_wheelchair", recent_visit=True, has_order=False))
    assert reqs["face_to_face"].met is True
    assert reqs["written_order"].met is False


def test_clinical_and_supplier_items_stay_unknown():
    # Medical necessity is the PCP's call; the supplier is decided by the match leg.
    reqs = _reqs(IntakeRequest(equipment="standard_wheelchair", recent_visit=True))
    assert reqs["home_mobility_need"].met is None
    assert reqs["in_network_supplier"].met is None


def test_unknown_intake_stays_unknown_not_false():
    reqs = _reqs(IntakeRequest(equipment="standard_wheelchair"))
    assert reqs["face_to_face"].met is None
    assert reqs["written_order"].met is None


def test_unknown_equipment_uses_default_template():
    cl = coverage_requirements(IntakeRequest(equipment="something_exotic"))
    assert len(cl.requirements) == 3
    assert cl.cms_reference is None
