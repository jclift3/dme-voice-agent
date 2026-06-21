# DME Back-End Coordination: design rationale and decision log

The "why" behind the build. [WRITEUP.md](WRITEUP.md) is the deliverable and
[README.md](README.md) is how to run it. This connects the code to the thinking and
includes a defense kit for the live review.

## The central decision: where AI earns trust

Everything falls out of one position:

> The system owns coordination, not clinical or coverage judgment. Calling to discover
> runs on its own. Anything that commits on the patient's behalf is gated behind a care
> advocate and is reversible. It says "here's what's needed and what you'll owe," never
> "you're covered."

DME is a coordination problem across the patient, the PCP, and the supplier, and the
bottleneck is trust, not capacity. So I automated everything up to the trust line and
gated everything across it. It is enforced in code: `coverage.py` is rules and never a
verdict, the orchestrator marks the PCP-order and patient-update surfaces `gated=True`,
and `approve_plan()` is the only path that lets them commit.

## Decision log

**Supplier outreach is the deep surface.** The directory is sparse by design, so the
value is not in ranking known attributes, it is in calling to discover the facts and
handling the failure modes. I built discovery-based assessment: each call returns a
reach status and answers, and a transparent policy buckets the result (candidate,
wait-only, flagged, excluded, needs-recall, needs-recontact). Ranking is by what was
learned (soonest delivery, then nearest). Rejected: a pre-scored directory, which the
brief explicitly rules out, and which would skip the actual work.

**The four surfaces run through one orchestrator.** A `Case` flows through supplier
outreach, coverage, PCP order, and patient update. The orchestrator decides the next
action and surfaces blockers. The key judgment is that the unsigned written order is
critical path, so the next action names the order, not the supplier. A system that said
"found a supplier, done" would be confidently unhelpful.

**Reads are automated, commits are gated (reversibility).** Calling to discover and
reading coverage rules are reversible, so they run free. Sending the order request to
the PCP and calling the patient commit on her behalf, so a care advocate approves them.
Reversibility is the cleanest line for what to gate.

**AI for judgment, deterministic for rules, human for liability.** Claude synthesizes
the discovered call outcomes into a ranked plan with reasons; a deterministic fallback
applies the same policy, so the demo runs with no key and the evals have a stable
oracle. The coverage checklist and the gating logic are deterministic and auditable. A
care advocate owns every commit.

**Voice via Vapi, outbound, with LiveKit as the next step.** The coordination is phone
work, so the agent makes outbound calls (suppliers, then the patient) rather than taking
an intake call. Vapi is the fastest path to a real call for a demo; I would move to
LiveKit in production for control over audio and turn-taking. The backend is decoupled
from the voice layer, so the swap is contained.

**Model split.** A fast model in the live calls (latency is the experience), a stronger
model for the async synthesis (quality matters, latency does not).

**Coverage returns steps and cost, never a verdict.** For K0001 under Part B it lists
what is needed, notes there is no prior authorization, and states the roughly 20%
coinsurance Eleanor owes with no supplemental plan. Whether a claim actually pays
depends on the signed order, the supplier, and billing lining up, which is not the
system's call.

## What I did not build, and the tradeoff

| Not built | Status | Tradeoff |
|---|---|---|
| Live insurance authorization (270/271) | Mocked | K0001 needs no prior auth; eligibility is a structured call, not where the judgment is. |
| Live PCP/EHR order write | Mocked | The decision worth modeling is when to nudge; the fax is plumbing. |
| Real calls to real suppliers | Outcomes mocked in `data/` | The voice agent and Cekura personas are wired; cold-calling real businesses is not appropriate for a take-home. |
| Persistence, auth, multi-case queue | Skipped per the brief | One case, in memory, is enough to show the shape. |

## What would worry me about shipping this

The silent failure: a supplier says yes then goes quiet, or the order stalls in a
queue, and no one notices for a week. The system surfaces these to a care advocate
today, but production needs an SLA timer with alerting, which is the first thing I would
build. After that: accessibility on the patient call, and PHI handling (BAA-covered
vendors, retention) since these are real calls about real patients.

## How it is verified: three eval layers

1. **Backend policy** (`evals/run_evals.py`): the discovery policy holds (not-taking
   excluded, out-of-stock wait-only, no-assignment flagged, no-answer and yes-then-silent
   to follow-ups), coverage never fabricates a "met" and surfaces the cost, the right
   surfaces are gated, and the unsigned-order blocker is surfaced. No key.
2. **Live conversation** (`evals/conversation_evals.py`): the outbound supplier agent
   records the outcome and never discusses coverage when the supplier pushes.
3. **Deployed voice agent** (`cekura/`): Cekura plays the supplier persona, calls the
   deployed agent, and grades the audio against the same rubrics. Verified live (run
   670563): the no-commitments guardrail held under a supplier pushing for an order, and
   the suite caught a coverage slip and a metric-design issue. See
   [docs/cekura_results.md](docs/cekura_results.md).

## Defense kit: 45-minute live review

The one sentence: the system owns coordination, not coverage judgment; reads are
automated, commits are gated and reversible, and it never says "you're covered."

### Run-of-show
1. Frame (30s): intake is done, the work is back-end coordination across four surfaces,
   and the trust boundary is the idea.
2. `python -m sim.run_demo` or the console: build Eleanor's case.
3. Walk the supplier board: three ready, three call-backs, three that cannot serve, all
   discovered by calling. Point at the said-yes-then-silent supplier.
4. Point at the next action: the unsigned written order is the blocker, not the supplier.
5. Approve, and the gated surfaces fire; the patient update states the 20% and never
   claims coverage.
6. Proof: `evals/run_evals` and the test suite; Cekura for the deployed agent.

### Hard questions
- "Why is supplier outreach the deep part?" Because the directory is sparse, so the work
  is calling to discover, not ranking. That is where the advocate's time goes.
- "What happens when a supplier says yes then disappears?" It is flagged needs-recontact
  and surfaced, not counted as solved. In production a timer chases it.
- "Why gate the PCP request and the patient call but not the supplier calls?" Reversibility.
  Calling to ask is reversible; committing on her behalf is not.
- "Show me where it could claim coverage." It cannot: `coverage.py` returns steps and
  cost, the patient script is eval-checked, and the prompts forbid it. Tone in live speech
  is the residual risk, which is what the Cekura coverage rubric grades.
- "Original Medicare has no network, so what is 'in-network'?" Right, the wrong frame. It
  is enrolled plus accepts assignment plus taking patients plus in stock, discovered by
  calling, which is what the engine assesses.
