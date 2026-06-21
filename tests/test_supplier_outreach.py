"""Unit tests for supplier outreach (deterministic discovery path, forced hermetic).

The sparse directory tells you almost nothing; these assert the policy applied to what
is discovered by calling, including the failure modes the brief names.
"""

from app.cases import ELEANOR
from app.supplier_outreach import load_directory, work_suppliers


def _status(outreach):
    return {
        a.name: a.status.value
        for bucket in (outreach.shortlist, outreach.other, outreach.followups)
        for a in bucket
    }


def test_directory_is_sparse_name_phone_address():
    suppliers = load_directory()
    assert len(suppliers) == 9
    s = suppliers[0]
    assert s.name and s.phone and s.address


def test_uses_deterministic_path_without_key():
    assert work_suppliers(ELEANOR).used_ai is False


def test_top_pick_is_soonest_usable_supplier():
    top = work_suppliers(ELEANOR).shortlist[0]
    assert top.name == "Lakeshore Medical Supply"
    assert top.delivery_eta_days == 3


def test_shortlist_is_ranked_by_delivery_then_distance():
    names = [a.name for a in work_suppliers(ELEANOR).shortlist]
    assert names == ["Lakeshore Medical Supply", "Evanston Home Health", "Windy City Home Medical"]


def test_failure_modes_are_bucketed_correctly():
    st = _status(work_suppliers(ELEANOR))
    assert st["Prairie DME Solutions"] == "excluded"  # not taking patients
    assert st["Loop Medical Equipment"] == "wait_only"  # out of stock
    assert st["Cicero Medical Supply"] == "flagged"  # no assignment
    assert st["North Side Mobility"] == "needs_recall"  # no answer
    assert st["Southwest Care Supply"] == "needs_recall"  # voicemail
    assert st["Great Lakes Mobility"] == "needs_recontact"  # said yes then silent


def test_only_usable_suppliers_are_shortlisted():
    short = {a.name for a in work_suppliers(ELEANOR).shortlist}
    for blocked in ("Prairie DME Solutions", "Loop Medical Equipment", "Cicero Medical Supply"):
        assert blocked not in short
