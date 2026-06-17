# DME Voice Agent — Writeup (1 page)

*Proven on a real call: a live phone call to the agent captured the request, ran the
async Claude vendor match, and produced a coordination plan at the nurse gate.
Transcript + recording in [docs/sample_call.md](docs/sample_call.md).*

## 1. The slice
**The thesis:** the agent owns *coordination*, not *clinical or coverage judgment* — reads are
automated, liability-bearing writes are gated and reversible, and it says "here's what's needed,"
never "you're covered." We took the **front door + orchestration handoff**: the voice agent
answers the inbound call, captures a structured request, and decides what proceeds automatically
vs. what is gated. We built **one async leg for real** — in-network vendor research/matching —
and **closed the loop with a callback**.

We did **not** build the live PCP/EHR order write, the insurance coding loop, or a real supplier
feed. Tradeoff: those are plumbing and high-liability, not judgment. The interesting decisions —
*what to capture, when to nudge, who decides coverage* — all live in the slice we chose.

## 2. The implementation
- **AI in the product:** the live intake conversation, structured extraction from messy speech,
  and async vendor research/ranking with rationale.
- **Deterministic:** the Medicare coverage-*requirements* checklist, gating rules, validation.
  The agent surfaces *what's needed*; it never improvises eligibility.
- **Human:** a nurse-approval gate on every liability-bearing write.
- **Real:** inbound voice (Vapi), extraction, vendor matching, callback, the approval gate.
  **Mocked:** supplier directory, PCP office/EHR, insurance APIs. **Model split:** fast model
  in-conversation (latency = UX), strong model async (quality = matching).

On the real call the agent captured the plan *name* ("Humana Medicare Advantage") but not the
structured `plan_id`. The Claude match still inferred the network and excluded both trap
suppliers — more robust to incomplete capture than the deterministic fallback, which keys on
`plan_id`. A clean example of where AI judgment earns its place.

## 3. The tradeoffs
- **Where data would change decisions:** real vendor responsiveness data → learned ranking;
  extraction-confidence vs. nurse-correction logs → tune the auto-vs-human threshold;
  callback-outcome rates → learn what actually reduces patient chasing.
- **What would worry us shipping to real patients:** any tone that implies coverage certainty;
  accessibility (non-English, hard-of-hearing); PHI on the call; silent async failure where no
  callback ever happens. Our mitigations: hard no-coverage-claims rule, confidence-gated
  human routing, and approval gates on writes.
- **How we keep it safe with many moving parts:** three eval layers guard the trust boundary —
  backend policy, live-conversation guardrails, and Cekura persona-call simulation on the
  *deployed* voice agent (plus production monitoring on the same rubric). A real Cekura run held
  the no-coverage metric under an adversarial caller and caught two bugs (a non-terminating call;
  question-stacking) that we then fixed — see [docs/cekura_results.md](docs/cekura_results.md).

---
### Demo run-of-show
1. Call the number → agent intakes a wheelchair request (PCP office closed, no order yet),
   capturing it via `capture_request`; ask "is this covered?" to trigger `coverage_requirements`
   (it returns the *steps needed*, never a yes/no).
2. End the call → backend builds the coordination plan (async vendor matching runs here).
3. Nurse console: show the ranked, reasoned shortlist with the two trap vendors correctly
   excluded (out-of-network; doesn't accept assignment) — proof it's judgment, not a lookup.
4. Approve → the gated legs fire and the callback goes out with the plan + timeline.
5. Show two failure paths: no in-network vendor → honest escalation; low-confidence
   extraction → routed to a human instead of guessing.

**Bulletproof fallback:** `python -m sim.run_demo` runs the entire thread (all three scenarios)
with no telephony and no API key — so the demo never depends on a live phone call or a network
hiccup. With `ANTHROPIC_API_KEY` set, the vendor matching runs on Claude; without it, the
deterministic fallback produces the same shape.
