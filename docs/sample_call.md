# Sample call — live transcript

A real call placed to the DME intake agent (+1 323 614 7503) during the build,
captured from the Vapi API. This is the artifact for async reviewers who can't
place a live call.

- **Call id:** `019eccff-33d2-7000-a2ae-94a7103e75be`
- **Ended:** customer-ended-call
- **Cost:** $0.2613
- **Model in-call:** claude-haiku-4-5 (fast model; latency = UX)
- **Recording:** https://storage.vapi.ai/019eccff-33d2-7000-a2ae-94a7103e75be-1781555878644-db8246c1-c92b-4183-ba25-6960974d9436-mono.wav

## What this call demonstrates
- Natural intake: equipment, plan, ZIP, callback number captured from messy speech.
- **An honest UX finding:** the agent front-loaded several questions at once; the
  caller pushed back ("can you ask them one by one?") and the agent recovered
  ("You're absolutely right... let me slow down"). Real, and worth fixing — see
  DESIGN.md §6. The fix is a prompt constraint to ask one question per turn.
- The structured result this produced is plan `plan_b2199151`: `plan_id` was left
  null (only the spoken plan *name* was captured), yet the async Claude match still
  inferred the Humana MA PPO network and excluded both trap suppliers correctly.

## Transcript

```
AI: Hi. Thanks for calling. I can help you get medical equipment set up. What do you need today?
User: I think I need a wheelchair. My doctor saw me last week but I don't have an order yet.
AI: I'm glad your doctor saw you recently. That's helpful. Me get some information so we can move forward smoothly. A few quick questions. 1, what's your ZIP code? 2, what's your doctor's name? Your primary care doctor? 3, do you have Medicare? Now if so, what's the name of your plan, or do you know, like, the plan ID? For?
User: I mean, that's that's a lot of questions, but can you
AI: What's that, bud?
User: you just ask them 1 by 1?
AI: You're absolutely right. My apologies. Let me slow down. What's your ZIP code?
User: 7 8 7 0 4.
AI: Got it. Um, 7 8 7 0 4. Thank you. What's your primary care doctor's name?
User: I forgot his name.
AI: No problem at all. We can look that up. Do you remember what clinic or hospital system you go to?
User: I'm not sure. It's the main 1 the main hospital there.
AI: That's okay. We'll track that down. Me ask you this. Do you have your Medicare card handy? What's the name of your Medicare plan or the plan ID if you can see it?
User: I have Humana Medicare Advantage.
AI: Perfect. Humana Medicare Advantage. Thank you. And do you have a callback number where we can reach you?
User: Yeah. 6 7 8 5 2 2 3 9 8 6.
AI: Great. Thank you. Let me just confirm that number. 6 7 8 5 2 2 3 9 8 6. Is that right?
User: That's the 1.
AI: Perfect. So just to recap, uh, you need a wheelchair. You saw your doctor last week. You have Humana Medicare Advantage, and we'll try track down your PCP's name from the main hospital. In your area. We have your callback number Let me let me save all of this down for our team. This will just take a sec.

```
