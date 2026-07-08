"""Functional tests for the HTTP surface: build a case, review it, approve or reject."""


def test_health(client):
    assert client.get("/health").json() == {"ok": True}


def test_console_is_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "coordination" in r.text.lower()


def test_build_case_creates_a_plan(client):
    pid = client.post("/case/build").json()["plan_id"]
    assert pid.startswith("case_")
    assert len(client.get("/plans").json()) == 1
    plan = client.get(f"/plans/{pid}").json()
    assert plan["case"]["patient_name"] == "Eleanor Martinez"
    assert plan["coverage"]["hcpcs"] == "K0001"


def test_build_then_approve_flow(client):
    pid = client.post("/case/build").json()["plan_id"]
    approved = client.post(f"/plans/{pid}/approve").json()
    assert approved["plan"]["gate"] == "approved"
    assert approved["patient_update"]["mode"] == "mock"
    # the patient script never claims coverage
    assert "you are covered" not in approved["plan"]["patient_update_script"].lower()


def test_reject_endpoint(client):
    pid = client.post("/case/build").json()["plan_id"]
    assert client.post(f"/plans/{pid}/reject?reason=hold").json()["gate"] == "rejected"


def test_unknown_plan_returns_404(client):
    assert client.get("/plans/nope").status_code == 404


def test_caseload_builds_a_triage_spread(client):
    assert client.post("/caseload/build").json()["count"] == 4
    plans = client.get("/plans").json()
    assert len(plans) == 4
    # a meaningful queue needs variety: some waiting on the order, one already complete
    assert any(p["order"]["status"] != "signed" for p in plans)  # waiting on order
    assert any(p["gate"] == "approved" for p in plans)  # complete
