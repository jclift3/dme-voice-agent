# Demo walkthrough (10 minutes)

A narrated run for the live review. It tells you what to click, what to say, and, at
every step, what is real versus simulated so you can call it out with confidence.

**The one sentence to open and close with:** the system owns coordination, not clinical
or coverage judgment. Calling to discover runs on its own; anything that commits on the
patient's behalf is gated behind a care advocate and is reversible. It says "here's
what's needed and what you'll owe," never "you're covered."

## Before you start (have these open)
- Live console: https://dme-coordination-jclift3.fly.dev/ (click Reset once so it is clean)
- A terminal in the repo (for `python -m sim.run_demo` and `python -m evals.run_evals`)
- [docs/cekura_results.md](docs/cekura_results.md) (the voice-eval scorecard)
- The repo: https://github.com/jclift3/dme-voice-agent

## What is real vs simulated (know this cold)
- **Real:** all the coordination *reasoning* (bucketing suppliers into ready / call-back /
  can't-serve with the right reasons, ranking, the K0001/Part B coverage rules, the
  next-action and blocker logic, the trust-boundary gating, the patient-script wording).
  Also real: the deployed Vapi outbound voice agent, and the Cekura eval run against it.
- **Simulated:** the supplier *call outcomes* (hand-authored in `data/`), the supplier
  directory CSV (a stand-in I wrote, because their CSV was not provided), the PCP office,
  Medicare eligibility, and, in the web view, the patient callback (mock mode).
- **The honest line:** the web console shows the reasoning over simulated call outcomes.
  The actual phone calls are real, but they live on the voice + Cekura layer, which I
  show in Part 3, not on this web page.

---

## Part 1 — Frame the problem (1.5 min)
**SAY:** "DME coordination is a three-party problem: the patient, the PCP, and the
supplier. Intake is already done. The hard part is coordinating across all three without
a care advocate chasing each one by hand. A care advocate calls suppliers, chases the
written order, pins down coverage, and keeps the patient in the loop. The failure modes
are where the time goes: a supplier says yes then goes silent, the order stalls in a
queue, the patient goes quiet. My system automates the legwork and hands the advocate the
decisions that actually need a human."

**SAY (the thesis):** point at the blue legend bar. "This line matters: the reasoning and
the voice agent are real; the call outcomes and the directory are simulated in this view."

## Part 2 — The console (4 min)
**DO (the queue, 30s):** Click **Build caseload**.
**SAY:** "One advocate carries several cases at once, so the landing is a triage queue.
It sorts by what needs attention: two are waiting on the written order, one is ready to
confirm, one is complete. I can filter to 'needs attention' and work those first. This is
the case management layer. Let me open Eleanor." **DO:** Click **Review** on Eleanor (or
**Just Eleanor's case** for the animated single view).

**DO:** Watch it dial each supplier one at a time.
**SAY:** "The directory gives me only name, phone, and address. Everything that decides
whether a supplier can serve Eleanor is discovered by calling. Watch it work the list."

When the board settles, walk it top to bottom:
- **Next action (green):** "Notice it does not say 'found a supplier, done.' The real
  blocker is the written order the doctor has not signed. That is the next action."
- **Blockers (red):** point at the said-yes-then-silent supplier. "Great Lakes agreed on
  the call then went quiet, so it is flagged for re-contact, not counted as solved. That
  is the exact failure mode the brief calls out."
- **Supplier board:** "Three are ready, ranked by soonest delivery. Three need a callback
  (no answer, voicemail, went silent). Three cannot serve: one is not taking new Medicare
  patients, one is out of stock, one does not accept assignment so she would pay more.
  None of that was in the directory. It was learned by calling." **Call out:** "These call
  outcomes are simulated here; the real calls run on the voice layer I will show next."
- **Coverage:** "Deterministic rules for K0001 under Part B. It lists what is needed, that
  there is no prior auth, and that she owes about 20% since she has no supplemental plan.
  It never says she is covered. That is a claims decision, not the system's call."
- **Coordination surfaces and the trust boundary:** "Above the line, calling and checking
  coverage ran on their own because they are reversible reads. Below the line, sending the
  order request to the PCP and calling the patient are gated. They commit on her behalf."

**DO:** Click **Approve gated surfaces**.
**SAY:** "The care advocate approves. Now the patient update is sent. Read it: it states
the plan, the timeline, and the roughly 20% cost, and it never claims coverage."

**SAY (why the gate is the point):** "This is the safety design. The system did nine
calls of legwork and handed me one decision. It cannot commit or make a coverage call
without a person."

**DO:** Scroll to the **Interaction log**.
**SAY:** "Every call and decision is recorded: which supplier was phoned, what was asked,
what came back, the coverage check, and the advocate's approval, with timestamps and who
did what. This is the auditability. It answers 'where is the record of those calls,' and
it is the substrate for improvement: you label these outcomes to tune the ranking and the
prompts, and in production Cekura monitors the real calls against the same rubrics."

## Part 3 — The voice and eval reality (3 min)
This is where the real calls live, and it is the most important part for a voice role.
**SAY:** "The web view simulated the calls so the demo is deterministic. But the outbound
agent is real and deployed on Vapi. And I did not just trust it, I tested it."

**DO:** Open [docs/cekura_results.md](docs/cekura_results.md).
**SAY:** "I used Cekura to have LLM supplier personas place real calls to the deployed
agent and grade the audio. The safety-critical metric, that the agent never commits and
never discusses coverage, held under a supplier pushing for a commitment. The suite also
caught two real things: the agent slipped into coverage talk while declining a commitment,
which I fixed and re-verified, and a metric that failed because it tried to grade a tool
call from audio, which is a metric-design lesson. That found-fixed-verified loop is the
point: it is how you keep a voice agent honest with many moving parts."

**SAY:** "And it is all backed by tests." **DO (optional):** run `python -m evals.run_evals`
in the terminal. "Five policy evals, 27 unit and functional tests, green in CI on every
push."

## Part 4 — Sequencing, cut list, what's next (1.5 min)
**SAY (sequencing):** "I built supplier outreach first and deepest because that is where
the time goes. Then the orchestrator across all four surfaces with the care-advocate gate."

**SAY (the cut, honestly):** "I deliberately cut three of the five failure modes: the order
arriving with a wrong billing code, the patient going quiet, and active recovery when the
order stalls. I surface the stall as the blocker but do not yet run the re-send loop. I
chose depth on supplier outreach over breadth."

**SAY (what's next, with the why):** "One more day: make discovery real by wiring the live
supplier calls and running the Cekura suite against them, plus a re-contact scheduler that
catches the silent supplier. Two weeks, in order: SLA alerting on stalls first because that
invisible failure loses a week, then persistence and a case queue, then the real PCP leg,
then close the billing-code and patient-goes-quiet gaps, then learned ranking. Discovery,
then failure-catching, then scale, then optimize."

## The demo-safety fallback
If the live URL misbehaves, run `python -m sim.run_demo` in the terminal. It works the
same case end to end with no keys and no network, and prints the whole thread.

## Likely questions (short answers)
- **"Is there a database?"** No, in-memory by design (the brief says skip a persistent DB).
  Persistence and a case queue are the first scale item.
- **"Is the directory real?"** No. Their CSV was not provided, so I wrote a stand-in with
  the exact sparse shape (name, phone, address). The code reads that path, so their file
  drops in unchanged.
- **"Why only one human decision?"** The web console gives one gate today. The value is the
  legwork it did before the gate, and the guarantee that nothing commits without a person.
  More granular approvals and follow-up actions are a natural next step.
- **"Original Medicare has no network, so what is 'in-network'?"** Right, wrong frame. It is
  enrolled plus accepts assignment plus taking patients plus in stock, discovered by
  calling, which is what the engine assesses.
