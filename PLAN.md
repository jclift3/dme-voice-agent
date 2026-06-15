# DME Voice Agent — Build Plan

> Take-home thesis: this is a **3-party coordination problem** (patient ↔ PCP ↔ DME vendor).
> The win condition is a sharp, defensible **trust boundary** + one genuinely working voice thread.
> Grading is on *how we think*, not coverage. Optimize for defensibility, not features.

---

## 1. The slice (what we own, what we defend)

**The voice agent owns the front door + the orchestration handoff.** It takes the inbound
call, captures everything structured, and decides what proceeds automatically vs. what is
gated. It does **not** make clinical (medical-necessity) or coverage/billing determinations —
those stay with the PCP and a nurse-approval gate.

We then build **one async leg for real** — in-network vendor research/matching, the exact task
nurses say is painful — and **close the loop with a callback**.

**One-line defense:** *Reads are automated; liability-bearing writes are gated and reversible.
The agent says "here's what's needed," never "you're covered."*

**What we deliberately do NOT build (and the tradeoff):**
- Live PCP/EHR order write — mocked. Tradeoff: we don't prove the hardest integration, but it's
  pure plumbing, not judgment; the interesting decision is *when* to nudge, which we model.
- Insurance coding fix-loop — mocked. Tradeoff: high-liability, low-signal for a 3-hr demo.
- Real supplier directory — mocked JSON. Tradeoff: the *matching reasoning* is what we're
  testing; the data feed is replaceable.

---

## 2. Architecture — the thin thread

```
  Patient phone call
        │  (real, Vapi: Deepgram STT + fast LLM + TTS)
        ▼
┌─────────────────────────────────────────────┐
│  Vapi assistant — "intake coordinator"        │
│  tools (function calls → our webhook):        │
│   • capture_request(equipment, urgency,       │
│       plan, zip, pcp, recent_visit, has_order)│
│   • coverage_requirements(equipment)  ← rules │
│       (returns WHAT'S NEEDED, not a yes/no)   │
└───────────────┬───────────────────────────────┘
                │  end-of-call webhook
                ▼
┌─────────────────────────────────────────────┐
│  FastAPI orchestration backend                │
│   1. Vendor matching (AI, strong model):      │
│        rank in-network suppliers over mocked   │
│        directory by plan + zip + stock +       │
│        responsiveness; emit rationale          │
│   2. PCP leg (MOCKED): draft order-nudge,      │
│        queued for nurse                        │
│   3. Build coordination_plan object            │
│   4. ► NURSE APPROVAL GATE ◄ (human-in-loop)   │
│        liability-bearing actions require OK     │
└───────────────┬───────────────────────────────┘
                │  on approval
                ▼
  Callback to patient (Vapi outbound call or SMS):
  "2 in-network suppliers found; your PCP needs to
   sign the order; here's your timeline."
```

**Model split (a tradeoff worth stating):** *fast* model in the live conversation (latency is
UX), *strong* model async for vendor research (quality matters, latency doesn't).

---

## 3. Real / Mocked / Deterministic

| Layer | Status | Why |
|---|---|---|
| Inbound voice call | **REAL** | The whole point; de-risk first. |
| Structured extraction (tool calls) | **REAL** | Where voice AI earns trust. |
| Vendor matching & ranking | **REAL (AI)** | The judgment centerpiece nurses do today. |
| Callback (voice or SMS) | **REAL** | Proves loop closure. |
| Nurse approval gate | **REAL (minimal UI/JSON)** | The trust boundary, made concrete. |
| Coverage *requirements* checklist | **DETERMINISTIC** | Rules, not vibes; AI must not improvise eligibility. |
| Gating / validation / dedupe | **DETERMINISTIC** | Reliability over flexibility. |
| Supplier directory data | **MOCKED (JSON)** | Replaceable feed; not what's being tested. |
| PCP office / EHR order write | **MOCKED** | Office closed in scenario; pure plumbing. |
| Insurance eligibility / coding | **MOCKED** | High liability, low demo signal. |

---

## 4. The trust boundary (the heart of the defense)

| AI **earns** trust | AI does **NOT** earn trust |
|---|---|
| Natural intake, empathy, follow-up questions | Medical-necessity determination → **PCP** |
| Structured extraction from messy speech | Definitive coverage/eligibility statements → **gated + deterministic** |
| Vendor research synthesis & ranking | Insurance coding fixes → **human** |
| Status communication / expectation-setting | Placing the order → **nurse-approved write** |

Guardrails: confidence threshold on extraction (low → route to human, never guess);
hard rule the agent never states coverage; every external *write* passes the approval gate.

---

## 5. 3-hour build sequence (risk-first)

> Do the riskiest integration first so we know by ~90 min whether to fall back.

- **0:00–0:30** — Vapi assistant: intake system prompt + voice + tool schemas. FastAPI skeleton + tunnel for webhooks.
- **0:30–1:30** — **Thin thread:** one real inbound call → `capture_request` tool fires → end-of-call webhook hits backend. Prove the live round-trip.
- **1:30–2:30** — Async orchestration: vendor matching over mocked directory (AI centerpiece) + `coordination_plan` + minimal nurse approval gate.
- **2:30–3:00** — Callback (Vapi outbound or SMS) closes the loop. Add 1–2 failure paths. Record one clean demo run.

**Fallback ladder if voice stalls:** Vapi inbound → if tunnel/telephony flaky, browser-voice harness → if all else fails, scripted transcript driving the same backend (backend is the real work either way).

---

## 6. Failure handling (they ask explicitly)

- Ambiguous/missing info → agent asks follow-ups; unresolved → flag for nurse, don't guess.
- Low-confidence extraction → below threshold routes to human review.
- No in-network vendor found → escalate to nurse; tell patient honestly on callback.
- Voice infra fails mid-call → graceful "a nurse will call you back" fallback.
- Coverage question pressure → agent restates "here's what's needed," never confirms coverage.

---

## 7. Where data would change our decisions (for the writeup move #3)

- Real responsiveness/fulfillment data per vendor → turns our heuristic ranking into a learned one.
- Extraction-confidence vs. nurse-correction logs → tune the auto-vs-human threshold empirically.
- Callback outcome rates → learn what expectation-setting actually reduces inbound chasing.

**What would worry us shipping this shape to real patients:** any path where the agent's tone
implies coverage certainty; non-English / hard-of-hearing access; PHI handling on the call;
silent failure where async work stalls and no one calls the patient back.
