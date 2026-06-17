"""Functional tests for the HTTP surface: the Vapi webhook + nurse console.

Exercises the same paths Vapi and the console hit, end to end, against the real
FastAPI app via TestClient."""


def _tool_call(name, args, call_id="c1"):
    return {
        "message": {
            "type": "tool-calls",
            "call": {"id": call_id},
            "toolCallList": [{"id": "t1", "function": {"name": name, "arguments": args}}],
        }
    }


def test_health(client):
    assert client.get("/health").json() == {"ok": True}


def test_console_is_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "nurse console" in r.text.lower()


def test_coverage_tool_returns_steps_never_a_verdict(client):
    r = client.post(
        "/vapi/webhook",
        json=_tool_call("coverage_requirements", {"equipment": "standard_wheelchair"}),
    )
    result = r.json()["results"][0]["result"].lower()
    assert "you're covered" not in result and "you are covered" not in result
    assert "order" in result  # it lists the steps needed


def test_call_to_plan_to_approve_flow(client):
    # 1. capture across the call
    client.post(
        "/vapi/webhook",
        json=_tool_call(
            "capture_request",
            {
                "equipment": "standard_wheelchair",
                "plan_id": "HUM-MA-PPO",
                "zip": "78704",
                "recent_visit": True,
                "has_order": False,
                "patient_callback_number": "+15125550142",
                "confidence": 0.95,
            },
        ),
    )
    # 2. end of call builds the plan
    end = client.post(
        "/vapi/webhook", json={"message": {"type": "end-of-call-report", "call": {"id": "c1"}}}
    )
    plan_id = end.json()["plan_id"]
    assert end.json()["escalated"] is False

    # 3. nurse approves -> gate opens, callback fires in mock mode
    approved = client.post(f"/plans/{plan_id}/approve").json()
    assert approved["plan"]["gate"] == "approved"
    assert approved["callback"]["mode"] == "mock"


def test_end_of_call_without_capture_builds_nothing(client):
    r = client.post(
        "/vapi/webhook", json={"message": {"type": "end-of-call-report", "call": {"id": "empty"}}}
    )
    assert "plan_id" not in r.json()


def test_demo_seed_scenarios(client):
    assert client.post("/demo/seed?scenario=happy").status_code == 200
    no_vendor = client.post("/demo/seed?scenario=no_vendor").json()["plan_id"]
    assert client.get(f"/plans/{no_vendor}").json()["escalated_to_human"] is True
    assert len(client.get("/plans").json()) == 2


def test_reject_endpoint(client):
    pid = client.post("/demo/seed?scenario=happy").json()["plan_id"]
    assert client.post(f"/plans/{pid}/reject?reason=ineligible").json()["gate"] == "rejected"


def test_unknown_plan_returns_404(client):
    assert client.get("/plans/nope").status_code == 404
