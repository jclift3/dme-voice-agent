"""Unit tests for vendor matching (deterministic fallback path, forced hermetic).

These assert the *policy* the trap suppliers exist to prove: network and
assignment constraints win over surface signals like stock and responsiveness.
"""

from app.models import IntakeRequest
from app.vendor_match import match_vendors

HUMANA = IntakeRequest(equipment="standard_wheelchair", plan_id="HUM-MA-PPO", zip="78704")


def _ids(vendors):
    return {v.id for v in vendors}


def test_uses_deterministic_fallback_without_key():
    assert match_vendors(HUMANA).used_ai is False


def test_out_of_network_supplier_is_excluded_despite_good_signals():
    m = match_vendors(HUMANA)
    assert "sup_003" not in _ids(m.shortlist)  # in stock + responsive, wrong network
    assert "sup_003" in _ids(m.excluded)


def test_no_assignment_supplier_is_excluded():
    m = match_vendors(HUMANA)
    assert "sup_004" not in _ids(m.shortlist)
    assert "sup_004" in _ids(m.excluded)


def test_top_pick_is_in_network_and_in_stock():
    top = match_vendors(HUMANA).shortlist[0]
    assert top.id in {"sup_001", "sup_005"}
    assert top.in_stock is True


def test_backordered_supplier_is_never_ranked_first():
    m = match_vendors(HUMANA)
    assert m.shortlist[0].id != "sup_002"


def test_no_in_network_supplier_yields_empty_shortlist():
    m = match_vendors(IntakeRequest(equipment="standard_wheelchair", plan_id="CIGNA-MA-HMO"))
    assert m.shortlist == []
    assert len(m.excluded) > 0
