# DME Voice Agent: Writeup

I built and deployed this on a real phone number. A live call captured the request, the
async vendor match ran on Claude, and a coordination plan landed at the nurse gate. The
transcript and recording are in [docs/sample_call.md](docs/sample_call.md).

## 1. The slice

The agent owns coordination, not clinical or coverage judgment. Reads are automated,
liability-bearing writes are gated behind a nurse and reversible, and it tells the
patient "here's what's needed," never "you're covered."

I took the front door and the orchestration handoff. The voice agent answers the inbound
call, captures a structured request, and decides what proceeds on its own versus what
gets gated. I built one async leg for real, the in-network vendor research and matching,
because that is the task nurses say is most painful. Then it closes the loop with a
callback.

I did not build the live PCP/EHR order write, the insurance coding loop, or a real
supplier feed. Those are plumbing or high-liability work with low signal for a short
exercise. The decisions worth probing (what to capture, when to nudge the PCP, who
decides coverage) all sit inside the slice I chose.

## 2. The implementation

AI does the judgment work: the live intake conversation, and the vendor research and
ranking with a written rationale a nurse can check. Deterministic code does the rules:
the Medicare coverage-requirements checklist and the gating logic, so the agent surfaces
what is needed and never improvises eligibility. A human owns the liability: a nurse
approves every write that reaches the patient or the PCP.

Real: the inbound voice call (Vapi), the extraction, the vendor matching, the callback,
and the approval gate. Mocked: the supplier directory, the PCP office, and the insurance
APIs. The model split is deliberate. A fast model runs the live conversation because
latency is the user experience on a phone call, and a stronger model runs the async
research because there quality matters and latency does not.

One thing I would change with more time: I would move the voice layer to LiveKit for the
control it gives over audio, turn-taking, and tool orchestration. I used Vapi here
because it gets a real, good-sounding call running fast, which is what a short demo
needs. The backend is decoupled from the voice platform, so that swap is contained.

## 3. The tradeoffs

The eval work was the most interesting part, and on a system with this many moving parts
it is what keeps the agent honest. I guard the trust boundary at three levels: backend
policy tests, live-conversation guardrail tests, and persona-driven voice simulation
against the deployed agent using Cekura. A real Cekura run held the "never claims
coverage" metric under a caller who pushed hard for a yes-or-no answer, and it caught two
real bugs: a call that would not end and a habit of stacking questions. I fixed both. See
[docs/cekura_results.md](docs/cekura_results.md).

Where data would change my decisions: real vendor responsiveness data turns the
hand-tuned ranking into a learned one, logs of extraction confidence versus nurse
corrections set the auto-versus-human threshold from evidence rather than a guess, and
callback-outcome rates show whether better expectation-setting actually cuts how much a
patient has to chase people.

What would worry me about shipping to real patients: tone that implies coverage
certainty, since speech is harder to control than text. Silent async failure, where a
plan stalls and no callback fires, which is invisible and needs an SLA timer with
alerting. Accessibility for non-English and hard-of-hearing callers, which I did not
handle. And PHI on the call, which needs BAA-covered vendors and a retention policy.

## Demo run-of-show

Call the number, ask for a wheelchair, and ask "am I covered?" to see it return the steps
rather than a verdict. Hang up, and the backend builds the plan with the vendor match.
In the console, the two trap suppliers are excluded with reasons, which shows it is
matching and not a lookup. Approve, and the gated legs fire and the callback goes out. To
run the whole thread with no phone and no keys: `python -m sim.run_demo`.
