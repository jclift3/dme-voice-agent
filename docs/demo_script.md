# Demo video script (~3 min)

A tight screen-recording script for the async submission. Record with the backend running
(`uvicorn app.main:app --port 8000`) and the console open. Speak the *italics*, do the
**bold**.

**[0:00, frame, 20s]**
*"DME coordination is a three-party problem: the patient, the PCP, and the vendor. Nurses
do it end to end today. I took the front door plus one real async leg. The idea is that
the agent owns coordination, not coverage. Reads are automated, anything that touches
liability is gated, and it says 'here's what's needed,' never 'you're covered.'"*

**[0:20, the real call, 50s]**
**Play 20 to 30 seconds of the recording** (the link is in docs/sample_call.md), or place
a live call to +1 323 614 7503.
*"This is a real call. It captures the request from natural speech. One honest UX finding:
early on it front-loaded questions, the caller pushed back, and it recovered. That became
a Cekura metric, which I'll show in a second."*
**Ask on the call: "Am I covered?"**
*"It returns the steps needed, never a yes or no. That's the trust boundary, live."*

**[1:10, the handoff and the AI judgment, 45s]**
**Switch to the console.** Point at the new plan.
*"Call ends, the backend runs the vendor match on Claude. Here's the ranked shortlist with
reasoning, and the two excluded suppliers: one is out of network despite being responsive,
one doesn't accept assignment. That's matching, not a lookup. And on this call I only said
'Humana,' no plan ID, yet it still inferred the network correctly."*

**[1:55, the gate and the loop close, 30s]**
**Point at the trust-boundary divider, then click Approve.**
*"Vendor research ran automatically because it's a read. The PCP nudge and the patient
callback sit below the line, gated. I approve, the callback fires, and the script never
claims coverage."*

**[2:25, proof, 35s]**
**Run `python -m evals.run_evals` and `python -m evals.conversation_evals`.**
*"I encoded the policy as tests: trust boundary holds, escalates instead of guessing, never
claims coverage under pressure. These run with no key and no phone."*
**Show `cekura/` briefly.**
*"For the deployed agent, Cekura drives persona callers into the live number and grades the
audio against those same rubrics, plus it monitors production. Local evals for the logic,
Cekura for the voice."*

**[3:00, close]**
*"Full thread, real call, AI judgment that's provably right on the traps, and a three-layer
eval stack that already caught two bugs on the deployed agent, the call not terminating and
question-stacking, both of which I fixed. Happy to dig into any decision."*

### Failure-path b-roll (optional, if time)
Seed `no_vendor` and `low_conf` from the console. Both escalate to a human instead of
guessing. One line: *"The scary failure mode isn't a wrong answer, it's a confident one, so
it routes to a nurse."*
