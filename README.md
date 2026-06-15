# DME Voice Agent — working slice

A voice agent that takes a Medicare patient's inbound call for durable medical
equipment, captures the request, does the in-network vendor research async, and
calls back — with a nurse approval gate on everything that touches liability.

**The thesis:** the agent owns *coordination*, not *clinical or coverage
judgment*. Reads are automated; liability-bearing writes are gated and
reversible. The agent says "here's what's needed," never "you're covered."

See [PLAN.md](PLAN.md) for the full design and [WRITEUP.md](WRITEUP.md) for the
1-page writeup.

## What's real / mocked / deterministic

| Layer | Status |
|---|---|
| Inbound voice call | REAL (Vapi — config in `vapi/`) |
| Structured extraction during the call | REAL (Vapi tool calls → `app/main.py`) |
| In-network vendor matching + ranking | REAL — Claude (`claude-opus-4-8`), with a deterministic fallback |
| Coverage *requirements* checklist | DETERMINISTIC (`app/coverage.py`) — never a coverage decision |
| Nurse approval gate | REAL (`app/store.py`, console endpoints) |
| Patient callback | REAL via Vapi outbound, MOCK by default (`app/callback.py`) |
| Supplier directory, PCP office/EHR, insurance | MOCKED (`mock_suppliers.json`) |

## Run the demo (no telephony, no API key needed)

```bash
pip install -r requirements.txt
python -m sim.run_demo
```

This drives the full thread on the scenario from the brief (wheelchair, recent
PCP visit, no order, PCP office closed) plus two failure paths (no in-network
supplier; low-confidence extraction → human). The vendor directory has two
"trap" suppliers so a correct ranking proves judgment, not a lookup.

**To run the AI vendor-matching with Claude** (otherwise the deterministic
fallback runs):

```bash
ANTHROPIC_API_KEY=sk-... python -m sim.run_demo
```

## Run the backend + nurse console

```bash
uvicorn app.main:app --port 8000 --reload
# then open http://127.0.0.1:8000/   (visual nurse console)
# expose for Vapi:  ngrok http 8000   (or any tunnel)
```

The console (`/`) is the trust boundary made clickable: simulate an inbound call
with one button, see the ranked vendors with the trap suppliers excluded, then
Approve to watch the gated legs fire and the callback script appear.

Endpoints:
- `GET  /` — nurse console (HTML)
- `POST /vapi/webhook` — Vapi tool-calls + end-of-call-report
- `POST /demo/seed?scenario=happy|no_vendor|low_conf` — seed a plan (drives the console)
- `GET  /plans` · `GET /plans/{id}` — plan data
- `POST /plans/{id}/approve` — fires the gated legs + patient callback
- `POST /plans/{id}/reject?reason=...`

## Verify the behavior (evals)

```bash
python -m evals.run_evals          # 6 evals; asserts the policy, not a model's phrasing
ANTHROPIC_API_KEY=... python -m evals.run_evals   # same suite, AI vendor-matching path
```

The evals guard the parts that matter: the trust boundary holds (out-of-network
and no-assignment suppliers never get shortlisted), the agent escalates instead
of guessing, coverage never fabricates a "met", gated legs stay gated, and the
callback never claims coverage. See [DESIGN.md](DESIGN.md) for the full rationale.

Quick local exercise of the webhook → approve flow:

```bash
python -c "from fastapi.testclient import TestClient; from app.main import app; c=TestClient(app); \
print(c.post('/vapi/webhook', json={'message':{'type':'tool-calls','call':{'id':'c1'},'toolCallList':[{'id':'t1','function':{'name':'capture_request','arguments':{'equipment':'standard_wheelchair','plan_id':'HUM-MA-PPO','confidence':0.95}}}]}}).json())"
```

## Wire up real voice (Vapi)

1. Create an assistant from `vapi/assistant.json` (paste `vapi/system_prompt.md`
   into the system message).
2. Set the assistant `server.url` to `https://<your-tunnel>/vapi/webhook`.
3. For the callback leg, set `VAPI_API_KEY` and `VAPI_PHONE_NUMBER_ID`; without
   them the callback runs in mock mode (logs the script).

Model split on purpose: a **fast** model (`claude-haiku-4-5`) runs the live
conversation where latency is UX; the **strong** model (`claude-opus-4-8`) runs
the async vendor research where quality matters and latency doesn't.
