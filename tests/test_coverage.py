"""Unit tests for the deterministic coverage rules (K0001, Original Medicare Part B)."""

from app.cases import ELEANOR
from app.coverage import coverage_check


def _reqs():
    return {r.label: r for r in coverage_check(ELEANOR).requirements}


def test_hcpcs_and_cms_link():
    cov = coverage_check(ELEANOR)
    assert cov.hcpcs == "K0001"
    assert cov.cms_reference and "medicare.gov" in cov.cms_reference


def test_headline_is_conditional_never_a_verdict():
    cov = coverage_check(ELEANOR)
    assert "when these are in place" in cov.headline.lower()
    assert "you're covered" not in cov.headline.lower()


def test_met_resolves_from_the_case():
    reqs = _reqs()
    assert reqs["face_to_face"].met is True  # visit done
    assert reqs["written_order"].met is False  # not submitted yet


def test_supplier_and_necessity_stay_unknown():
    reqs = _reqs()
    assert reqs["enrolled_supplier"].met is None  # decided by outreach
    assert reqs["medical_necessity"].met is None  # the provider's call


def test_k0001_needs_no_prior_auth():
    assert coverage_check(ELEANOR).prior_auth_required is False


def test_surfaces_the_cost_share():
    assert "20%" in coverage_check(ELEANOR).estimated_patient_responsibility
