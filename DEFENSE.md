# Defense kit — 45-minute live review

Everything you need walking in: the run-of-show, the fallback if voice breaks,
and the hard-question bank. The one sentence everything ladders to:

> **The agent owns coordination, not clinical or coverage judgment. Reads are
> automated; liability-bearing writes are gated and reversible. It says "here's
> what's needed," never "you're covered."**

---

## Run-of-show (target ~10 min, leave 30+ for questions)

**Pre-flight (before the call):**
- `uvicorn app.main:app --port 8000` running; console open at `http://127.0.0.1:8000/`.
- Terminal ready with `python -m sim.run_demo` as the bulletproof fallback.
- If doing a live call: Vapi number dialed once already today to confirm it works.

**The narrative (don't just click — tell the story):**
1. **Frame it (30s).** "DME is a 3-party coordination problem. Nurses do it
   end-to-end today. I took the front door + one real async leg, because that's
   where voice AI shines and where the trust line is sharpest."
2. **The call (2–3 min).** Place the call / play the recording. Ask it "am I
   covered?" on purpose — show it returns *steps*, not a verdict. That's the thesis,
   live.
3. **The handoff (1 min).** Call ends → console shows a new plan. Point at the
   **trust boundary divider**: vendor research ran automatically (a read); the PCP
   nudge and callback sit below it, gated.
4. **The judgment (2 min).** Walk the vendor shortlist. Point at the two excluded
   traps — out-of-network (good signals, wrong network) and no-assignment. "This is
   why it's matching, not a lookup." If AI path is on, show the rationale text.
5. **The gate + loop close (1 min).** Approve → gated legs fire, callback script
   appears. Read it aloud: notice it never says "covered."
6. **Failure paths (1 min).** Seed `no_vendor` and `low_conf` from the console —
   both escalate to a human instead of guessing.
7. **Proof (1 min).** `python -m evals.run_evals` (6/6) and
   `python -m evals.conversation_evals`. "I encoded the policy as tests, so the
   trust boundary can't silently regress."

**If voice breaks:** don't fight it. "Telephony's flaky in the room — here's the
identical thread without the phone," and run `python -m sim.run_demo`. The point
was never the phone; it's the coordination logic, which is the same either way.

---

## Hard-question bank

**On the slice / product**
- *"Why not automate the whole thing?"* — The bottleneck isn't capacity, it's
  trust. Automating coverage/clinical calls is where AI loses and where the
  liability is. I automated up to that line and gated the rest.
- *"The nurse is still in the loop — isn't the point to remove them?"* — I removed
  the *chasing*, not the *judgment*. The nurse goes from doing 100% of the legwork
  to approving a finished plan. That's the leverage, and it's measurable.
- *"What's the actual time saved?"* — Today a nurse researches vendors, nudges the
  PCP, and calls back. We collapse the research + drafting + first patient contact;
  the nurse reviews instead of originates.

**On the trust boundary (the core)**
- *"Show me where the agent could still tell someone they're covered."* — Three
  defenses: `coverage.py` returns steps not verdicts; the callback script is
  eval-checked; the system prompt forbids it. The residual risk is *tone in live
  speech* — which is why I wrote conversation evals that push the agent for a
  yes/no and assert it holds. I'd want red-team transcripts before shipping.
- *"What if extraction is confidently wrong?"* (the sharpest one) — `confidence` is
  self-reported, so a confidently-wrong capture is the real risk. Mitigation today:
  the nurse sees the *full captured request* before approving anything, so a bad
  capture gets caught at the gate. To do it right I'd need calibration data —
  confidence vs. nurse-correction rates — to know if the model's confidence means
  anything.
- *"Where did 0.6 come from?"* — A guess, honestly. It's a placeholder for a number
  the correction-log data should set. I made it a single named constant for exactly
  that reason.

**On engineering**
- *"Why Vapi instead of building it?"* — Fastest path to a real call that sounds
  good; the interesting logic stays in my backend, not locked to the vendor. The
  sim proves I'm not dependent on it.
- *"How do you know the AI ranking is right?"* — The evals assert *hard constraints*
  (out-of-network and no-assignment never shortlist; top pick is in-stock
  in-network), not an exact order — so they hold for both the model and the
  fallback. The trap suppliers are the proof.
- *"What's the deterministic fallback for?"* — Two things: the demo can't die on a
  network hiccup, and it's a readable oracle that makes the evals possible.
- *"Latency?"* — Fast model in-call (haiku) because latency is the UX; strong model
  (opus, adaptive thinking) async where latency doesn't matter. [Fill in a measured
  in-call number after the real call.]

**On shipping to patients**
- *"What worries you most?"* — Silent async failure: a plan stalls and no callback
  ever fires. It's invisible. The gate makes stalls visible to a nurse today; prod
  needs an SLA timer + alerting. After that: accessibility (non-English,
  hard-of-hearing) and PHI handling (BAA vendors, retention).
- *"Where would data change your decisions?"* — Vendor responsiveness data →
  learned ranking; confidence-vs-correction logs → the threshold; callback-outcome
  rates → whether expectation-setting actually reduces patient chasing.

---

## Things to have open in tabs
- `app/store.py` (the gate + escalation logic) — they'll likely ask to see it.
- `app/coverage.py` (steps, never a verdict).
- `evals/run_evals.py` + `evals/conversation_evals.py`.
- `DESIGN.md` (the decision log) for any "why did you..." you didn't pre-script.
