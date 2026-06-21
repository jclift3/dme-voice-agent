# DME Back-End Coordination: Writeup

Intake is done. This builds the coordination engine that takes the documented Eleanor
case and works it across the four surfaces (supplier outreach, PCP order, coverage,
patient update), with a care advocate approving anything that commits. It runs with no
keys and no phone: `python -m sim.run_demo`.

## Sequencing

I started from the documented case and built the surfaces in the order the time
actually goes.

**Supplier outreach first, and deepest.** The directory is sparse on purpose (name,
phone, address). Everything that decides whether a supplier can serve Eleanor is
discovered by calling: are they taking new Medicare patients, do they stock K0001, do
they accept assignment, how soon can they deliver, and did they even pick up. So I
built the engine that works the list, records what each call returns, and handles the
failure modes the brief names: no answer and voicemail go to a callback queue,
said-yes-then-silent gets flagged for re-contact, not-taking-patients is excluded,
out-of-stock is wait-only, and does-not-accept-assignment is flagged because it costs
her more. The ranking is built from what was learned, not from pre-known attributes.

**Then the orchestrator across all four surfaces.** Coverage is a deterministic check
for K0001 under Part B (what is needed, plus the roughly 20% she will owe, since she
has no supplemental plan). The PCP order surface models the real decision, which is
when to nudge: a verbal order is in the chart but the written order is not submitted,
so the system requests it and schedules a follow-up. The patient update closes the loop.

**The sequencing principle is the trust boundary.** Discovery runs free because calling
to learn is reversible. Anything that commits on Eleanor's behalf, sending the order
request or calling her, waits for a care advocate. And the system refuses to declare
victory on the supplier when the real blocker is elsewhere: the unsigned written order
is critical path, so it surfaces that as the next action, not "found a supplier, done."

## Technology and architecture

- **Python and FastAPI**, with Pydantic models as the contracts between surfaces. In
  memory, no DB, per the brief.
- **Voice via Vapi, outbound.** A supplier-outreach agent calls suppliers and records
  outcomes through a tool; a patient-update agent delivers the approved status. With
  more time I would move the voice layer to LiveKit for the control it gives over audio
  and turn-taking; Vapi is quick for a demo and the backend is decoupled from it, so the
  swap is contained.
- **AI where judgment lives.** Claude (opus, async) synthesizes the discovered call
  outcomes into a ranked plan with reasons. A deterministic fallback applies the same
  policy, so the demo always runs without a key and the evals have a stable oracle. A
  fast model runs the live calls, where latency is the experience.
- **Deterministic where rules live.** The coverage checklist and the gating and
  escalation logic. The system surfaces what is needed and what she owes, never a
  coverage verdict.
- **The sparse directory is a CSV** (name, phone, address). What matters is discovered
  by calling, mocked in `data/` for the demo, or placed by the voice agent and graded by
  Cekura supplier personas in production.
- **Tested and linted.** pytest (unit and functional), ruff, three eval layers, and a CI
  gate (`make gate`).

## The cut list

- **Live insurance authorization (270/271):** mocked. K0001 needs no prior auth, and
  eligibility is a structured API call, not where the coordination judgment is.
- **Live PCP or EHR write:** mocked. The interesting decision is when to nudge, which I
  model; the fax or portal itself is plumbing.
- **Real calls to real suppliers:** the call outcomes are mocked in `data/`. The voice
  agent and Cekura supplier personas are wired for it, but cold-calling real businesses
  is not appropriate for a take-home.
- **Persistence, auth, a multi-case queue:** skipped per the brief. One case, in memory.
- **Patient intake:** out of scope per the updated brief.

## What's next

**With one more day:** make discovery real. Wire the outbound supplier calls to the live
Vapi agent and the webhook so the outcomes come from actual calls, not the mock, and run
the Cekura supplier-persona suite against it. Add the re-call and re-contact scheduler so
follow-ups fire on a timer, which is what actually catches the said-yes-then-silent
supplier.

**With two weeks:** in priority order. First, an SLA timer with alerting on stalled
orders and silent suppliers, because that invisible failure mode is the one that quietly
loses a week. Then persistence and a real case queue so one advocate can carry many
cases. Then the real PCP order leg via fax or EHR behind the existing gate. Then a
learned supplier-ranking model once call-outcome history exists.

The order is deliberate: make discovery real, then make the failure-catching real, then
scale, then optimize. Catching stalls early is the care advocate's actual skill, so that
is what I would automate before anything fancy.
