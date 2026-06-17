# DME Voice Agent: design rationale and decision log

This is the "why" document: what I built, the choices I made, the alternatives I rejected,
and the tradeoffs I would defend. [WRITEUP.md](WRITEUP.md) is the 1-page deliverable and
[README.md](README.md) is how to run it. This connects the code to the thinking.

## 1. What I built

A working slice of a voice agent for the front door of Medicare DME coordination. The
thread, end to end:

1. Inbound call (Vapi). A warm intake coordinator captures the request from natural
   conversation via tool calls (`capture_request`), and answers "is this covered?" with the
   steps needed (`coverage_requirements`), never a verdict.
2. End of call. The backend kicks off async coordination and builds a `CoordinationPlan`.
3. Async work. In-network vendor research and matching, the task nurses say is painful, run
   by Claude over a mocked supplier directory, producing a ranked and reasoned shortlist.
4. Trust boundary. A nurse approval gate. Liability-bearing legs (the PCP nudge, the patient
   callback) do not fire until a human approves. Reads (the vendor research) are automatic.
5. Callback. Closes the loop with the plan and a timeline.

It is verifiable three ways without any keys: the visual console (`/`), the no-telephony
demo (`python -m sim.run_demo`), and the eval suite (`python -m evals.run_evals`).

## 2. The central decision: where AI earns trust

Every other choice falls out of one position:

> The agent owns coordination, not clinical or coverage judgment. Reads are automated,
> liability-bearing writes are gated and reversible, and the agent says "here's what's
> needed," never "you're covered."

DME is a coordination problem across three parties, and the bottleneck is not capacity, it
is trust. So I automated everything up to the trust line and gated everything across it.

| AI earns trust (automated) | AI does not earn trust (gated, deterministic, or human) |
|---|---|
| Natural intake, empathy, follow-ups | Medical-necessity determination, which goes to the PCP |
| Structured extraction from messy speech | Definitive coverage statements, which are deterministic plus human |
| Vendor research synthesis and ranking | Insurance coding fixes, which go to a human |
| Status communication and expectation-setting | Placing the order or calling the patient, which is a nurse-approved write |

This is the line I would defend, and it is enforced in code: `coverage.py` is rules and
never a verdict, `store.py` marks the PCP-nudge and callback legs `gated=True`, and
`approve_plan()` is the only path that lets them proceed.

## 3. Decision log

Each entry is the choice, what I rejected, and why.

**Slice: front door plus one real async leg plus callback.** I rejected automating the
whole workflow, building only the async vendor research, and building a polished facade of
all five legs. The front door is where voice AI obviously shines and where the trust line
is sharpest (you must never tell a Medicare patient they are covered). One async leg built
for real proves the hard, judgment-heavy part, and the callback proves loop closure. A
working end-to-end thread beats a broad facade.

**Voice via Vapi, with LiveKit as the next step.** I rejected Twilio plus a realtime model
(more plumbing, more to break live) and browser-only voice (no real phone call). Vapi is
the fastest path to a real, good-sounding phone call in a short exercise, and the backend
stays mine, so the interesting logic is not locked to the vendor. With more time I would
move to LiveKit for the control it gives over the audio pipeline, turn-taking, and tool
orchestration, which a production healthcare agent needs. Because the backend is decoupled
from the voice layer, that swap is contained. As a fallback, `sim/run_demo.py` drives the
identical backend with no phone, so the demo never depends on telephony.

**Model split: fast in-call, strong async.** `claude-haiku-4-5` runs the live conversation,
where latency is the user experience. `claude-opus-4-8` with adaptive thinking runs the
async vendor research, where quality matters and latency does not. One model for both would
either make the call laggy or the research shallow.

**AI versus deterministic versus human, per component.** AI does the conversation (Vapi) and
the vendor research and ranking (`vendor_match.py`), because both are judgment under
messiness. Deterministic code does the coverage-requirements checklist (`coverage.py`) and
the gating and escalation rules (`store.py`), because reliability and auditability beat
flexibility and the agent must not improvise eligibility. A human owns the approval gate on
every liability-bearing write.

**Approval gate on writes, reads run free.** Reversibility is the cleanest criterion for
what to gate. Reading a supplier directory is reversible and safe to automate. Faxing a PCP
or telling a patient something is not, so those get a human in the loop. This is also the
"reversible" story the brief asks about.

**Confidence threshold and escalation, so the agent does not guess.** When
`IntakeRequest.confidence` is below 0.6 the plan escalates to a human instead of acting, and
when no in-network vendor is found it escalates and the callback tells the patient honestly.
The dangerous failure mode here is not a wrong answer, it is a confident wrong answer to a
vulnerable patient, so the system is built to fail loud and route to a human.

**Deterministic fallback for vendor matching.** `vendor_match.py` tries Claude and, with no
API key or on any error, a transparent scoring function produces the same shape. This does
two things: the demo always runs and cannot die on a network hiccup, and the fallback is a
readable oracle, which is what lets the eval suite assert hard constraints that hold for both
the AI and the rules paths.

**Coverage as rules that return steps, never a verdict.** `coverage_requirements()` returns
what is needed with each item resolved from intake as met, unmet, or unknown, and it leaves
clinical items (like home mobility need) unknown because that is the PCP's call. This is the
trust boundary in miniature: unknown stays unknown, nothing is fabricated, and there is never
a yes or no.

## 4. What I did not build, and the tradeoff

| Not built | Status | The tradeoff I accept |
|---|---|---|
| Live PCP/EHR order write | Mocked (drafted, queued for a nurse) | I do not prove the hardest integration, but it is plumbing, not judgment. The interesting decision is when to nudge, which I model. |
| Insurance eligibility and coding loop | Mocked | High liability, low signal for a short exercise. |
| Real supplier directory | Mocked JSON with traps | The matching reasoning is what is under test. The data feed is a replaceable adapter. |
| Auth, persistent DB, UI polish | Skipped per the brief | An in-memory store and a one-file console are enough to show the shape. None of it changes the design. |

## 5. Where data would change my decisions

Real vendor responsiveness and fulfillment data would turn the hand-tuned ranking into a
learned one. Logs of extraction confidence versus nurse corrections would let me set the
auto-versus-human threshold (currently 0.6) from evidence instead of a guess. Callback-outcome
rates would tell me whether better expectation-setting actually reduces how much a patient has
to chase everyone, which is the real business metric.

## 6. What would worry me about shipping this to real patients

Tone that implies coverage certainty, mitigated by a hard no-coverage-claims rule in the
prompt and a callback script that is eval-checked, though tone in live speech is harder to
guarantee than text, so I would want red-team transcripts before shipping. Silent async
failure, where a plan stalls and no callback ever fires, which is the scariest path because it
is invisible. Today the gate makes stalls visible to a nurse, but production needs an SLA timer
with alerting. Accessibility for non-English and hard-of-hearing callers, which is not handled.
And PHI on the call, which in production needs BAA-covered vendors, encryption, and a retention
policy.

## 7. How I would productionize (in order)

1. Real PCP leg via fax or EHR (Redox, Health Gorilla) behind the existing gate.
2. Persistence and nurse auth, turning the in-memory store into a real queue.
3. SLA timers and alerting on stalled plans, to close the silent-failure gap.
4. Eligibility via a real 270/271 check, still surfaced as what is needed and still gated.
5. Learned vendor ranking once responsiveness data exists.

## 8. How it is verified: three eval layers

1. Backend policy (`evals/run_evals.py`): trust boundary, escalation, gating, coverage never
   fabricated. Instant, no key. It asserts the policy, not phrasing, so it passes on both the
   Claude and the fallback paths.
2. Live conversation (`evals/conversation_evals.py`): extraction plus never-claims-coverage
   under adversarial turns (Anthropic API).
3. Deployed voice agent (`cekura/`): Cekura drives LLM persona callers into the deployed Vapi
   number and grades the audio against the same trust-boundary rubrics, then monitors
   production. It catches what the local layers cannot: interruptions, speech recognition,
   latency, drift, and call-handling. See [cekura/README.md](cekura/README.md).

The loop paid off. A real Cekura run surfaced two bugs on the deployed agent: the call never
terminated (about ten-minute calls and a goodbye loop) and the agent stacked questions. I
fixed the first decisively (an `endCall` tool plus a 300-second cap, so the call dropped from
9:58 to 2:11 and the agent ends it itself) and substantially improved the second, while the
safety-critical `never_claims_coverage` metric held throughout, including under an adversarial
coverage-pressure caller. Found, fixed, re-verified: [docs/cekura_results.md](docs/cekura_results.md).

## 9. Defense kit: 45-minute live review

The one sentence everything ladders to:

> The agent owns coordination, not clinical or coverage judgment. Reads are automated,
> liability-bearing writes are gated and reversible, and it says "here's what's needed," never
> "you're covered."

### Run-of-show (about 10 minutes, leaving 30-plus for questions)

Pre-flight: backend on `:8000`, console open, `python -m sim.run_demo` ready as the
voice-breaks fallback, and the number dialed once already that day.

1. Frame (30s): a three-party coordination problem. I took the front door plus one real async
   leg, and the trust boundary is the idea.
2. The call (2 to 3 min): place it or play the recording. Ask "am I covered?" and it returns
   the steps, not a verdict.
3. Handoff (1 min): call ends, a plan appears, point at the trust-boundary divider (vendor
   research auto, PCP nudge and callback gated).
4. Judgment (2 min): walk the shortlist. The two excluded traps prove matching, not lookup.
   Note that `plan_id` was null yet Claude inferred the network.
5. Gate and loop (1 min): approve, the gated legs fire, the callback script appears and never
   says covered.
6. Failure paths (1 min): seed `no_vendor` and `low_conf`, both escalate.
7. Proof (1 min): `evals/run_evals` and `conversation_evals`, then mention Cekura for the
   deployed agent.

If voice breaks in the room: "telephony is flaky here, so here is the identical thread without
the phone," then run `python -m sim.run_demo`. The logic is the same either way.

### Hard-question bank

- "Why not automate the whole thing?" The bottleneck is trust, not capacity. Automating
  coverage and clinical calls is where AI loses and where the liability sits. I automated up to
  that line.
- "The nurse is still in the loop, isn't the point to remove them?" I removed the chasing, not
  the judgment. The nurse goes from doing all the legwork to approving a finished plan.
- "Show me where it could still say you're covered." `coverage.py` returns steps, the callback
  is eval-checked, and the prompt forbids it. The residual risk is tone in live speech, which is
  why the Cekura `never_claims_coverage` metric grades real audio.
- "What if extraction is confidently wrong?" This is the sharpest one. `confidence` is
  self-reported, so a confidently-wrong capture is the real risk. The nurse sees the full
  captured request before approving, and setting the 0.6 threshold properly needs
  correction-log data.
- "How do you know the AI ranking is right?" The evals assert hard constraints (out-of-network
  and no-assignment suppliers never get shortlisted), not an exact order, so they hold for both
  the model and the fallback. The traps are the proof.
- "Latency?" Fast model in-call, strong model async. Measure the in-call number from the real
  call, and Cekura tracks it continuously.
- "What worries you about shipping to patients?" Silent async failure (a stalled plan, no
  callback) needs an SLA timer with alerting, then accessibility and PHI handling.

### Tabs to have open
`app/store.py` (the gate and escalation), `app/coverage.py` (steps, never a verdict), `evals/`,
`cekura/provision.py`, and this file.
