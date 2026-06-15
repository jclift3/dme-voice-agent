# DME Voice Agent — design rationale & decision log

This is the "why" document: what we built, the choices we made, the alternatives
we rejected, and the tradeoffs we'd defend. [PLAN.md](PLAN.md) is the build plan,
[WRITEUP.md](WRITEUP.md) is the 1-page deliverable, [README.md](README.md) is how
to run it. This is the narrative that connects the code to the thinking.

---

## 1. What we built

A working slice of a voice agent that handles the *front door* of Medicare DME
coordination. The thread, end to end:

1. **Inbound call** (Vapi) — a warm intake coordinator captures the request from
   natural conversation via tool calls (`capture_request`), and answers "is this
   covered?" with the *steps needed* (`coverage_requirements`), never a verdict.
2. **End of call** — the backend kicks off async coordination and builds a
   `CoordinationPlan`.
3. **Async work** — in-network vendor research/matching (the task nurses say is
   painful), run by Claude over a mocked supplier directory, producing a ranked,
   *reasoned* shortlist.
4. **Trust boundary** — a nurse approval gate. Liability-bearing legs (PCP nudge,
   patient callback) don't fire until a human approves; reads (vendor research)
   are automatic.
5. **Callback** — closes the loop with the plan + timeline.

It's verifiable three ways: the visual console (`/`), the no-telephony demo
(`python -m sim.run_demo`), and the eval suite (`python -m evals.run_evals`).

---

## 2. The central decision: where AI earns trust

Every other choice falls out of one position:

> **The agent owns *coordination*, not *clinical or coverage judgment*. Reads are
> automated; liability-bearing writes are gated and reversible. The agent says
> "here's what's needed," never "you're covered."**

The DME problem is a coordination problem across three parties, and the
bottleneck isn't capacity — it's *trust*. So we automated everything up to the
trust line and gated everything across it:

| AI earns trust (automated) | AI does NOT earn trust (gated / deterministic / human) |
|---|---|
| Natural intake, empathy, follow-ups | Medical-necessity determination → **PCP** |
| Structured extraction from messy speech | Definitive coverage/eligibility statements → **deterministic + human** |
| Vendor research synthesis & ranking | Insurance coding fixes → **human** |
| Status communication / expectation-setting | Placing the order, calling the patient → **nurse-approved write** |

This is the line we'd defend in the interview, and it's enforced in code:
`coverage.py` is rules (never a verdict), `store.py` marks the PCP-nudge and
callback legs `gated=True`, and `approve_plan()` is the only path that lets them
proceed.

---

## 3. Decision log

Each row: the choice, what we rejected, and why.

### Slice — front door + one real async leg + callback
- **Rejected:** (a) automate the *whole* workflow; (b) build only the async vendor
  research; (c) a polished facade of all five legs.
- **Why:** The front door is where voice AI obviously shines *and* where the trust
  line is sharpest (you must never tell a Medicare patient they're covered). One
  async leg built for real (vendor matching) proves the hard, judgment-heavy part;
  the callback proves loop closure. A working end-to-end thread beats a broad
  facade — and it's exactly what the brief asked for.

### Voice via Vapi (managed platform)
- **Rejected:** Twilio + a realtime model (more plumbing, more to break live);
  browser-only voice (no real phone call).
- **Why:** Fastest path to a real phone call that sounds good, least plumbing in a
  time-box. The backend stays ours, so the interesting logic isn't locked to the
  vendor. **Fallback ladder:** if telephony is flaky in the demo, `sim/run_demo.py`
  drives the identical backend with no phone — the real work is the same either way.

### Model split — fast in-call, strong async
- `claude-haiku-4-5` runs the live conversation (latency *is* the UX);
  `claude-opus-4-8` with adaptive thinking runs the async vendor research (quality
  matters, latency doesn't).
- **Why:** These are genuinely different jobs with opposite constraints. Using one
  model for both would either make the call laggy or the research shallow.

### AI vs deterministic vs human, per component
- **AI:** the conversation (Vapi) and vendor research/ranking (`vendor_match.py`).
  These are *judgment under messiness* — what AI is good at and rules aren't.
- **Deterministic:** the coverage *requirements* checklist (`coverage.py`) and the
  gating/escalation rules (`store.py`). Reliability and auditability over
  flexibility — the agent must not improvise eligibility.
- **Human:** the approval gate on every liability-bearing write.

### Approval gate on writes; reads run free (reversibility)
- **Why:** Reversibility is the cleanest criterion for what to gate. Reading a
  supplier directory is reversible and safe to automate. Faxing a PCP or telling a
  patient something is not — those get a human in the loop. This is also the
  engineering "reversible" story the brief asks about.

### Confidence threshold + escalation — don't guess
- `IntakeRequest.confidence < 0.6` → escalate to a human instead of acting.
  No in-network vendor found → escalate, and the callback tells the patient
  honestly.
- **Why:** The dangerous failure mode here isn't a wrong answer, it's a *confident*
  wrong answer to a vulnerable patient. The system is built to fail loud and route
  to a human, not to paper over uncertainty.

### Deterministic fallback for vendor matching
- `vendor_match.py` tries Claude; on no API key or any error, a transparent scoring
  function produces the same shape.
- **Why:** two birds. (1) The demo *always* runs and can't die on a network hiccup.
  (2) The fallback is a readable oracle, which is what lets the eval suite assert
  hard constraints that hold for *both* the AI and rules paths.

### Coverage as rules that return steps, never a verdict
- `coverage_requirements()` returns "here's what's needed" with per-item
  met/unmet/unknown resolved from intake — and leaves clinical items (`home
  mobility need`) `unknown` because that's the PCP's call.
- **Why:** This is the trust boundary in miniature. Unknown stays unknown; we never
  fabricate a "met," and we never emit a yes/no.

---

## 4. What we did NOT build, and the tradeoff

| Not built | Status | The tradeoff we accept |
|---|---|---|
| Live PCP / EHR order write | Mocked (drafted, queued for nurse) | We don't prove the hardest integration — but it's plumbing, not judgment. The interesting decision is *when* to nudge, which we model. |
| Insurance eligibility / coding loop | Mocked | High-liability, low demo-signal in a time-box. |
| Real supplier directory | Mocked JSON with traps | The *matching reasoning* is what's under test; the data feed is a replaceable adapter. |
| Auth, persistent DB, UI polish | Skipped per brief | In-memory store and a one-file console are enough to show the shape; none of it changes the design. |

---

## 5. Where data would change our decisions

- **Vendor responsiveness / fulfillment data** → turns our heuristic ranking into a
  learned one; today the ranking weights are hand-set.
- **Extraction-confidence vs. nurse-correction logs** → lets us tune the
  auto-vs-human threshold (currently 0.6) empirically instead of by guess.
- **Callback-outcome rates** → tells us whether better expectation-setting actually
  reduces the patient's downstream chasing — the real business metric.

---

## 6. What would worry us shipping this to real patients

- **Tone implying coverage certainty.** Mitigated by a hard no-coverage-claims rule
  in the system prompt *and* a callback script that's been checked (and eval'd) to
  never say "approved"/"covered" — but tone in live speech is harder to guarantee
  than text, and we'd want red-team transcripts before shipping.
- **Silent async failure** — a plan that stalls and no callback ever fires. The
  scariest path because it's invisible. Today the gate makes stalls visible to a
  nurse; in production this needs an SLA timer + alerting.
- **Accessibility** — non-English speakers, hard-of-hearing patients. Not handled.
- **PHI on the call** — intake captures health info; real deployment needs BAA-
  covered vendors, encryption, and retention policy.

---

## 7. How we'd productionize (next steps, in order)

1. Real PCP leg via fax/EHR (Redox/Health Gorilla) behind the existing gate.
2. Persistence + nurse auth; the in-memory store becomes a real queue.
3. SLA timers + alerting on stalled plans (close the silent-failure gap).
4. Eligibility via a real 270/271 check — still surfaced as "what's needed,"
   still gated.
5. Learned vendor ranking once responsiveness data exists.

---

## 8. How it's verified

- **`python -m evals.run_evals`** — 6 evals asserting the *policy*, not a model's
  phrasing, so they pass on both the Claude and fallback paths: trust boundary
  holds (traps excluded), escalation fires, coverage resolves correctly, gated
  legs are gated, callback never claims coverage.
- **`python -m sim.run_demo`** — the full thread on the brief's scenario + two
  failure paths, no telephony, no key.
- **Console (`/`)** — the trust boundary made clickable; approve a plan and watch
  the gated legs fire and the callback script appear.
