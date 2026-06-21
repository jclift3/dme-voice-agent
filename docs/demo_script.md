# Demo video script (~3 min)

A tight screen-recording script for the async submission. Record with the backend
running (`uvicorn app.main:app --port 8000`) and the console open. Speak the *italics*,
do the **bold**.

**[0:00, frame, 25s]**
*"DME coordination is a three-party problem: the patient, the PCP, and the supplier.
Intake is already done, so this is the back-end coordination. The idea is that the
system owns coordination, not coverage. Calling to discover runs on its own, anything
that commits on the patient's behalf is gated behind a care advocate, and it never tells
a patient they're covered."*

**[0:25, build the case, 20s]**
**Click "Build Eleanor's case."**
*"Eleanor needs a standard manual wheelchair, K0001, Original Medicare Part B. The
directory is sparse on purpose, just names and phone numbers, so everything that matters
gets discovered by calling."*

**[0:45, the supplier board, 60s]**
**Point at the supplier section.**
*"It worked the whole list. Three can serve her now, ranked by soonest delivery. Three
need a callback, and here is the interesting one: Great Lakes said yes on the call and
then went silent, so it is flagged for re-contact, not counted as solved. And three
can't serve her: one isn't taking new Medicare patients, one is out of stock, and one
doesn't accept assignment, so she'd pay more. That is the actual coordination work, and
none of it was in the directory."*

**[1:45, the blocker and the gate, 45s]**
**Point at the next action and the blockers.**
*"Notice it does not say 'found a supplier, done.' The real blocker is the written order,
which the doctor hasn't signed yet, so that is the next action. Below the trust boundary,
sending the order request and calling the patient are gated. Discovery above the line ran
on its own."*

**[2:30, approve and close, 30s]**
**Click Approve.**
*"The care advocate approves, the gated surfaces fire, and the patient update goes out. It
states the timeline and that she'll owe about 20%, and it never says she's covered."*

**[3:00, proof]**
*"It's tested and linted: backend policy evals, a live-conversation guardrail eval, and
Cekura supplier personas for the deployed voice agent. Happy to dig into any decision."*

### Run it with no setup
`python -m sim.run_demo` works the same case end to end with no keys and no phone.
